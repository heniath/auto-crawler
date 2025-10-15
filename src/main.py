"""
Main Entry Point - Social Media Crawler
Usage: python -m src.main facebook
"""
import sys
import asyncio
from pathlib import Path

# Import configs
from src.configs.settings import (
    MONGO_URI, MONGO_DB, FACEBOOK_COOKIE, FACEBOOK_KEYWORDS,
    MAX_SCROLLS, DATA_DIR, LOG_DIR, LOG_LEVEL, validate_config
)

# Import core modules
from src.core.utils.logger import setup_logger
from src.core.database import init_database, close_database

# Setup logger
logger = setup_logger('main', log_dir=LOG_DIR, level=LOG_LEVEL)


async def run_facebook():
    """Run Facebook crawler"""
    from src.crawlers.facebook.scraper import run_facebook_scraper

    logger.info('Starting Facebook crawler...')
    await run_facebook_scraper(
        cookie=FACEBOOK_COOKIE,
        keywords=FACEBOOK_KEYWORDS,
        data_dir=DATA_DIR,
        max_scrolls=MAX_SCROLLS
    )


async def run_all():
    """Run all crawlers"""
    logger.info('Running all crawlers...')

    # Facebook
    await run_facebook()

    # Add other crawlers here when implemented
    # await run_shopee()
    # await run_tiktok()
    # await run_youtube()


async def main_async(platform: str):
    """Main async function"""

    # Validate configuration
    try:
        validate_config()
    except ValueError as e:
        logger.error(f'Configuration error: {e}')
        sys.exit(1)

    # Initialize database
    try:
        init_database(MONGO_URI, MONGO_DB)
        logger.info('Database initialized successfully')
    except Exception as e:
        logger.error(f'Failed to initialize database: {e}')
        sys.exit(1)

    # Run crawler
    try:
        if platform == 'facebook':
            await run_facebook()

        elif platform == 'shopee':
            logger.warning('Shopee crawler not implemented yet')

        elif platform == 'tiktok':
            logger.warning('TikTok crawler not implemented yet')

        elif platform == 'youtube':
            logger.warning('YouTube crawler not implemented yet')

        elif platform == 'all':
            await run_all()

        else:
            logger.error(f'Unknown platform: {platform}')
            logger.info('Available platforms: facebook, shopee, tiktok, youtube, all')
            sys.exit(1)

    finally:
        # Close database connection
        close_database()


def main():
    """Main entry point"""

    if len(sys.argv) < 2:
        logger.error('Usage: python -m src.main <platform>')
        logger.info('Available platforms: facebook, shopee, tiktok, youtube, all')
        sys.exit(1)

    platform = sys.argv[1].lower()

    logger.info(f'Starting crawler for platform: {platform}')

    try:
        asyncio.run(main_async(platform))
        logger.info('Crawler completed successfully')

    except KeyboardInterrupt:
        logger.warning('Crawler stopped by user (Ctrl+C)')
        sys.exit(0)

    except Exception as e:
        logger.error(f'Crawler failed with error: {e}', exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()