"""
Facebook Database Operations
"""
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError, OperationFailure
import logging

from src.core.database import get_database

logger = logging.getLogger(__name__)


def create_indexes():
    """Create MongoDB indexes for optimal performance"""
    db = get_database()
    posts = db['posts']
    metrics = db['metrics_snapshot']

    try:
        # Clean null/missing post_ids
        result = posts.delete_many({
            '$or': [
                {'post_id': None},
                {'post_id': {'$exists': False}}
            ]
        })
        if result.deleted_count > 0:
            logger.info(f'Cleaned {result.deleted_count} documents with null post_id')

        # Drop existing post_id index if it exists
        try:
            posts.drop_index('post_id_1')
            logger.debug('Dropped existing post_id index')
        except OperationFailure:
            pass

        # Create indexes
        posts.create_index('post_id', unique=True)
        posts.create_index('author_id')
        posts.create_index('created_at')
        posts.create_index([('matched_keywords', 1)])
        posts.create_index([('category', 1)])
        posts.create_index([('platform', 1)])
        posts.create_index([('scraped_at', -1)])

        metrics.create_index([('post_id', 1), ('snapshot_time', -1)])
        metrics.create_index('snapshot_time')
        metrics.create_index('crawl_session_id')

        logger.info('✓ Database indexes created successfully')

    except Exception as e:
        logger.error(f'Error creating indexes: {e}')
        raise


def classify_category(text: str, keyword: str) -> str:
    """
    Classify post into product category

    Args:
        text: Post content
        keyword: Matched keyword

    Returns:
        Category string
    """
    text_lower = text.lower()
    keyword_lower = keyword.lower()

    categories = {
        'refrigerator': ['tủ lạnh', 'tu lanh', 'tủ đông', 'refrigerator', 'fridge'],
        'rice_cooker': ['nồi cơm điện', 'noi com dien', 'rice cooker'],
        'washing_machine': ['máy giặt', 'may giat', 'washing machine'],
        'tv': ['tivi', 'tv', 'ti vi', 'smart tv'],
        'air_fryer': ['nồi chiên không dầu', 'air fryer', 'lò nướng'],
        'stove': ['bếp ga', 'bep ga', 'bếp từ', 'bep tu'],
        'vacuum': ['máy hút bụi', 'may hut bui', 'vacuum'],
        'fan': ['quạt', 'quat', 'fan'],
        'kettle': ['ấm siêu tốc', 'am sieu toc', 'ấm đun'],
        'iron': ['bàn ủi', 'ban ui', 'iron']
    }

    for category, keywords in categories.items():
        if any(kw in keyword_lower for kw in keywords):
            return category
        if any(kw in text_lower for kw in keywords):
            return category

    return 'general'


def transform_post(raw_post: Dict[str, Any], keyword: str, session_id: str) -> tuple:
    """
    Transform raw scraped post into database documents

    Args:
        raw_post: Raw post data from scraper
        keyword: Search keyword
        session_id: Crawl session ID

    Returns:
        Tuple of (post_doc, metrics_doc)
    """
    # Parse timestamp
    created_at = None
    if raw_post.get('publish_time'):
        try:
            created_at = datetime.fromtimestamp(raw_post['publish_time'], tz=timezone.utc)
        except:
            pass

    # Extract media URLs
    media_urls = []
    for att in raw_post.get('attachments', []):
        url = att.get('url') or att.get('thumbnail')
        if url:
            media_urls.append(url)

    # Create post ID with platform prefix
    native_id = raw_post.get('id')
    platform = 'facebook'
    post_id = f"{platform}_{native_id}"

    # Author info
    author_id = raw_post.get('author_id')
    author_name = raw_post.get('owner', 'Unknown')

    if not author_id:
        author_id = f"{platform}_user_{hash(author_name) % 1000000000}"

    # Post document
    post_doc = {
        'post_id': post_id,
        'author_name': author_name,
        'author_id': author_id,
        'content': raw_post.get('text', ''),
        'media_urls': media_urls,
        'created_at': created_at,
        'matched_keywords': [keyword] if keyword else [],
        'category': classify_category(raw_post.get('text', ''), keyword),
        'platform': platform,
        'scraped_at': datetime.now(timezone.utc),
        'crawl_session_id': session_id,
        'platform_data': {
            'native_post_id': native_id,
            'native_author_id': raw_post.get('author_id'),
            'post_type': raw_post.get('type'),
            'extraction_method': raw_post.get('extraction_method')
        }
    }

    # Metrics document
    reactions = raw_post.get('reactions', {})
    metrics_doc = {
        'post_id': post_id,
        'likes': reactions.get('total', 0),
        'comments': raw_post.get('comment_count', 0),
        'shares': raw_post.get('share_count', 0),
        'views': raw_post.get('view_count', 0),
        'reaction_breakdown': {k: v for k, v in reactions.items() if k != 'total'},
        'snapshot_time': datetime.now(timezone.utc),
        'crawl_session_id': session_id
    }

    return post_doc, metrics_doc


