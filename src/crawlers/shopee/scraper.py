"""
Shopee Product Scraper using Playwright
Multi-worker version adapted for GitHub Actions (single worker)
"""
import re
import time
import random
from datetime import datetime
from typing import List, Dict, Any
import pytz
from playwright.sync_api import sync_playwright
import logging

from src.crawlers.shopee.database import (
    insert_products_batch,
    create_indexes,
    get_trending_products,
    calc_discount_percent,
    convert_ctime
)

logger = logging.getLogger(__name__)

TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => false});
window.chrome = { runtime: {} };
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.__proto__.query = function(parameters) {
  if (parameters && parameters.name === 'notifications') {
    return Promise.resolve({ state: Notification.permission });
  }
  return originalQuery(parameters);
};
Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
"""


def clean_text(text: str) -> str:
    """Clean and normalize text"""
    return re.sub(r"\s+", " ", text).strip()


def generate_keyword_variants(base_keyword: str, variants_count: int = 10) -> List[str]:
    """Generate search keyword variations"""
    variants = [
        base_keyword,
        f"{base_keyword} giá rẻ",
        f"{base_keyword} tốt nhất",
        f"mua {base_keyword}",
        f"{base_keyword} sale",
        f"{base_keyword} hot",
        f"{base_keyword} 2025",
        f"{base_keyword} đáng mua",
        f"{base_keyword} review",
        f"{base_keyword} chất lượng",
    ]
    return variants[:variants_count]


class ShopeeScraper:
    """Shopee Product Scraper using Playwright"""

    def __init__(
            self,
            headless: bool = True,
            variants_per_category: int = 10,
            max_pages_per_variant: int = 2,
            target_per_category: int = 500
    ):
        """
        Initialize scraper

        Args:
            headless: Run browser in headless mode
            variants_per_category: Number of keyword variations per category
            max_pages_per_variant: Maximum pages to scrape per keyword variant
            target_per_category: Target number of products per category
        """
        self.headless = headless
        self.variants_per_category = variants_per_category
        self.max_pages_per_variant = max_pages_per_variant
        self.target_per_category = target_per_category

    def scrape_category(
            self,
            page,
            category: str,
            category_products: List[Dict],
            seen_ids: set
    ) -> int:
        """
        Scrape products for a category

        Args:
            page: Playwright page object
            category: Product category
            category_products: List to store collected products
            seen_ids: Set of already seen product IDs

        Returns:
            Number of new products collected
        """
        logger.info(f"=== Starting scrape for category: '{category}' ===")
        start_count = len(category_products)
        variants = generate_keyword_variants(category, self.variants_per_category)

        for kw_idx, kw in enumerate(variants, 1):
            if len(category_products) >= self.target_per_category:
                break

            logger.info(f"🔎 Variant {kw_idx}/{len(variants)}: '{kw}'")

            for page_idx in range(self.max_pages_per_variant):
                if len(category_products) >= self.target_per_category:
                    break

                url = f"https://shopee.vn/search?keyword={kw}&page={page_idx}"

                # Response handler to capture API data
                def handle_response(resp):
                    try:
                        if "/api/v4/search/search_items" in resp.url:
                            try:
                                data = resp.json()
                            except:
                                data = {}

                            items = data.get("items", [])
                            for i in items:
                                item = i.get("item_basic", {})
                                itemid = item.get("itemid")

                                if not itemid or itemid in seen_ids:
                                    continue

                                seen_ids.add(itemid)

                                # Calculate prices and discount
                                price = float(item.get("price", item.get("price_min", 0))) / 100000
                                price_before = float(item.get("price_before_discount", price * 100000)) / 100000
                                discount = calc_discount_percent(price_before, price)

                                # Get rating info
                                rating_star = round(item.get("item_rating", {}).get("rating_star", 0), 2)
                                rating_count = item.get("item_rating", {}).get("rating_count", [0])[0]

                                product = {
                                    "itemid": itemid,
                                    "shopid": item.get("shopid"),
                                    "name": clean_text(item.get("name", "")),
                                    "price": price,
                                    "price_before_discount": price_before,
                                    "discount": discount,
                                    "sold_recent": item.get("sold", 0),
                                    "sold_total": item.get("historical_sold", 0),
                                    "rating_star": rating_star,
                                    "rating_count": rating_count,
                                    "flash_sale": item.get("flash_sale", False),
                                    "ctime": convert_ctime(item.get("ctime", 0)),
                                    "category": category,
                                }
                                category_products.append(product)
                    except Exception as e:
                        logger.debug(f"Error handling response: {e}")

                page.on("response", handle_response)

                # Navigate to page
                try:
                    page.goto(url, timeout=60000)
                    time.sleep(random.uniform(2, 4))

                    # Scroll to load more items
                    for _ in range(random.randint(2, 4)):
                        page.mouse.wheel(0, random.randint(800, 2000))
                        time.sleep(random.uniform(1, 3))

                except Exception as e:
                    logger.warning(f"Error loading page: {e}")

                # Remove handler to avoid memory leak
                page.remove_listener("response", handle_response)

                logger.info(f"  Page {page_idx}: Total products = {len(category_products)}")

        final_new = len(category_products) - start_count
        logger.info(f"✅ Category '{category}' complete: +{final_new} new products")
        return final_new

    def scrape_categories(self, categories: List[str]) -> Dict[str, Any]:
        """
        Scrape multiple categories

        Args:
            categories: List of product categories

        Returns:
            Dictionary with collected products and stats
        """
        logger.info('=' * 70)
        logger.info('📋 Categories to scrape:')
        for i, cat in enumerate(categories, 1):
            logger.info(f"  {i}. {cat}")

        category_products = []
        seen_ids = set()
        category_stats = {}

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox"
                ]
            )

            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=DEFAULT_USER_AGENT,
                locale='en-US',
                timezone_id='Asia/Ho_Chi_Minh'
            )

            page = context.new_page()

            # Set user agent
            page.evaluate(
                f"() => {{ Object.defineProperty(navigator, 'userAgent', {{get: () => '{DEFAULT_USER_AGENT}'}}); }}")
            page.add_init_script(STEALTH_JS)

            # Process each category
            logger.info("\n🚀 Starting collection...\n")

            try:
                for idx, category in enumerate(categories, 1):
                    before_count = len(category_products)

                    new_count = self.scrape_category(
                        page, category, category_products, seen_ids
                    )

                    category_stats[category] = new_count

                    # Progress update
                    progress = idx / len(categories) * 100
                    logger.info(f"Progress: {progress:.0f}% ({idx}/{len(categories)} categories)")

                    # Delay between categories
                    if idx < len(categories):
                        wait_time = random.uniform(3, 7)
                        logger.info(f"⏸ Waiting {wait_time:.1f}s before next category...")
                        time.sleep(wait_time)

            except KeyboardInterrupt:
                logger.warning("⏸ Stopped by user")
            finally:
                browser.close()

        return {
            'collected_products': category_products,
            'category_stats': category_stats
        }


def run_shopee_scraper(
        categories: List[str],
        headless: bool = True,
        variants_per_category: int = 10,
        max_pages_per_variant: int = 2,
        target_per_category: int = 500
):
    """
    Run Shopee scraper for multiple categories (synchronous version)

    Args:
        categories: List of product categories to search
        headless: Run browser in headless mode
        variants_per_category: Number of keyword variations per category
        max_pages_per_variant: Maximum pages to scrape per keyword variant
        target_per_category: Target number of products per category
    """
    logger.info('=' * 70)
    logger.info('SHOPEE SCRAPER STARTED')
    logger.info('=' * 70)

    # Validate inputs
    if not categories:
        logger.error('Categories are required')
        return

    # Initialize database
    logger.info('Initializing database...')
    try:
        create_indexes()
    except Exception as e:
        logger.error(f'Failed to initialize database: {e}')
        return

    # Create scraper
    scraper = ShopeeScraper(
        headless=headless,
        variants_per_category=variants_per_category,
        max_pages_per_variant=max_pages_per_variant,
        target_per_category=target_per_category
    )

    # Scrape products
    try:
        result = scraper.scrape_categories(categories)
        collected_products = result['collected_products']
        category_stats = result['category_stats']

        logger.info('\n' + '=' * 70)
        logger.info('Scraping completed')
        logger.info('=' * 70)
        logger.info(f'Total unique products collected: {len(collected_products)}')

        # Save to database by category
        total_added_history = 0
        total_added_main = 0
        total_updated_main = 0

        # Group products by category
        products_by_category = {}
        for product in collected_products:
            cat = product['category']
            if cat not in products_by_category:
                products_by_category[cat] = []
            products_by_category[cat].append(product)

        # Insert each category
        for category, products in products_by_category.items():
            if products:
                logger.info(f'\nSaving {len(products)} products for category "{category}"...')
                db_result = insert_products_batch(products, category)

                logger.info(
                    f"  History +{db_result['history_inserted']}, "
                    f"Main +{db_result['products_inserted']}, "
                    f"Updated {db_result['products_updated']}"
                )

                total_added_history += db_result['history_inserted']
                total_added_main += db_result['products_inserted']
                total_updated_main += db_result['products_updated']

        logger.info('\n' + '=' * 70)
        logger.info('DATABASE SUMMARY')
        logger.info('=' * 70)
        logger.info(f"Total History: +{total_added_history}")
        logger.info(f"Total Main: +{total_added_main}")
        logger.info(f"Total Updated: {total_updated_main}")

        # Print per-category stats
        logger.info('\nPer-category results:')
        for category, count in category_stats.items():
            logger.info(f'  {category}: {count} products')

        # Show trending products
        try:
            trending = get_trending_products(min_sales=100, limit=5)
            if trending:
                logger.info('\n' + '=' * 70)
                logger.info('TOP TRENDING PRODUCTS')
                logger.info('=' * 70)

                for i, product in enumerate(trending, 1):
                    sales = product.get('sold_total', 0)
                    name = product.get('name', 'Unknown')[:60]
                    price = product.get('price', 0)
                    logger.info(f'{i}. {name}... (₫{price:,.0f}, {sales:,} sold)')
        except Exception as e:
            logger.debug(f'Could not fetch trending products: {e}')

    except Exception as e:
        logger.error(f'Error during scraping: {e}', exc_info=True)
        raise

    logger.info('\n' + '=' * 70)
    logger.info('Done!')
    logger.info('=' * 70)