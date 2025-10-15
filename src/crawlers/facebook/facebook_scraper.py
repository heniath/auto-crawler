"""
Facebook Search Scraper with MongoDB Integration
Automatically saves scraped posts to MongoDB
"""
from dotenv import load_dotenv
import asyncio
import os
import json
from typing import List, Dict, Any
from playwright.async_api import async_playwright
from datetime import datetime, timezone

# Import MongoDB functions from the correct module
# Make sure this file is NOT named MongoDB.py
from database import (
    create_indexes,
    insert_posts_with_metrics,
    get_trending_posts,
    get_post_metrics_history
)

# Your cookie
# COOKIE = 'c_user=<c_user>; xs=<xs>; fr=<fr>; datr=<datr>'
load_dotenv()
COOKIE = os.getenv('COOKIE')

# Keywords to search
KEYWORDS = ['tủ lạnh', 'máy giặt', 'nồi chiên không dầu']

DATA_DIR = 'data_search'
os.makedirs(DATA_DIR, exist_ok=True)


def safe_get(obj, *paths):
    """Safely navigate nested dict paths"""
    for path in paths:
        if obj is None:
            return None
        if isinstance(obj, dict):
            obj = obj.get(path)
        elif isinstance(obj, list) and isinstance(path, int):
            try:
                obj = obj[path]
            except IndexError:
                return None
        else:
            return None
    return obj


def parse_count(count_str):
    """Parse counts like '2.9K' or '298' to integers"""
    if isinstance(count_str, int):
        return count_str
    if isinstance(count_str, str):
        count_str = count_str.upper().replace(',', '')
        if 'K' in count_str:
            return int(float(count_str.replace('K', '')) * 1000)
        if 'M' in count_str:
            return int(float(count_str.replace('M', '')) * 1000000)
        try:
            return int(count_str)
        except:
            return 0
    return 0


