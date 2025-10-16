"""
Database Module - MongoDB Connection Manager with Multi-Database Support
Supports connecting to multiple databases simultaneously for different platforms
"""
from _typeshed import _T_co

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    MongoDB Connection Manager with Multi-Database Support
    Manages connections to multiple databases (one per platform)
    Uses Singleton Pattern to ensure single client connection
    """

    _instance: Optional['DatabaseManager'] = None
    _client: Optional[MongoClient] = None
    _databases: Dict[str, any] = {}

    def __new__(cls, mongo_uri: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._mongo_uri = mongo_uri
            cls._instance._databases = {}
        return cls._instance

    def connect(self):
        """Establish MongoDB connection to the cluster"""
        if self._client is None:
            try:
                logger.info(f"Connecting to MongoDB cluster...")

                self._client = MongoClient(
                    self._mongo_uri,
                    serverSelectionTimeoutMS=10000,
                    connectTimeoutMS=10000
                )

                # Test connection
                self._client.admin.command('ping')
                logger.info("✓ MongoDB connection established successfully")

            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.error(f"✗ Failed to connect to MongoDB: {e}")
                raise
            except Exception as e:
                logger.error(f"✗ Unexpected error connecting to MongoDB: {e}")
                raise

        return self._client

    def get_database(self, db_name: str = None):
        """
        Get database instance by name

        Args:
            db_name: Database name. If None, returns the default primary database

        Returns:
            Database instance
        """
        if self._client is None:
            self.connect()

        # Use default database if no name specified
        if db_name is None:
            if not self._databases:
                raise RuntimeError("No default database set. Specify db_name parameter.")
            # Return first database as default
            return next(iter(self._databases.values()))

        # Cache database instances
        if db_name not in self._databases:
            self._databases[db_name] = self._client[db_name]
            logger.info(f"Connected to database: {db_name}")

        return self._databases[db_name]

    def get_collection(self, collection_name: str, db_name: str = None):
        """
        Get collection from specified database

        Args:
            collection_name: Collection name
            db_name: Database name. If None, uses default database

        Returns:
            Collection instance
        """
        db = self.get_database(db_name)
        return db[collection_name]

    def get_facebook_db(self):
        """Get Facebook database instance"""
        return self.get_database('facebook_db')

    def get_youtube_db(self):
        """Get YouTube database instance"""
        return self.get_database('youtube_db')

    def get_shopee_db(self):
        """Get Shopee database instance"""
        return self.get_database('shopee_db')

    def get_tiktok_db(self):
        """Get TikTok database instance"""
        return self.get_database('tiktok_db')

    def close(self):
        """Close MongoDB connection and clear all cached databases"""
        if self._client:
            self._client.close()
            self._client = None
            self._databases = {}
            logger.info("MongoDB connection closed")

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None
_current_db_name: Optional[str] = None


def init_database(mongo_uri: str, db_name: str = None):
    """
    Initialize global database manager

    Args:
        mongo_uri: MongoDB connection URI
        db_name: Default database name (optional, for backward compatibility)

    Returns:
        DatabaseManager instance
    """
    global _db_manager, _current_db_name

    _db_manager = DatabaseManager(mongo_uri)
    _db_manager.connect()

    # Set default database if provided
    if db_name:
        _current_db_name = db_name
        _db_manager.get_database(db_name)

    return _db_manager


def get_database(db_name: str = None) -> _T_co | Any:
    """
    Get database instance

    Args:
        db_name: Database name. If None, uses the default database set during init

    Returns:
        Database instance
    """
    if _db_manager is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    # Use default database name if not specified
    if db_name is None and _current_db_name is not None:
        db_name = _current_db_name

    return _db_manager.get_database(db_name)


def get_collection(name: str, db_name: str = None):
    """
    Get collection from specified database

    Args:
        name: Collection name
        db_name: Database name. If None, uses default database

    Returns:
        Collection instance
    """
    if _db_manager is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    # Use default database name if not specified
    if db_name is None and _current_db_name is not None:
        db_name = _current_db_name

    return _db_manager.get_collection(name, db_name)


def get_facebook_database():
    """Get Facebook database instance"""
    if _db_manager is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db_manager.get_facebook_db()


def get_youtube_database():
    """Get YouTube database instance"""
    if _db_manager is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db_manager.get_youtube_db()


def get_shopee_database():
    """Get Shopee database instance"""
    if _db_manager is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db_manager.get_shopee_db()


def get_tiktok_database():
    """Get TikTok database instance"""
    if _db_manager is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db_manager.get_tiktok_db()


def close_database():
    """Close global database connection"""
    global _db_manager, _current_db_name
    if _db_manager:
        _db_manager.close()
        _db_manager = None
        _current_db_name = None