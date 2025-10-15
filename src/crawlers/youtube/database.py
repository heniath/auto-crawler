"""
YouTube Database Operations
Handles video storage with master/history pattern
"""
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError
import logging

from src.core.database import get_database

# Import configs
from src.configs.settings import (
    MONGO_URI,
    FACEBOOK_DB, YOUTUBE_DB, SHOPEE_DB, TIKTOK_DB,
    FACEBOOK_COOKIE, FACEBOOK_KEYWORDS, MAX_SCROLLS,
    YOUTUBE_API_KEYS, YOUTUBE_KEYWORDS, YOUTUBE_MAX_VIDEOS_PER_KEYWORD,
    DATA_DIR, LOG_DIR, LOG_LEVEL, validate_config
)

logger = logging.getLogger(__name__)


def create_indexes():
    """Create MongoDB indexes for YouTube collections"""
    db = get_database(YOUTUBE_DB)
    master = db['videos']
    history = db['snapshots']

    try:
        # Master collection indexes
        master.create_index('video_id', unique=True)
        master.create_index('channel_id')
        master.create_index('category')
        master.create_index([('views', -1)])
        master.create_index([('published_at', -1)])
        master.create_index([('last_crawl_date', -1)])

        # History collection indexes
        history.create_index([('video_id', 1), ('crawl_date', -1)])
        history.create_index('crawl_date')
        history.create_index('category')

        logger.info('✓ YouTube database indexes created successfully')

    except Exception as e:
        logger.error(f'Error creating YouTube indexes: {e}')
        raise


def classify_category(title: str, tags: str, query: str) -> str:
    """
    Classify video into product category based on title, tags, and search query

    Args:
        title: Video title
        tags: Video tags (comma-separated)
        query: Search query used

    Returns:
        Category identifier
    """
    text = f"{title} {tags} {query}".lower()

    categories = {
        'rice_cooker': ['nồi cơm điện', 'noi com dien', 'rice cooker'],
        'refrigerator': ['tủ lạnh', 'tu lanh', 'tủ đông', 'refrigerator'],
        'washing_machine': ['máy giặt', 'may giat', 'washing machine'],
        'stove': ['bếp', 'bep', 'stove', 'bếp ga', 'bếp từ'],
        'fan': ['quạt', 'quat', 'fan'],
        'kettle': ['ấm siêu tốc', 'am sieu toc', 'kettle', 'ấm đun'],
        'iron': ['bàn ủi', 'ban ui', 'iron'],
        'vacuum': ['máy hút bụi', 'may hut bui', 'vacuum'],
        'tv': ['tivi', 'ti vi', 'tv', 'smart tv', 'television'],
        'oven': ['lò nướng', 'lo nuong', 'oven', 'air fryer']
    }

    for category, keywords in categories.items():
        if any(kw in text for kw in keywords):
            return category

    return 'general'


def transform_video(raw_video: Dict[str, Any], category: str, crawl_date: str) -> tuple:
    """
    Transform raw video data into master and history documents

    Args:
        raw_video: Raw video data from YouTube API
        category: Video category
        crawl_date: Current crawl date

    Returns:
        Tuple of (master_doc, history_doc)
    """
    video_id = raw_video['video_id']

    # Master document (static + latest metrics)
    master_doc = {
        'video_id': video_id,
        'title': raw_video['title'],
        'channel_id': raw_video.get('channel_id', ''),
        'channel_title': raw_video['channel_title'],
        'published_at': raw_video['published_at'],
        'category': category,
        'platform': 'youtube',
        'tags': raw_video.get('tags', ''),
        'views': raw_video['views'],
        'likes': raw_video['likes'],
        'comments': raw_video['comments'],
        'first_crawl_date': crawl_date,
        'last_crawl_date': crawl_date
    }

    # History document (snapshot)
    history_doc = {
        'video_id': video_id,
        'views': raw_video['views'],
        'likes': raw_video['likes'],
        'comments': raw_video['comments'],
        'crawl_date': crawl_date,
        'category': category,
        'platform': 'youtube'
    }

    return master_doc, history_doc


def insert_videos(videos: List[Dict[str, Any]], query: str) -> Dict[str, int]:
    """
    Insert videos into master and history collections

    Args:
        videos: List of video data from YouTube API
        query: Search query used

    Returns:
        Statistics dictionary
    """
    db = get_database()
    master = db['videos']
    history = db['snapshots']

    crawl_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    master_operations = []
    history_documents = []

    for video in videos:
        if not video.get('video_id'):
            logger.warning('Skipping video without ID')
            continue

        # Determine category
        category = classify_category(
            video.get('title', ''),
            video.get('tags', ''),
            query
        )

        master_doc, history_doc = transform_video(video, category, crawl_date)

        # Upsert operation for master
        master_operations.append(
            UpdateOne(
                {'video_id': master_doc['video_id']},
                {
                    '$setOnInsert': {
                        'video_id': master_doc['video_id'],
                        'title': master_doc['title'],
                        'channel_id': master_doc['channel_id'],
                        'channel_title': master_doc['channel_title'],
                        'published_at': master_doc['published_at'],
                        'category': master_doc['category'],
                        'platform': master_doc['platform'],
                        'tags': master_doc['tags'],
                        'first_crawl_date': crawl_date
                    },
                    '$set': {
                        'views': master_doc['views'],
                        'likes': master_doc['likes'],
                        'comments': master_doc['comments'],
                        'last_crawl_date': crawl_date
                    }
                },
                upsert=True
            )
        )

        # Always insert new history snapshot
        history_documents.append(history_doc)

    result = {
        'videos_inserted': 0,
        'videos_updated': 0,
        'history_inserted': 0,
        'errors': 0
    }

    # Execute master operations
    if master_operations:
        try:
            master_result = master.bulk_write(master_operations, ordered=False)
            result['videos_inserted'] = master_result.upserted_count
            result['videos_updated'] = master_result.modified_count
        except BulkWriteError as e:
            result['errors'] = len(e.details.get('writeErrors', []))
            logger.error(f'Master bulk write errors: {result["errors"]}')

    # Insert history snapshots
    if history_documents:
        try:
            history_result = history.insert_many(history_documents, ordered=False)
            result['history_inserted'] = len(history_result.inserted_ids)
        except Exception as e:
            logger.error(f'Error inserting history: {e}')

    return result


def get_trending_videos(category: Optional[str] = None, min_views: int = 1000, limit: int = 20) -> List[Dict]:
    """
    Get trending videos from database

    Args:
        category: Filter by category (optional)
        min_views: Minimum view count
        limit: Maximum number of results

    Returns:
        List of trending videos
    """
    db = get_database()
    master = db['videos']

    match_stage = {'views': {'$gte': min_views}}
    if category:
        match_stage['category'] = category

    pipeline = [
        {'$match': match_stage},
        {'$sort': {'views': -1}},
        {'$limit': limit},
        {
            '$project': {
                'video_id': 1,
                'title': 1,
                'channel_title': 1,
                'category': 1,
                'views': 1,
                'likes': 1,
                'comments': 1,
                'published_at': 1
            }
        }
    ]

    return list(master.aggregate(pipeline))