"""
Main Entry Point - Social Media Crawler with Multi-Database Support
Usage: python -m src.main <platform>
Available platforms: facebook, youtube, shopee, tiktok, all
"""
import sys
from pathlib import Path

# Import configs
from src.configs.settings import (
    MONGO_URI,
    FACEBOOK_DB, YOUTUBE_DB, SHOPEE_DB, TIKTOK_DB,
    FACEBOOK_COOKIE, FACEBOOK_KEYWORDS, MAX_SCROLLS,
    YOUTUBE_API_KEYS, YOUTUBE_KEYWORDS, YOUTUBE_MAX_VIDEOS_PER_KEYWORD,
    SHOPEE_CATEGORIES, SHOPEE_HEADLESS, SHOPEE_VARIANTS_PER_CATEGORY,
    SHOPEE_MAX_PAGES_PER_VARIANT, SHOPEE_TARGET_PER_CATEGORY,
    TIKTOK_KEYWORDS, TIKTOK_HEADLESS, TIKTOK_TARGET_PER_CATEGORY,
    DATA_DIR, LOG_DIR, LOG_LEVEL, validate_config
)

# Import core modules
from src.core.utils.logger import setup_logger
from src.core.database import init_database, close_database

# Setup logger
logger = setup_logger('main', log_dir=LOG_DIR, level=LOG_LEVEL)


def run_facebook():
    """Run Facebook crawler (async)"""
    import asyncio
    from src.crawlers.facebook.scraper import run_facebook_scraper

    logger.info('Starting Facebook crawler...')
    logger.info(f'Database: {FACEBOOK_DB}')

    asyncio.run(run_facebook_scraper(
        cookie=FACEBOOK_COOKIE,
        keywords=FACEBOOK_KEYWORDS,
        data_dir=DATA_DIR,
        max_scrolls=MAX_SCROLLS
    ))


def run_youtube():
    """Run YouTube crawler (async)"""
    import asyncio
    from src.crawlers.youtube.scraper import run_youtube_scraper

    logger.info('Starting YouTube crawler...')
    logger.info(f'Database: {YOUTUBE_DB}')

    asyncio.run(run_youtube_scraper(
        api_keys=YOUTUBE_API_KEYS,
        keywords=YOUTUBE_KEYWORDS,
        max_videos_per_keyword=YOUTUBE_MAX_VIDEOS_PER_KEYWORD
    ))


def run_shopee():
    """Run Shopee crawler (synchronous - uses sync_playwright)"""
    from src.crawlers.shopee.scraper import run_shopee_scraper

    logger.info('Starting Shopee crawler...')
    logger.info(f'Database: {SHOPEE_DB}')

    run_shopee_scraper(
        categories=SHOPEE_CATEGORIES,
        headless=SHOPEE_HEADLESS,
        variants_per_category=SHOPEE_VARIANTS_PER_CATEGORY,
        max_pages_per_variant=SHOPEE_MAX_PAGES_PER_VARIANT,
        target_per_category=SHOPEE_TARGET_PER_CATEGORY
    )


def run_tiktok():
    """Run TikTok crawler (synchronous - uses sync_playwright)"""
    from src.crawlers.tiktok.scraper import run_tiktok_scraper

    logger.info('Starting TikTok crawler...')
    logger.info(f'Database: {TIKTOK_DB}')

    run_tiktok_scraper(
        keywords=TIKTOK_KEYWORDS,
        headless=TIKTOK_HEADLESS,
        target_per_category=TIKTOK_TARGET_PER_CATEGORY
    )


def run_all():
    """Run all crawlers sequentially"""
    logger.info('Running all crawlers...')

    platforms = [
        ('facebook', run_facebook),
        ('youtube', run_youtube),
        ('shopee', run_shopee),
        ('tiktok', run_tiktok),
    ]

    results = {}

    for platform_name, platform_func in platforms:
        try:
            logger.info(f'\n{"="*70}')
            logger.info(f'Starting {platform_name.upper()} crawler')
            logger.info(f'{"="*70}')

            platform_func()
            results[platform_name] = 'SUCCESS'

        except Exception as e:
            logger.error(f'{platform_name.capitalize()} crawler failed: {e}')
            results[platform_name] = f'FAILED: {str(e)[:100]}'

    # Print summary
    logger.info('\n' + '='*70)
    logger.info('ALL CRAWLERS COMPLETED')
    logger.info('='*70)

    for platform, status in results.items():
        status_emoji = '✓' if status == 'SUCCESS' else '✗'
        logger.info(f'{status_emoji} {platform.capitalize()}: {status}')


def main():
    """Main entry point"""

    if len(sys.argv) < 2:
        logger.error('Usage: python -m src.main <platform>')
        logger.info('Available platforms: facebook, youtube, shopee, tiktok, all')
        sys.exit(1)

    platform = sys.argv[1].lower()

    # Validate configuration for the selected platform
    try:
        if platform == 'all':
            validate_config()
        else:
            validate_config(platforms=[platform])
    except ValueError as e:
        logger.error(f'Configuration error: {e}')
        sys.exit(1)

    # Initialize database connection
    try:
        init_database(MONGO_URI)
        logger.info('✓ MongoDB cluster connection established')
        logger.info(f'  Available databases:')
        logger.info(f'    - Facebook: {FACEBOOK_DB}')
        logger.info(f'    - YouTube: {YOUTUBE_DB}')
        logger.info(f'    - Shopee: {SHOPEE_DB}')
        logger.info(f'    - TikTok: {TIKTOK_DB}')
    except Exception as e:
        logger.error(f'Failed to initialize database: {e}')
        sys.exit(1)

    # Run crawler
    try:
        logger.info(f'Starting crawler for platform: {platform}')
        logger.info(f'MongoDB URI: {MONGO_URI[:50]}...')

        if platform == 'facebook':
            run_facebook()

        elif platform == 'youtube':
            run_youtube()

        elif platform == 'shopee':
            run_shopee()

        elif platform == 'tiktok':
            run_tiktok()

        elif platform == 'all':
            run_all()

        else:
            logger.error(f'Unknown platform: {platform}')
            logger.info('Available platforms: facebook, youtube, shopee, tiktok, all')
            sys.exit(1)

        logger.info('Crawler completed successfully')

    except KeyboardInterrupt:
        logger.warning('Crawler stopped by user (Ctrl+C)')
        sys.exit(0)

    except Exception as e:
        logger.error(f'Crawler failed with error: {e}', exc_info=True)
        sys.exit(1)

    finally:
        # Close database connection
        close_database()


if __name__ == '__main__':
    main()