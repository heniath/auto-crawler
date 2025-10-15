"""
Facebook Search Scraper - Improved for GitHub Actions
"""
import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any
from playwright.async_api import async_playwright
import logging

from src.crawlers.facebook.parser import extract_post_from_node, safe_get
from src.crawlers.facebook.database import create_indexes, insert_posts, get_trending_posts

logger = logging.getLogger(__name__)


class FacebookScraper:
    """Facebook Search Scraper using Playwright"""

    def __init__(self, cookie: str, data_dir: Path):
        """
        Initialize scraper

        Args:
            cookie: Facebook cookie string
            data_dir: Directory to save raw data
        """
        self.cookie = cookie
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

    async def scrape_keyword(self, keyword: str, max_scrolls: int = 5, scroll_delay: int = 2500) -> List[Dict[str, Any]]:
        """
        Scrape Facebook search results for a keyword

        Args:
            keyword: Search keyword
            max_scrolls: Number of scrolls to perform
            scroll_delay: Delay between scrolls (ms)

        Returns:
            List of extracted posts
        """
        search_url = f'https://www.facebook.com/search/posts?q={keyword}'
        raw_log_path = self.data_dir / f'graphql_{keyword.replace(" ", "_")}.json'

        # Clear old log
        if raw_log_path.exists():
            raw_log_path.unlink()

        logger.info(f'Scraping keyword: "{keyword}"')
        logger.info(f'URL: {search_url}')

        async with async_playwright() as p:
            # Cải thiện browser launch options cho GitHub Actions
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',  # Giảm memory usage
                    '--disable-blink-features=AutomationControlled',  # Ẩn automation
                    '--disable-web-security',  # Tắt CORS (chỉ dùng cho scraping)
                ]
            )

            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='vi-VN',
                timezone_id='Asia/Ho_Chi_Minh',
                # Thêm extra headers để giống browser thật hơn
                extra_http_headers={
                    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )

            # Add cookies
            cookies_list = []
            for c in self.cookie.split('; '):
                if '=' in c:
                    name, value = c.split('=', 1)
                    cookies_list.append({
                        'name': name.strip(),
                        'value': value.strip(),
                        'domain': '.facebook.com',
                        'path': '/'
                    })

            await context.add_cookies(cookies_list)

            page = await context.new_page()
            page.set_default_navigation_timeout(90000)  # Tăng timeout lên 90s

            # Intercept GraphQL responses
            graphql_responses = []
            response_count = 0

            async def on_response(response):
                nonlocal response_count
                url = response.url

                if 'graphql' in url or 'api/graphql' in url:
                    try:
                        body = await response.text()

                        # Skip empty responses
                        if not body or len(body) < 10:
                            return

                        # Remove Facebook's XSS protection prefix
                        original_body = body
                        if body.startswith('for (;;);'):
                            body = body[9:]

                        # Try to parse to check if it's valid JSON
                        try:
                            test_data = json.loads(body)

                            # Check if this contains search results
                            has_serp = safe_get(test_data, 'data', 'serpResponse') is not None

                            if has_serp:
                                graphql_responses.append(body)
                                response_count += 1

                                # Save to file
                                with open(raw_log_path, 'a', encoding='utf-8') as f:
                                    f.write(f'=== RESPONSE {response_count} ===\n')
                                    f.write(body + '\n\n')

                                logger.info(f'Captured search response #{response_count} (length: {len(body):,} chars)')
                            else:
                                logger.debug(f'Skipped non-search response (keys: {list(test_data.get("data", {}).keys())[:3]})')

                        except json.JSONDecodeError:
                            # Not valid JSON, skip
                            logger.debug(f'Skipped invalid JSON response (length: {len(body)})')

                    except Exception as e:
                        logger.debug(f'Error reading response: {e}')

            page.on('response', on_response)

            try:
                logger.info('Navigating to search page...')
                await page.goto(search_url, wait_until='domcontentloaded', timeout=90000)

                # Chờ lâu hơn để trang load hoàn toàn
                await page.wait_for_timeout(5000)  # Tăng từ 3s lên 5s

                # Kiểm tra xem có bị redirect về login không
                current_url = page.url
                if 'login' in current_url.lower():
                    logger.error('❌ Facebook redirected to login page - Cookie may be invalid or expired')
                    # Save screenshot for debugging
                    screenshot_path = self.data_dir / f'error_login_{keyword.replace(" ", "_")}.png'
                    await page.screenshot(path=screenshot_path)
                    logger.info(f'Saved screenshot to {screenshot_path}')
                    return []

                # Kiểm tra xem có checkpoint/security check không
                page_content = await page.content()
                if 'checkpoint' in page_content.lower() or 'security' in page_content.lower():
                    logger.error('❌ Facebook security checkpoint detected')
                    screenshot_path = self.data_dir / f'error_checkpoint_{keyword.replace(" ", "_")}.png'
                    await page.screenshot(path=screenshot_path)
                    logger.info(f'Saved screenshot to {screenshot_path}')
                    return []

                logger.info(f'✓ Successfully loaded page: {current_url}')
                logger.info(f'Scrolling {max_scrolls} times...')

                for i in range(max_scrolls):
                    # Scroll với animation để giống người dùng thật
                    await page.evaluate('''
                        window.scrollBy({
                            top: document.body.scrollHeight,
                            left: 0,
                            behavior: 'smooth'
                        })
                    ''')
                    await page.wait_for_timeout(scroll_delay)
                    logger.info(f'  Scroll {i + 1}/{max_scrolls} - Captured {len(graphql_responses)} responses')

                    # Thêm random mouse movement để giống người dùng thật
                    if i % 2 == 0:
                        try:
                            await page.mouse.move(100 + i * 50, 100 + i * 50)
                        except:
                            pass

                # Wait for final responses
                await page.wait_for_timeout(3000)  # Tăng từ 2s lên 3s

                # Save final screenshot for debugging
                if len(graphql_responses) == 0:
                    screenshot_path = self.data_dir / f'final_page_{keyword.replace(" ", "_")}.png'
                    await page.screenshot(path=screenshot_path, full_page=True)
                    logger.warning(f'⚠️ No responses captured. Saved screenshot to {screenshot_path}')

            except Exception as e:
                logger.error(f'Error during scraping: {e}')
                # Save error screenshot
                try:
                    screenshot_path = self.data_dir / f'error_{keyword.replace(" ", "_")}.png'
                    await page.screenshot(path=screenshot_path)
                    logger.info(f'Saved error screenshot to {screenshot_path}')
                except:
                    pass

            finally:
                await browser.close()

        logger.info(f'Total GraphQL responses captured: {len(graphql_responses)}')

        # Parse captured data
        return self._parse_responses(graphql_responses, keyword)

    def _parse_responses(self, responses: List[str], keyword: str) -> List[Dict[str, Any]]:
        """
        Parse GraphQL responses and extract posts

        Args:
            responses: List of GraphQL response strings
            keyword: Search keyword

        Returns:
            List of extracted posts
        """
        posts = []

        for idx, response_text in enumerate(responses):
            # Try multiple parsing strategies
            data = None

            # Strategy 1: Direct JSON parse
            try:
                data = json.loads(response_text)
                logger.debug(f'Response {idx}: Parsed successfully (direct)')
            except json.JSONDecodeError:
                pass

            # Strategy 2: Remove common prefixes
            if data is None:
                for prefix in ['for (;;);', 'while(1);', 'while(true);']:
                    if response_text.startswith(prefix):
                        try:
                            data = json.loads(response_text[len(prefix):])
                            logger.debug(f'Response {idx}: Parsed successfully (removed prefix)')
                            break
                        except:
                            pass

            # Strategy 3: Find JSON start
            if data is None:
                for start_char in ('{', '['):
                    json_start = response_text.find(start_char)
                    if json_start != -1:
                        try:
                            data = json.loads(response_text[json_start:])
                            logger.debug(f'Response {idx}: Parsed successfully (found start)')
                            break
                        except:
                            continue

            # If all strategies fail
            if data is None:
                logger.warning(f'Response {idx}: Failed to parse JSON (length: {len(response_text)})')
                # Save problematic response for debugging
                debug_file = self.data_dir / f'debug_response_{idx}.txt'
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(response_text[:1000])  # First 1000 chars
                logger.debug(f'Saved first 1000 chars to {debug_file}')
                continue

            # Extract search results
            edges = safe_get(data, 'data', 'serpResponse', 'results', 'edges')

            if not edges:
                # Try alternative paths
                edges = safe_get(data, 'data', 'results', 'edges')

            if not edges:
                logger.debug(f'Response {idx}: No search results found in data structure')
                # Log available keys for debugging
                if isinstance(data, dict) and 'data' in data:
                    logger.debug(f'Available keys in data: {list(data.get("data", {}).keys())[:5]}')
                continue

            logger.info(f'Response {idx}: Found {len(edges)} posts')

            for edge_idx, edge in enumerate(edges):
                try:
                    post = extract_post_from_node(edge, keyword)

                    if post and post.get('id'):
                        # Quality filter: must have text or attachments
                        if post.get('text') or post.get('attachments'):
                            posts.append(post)
                            logger.debug(f'  Post {edge_idx}: {post.get("owner", "Unknown")[:30]} - {len(post.get("text", ""))} chars')
                        else:
                            logger.debug(f'  Post {edge_idx}: Skipped (no text/attachments)')
                    else:
                        logger.debug(f'  Post {edge_idx}: Failed to extract (no ID)')

                except Exception as e:
                    logger.error(f'  Post {edge_idx}: Extraction error - {str(e)[:100]}')

        logger.info(f'Total posts extracted: {len(posts)}')
        return posts