def insert_posts(scraped_posts: List[Dict[str, Any]], keyword: str = '') -> Dict[str, int]:
    """
    Insert posts and metrics into MongoDB

    Args:
        scraped_posts: List of scraped posts
        keyword: Search keyword

    Returns:
        Dictionary with insertion statistics
    """
    db = get_database()
    posts_collection = db['posts']
    metrics_collection = db['metrics_snapshot']

    session_id = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M')

    post_operations = []
    metrics_documents = []

    for raw_post in scraped_posts:
        # Skip posts without ID
        if not raw_post.get('id'):
            logger.warning('Skipping post without ID')
            continue

        post_doc, metrics_doc = transform_post(raw_post, keyword, session_id)

        # Upsert post (update if exists, insert if new)
        post_operations.append(
            UpdateOne(
                {'post_id': post_doc['post_id']},
                {
                    '$setOnInsert': {
                        'author_name': post_doc['author_name'],
                        'author_id': post_doc['author_id'],
                        'content': post_doc['content'],
                        'media_urls': post_doc['media_urls'],
                        'created_at': post_doc['created_at'],
                        'category': post_doc['category'],
                        'platform': post_doc['platform'],
                        'platform_data': post_doc['platform_data']
                    },
                    '$set': {
                        'scraped_at': post_doc['scraped_at'],
                        'crawl_session_id': session_id
                    },
                    '$addToSet': {
                        'matched_keywords': keyword
                    }
                },
                upsert=True
            )
        )

        # Always insert new metrics snapshot
        metrics_documents.append(metrics_doc)

    result = {
        'posts_inserted': 0,
        'posts_updated': 0,
        'metrics_inserted': 0,
        'errors': 0
    }

    # Execute post operations
    if post_operations:
        try:
            posts_result = posts_collection.bulk_write(post_operations, ordered=False)
            result['posts_inserted'] = posts_result.upserted_count
            result['posts_updated'] = posts_result.modified_count
        except BulkWriteError as e:
            result['errors'] = len(e.details.get('writeErrors', []))
            logger.error(f'Bulk write errors: {result["errors"]}')

    # Insert metrics
    if metrics_documents:
        try:
            metrics_result = metrics_collection.insert_many(metrics_documents, ordered=False)
            result['metrics_inserted'] = len(metrics_result.inserted_ids)
        except Exception as e:
            logger.error(f'Error inserting metrics: {e}')

    return result


def get_trending_posts(category: Optional[str] = None, hours: int = 24, min_engagement: int = 10) -> List[Dict]:
    """
    Get trending posts from database

    Args:
        category: Filter by category (optional)
        hours: Time window in hours
        min_engagement: Minimum engagement threshold

    Returns:
        List of trending posts with metrics
    """
    db = get_database()

    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)

    match_stage = {'created_at': {'$gte': time_threshold}}
    if category:
        match_stage['category'] = category

    pipeline = [
        {'$match': match_stage},
        {
            '$lookup': {
                'from': 'metrics_snapshot',
                'let': {'post_id': '$post_id'},
                'pipeline': [
                    {'$match': {'$expr': {'$eq': ['$post_id', '$post_id']}}},
                    {'$sort': {'snapshot_time': -1}},
                    {'$limit': 1}
                ],
                'as': 'latest_metrics'
            }
        },
        {'$unwind': '$latest_metrics'},
        {
            '$addFields': {
                'total_engagement': {
                    '$add': [
                        '$latest_metrics.likes',
                        '$latest_metrics.comments',
                        '$latest_metrics.shares'
                    ]
                }
            }
        },
        {'$match': {'total_engagement': {'$gte': min_engagement}}},
        {'$sort': {'total_engagement': -1}},
        {'$limit': 20}
    ]

    posts = db['posts']
    return list(posts.aggregate(pipeline))