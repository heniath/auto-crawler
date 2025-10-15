"""
YouTube Video Scraper using YouTube Data API v3
Implements API key rotation and robust error handling
"""
import time
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging

from src.crawlers.youtube.database import create_indexes, insert_videos, get_trending_videos

logger = logging.getLogger(__name__)


class YouTubeScraper:
    """YouTube Data API v3 Scraper with key rotation"""

    def __init__(self, api_keys: List[str]):
        """
        Initialize scraper with API keys

        Args:
            api_keys: List of YouTube Data API v3 keys
        """
        self.api_keys = api_keys
        self.current_key_index = 0
        self.youtube = self._get_client()
        self.excluded_channels = ['yến nồi cơm điện']  # Blacklisted channels

    def _get_client(self):
        """Get YouTube API client with current key"""
        if self.current_key_index >= len(self.api_keys):
            raise Exception('All API keys exhausted')

        api_key = self.api_keys[self.current_key_index]
        logger.info(f'Using API key #{self.current_key_index + 1}/{len(self.api_keys)}')
        return build('youtube', 'v3', developerKey=api_key)

    def _rotate_key(self):
        """Rotate to next API key"""
        self.current_key_index += 1
        if self.current_key_index >= len(self.api_keys):
            raise Exception('All API keys exhausted')

        self.youtube = self._get_client()
        logger.info(f'🔑 Rotated to API key #{self.current_key_index + 1}')

    def _is_channel_excluded(self, channel_title: str) -> bool:
        """Check if channel should be excluded"""
        if not channel_title:
            return False

        channel_lower = channel_title.strip().lower()
        return any(excluded in channel_lower for excluded in self.excluded_channels)

    def search_videos(self, query: str, max_results: int = 400) -> List[Dict[str, Any]]:
        """
        Search for videos by query

        Args:
            query: Search query
            max_results: Maximum number of videos to fetch

        Returns:
            List of video data dictionaries
        """
        videos = []
        seen_ids = set()
        next_page_token = None
        page_count = 0
        max_pages = (max_results // 50) + 1

        logger.info(f'Searching videos for: "{query}"')
        logger.info(f'Target: {max_results} videos')

        while len(videos) < max_results and page_count < max_pages:
            try:
                # Search request
                search_response = self.youtube.search().list(
                    q=query,
                    part='id,snippet',
                    type='video',
                    maxResults=min(50, max_results - len(videos)),
                    pageToken=next_page_token,
                    order='relevance',
                    relevanceLanguage='vi'
                ).execute()

                page_count += 1
                video_ids = []

                # Collect video IDs
                for item in search_response.get('items', []):
                    video_id = item['id']['videoId']

                    if video_id in seen_ids:
                        continue

                    # Quick channel filter from snippet
                    channel_title = item['snippet'].get('channelTitle', '')
                    if self._is_channel_excluded(channel_title):
                        logger.debug(f'Excluded channel: {channel_title}')
                        continue

                    seen_ids.add(video_id)
                    video_ids.append(video_id)

                # Fetch video details in batch
                if video_ids:
                    video_details = self._get_video_details(video_ids)
                    videos.extend(video_details)

                logger.info(f'  Page {page_count}: +{len(video_ids)} videos (Total: {len(videos)})')

                # Check for next page
                next_page_token = search_response.get('nextPageToken')
                if not next_page_token:
                    logger.info('No more pages available')
                    break

                # Rate limiting
                time.sleep(1)

            except HttpError as e:
                if e.resp.status == 403:
                    logger.warning(f'Quota exceeded on key #{self.current_key_index + 1}')
                    self._rotate_key()
                    continue
                else:
                    logger.error(f'HTTP error during search: {e}')
                    break

            except Exception as e:
                logger.error(f'Error during search: {e}')
                break

        logger.info(f'✓ Search completed: {len(videos)} videos found')
        return videos

    def _get_video_details(self, video_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch detailed information for videos

        Args:
            video_ids: List of video IDs

        Returns:
            List of video data dictionaries
        """
        videos = []

        try:
            # Videos can be fetched in batches of 50
            for i in range(0, len(video_ids), 50):
                batch_ids = video_ids[i:i+50]

                video_response = self.youtube.videos().list(
                    part='snippet,statistics,contentDetails',
                    id=','.join(batch_ids)
                ).execute()

                for item in video_response.get('items', []):
                    snippet = item['snippet']
                    stats = item.get('statistics', {})

                    # Apply channel filter
                    channel_title = snippet.get('channelTitle', '')
                    if self._is_channel_excluded(channel_title):
                        continue

                    video_data = {
                        'video_id': item['id'],
                        'title': snippet['title'],
                        'channel_id': snippet.get('channelId', ''),
                        'channel_title': channel_title,
                        'published_at': snippet['publishedAt'].split('T')[0],
                        'views': int(stats.get('viewCount', 0)),
                        'likes': int(stats.get('likeCount', 0)),
                        'comments': int(stats.get('commentCount', 0)),
                        'tags': ', '.join(snippet.get('tags', []))
                    }

                    videos.append(video_data)

                # Rate limiting between batches
                if i + 50 < len(video_ids):
                    time.sleep(0.5)

        except HttpError as e:
            if e.resp.status == 403:
                logger.warning(f'Quota exceeded during video details fetch')
                self._rotate_key()
            else:
                logger.error(f'HTTP error fetching video details: {e}')

        except Exception as e:
            logger.error(f'Error fetching video details: {e}')

        return videos


async def run_youtube_scraper(
    api_keys: List[str],
    keywords: List[str],
    max_videos_per_keyword: int = 400
):
    """
    Run YouTube scraper for multiple keywords

    Args:
        api_keys: List of YouTube Data API keys
        keywords: List of search keywords
        max_videos_per_keyword: Maximum videos per keyword
    """
    logger.info('='*70)
    logger.info('YOUTUBE SCRAPER STARTED')
    logger.info('='*70)

    # Validate inputs
    if not api_keys or not keywords:
        logger.error('API keys and keywords are required')
        return

    # Initialize database
    logger.info('Initializing database...')
    try:
        create_indexes()
    except Exception as e:
        logger.error(f'Failed to initialize database: {e}')
        return

    # Create scraper
    try:
        scraper = YouTubeScraper(api_keys)
    except Exception as e:
        logger.error(f'Failed to create scraper: {e}')
        return

    total_videos = 0
    keyword_stats = {}

    # Process each keyword
    for idx, keyword in enumerate(keywords, 1):
        keyword = keyword.strip()
        if not keyword:
            continue

        try:
            logger.info(f'\n{"="*70}')
            logger.info(f'Keyword {idx}/{len(keywords)}: "{keyword}"')
            logger.info(f'{"="*70}')

            # Search videos
            videos = scraper.search_videos(keyword, max_results=max_videos_per_keyword)

            if videos:
                # Save to database
                logger.info(f'Saving {len(videos)} videos to database...')
                result = insert_videos(videos, query=keyword)

                logger.info(f'Database result: {result}')
                total_videos += len(videos)
                keyword_stats[keyword] = len(videos)
            else:
                logger.warning(f'No videos found for: "{keyword}"')
                keyword_stats[keyword] = 0

            # Delay between keywords (except last one)
            if idx < len(keywords):
                logger.info('Waiting 2 seconds before next keyword...')
                time.sleep(2)

        except Exception as e:
            logger.error(f'Error processing keyword "{keyword}": {e}')
            keyword_stats[keyword] = 0
            continue

    # Print summary
    logger.info('\n' + '='*70)
    logger.info('SCRAPING COMPLETED')
    logger.info('='*70)
    logger.info(f'Total videos collected: {total_videos}')

    logger.info('\nPer-keyword results:')
    for keyword, count in keyword_stats.items():
        logger.info(f'  "{keyword}": {count} videos')

    # Show trending videos
    try:
        trending = get_trending_videos(min_views=1000, limit=5)
        if trending:
            logger.info('\n' + '='*70)
            logger.info('TOP TRENDING VIDEOS')
            logger.info('='*70)

            for i, video in enumerate(trending, 1):
                views = video.get('views', 0)
                title = video.get('title', 'Unknown')[:60]
                logger.info(f'{i}. {title}... ({views:,} views)')
    except Exception as e:
        logger.debug(f'Could not fetch trending videos: {e}')

    logger.info('\n' + '='*70)
    logger.info('Done!')
    logger.info('='*70)