async def run_facebook_scraper(cookie: str, keywords: List[str], data_dir: Path, max_scrolls: int = 5):
    """
    Run Facebook scraper for multiple keywords

    Args:
        cookie: Facebook cookie
        keywords: List of keywords to search
        data_dir: Directory to save data
        max_scrolls: Number of scrolls per keyword
    """
    logger.info('='*70)
    logger.info('FACEBOOK SCRAPER STARTED')
    logger.info('='*70)

    # Validate cookie
    if not cookie:
        logger.error('❌ Facebook cookie is required')
        return

    # Log cookie info (first and last 10 chars only for security)
    if len(cookie) > 20:
        logger.info(f'Cookie: {cookie[:10]}...{cookie[-10:]} (length: {len(cookie)})')
    else:
        logger.warning('⚠️ Cookie seems too short, may be invalid')

    # Initialize database indexes
    logger.info('Initializing database...')
    try:
        create_indexes()
    except Exception as e:
        logger.error(f'Failed to initialize database: {e}')
        return

    # Create scraper
    scraper = FacebookScraper(cookie, data_dir)

    all_posts = []
    keyword_stats = {}

    # Scrape each keyword
    for keyword in keywords:
        keyword = keyword.strip()
        if not keyword:
            continue

        try:
            logger.info(f'\n{"="*70}')
            logger.info(f'Processing keyword: "{keyword}"')
            logger.info(f'{"="*70}')

            posts = await scraper.scrape_keyword(keyword, max_scrolls=max_scrolls)
            all_posts.extend(posts)
            keyword_stats[keyword] = len(posts)

            # Save to database
            if posts:
                logger.info(f'✓ Saving {len(posts)} posts to database...')
                result = insert_posts(posts, keyword=keyword)
                logger.info(f'Database result: {result}')
            else:
                logger.warning(f'⚠️ No posts found for keyword: "{keyword}"')

            # Delay between keywords
            if len(keywords) > 1:
                logger.info('Waiting 5 seconds before next keyword...')
                await asyncio.sleep(5)

        except Exception as e:
            logger.error(f'❌ Error scraping keyword "{keyword}": {e}')
            import traceback
            logger.error(traceback.format_exc())

    # Save JSON backup
    unique_posts = []
    seen_ids = set()
    for post in all_posts:
        if post['id'] not in seen_ids:
            seen_ids.add(post['id'])
            unique_posts.append(post)

    output_path = data_dir / 'facebook_posts.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(unique_posts, f, ensure_ascii=False, indent=2)

    # Print summary
    logger.info('\n' + '='*70)
    logger.info('SCRAPING COMPLETED')
    logger.info('='*70)
    logger.info(f'Total unique posts: {len(unique_posts)}')
    logger.info(f'Saved to: {output_path}')

    logger.info('\nPer-keyword results:')
    for keyword, count in keyword_stats.items():
        logger.info(f'  "{keyword}": {count} posts')

    # Show trending posts
    try:
        trending = get_trending_posts(hours=168, min_engagement=5)
        if trending:
            logger.info('\n' + '='*70)
            logger.info('TOP TRENDING POSTS (Last 7 days)')
            logger.info('='*70)

            for i, post in enumerate(trending[:5], 1):
                engagement = post.get('total_engagement', 0)
                logger.info(f'{i}. {post.get("author_name", "Unknown")}: {engagement} engagement')
    except Exception as e:
        logger.debug(f'Could not fetch trending posts: {e}')

    logger.info('\n' + '='*70)
    logger.info('Done!')
    logger.info('='*70)