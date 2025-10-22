"""
TikTok Database Operations
Exactly matching original tiktok_scraper.py logic
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
import pytz
import logging

from src.core.database import get_tiktok_database

logger = logging.getLogger(__name__)


def create_indexes():
    """Create MongoDB indexes for TikTok collections"""
    db = get_tiktok_database()

    # Collections (matching original script names)
    master = db['Video_Category']
    history = db['Video_Category_Details_History']

    try:
        # Clean null/missing IDs
        result = master.delete_many({
            '$or': [
                {'id': None},
                {'id': {'$exists': False}}
            ]
        })
        if result.deleted_count > 0:
            logger.info(f'Cleaned {result.deleted_count} documents with null id')

        # Master collection indexes
        master.create_index('id', unique=True)
        master.create_index('author_username')
        master.create_index('category')
        master.create_index([('create_time', -1)])
        master.create_index([('first_day_crawling', -1)])
        master.create_index([('last_day_crawling', -1)])

        # History collection indexes
        history.create_index([('id', 1), ('crawl_date', -1)])
        history.create_index('crawl_date')
        history.create_index('category')
        history.create_index('author_username')

        logger.info('✓ TikTok database indexes created successfully')

    except Exception as e:
        logger.error(f'Error creating TikTok indexes: {e}')
        raise


def insert_videos_batch(collected_items: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Insert videos into master and history collections
    Exactly matching original script logic

    Args:
        collected_items: List of items with 'video' and 'category' keys

    Returns:
        Statistics dictionary
    """
    db = get_tiktok_database()
    collection_main = db['Video_Category']
    collection_history = db['Video_Category_Details_History']

    timezone = pytz.timezone("Asia/Ho_Chi_Minh")
    now_vn = datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S")

    history_rows = []
    main_docs = {}

    # Process collected items (matching original logic exactly)
    for item in collected_items:
        v = item["video"]
        category = item["category"]
        stats = v.get("stats", {}) or v.get("statsV2", {}) or {}
        author = v.get("author", {}) or {}
        vid = v.get("id") or v.get("video", {}).get("id")

        # Parse create_time
        create_time = ""
        if v.get("createTime"):
            try:
                create_time = datetime.fromtimestamp(
                    int(v["createTime"]),
                    timezone
                ).strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass

        # History document
        doc_history = {
            "id": vid,
            "author_username": author.get("uniqueId"),
            "author_nickname": author.get("nickname"),
            "create_time": create_time,
            "likes": stats.get("diggCount", 0),
            "shares": stats.get("shareCount", 0),
            "comments": stats.get("commentCount", 0),
            "views": stats.get("playCount", 0),
            "saved": stats.get("collectCount", 0),
            "caption": (v.get("desc", "") or "")[:400],
            "category": category,
            "crawl_date": now_vn
        }
        history_rows.append(doc_history)

        # Master document
        if vid not in main_docs:
            main_docs[vid] = {
                "id": vid,
                "author_username": author.get("uniqueId"),
                "author_nickname": author.get("nickname"),
                "create_time": create_time,
                "caption": (v.get("desc", "") or "")[:400],
                "category": category,
                "first_day_crawling": now_vn,
                "last_day_crawling": now_vn
            }
        else:
            main_docs[vid]["last_day_crawling"] = now_vn

    # Insert/Update to MongoDB (matching original logic)
    added_main = 0
    updated_main = 0

    # Insert history (always insert all)
    if history_rows:
        collection_history.insert_many(history_rows)

    # Insert/update main
    if main_docs:
        for doc in main_docs.values():
            existing = collection_main.find_one({"id": doc["id"]})
            if existing:
                collection_main.update_one(
                    {"id": doc["id"]},
                    {"$set": {"last_day_crawling": doc["last_day_crawling"]}}
                )
                updated_main += 1
            else:
                collection_main.insert_one(doc)
                added_main += 1

    return {
        'videos_inserted': added_main,
        'videos_updated': updated_main,
        'history_inserted': len(history_rows),
        'errors': 0
    }


def get_trending_videos(
        category: Optional[str] = None,
        hours: int = 168,
        min_views: int = 1000,
        limit: int = 20
) -> List[Dict]:
    """
    Get trending videos from database

    Args:
        category: Filter by category (optional)
        hours: Time window in hours (default: 7 days)
        min_views: Minimum view count
        limit: Maximum number of results

    Returns:
        List of trending videos
    """
    db = get_tiktok_database()
    history = db['Video_Category_Details_History']

    # Calculate time threshold
    from datetime import timedelta
    timezone = pytz.timezone("Asia/Ho_Chi_Minh")
    time_threshold = (datetime.now(timezone) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    match_stage = {
        'crawl_date': {'$gte': time_threshold},
        'views': {'$gte': min_views}
    }

    if category:
        match_stage['category'] = category

    pipeline = [
        {'$match': match_stage},
        {'$sort': {'views': -1}},
        {'$limit': limit},
        {
            '$project': {
                'id': 1,
                'author_username': 1,
                'author_nickname': 1,
                'caption': 1,
                'category': 1,
                'views': 1,
                'likes': 1,
                'comments': 1,
                'shares': 1,
                'crawl_date': 1
            }
        }
    ]

    return list(history.aggregate(pipeline))