def extract_post_from_search_node(node: Dict[str, Any], keyword: str) -> Dict[str, Any]:
    """
    Extract post data from search result node with PROPER author_id
    Structure: rendering_strategy.view_model.click_model.story
    """

    # Navigate to the story object
    story = safe_get(node, 'rendering_strategy', 'view_model', 'click_model', 'story')

    if not story:
        return None

    post = {
        'id': story.get('id'),
        'type': story.get('__typename', 'Story'),
        'keyword': keyword,
        'collected_at': int(asyncio.get_event_loop().time()),
        'extraction_method': 'graphql'
    }

    # === TEXT ===
    text = safe_get(story, 'comet_sections', 'content', 'story', 'comet_sections', 'message', 'story', 'message',
                    'text')
    if not text:
        text = safe_get(story, 'message', 'text')
    post['text'] = text or ''

    # ============================================
    # === AUTHOR ID & NAME (QUAN TRỌNG!) ===
    # ============================================

    # METHOD 1: Từ actors array (ƯU TIÊN)
    actors = safe_get(story, 'comet_sections', 'content', 'story', 'actors')
    author_id = None
    author_name = None

    if actors and isinstance(actors, list) and len(actors) > 0:
        actor = actors[0]
        author_id = actor.get('id')  # ✅ ID thực của Page/Profile
        author_name = actor.get('name')

        # Debug: In ra để kiểm tra
        if author_id:
            print(f'      [DEBUG] Author from actors: {author_name} (ID: {author_id})')

    # METHOD 2: Từ owning_profile (Fallback)
    if not author_id:
        profile = safe_get(story, 'comet_sections', 'feedback', 'story',
                           'story_ufi_container', 'story', 'feedback_context',
                           'feedback_target_with_context', 'owning_profile')
        if profile:
            author_id = profile.get('id')
            author_name = profile.get('name')

            if author_id:
                print(f'      [DEBUG] Author from owning_profile: {author_name} (ID: {author_id})')

    # METHOD 3: Từ comet_sections.context_layout (Fallback 2)
    if not author_id:
        context_actors = safe_get(story, 'comet_sections', 'context_layout', 'story',
                                  'comet_sections', 'actor_photo', 'story', 'actors')
        if context_actors and isinstance(context_actors, list) and len(context_actors) > 0:
            actor = context_actors[0]
            author_id = actor.get('id')
            author_name = actor.get('name')

            if author_id:
                print(f'      [DEBUG] Author from context_layout: {author_name} (ID: {author_id})')

    # METHOD 4: Từ comet_sections.aggregated_stories (Fallback 3 - cho Group posts)
    if not author_id:
        agg_profile = safe_get(story, 'comet_sections', 'aggregated_stories', 'story',
                               'attached_story', 'comet_sections', 'actor_photo', 'story',
                               'actors', 0)
        if agg_profile:
            author_id = agg_profile.get('id')
            author_name = agg_profile.get('name')

            if author_id:
                print(f'      [DEBUG] Author from aggregated_stories: {author_name} (ID: {author_id})')

    # Fallback cuối: Nếu vẫn không có ID, dùng name làm placeholder
    if not author_name:
        author_name = safe_get(story, 'comet_sections', 'content', 'story', 'actors', 0, 'name')
        if not author_name:
            author_name = 'Unknown'

    # ⚠️ CẢNH BÁO: Nếu không lấy được ID thực
    if not author_id:
        print(f'      [⚠️  WARNING] Could not extract author_id for post {post["id"]}, using fallback')
        # Tạo ID tạm từ name (không lý tưởng nhưng tốt hơn None)
        author_id = f'fb_user_{hash(author_name) % 1000000000}'  # Hash name thành số

    post['author_id'] = author_id
    post['owner'] = author_name

    # ============================================

    # === TIMESTAMP ===
    publish_time = safe_get(story, 'comet_sections', 'timestamp', 'story', 'creation_time')
    if not publish_time:
        publish_time = safe_get(story, 'comet_sections', 'context_layout', 'story',
                                'comet_sections', 'metadata', 1, 'story', 'creation_time')
    post['publish_time'] = publish_time or 0

    # === COMMENT COUNT ===
    comment_count = safe_get(story, 'comet_sections', 'feedback', 'story',
                             'story_ufi_container', 'story', 'feedback_context',
                             'feedback_target_with_context', 'comet_ufi_summary_and_actions_renderer',
                             'feedback', 'comments_count_summary_renderer', 'feedback',
                             'comment_rendering_instance', 'comments', 'total_count')
    post['comment_count'] = int(comment_count) if comment_count else 0

    # === SHARE COUNT ===
    share_count = safe_get(story, 'comet_sections', 'feedback', 'story',
                           'story_ufi_container', 'story', 'feedback_context',
                           'feedback_target_with_context', 'comet_ufi_summary_and_actions_renderer',
                           'feedback', 'share_count', 'count')
    post['share_count'] = int(share_count) if share_count else 0

    # === VIEW COUNT ===
    view_count = safe_get(story, 'attachments', 0, 'styles', 'attachment', 'media', 'video_view_count')
    post['view_count'] = int(view_count) if view_count else 0

    # === REACTIONS ===
    reactions = {}
    ufi_feedback = safe_get(story, 'comet_sections', 'feedback', 'story',
                            'story_ufi_container', 'story', 'feedback_context',
                            'feedback_target_with_context', 'comet_ufi_summary_and_actions_renderer',
                            'feedback')

    if ufi_feedback:
        total = ufi_feedback.get('i18n_reaction_count')
        if total:
            reactions['total'] = parse_count(total)

        # Top reactions breakdown
        top_reactions = safe_get(ufi_feedback, 'top_reactions', 'edges')
        if top_reactions:
            for edge in top_reactions:
                reaction_node = edge.get('node', {})
                name = reaction_node.get('localized_name') or reaction_node.get('reaction_type')
                count = edge.get('reaction_count') or edge.get('i18n_reaction_count')
                if name and count:
                    reactions[name] = parse_count(count)

    post['reactions'] = reactions

    # === ATTACHMENTS ===
    attachments = []
    story_attachments = story.get('attachments', []) or []

    for att in story_attachments:
        try:
            media = safe_get(att, 'styles', 'attachment', 'media')
            if not media:
                continue

            att_obj = {
                'type': media.get('__typename') if isinstance(media, dict) else None,
                'id': media.get('id') if isinstance(media, dict) else None,
                'url': None,
                'thumbnail': None,
                'alt_text': ''
            }

            # Try to get URL
            url = safe_get(att, 'styles', 'attachment', 'url')
            if not url and media:
                url = media.get('url')

            # Try to get thumbnail
            thumb = safe_get(media, 'thumbnailImage', 'uri')
            if not thumb:
                thumb = safe_get(media, 'preferred_story_attachment_image', 'uri')

            if url or att_obj['id']:
                att_obj['url'] = url
                att_obj['thumbnail'] = thumb
                attachments.append(att_obj)

        except Exception as e:
            continue

    post['attachments'] = attachments

    return post

