"""
TikTok Video Scraper using Playwright (sync version)
Based on original tiktok_scraper.py with MongoDB integration
"""
import time
import random
import urllib.parse
from datetime import datetime
from typing import List, Dict
import pytz
from playwright.sync_api import sync_playwright
import logging

from src.crawlers.tiktok.database import insert_videos_batch, create_indexes, get_trending_videos

logger = logging.getLogger(__name__)


class TikTokScraper:
    """TikTok Search Scraper using Playwright (synchronous)"""

    def __init__(self, headless: bool = True, target_per_category: int = 100):
        """
        Initialize scraper

        Args:
            headless: Run browser in headless mode
            target_per_category: Target number of videos per category
        """
        self.headless = headless
        self.scroll_pause_min = 2.0
        self.scroll_pause_max = 4.0
        self.max_rounds_per_keyword = 50
        self.target_per_category = target_per_category
        self.timezone = pytz.timezone("Asia/Ho_Chi_Minh")

    def generate_keyword_variations(self, base_keyword: str) -> List[str]:
        """Generate search keyword variations"""
        variations = [
            base_keyword,
            f"review {base_keyword}",
            f"{base_keyword} giá rẻ",
            f"{base_keyword} đáng mua 2025",
            f"{base_keyword} hot nhất",
            f"{base_keyword} chất lượng",
            f"{base_keyword} tốt nhất",
            f"mua {base_keyword}",
            f"{base_keyword} sale",
            f"{base_keyword} trending",
        ]
        return variations

    def scrape_keyword(
        self,
        page,
        base_keyword: str,
        keyword_variations: List[str],
        collected_items: List[Dict],
        seen_ids: set,
        current_category: Dict
    ) -> int:
        """
        Scrape videos for a keyword and its variations

        Args:
            page: Playwright page object
            base_keyword: Base search keyword
            keyword_variations: List of keyword variations
            collected_items: List to store collected videos
            seen_ids: Set of already seen video IDs
            current_category: Dict with current category name

        Returns:
            Number of new videos collected
        """
        logger.info(f"=== BẮT ĐẦU SCRAPE CHO CATEGORY: '{base_keyword}' ===")
        start_count = sum(1 for it in collected_items if it["category"] == base_keyword)
        target = self.target_per_category

        for idx, keyword in enumerate(keyword_variations, 1):
            logger.info(f"🔎 Biến thể {idx}/{len(keyword_variations)}: '{keyword}'")
            search_page = f"https://www.tiktok.com/search?q={urllib.parse.quote(keyword)}"

            try:
                page.goto(search_page, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception as e:
                logger.warning(f"⚠️ Lỗi load trang cho '{keyword}': {e}")
                continue

            # Random mouse movements to appear human-like
            time.sleep(random.uniform(1.0, 2.5))
            for _ in range(2):
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                page.mouse.move(x, y, steps=random.randint(3, 10))
                time.sleep(random.uniform(0.1, 0.4))
            page.mouse.wheel(0, random.randint(200, 400))
            time.sleep(random.uniform(0.8, 1.5))

            # Scroll and collect
            rounds = 0
            last_count_category = sum(1 for it in collected_items if it["category"] == base_keyword)
            unchanged = 0

            while rounds < self.max_rounds_per_keyword:
                rounds += 1
                scroll_amount = random.randint(3500, 6000)
                page.mouse.wheel(0, scroll_amount)
                pause = random.uniform(self.scroll_pause_min, self.scroll_pause_max)
                page.wait_for_timeout(int(pause * 1000))

                cur_count_category = sum(1 for it in collected_items if it["category"] == base_keyword)
                new_videos = cur_count_category - last_count_category

                # Progress update
                logger.info(f"  🔁 vòng {rounds}: +{new_videos} video | Tổng: {cur_count_category}")

                # Check if target reached
                if target and cur_count_category >= target:
                    logger.info(f"🎯 Đã đạt mục tiêu {target} video cho '{base_keyword}'!")
                    return cur_count_category - start_count

                # Check if no new videos
                if cur_count_category == last_count_category:
                    unchanged += 1
                    if unchanged >= 5:
                        logger.info(f"✅ Biến thể '{keyword}' hết video mới.")
                        break
                else:
                    unchanged = 0
                    last_count_category = cur_count_category

            # Delay between variations
            if idx < len(keyword_variations):
                wait_time = random.uniform(2, 5)
                logger.info(f"⏸ Nghỉ {wait_time:.1f}s trước khi chuyển biến thể...")
                time.sleep(wait_time)

            # Check if target reached
            if target and sum(1 for it in collected_items if it["category"] == base_keyword) >= target:
                break

        final_new = sum(1 for it in collected_items if it["category"] == base_keyword) - start_count
        logger.info(f"✅ Kết thúc category '{base_keyword}': +{final_new} video mới.")
        return final_new

    def scrape_keywords(self, base_keywords: List[str]) -> Dict[str, List[Dict]]:
        """
        Scrape multiple keywords

        Args:
            base_keywords: List of base keywords to search

        Returns:
            Dictionary with collected items and stats
        """
        logger.info('='*70)
        logger.info('📋 Danh sách categories:')
        for i, kw in enumerate(base_keywords, 1):
            logger.info(f"  {i}. {kw}")

        collected_items = []
        seen_ids = set()
        keyword_stats = {}
        current_category = {"name": None}

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
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='Asia/Ho_Chi_Minh'
            )

            page = context.new_page()

            # Anti-detection scripts
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
            """)

            # Network response handler
            def handle_response(response):
                url = response.url
                if "/api/search/general/full/" in url:
                    try:
                        data = response.json()
                        for v in data.get("data", []):
                            video = v.get("item", v)
                            if not isinstance(video, dict):
                                continue

                            vid = video.get("id") or video.get("video", {}).get("id")
                            if not vid or vid in seen_ids:
                                continue

                            seen_ids.add(vid)
                            collected_items.append({
                                "video": video,
                                "category": current_category["name"]
                            })

                            desc = video.get("desc", "")[:60]
                            logger.info(f"📹 [{current_category['name']}] {desc}...")
                    except Exception:
                        pass

            page.on("response", handle_response)

            # Process each keyword
            logger.info("\n🚀 Bắt đầu thu thập...\n")
            try:
                for base_kw in base_keywords:
                    current_category["name"] = base_kw
                    keyword_variations = self.generate_keyword_variations(base_kw)

                    new_count = self.scrape_keyword(
                        page, base_kw, keyword_variations,
                        collected_items, seen_ids, current_category
                    )

                    keyword_stats[base_kw] = new_count

                    # Delay between categories
                    if base_kw != base_keywords[-1]:
                        wait_time = random.uniform(3, 7)
                        logger.info(f"⏸ Nghỉ {wait_time:.1f}s trước khi chuyển category...")
                        time.sleep(wait_time)

            except KeyboardInterrupt:
                logger.warning("⏸ Dừng bởi người dùng.")
            finally:
                browser.close()

        return {
            'collected_items': collected_items,
            'keyword_stats': keyword_stats
        }


def run_tiktok_scraper(
    keywords: List[str],
    headless: bool = True,
    target_per_category: int = 100
):
    """
    Run TikTok scraper for multiple keywords (synchronous version)

    Args:
        keywords: List of keywords to search
        headless: Run browser in headless mode
        target_per_category: Target number of videos per category
    """
    logger.info('='*70)
    logger.info('TIKTOK SCRAPER STARTED')
    logger.info('='*70)

    # Validate inputs
    if not keywords:
        logger.error('Keywords are required')
        return

    # Initialize database
    logger.info('Initializing database...')
    try:
        create_indexes()
    except Exception as e:
        logger.error(f'Failed to initialize database: {e}')
        return

    # Create scraper
    scraper = TikTokScraper(
        headless=headless,
        target_per_category=target_per_category
    )

    # Scrape videos
    try:
        result = scraper.scrape_keywords(keywords)
        collected_items = result['collected_items']
        keyword_stats = result['keyword_stats']

        logger.info('\n' + '='*70)
        logger.info('Scraping completed')
        logger.info('='*70)
        logger.info(f'Total unique videos collected: {len(collected_items)}')

        # Save to database using batch insert (like original script)
        if collected_items:
            logger.info('\nSaving to database...')
            db_result = insert_videos_batch(collected_items)

            logger.info(f"✅ Đã thêm {db_result['history_inserted']} video vào Video_Category_Details_History.")
            logger.info(f"✅ Đã thêm {db_result['videos_inserted']} video mới vào Video_Category.")
            logger.info(f"♻️ Đã cập nhật {db_result['videos_updated']} video trùng (chỉ update ngày).")

        # Print per-keyword stats
        logger.info('\nPer-keyword results:')
        for category, count in keyword_stats.items():
            logger.info(f'  {category}: {count} videos')

        # Show trending videos
        try:
            trending = get_trending_videos(min_views=1000, limit=5)
            if trending:
                logger.info('\n' + '='*70)
                logger.info('TOP TRENDING VIDEOS (Last 7 days)')
                logger.info('='*70)

                for i, video in enumerate(trending[:5], 1):
                    views = video.get('views', 0)
                    caption = video.get('caption', 'No caption')[:50]
                    author = video.get('author_nickname', 'Unknown')
                    logger.info(f'{i}. {author}: {caption}... ({views:,} views)')
        except Exception as e:
            logger.debug(f'Could not fetch trending videos: {e}')

    except Exception as e:
        logger.error(f'Error during scraping: {e}', exc_info=True)
        raise

    logger.info('\n' + '='*70)
    logger.info('Done!')
    logger.info('='*70)