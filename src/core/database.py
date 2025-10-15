"""
Database Module - MongoDB Connection Manager
"""
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    MongoDB Connection Manager (Singleton Pattern)
    Ensures only one connection throughout the application
    """

    _instance: Optional['DatabaseManager'] = None
    _client: Optional[MongoClient] = None
    _db = None

    def __new__(cls, mongo_uri: str = None, db_name: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._mongo_uri = mongo_uri
            cls._instance._db_name = db_name
        return cls._instance

    def connect(self):
        """Establish MongoDB connection"""
        if self._client is None:
            try:
                logger.info(f"Connecting to MongoDB database: {self._db_name}")

                self._client = MongoClient(
                    self._mongo_uri,
                    serverSelectionTimeoutMS=10000,
                    connectTimeoutMS=10000
                )

                # Test connection
                self._client.admin.command('ping')
                self._db = self._client[self._db_name]

                logger.info("✓ MongoDB connection established successfully")

            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.error(f"✗ Failed to connect to MongoDB: {e}")
                raise
            except Exception as e:
                logger.error(f"✗ Unexpected error connecting to MongoDB: {e}")
                raise

        return self._client

    def get_database(self):
        """Get database instance"""
        if self._db is None:
            self.connect()
        return self._db

    def get_collection(self, name: str):
        """Get collection by name"""
        db = self.get_database()
        return db[name]

    def close(self):
        """Close MongoDB connection"""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
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


def init_database(mongo_uri: str, db_name: str):
    """
    Initialize global database manager

    Args:
        mongo_uri: MongoDB connection URI
        db_name: Database name
    """
    global _db_manager
    _db_manager = DatabaseManager(mongo_uri, db_name)
    return _db_manager


def get_database():
    """Get global database instance"""
    if _db_manager is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db_manager.get_database()


def get_collection(name: str):
    """Get collection from global database"""
    if _db_manager is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db_manager.get_collection(name)


def close_database():
    """Close global database connection"""
    if _db_manager:
        _db_manager.close()