async def scrape_search_keyword(keyword: str, max_scrolls: int = 5, save_to_db: bool = True):
    """Scrape search results for a single keyword"""

    search_url = f'https://www.facebook.com/search/posts?q={keyword}'
    raw_log_path = os.path.join(DATA_DIR, f'graphql_{keyword.replace(" ", "_")}.json')

    # Clear old log
    if os.path.exists(raw_log_path):
        os.remove(raw_log_path)

    print(f'\n{"="*70}')
    print(f'Scraping keyword: "{keyword}"')
    print(f'{"="*70}')

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        # Add cookies
        for c in COOKIE.split('; '):
            name, value = c.split('=', 1)
            await context.add_cookies([{
                'name': name,
                'value': value,
                'domain': '.facebook.com',
                'path': '/'
            }])

        page = await context.new_page()
        page.set_default_navigation_timeout(60000)

        # Intercept GraphQL responses
        async def on_response(response):
            url = response.url

            # Look for search-related GraphQL responses
            if 'graphql' in url or 'api/graphql' in url:
                try:
                    body = await response.text()

                    # Remove Facebook's XSS protection prefix
                    if body.startswith('for (;;);'):
                        body = body[9:]

                    # Check if this is a search response
                    if 'serpResponse' in body or 'SearchPostsResultPaginatedDeferrableQuery' in body:
                        with open(raw_log_path, 'a', encoding='utf-8') as f:
                            f.write(body + '\n\n')
                        print(f'  [✓] Captured search GraphQL response')

                except Exception as e:
                    print(f'  [!] Error reading response: {e}')

        page.on('response', on_response)

        try:
            print(f'[*] Navigating to search page...')
            await page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(3000)

            print(f'[*] Scrolling to load more posts...')
            for i in range(max_scrolls):
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(2500)
                print(f'  Scroll {i + 1}/{max_scrolls}')

            # Wait a bit for final responses
            await page.wait_for_timeout(2000)

        except Exception as e:
            print(f'[!] Navigation/scroll error: {e}')
            print('[*] Continuing to parse what we captured...')

        await browser.close()

    # Parse the captured data
    posts = []

    if not os.path.exists(raw_log_path):
        print(f'[!] No GraphQL data captured for "{keyword}"')
        return posts

    with open(raw_log_path, 'r', encoding='utf-8') as f:
        raw = f.read()

    chunks = [c.strip() for c in raw.split('\n\n') if c.strip()]
    print(f'\n[*] Processing {len(chunks)} GraphQL response chunks...')

    for idx, chunk in enumerate(chunks):
        try:
            data = json.loads(chunk)
        except json.JSONDecodeError:
            # Try to find JSON start
            for start_char in ('{', '['):
                json_start = chunk.find(start_char)
                if json_start != -1:
                    try:
                        data = json.loads(chunk[json_start:])
                        break
                    except:
                        continue
            else:
                print(f'  [!] Chunk {idx}: Invalid JSON, skipping')
                continue

        # Look for search results
        edges = safe_get(data, 'data', 'serpResponse', 'results', 'edges')

        if edges:
            print(f'  [✓] Chunk {idx}: Found {len(edges)} search results')

            for edge_idx, edge in enumerate(edges):
                try:
                    post = extract_post_from_search_node(edge, keyword)

                    if post and post.get('id'):
                        # Quality filter
                        if post.get('text') or post.get('attachments'):
                            posts.append(post)
                            print(f'      - Post {edge_idx}: "{post.get("owner", "Unknown")[:30]}" - {len(post.get("text", ""))} chars')

                except Exception as e:
                    print(f'      - Post {edge_idx}: Error extracting - {e}')
                    continue
        else:
            print(f'  [!] Chunk {idx}: No search results found')

    # Save to MongoDB
    if save_to_db and posts:
        print(f'\n[*] Saving {len(posts)} posts to MongoDB...')
        result = insert_posts_with_metrics(posts, keyword=keyword)
        print(f'[✓] Database results: {result}')

    return posts


