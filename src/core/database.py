"""
MongoDB Database Module - Dual Collection Schema
Collection 1: posts (bài viết gốc, không trùng lặp)
Collection 2: metrics_snapshot (metrics theo thời gian)
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError, OperationFailure
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
MONGO_DB = os.getenv('MONGO_DB', 'facebook_scraper')

client = None


def get_mongo_client():
    """Get or create MongoDB client"""
    global client
    if client is None:
        client = MongoClient(MONGO_URI)
    return client


def get_database():
    """Get database instance"""
    return get_mongo_client()[MONGO_DB]


def clean_null_post_ids():
    """Remove documents with null post_id before creating unique index"""
    db = get_database()
    posts = db['posts']

    # Delete documents with null or missing post_id
    result = posts.delete_many({
        '$or': [
            {'post_id': None},
            {'post_id': {'$exists': False}}
        ]
    })

    print(f"[✓] Cleaned {result.deleted_count} documents with null post_id")
    return result.deleted_count


def create_indexes():
    """Create indexes for optimal query performance"""
    db = get_database()
    posts = db['posts']

    # First, clean any null post_ids
    print("[*] Checking for null post_ids...")
    clean_null_post_ids()

    # Drop existing post_id index if it exists (to recreate it properly)
    try:
        posts.drop_index('post_id_1')
        print("[✓] Dropped existing post_id index")
    except OperationFailure:
        pass  # Index doesn't exist, that's fine

    # Posts collection indexes
    try:
        posts.create_index('post_id', unique=True)
        print("[✓] Created unique index on post_id")
    except Exception as e:
        print(f"[!] Error creating post_id index: {e}")
        print("[!] Attempting to rebuild index...")
        # If still failing, there might be duplicates
        duplicates = list(posts.aggregate([
            {'$group': {'_id': '$post_id', 'count': {'$sum': 1}}},
            {'$match': {'count': {'$gt': 1}}}
        ]))
        if duplicates:
            print(f"[!] Found {len(duplicates)} duplicate post_ids:")
            for dup in duplicates[:5]:  # Show first 5
                print(f"    - post_id: {dup['_id']} (count: {dup['count']})")
            print("[!] Please clean duplicates manually or run clean_duplicate_posts()")
            return
        else:
            raise

    posts.create_index('author_id')
    posts.create_index('created_at')
    posts.create_index([('matched_keywords', 1)])
    posts.create_index([('category', 1)])
    posts.create_index([('platform', 1)])
    posts.create_index([('scraped_at', -1)])

    # Metrics snapshot indexes
    metrics = db['metrics_snapshot']
    metrics.create_index([('post_id', 1), ('snapshot_time', -1)])
    metrics.create_index('snapshot_time')
    metrics.create_index('crawl_session_id')

    print("Created all database indexes")


def clean_duplicate_posts():
    """Remove duplicate posts, keeping only the most recent one"""
    db = get_database()
    posts = db['posts']

    print("[*] Finding duplicate post_ids...")

    # Find all duplicate post_ids
    duplicates = list(posts.aggregate([
        {'$group': {
            '_id': '$post_id',
            'count': {'$sum': 1},
            'ids': {'$push': '$_id'}
        }},
        {'$match': {'count': {'$gt': 1}}}
    ]))

    if not duplicates:
        print("[✓] No duplicates found")
        return 0

    print(f"[!] Found {len(duplicates)} duplicate post_ids")

    # For each duplicate, keep the most recent one, delete others
    deleted_count = 0
    for dup in duplicates:
        post_id = dup['_id']
        doc_ids = dup['ids']

        # Get all documents with this post_id
        docs = list(posts.find({'post_id': post_id}).sort('scraped_at', -1))

        # Keep the first (most recent), delete the rest
        ids_to_delete = [doc['_id'] for doc in docs[1:]]

        if ids_to_delete:
            result = posts.delete_many({'_id': {'$in': ids_to_delete}})
            deleted_count += result.deleted_count
            print(f"  - Cleaned {result.deleted_count} duplicates for post_id: {post_id}")

    print(f"[✓] Deleted {deleted_count} duplicate documents")
    return deleted_count


def transform_scraped_post(raw_post: Dict[str, Any], keyword: str,
                           crawl_session_id: str) -> tuple:
    """
    Transform raw scraped post into two documents with proper IDs
    """

    # Convert Unix timestamp to datetime
    created_at = None
    if raw_post.get('publish_time'):
        try:
            created_at = datetime.fromtimestamp(raw_post['publish_time'], tz=timezone.utc)
        except:
            pass

    # Extract media URLs from attachments
    media_urls = []
    for att in raw_post.get('attachments', []):
        url = att.get('url') or att.get('thumbnail')
        if url:
            media_urls.append(url)

    # ============================================
    # === PROPER ID HANDLING ===
    # ============================================

    # Native post ID
    native_id = raw_post.get('id')

    # Add platform prefix to avoid cross-platform conflicts
    platform = 'facebook'
    post_id = f"{platform}_{native_id}"  # ✅ fb_123456789

    # Author ID (đã được extract từ scraper)
    author_id = raw_post.get('author_id')
    author_name = raw_post.get('owner', 'Unknown')

    # Validation: Ensure we have author_id
    if not author_id:
        print(f"[⚠️  WARNING] Post {native_id} missing author_id, using fallback")
        author_id = f"{platform}_user_{hash(author_name) % 1000000000}"

    # ============================================

    # === POST DOCUMENT (Collection 1: posts) ===
    post_doc = {
        'post_id': post_id,  # ✅ With platform prefix
        'author_name': author_name,
        'author_id': author_id,  # ✅ Real ID from GraphQL
        'content': raw_post.get('text', ''),
        'media_urls': media_urls,
        'created_at': created_at,

        # Search metadata
        'matched_keywords': [keyword] if keyword else [],
        'category': classify_post_category(raw_post.get('text', ''), keyword),
        'platform': platform,

        # Scraping metadata
        'scraped_at': datetime.now(timezone.utc),
        'crawl_session_id': crawl_session_id,

        # Platform-specific data
        'platform_data': {
            'native_post_id': native_id,  # ID gốc không có prefix
            'native_author_id': raw_post.get('author_id'),  # ID gốc của author
            'post_type': raw_post.get('type'),
            'extraction_method': raw_post.get('extraction_method')
        }
    }

    # === METRICS DOCUMENT (Collection 2: metrics_snapshot) ===
    reactions = raw_post.get('reactions', {})
    metrics_doc = {
        'post_id': post_id,  # ✅ Match with posts collection
        'likes': reactions.get('total', 0),
        'comments': raw_post.get('comment_count', 0),
        'shares': raw_post.get('share_count', 0),
        'views': raw_post.get('view_count', 0),

        # Reaction breakdown (if available)
        'reaction_breakdown': {k: v for k, v in reactions.items() if k != 'total'},

        'snapshot_time': datetime.now(timezone.utc),
        'crawl_session_id': crawl_session_id
    }

    return post_doc, metrics_doc


def classify_post_category(text: str, keyword: str) -> str:
    """
    Classify post into product category based on content

    Args:
        text: Post content
        keyword: Matched keyword

    Returns:
        Category string
    """
    text_lower = text.lower()
    keyword_lower = keyword.lower()

    # Define category mappings
    categories = {
        # 1. Tủ lạnh
        'refrigerator': {
            'name': 'Tủ lạnh',
            'priority': 10,
            'keywords': [
                'tủ lạnh', 'tu lanh', 'tủ đông', 'tu dong', 'tủ mát',
                'refrigerator', 'fridge', 'inverter tủ lạnh',
                '2 cửa', '1 cửa', 'side by side', 'ngăn đá',
                'ngăn đông', 'ngăn mát', 'cửa tủ lạnh'
            ],
            'negative_keywords': ['tủ lạnh mini xe hơi']
        },
        # 2. Nồi cơm điện
        'rice_cooker': {
            'name': 'Nồi cơm điện',
            'priority': 9,
            'keywords': [
                'nồi cơm điện', 'noi com dien', 'rice cooker',
                'nồi cơm', 'noi com', 'cơm điện', 'com dien',
                'nồi điện tử', 'nấu cơm', 'nau com',
                'lòng nồi', 'long noi', 'ruột nồi'
            ],
            'negative_keywords': ['nồi chiên', 'air fryer', 'nồi áp suất']
        },

        # 3. Máy giặt
        'washing_machine': {
            'name': 'Máy giặt',
            'priority': 9,
            'keywords': [
                'máy giặt', 'may giat', 'washing machine',
                'máy giặt cửa', 'máy giặt sấy', 'máy giặt lồng',
                'inverter máy giặt', 'cửa trước', 'cửa trên', 'cửa ngang',
                'lồng giặt', 'long giat', 'giặt sấy', 'kg máy giặt'
            ],
            'negative_keywords': []
        },

        # 4. Tivi
        'tv': {
            'name': 'Tivi',
            'priority': 9,
            'keywords': [
                'tivi', 'tv', 'ti vi', 'television',
                'smart tv', 'android tv', 'google tv',
                '4k tv', 'oled tv', 'qled tv', 'led tv',
                'inch tivi', 'màn hình tivi', '32 inch', '43 inch',
                '55 inch', '65 inch', '75 inch'
            ],
            'negative_keywords': ['màn hình máy tính', 'monitor', 'pc']
        },

        # 5. Lò nướng
        'oven': {
            'name': 'Lò nướng / Nồi chiên không dầu',
            'priority': 8,
            'keywords': [
                'lò nướng', 'lo nuong', 'oven', 'lò nướng điện',
                'lò nướng bánh', 'air fryer', 'nồi chiên không dầu',
                'nồi chiên', 'noi chien', 'chiên không dầu',
                'lò nướng thủy tinh', 'nướng bánh', 'chiên giòn'
            ],
            'negative_keywords': ['nồi cơm', 'nồi áp suất', 'lò vi sóng']
        },

        # 6. Bếp
        'stove': {
            'name': 'Bếp',
            'priority': 7,
            'keywords': [
                'bếp ga', 'bep ga', 'bếp từ', 'bep tu',
                'bếp điện', 'bếp hồng ngoại', 'bếp điện từ',
                'bếp đôi', 'bep doi', 'bếp đơn', 'cooktop',
                'bếp induction', 'mặt bếp', 'mat bep',
                'đầu đốt', 'dau dot'
            ],
            'negative_keywords': []
        },

        # 7. Máy hút bụi
        'vacuum': {
            'name': 'Máy hút bụi',
            'priority': 7,
            'keywords': [
                'máy hút bụi', 'may hut bui', 'vacuum', 'vacuum cleaner',
                'máy hút cầm tay', 'máy hút bụi robot', 'robot vacuum',
                'hút bụi', 'hut bui', 'hút khô', 'hút ướt'
            ],
            'negative_keywords': []
        },

        # 8. Quạt
        'fan': {
            'name': 'Quạt',
            'priority': 6,
            'keywords': [
                'quạt', 'quat', 'fan', 'quạt điện', 'quat dien',
                'quạt đứng', 'quat dung', 'quạt bàn', 'quat ban',
                'quạt trần', 'quat tran', 'quạt sạc', 'quạt mini',
                'quạt hơi nước', 'quạt không cánh',
                'cánh quạt', 'canh quat'
            ],
            'negative_keywords': []
        },

        # 9. Ấm siêu tốc
        'kettle': {
            'name': 'Ấm siêu tốc / Bình đun nước',
            'priority': 6,
            'keywords': [
                'ấm siêu tốc', 'am sieu toc', 'ấm đun', 'am dun',
                'ấm đun nước', 'bình đun siêu tốc', 'binh dun sieu toc',
                'electric kettle', 'ấm điện', 'am dien',
                'đun nước', 'dun nuoc', 'siêu tốc'
            ],
            'negative_keywords': ['bình nóng lạnh']
        },

        # 10. Bàn là
        'iron': {
            'name': 'Bàn ủi / Bàn là',
            'priority': 5,
            'keywords': [
                'bàn ủi', 'ban ui', 'iron', 'bàn là', 'ban la',
                'bàn ủi hơi', 'ban ui hoi', 'máy ủi', 'may ui',
                'máy là', 'ủi quần áo', 'ui quan ao',
                'mặt ủi', 'mat ui'
            ],
            'negative_keywords': []
        }
    }

    # Check keyword and text for category match
    for category, keywords in categories.items():
        if any(kw in keyword_lower for kw in keywords):
            return category
        if any(kw in text_lower for kw in keywords):
            return category

    return 'general'


def insert_posts_with_metrics(scraped_posts: List[Dict[str, Any]],
                               keyword: str = '') -> Dict[str, int]:
    """
    Insert posts and their metrics into MongoDB
    """
    db = get_database()
    posts_collection = db['posts']
    metrics_collection = db['metrics_snapshot']

    # Generate crawl session ID (timestamp-based)
    crawl_session_id = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M')

    # Prepare bulk operations
    post_operations = []
    metrics_documents = []

    for raw_post in scraped_posts:
        # Skip if no post_id (CRITICAL: avoid null post_ids)
        if not raw_post.get('id'):
            print(f"[!] Skipping post without id: {raw_post.get('owner', 'Unknown')[:30]}")
            continue

        # Transform into two documents
        post_doc, metrics_doc = transform_scraped_post(
            raw_post, keyword, crawl_session_id
        )

        # Posts: UPSERT (update if exists, insert if new)
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
                        'platform_data': post_doc['platform_data']  # ✅ Sửa từ 'raw_data' thành 'platform_data'
                    },
                    '$set': {
                        'scraped_at': post_doc['scraped_at'],
                        'crawl_session_id': crawl_session_id
                    },
                    '$addToSet': {
                        'matched_keywords': keyword  # Add keyword if not already present
                    }
                },
                upsert=True
            )
        )

        # Metrics: Always INSERT new snapshot
        metrics_documents.append(metrics_doc)

    # Execute bulk operations
    result = {
        'posts_inserted': 0,
        'posts_updated': 0,
        'metrics_inserted': 0,
        'errors': 0
    }

    # Insert/update posts
    if post_operations:
        try:
            posts_result = posts_collection.bulk_write(post_operations, ordered=False)
            result['posts_inserted'] = posts_result.upserted_count
            result['posts_updated'] = posts_result.modified_count
        except BulkWriteError as e:
            result['errors'] = len(e.details.get('writeErrors', []))
            print(f"[!] Bulk write errors: {result['errors']}")

    # Insert metrics snapshots
    if metrics_documents:
        try:
            metrics_result = metrics_collection.insert_many(metrics_documents, ordered=False)
            result['metrics_inserted'] = len(metrics_result.inserted_ids)
        except Exception as e:
            print(f"[!] Error inserting metrics: {e}")

    return result
def get_post_metrics_history(post_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get metrics history for a specific post

    Args:
        post_id: Post ID
        limit: Number of snapshots to return (most recent first)

    Returns:
        List of metrics snapshots
    """
    db = get_database()
    metrics = db['metrics_snapshot']

    cursor = metrics.find(
        {'post_id': post_id}
    ).sort('snapshot_time', -1).limit(limit)

    return list(cursor)


