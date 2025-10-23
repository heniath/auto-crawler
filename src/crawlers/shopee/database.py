"""
Shopee Database Operations
Handles product storage with master/history pattern
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
import pytz
import logging

from src.core.database import get_database

logger = logging.getLogger(__name__)

TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")


def create_indexes():
    """Create MongoDB indexes for Shopee collections"""
    from src.configs.settings import SHOPEE_DB
    db = get_database(SHOPEE_DB)

    # Collections (matching original script names)
    master = db['Shopee_ProductCategory']
    history = db['Shopee_ProductCategory_History']

    try:
        # Clean null/missing IDs
        result = master.delete_many({
            '$or': [
                {'itemid': None},
                {'itemid': {'$exists': False}}
            ]
        })
        if result.deleted_count > 0:
            logger.info(f'Cleaned {result.deleted_count} documents with null itemid')

        # Master collection indexes
        master.create_index('itemid', unique=True)
        master.create_index('shopid')
        master.create_index('category')
        master.create_index([('price', 1)])
        master.create_index([('sold_total', -1)])
        master.create_index([('rating_star', -1)])
        master.create_index([('first_day_crawling', -1)])
        master.create_index([('last_day_crawling', -1)])

        # History collection indexes
        history.create_index([('itemid', 1), ('crawl_date', -1)])
        history.create_index('crawl_date')
        history.create_index('category')
        history.create_index('shopid')

        logger.info('✓ Shopee database indexes created successfully')

    except Exception as e:
        logger.error(f'Error creating Shopee indexes: {e}')
        raise


def calc_discount_percent(price_before: float, price_after: float) -> str:
    """Calculate discount percentage"""
    try:
        if price_before > 0:
            return f"{round((price_before - price_after) / price_before * 100)}%"
    except:
        pass
    return "0%"


def convert_ctime(ctime: int) -> str:
    """Convert Unix timestamp to date string"""
    try:
        return datetime.fromtimestamp(ctime).strftime("%Y-%m-%d")
    except:
        return ""


def insert_products_batch(category_products: List[Dict[str, Any]], category: str) -> Dict[str, int]:
    """
    Insert products into master and history collections
    Exactly matching original script logic

    Args:
        category_products: List of product data
        category: Product category

    Returns:
        Statistics dictionary
    """
    from src.configs.settings import SHOPEE_DB
    db = get_database(SHOPEE_DB)
    collection_main = db['Shopee_ProductCategory']
    collection_history = db['Shopee_ProductCategory_History']

    now_vn = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

    history_rows = []
    main_docs = {}

    # Process products (matching original logic exactly)
    for item in category_products:
        itemid = item.get("itemid")
        if not itemid:
            continue

        # History document
        doc_history = item.copy()
        doc_history["crawl_date"] = now_vn
        history_rows.append(doc_history)

        # Master document
        if itemid not in main_docs:
            main_docs[itemid] = item.copy()
            main_docs[itemid]["first_day_crawling"] = now_vn
            main_docs[itemid]["last_day_crawling"] = now_vn
        else:
            main_docs[itemid]["last_day_crawling"] = now_vn

    # Insert to MongoDB (matching original logic)
    added_history = 0
    added_main = 0
    updated_main = 0

    if history_rows:
        collection_history.insert_many(history_rows)
        added_history = len(history_rows)

    if main_docs:
        for doc in main_docs.values():
            existing = collection_main.find_one({"itemid": doc["itemid"]})
            if existing:
                collection_main.update_one(
                    {"itemid": doc["itemid"]},
                    {"$set": {"last_day_crawling": doc["last_day_crawling"]}}
                )
                updated_main += 1
            else:
                collection_main.insert_one(doc)
                added_main += 1

    return {
        'products_inserted': added_main,
        'products_updated': updated_main,
        'history_inserted': added_history,
        'errors': 0
    }


def get_trending_products(
        category: Optional[str] = None,
        min_sales: int = 100,
        limit: int = 20
) -> List[Dict]:
    """
    Get trending products from database

    Args:
        category: Filter by category (optional)
        min_sales: Minimum sales count
        limit: Maximum number of results

    Returns:
        List of trending products
    """
    from src.configs.settings import SHOPEE_DB
    db = get_database(SHOPEE_DB)
    master = db['Shopee_ProductCategory']

    match_stage = {'sold_total': {'$gte': min_sales}}
    if category:
        match_stage['category'] = category

    pipeline = [
        {'$match': match_stage},
        {'$sort': {'sold_total': -1}},
        {'$limit': limit},
        {
            '$project': {
                'itemid': 1,
                'name': 1,
                'price': 1,
                'discount': 1,
                'sold_total': 1,
                'rating_star': 1,
                'category': 1
            }
        }
    ]

    return list(master.aggregate(pipeline))