async def main():
    """Main scraping workflow"""

    # Initialize database indexes (run once at startup)
    print('[*] Initializing MongoDB indexes...')
    create_indexes()

    all_posts = []
    keyword_results = {}

    # Scrape each keyword
    for keyword in KEYWORDS:
        posts = await scrape_search_keyword(keyword, max_scrolls=5, save_to_db=True)
        all_posts.extend(posts)
        keyword_results[keyword] = len(posts)

        # Polite delay between keywords
        if len(KEYWORDS) > 1:
            print(f'\n[*] Waiting 5 seconds before next keyword...')
            await asyncio.sleep(5)

    # Remove duplicates for JSON file
    seen_ids = set()
    unique_posts = []
    for post in all_posts:
        if post['id'] not in seen_ids:
            seen_ids.add(post['id'])
            unique_posts.append(post)

    # Save to JSON file as backup
    output_path = os.path.join(DATA_DIR, 'search_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(unique_posts, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f'\n{"="*70}')
    print('SCRAPING COMPLETED')
    print(f'{"="*70}')
    print(f'Total posts collected: {len(unique_posts)}')
    print(f'Saved to JSON: {output_path}')
    print(f'Saved to MongoDB: facebook_scraper.posts')

    print(f'\nPer-keyword breakdown:')
    for keyword, count in keyword_results.items():
        print(f'  - "{keyword}": {count} posts')

    # Statistics
    posts_with_text = sum(1 for p in unique_posts if p.get('text'))
    posts_with_images = sum(1 for p in unique_posts if p.get('attachments'))
    posts_with_reactions = sum(1 for p in unique_posts if p.get('reactions', {}).get('total', 0) > 0)

    print(f'\nContent statistics:')
    print(f'  - Posts with text: {posts_with_text}')
    print(f'  - Posts with images: {posts_with_images}')
    print(f'  - Posts with reactions: {posts_with_reactions}')

    # Show trending posts from database
    print(f'\n{"="*70}')
    print('TOP TRENDING POSTS (Last 7 days)')
    print(f'{"="*70}')

    trending = get_trending_posts(hours=168, min_engagement=5)  # 7 days

    if trending:
        for i, post in enumerate(trending[:5], 1):  # Show top 5
            metrics = post.get('latest_metrics', {})
            engagement = post.get('total_engagement', 0)

            print(f'\n{i}. [{post.get("category", "general").upper()}]')
            print(f'   Author: {post.get("author_name", "Unknown")}')
            print(f'   Content: {post.get("content", "")[:80]}...')
            print(f'   Engagement: {engagement} (👍 {metrics.get("likes", 0)} | 💬 {metrics.get("comments", 0)} | 🔄 {metrics.get("shares", 0)})')
            print(f'   Keywords: {", ".join(post.get("matched_keywords", []))}')
    else:
        print('[*] No trending posts found in the last 7 days')

    print(f'\n{"="*70}')
    print('Done! Check MongoDB for all saved data.')
    print(f'{"="*70}')


if __name__ == '__main__':

    asyncio.run(main())