def get_trending_posts(category: Optional[str] = None,
                       hours: int = 24,
                       min_engagement: int = 10) -> List[Dict[str, Any]]:
    """
    Get trending posts based on recent engagement

    Args:
        category: Filter by category (optional)
        hours: Look at posts from last N hours
        min_engagement: Minimum total engagement (likes + comments + shares)

    Returns:
        List of posts with their latest metrics
    """
    db = get_database()

    # Calculate time threshold
    from datetime import timedelta
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Build aggregation pipeline
    match_stage = {
        'created_at': {'$gte': time_threshold}
    }
    if category:
        match_stage['category'] = category

    pipeline = [
        {'$match': match_stage},
        {
            '$lookup': {
                'from': 'metrics_snapshot',
                'let': {'post_id': '$post_id'},
                'pipeline': [
                    {'$match': {'$expr': {'$eq': ['$post_id', '$$post_id']}}},
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


# ============================================
# Usage Example
# ============================================

if __name__ == '__main__':
    # Create indexes (run once)
    # This will automatically clean null post_ids and duplicates
    create_indexes()

    # Example: Insert scraped posts
    example_posts = [
        {
            'id': 'fb_123456',
            'owner': 'ABC Store',
            'text': 'Giới thiệu nồi chiên không dầu mới nhất 2025!',
            'publish_time': 1759932149,
            'comment_count': 120,
            'share_count': 40,
            'view_count': 0,
            'reactions': {'total': 350, 'Like': 300, 'Love': 50},
            'attachments': [
                {'url': 'https://example.com/image1.jpg'}
            ],
            'type': 'Story',
            'extraction_method': 'graphql'
        }
    ]

    result = insert_posts_with_metrics(example_posts, keyword='nồi chiên')
    print(f"\nResults: {result}")

    # Example: Get metrics history
    history = get_post_metrics_history('fb_123456', limit=5)
    print(f"\nMetrics history: {len(history)} snapshots")

    # Example: Get trending posts
    trending = get_trending_posts(category='air_fryer', hours=24)
    print(f"\nTrending posts: {len(trending)}")