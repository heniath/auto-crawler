"""
Configuration Settings - Load from environment variables
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# ============================================
# MongoDB Configuration
# ============================================
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')

# Database names for each platform
FACEBOOK_DB = os.getenv('FACEBOOK_DB', 'facebook_data')
YOUTUBE_DB = os.getenv('YOUTUBE_DB', 'youtube_data')
SHOPEE_DB = os.getenv('SHOPEE_DB', 'shopee_data')
TIKTOK_DB = os.getenv('TIKTOK_DB', 'TikTok_Data')

# Legacy support - default database
MONGO_DB = os.getenv('MONGO_DB', FACEBOOK_DB)

# ============================================
# Facebook Configuration
# ============================================
FACEBOOK_COOKIE = os.getenv('FACEBOOK_COOKIE', '')
FACEBOOK_KEYWORDS = [
    kw.strip()
    for kw in os.getenv('FACEBOOK_KEYWORDS', 'tủ lạnh,máy giặt').split(',')
]

# ============================================
# YouTube Configuration
# ============================================
YOUTUBE_API_KEYS = [
    key.strip()
    for key in os.getenv('YOUTUBE_API_KEYS', '').split(',')
    if key.strip()
]

YOUTUBE_KEYWORDS = [
    kw.strip()
    for kw in os.getenv('YOUTUBE_KEYWORDS',
        'Nồi cơm điện,Tủ lạnh,Bếp,Máy giặt,Quạt,Ấm siêu tốc,Bàn ủi,Máy hút bụi,Tivi,Lò nướng'
    ).split(',')
]

YOUTUBE_MAX_VIDEOS_PER_KEYWORD = int(os.getenv('YOUTUBE_MAX_VIDEOS_PER_KEYWORD', '400'))

# ============================================
# Shopee Configuration
# ============================================
SHOPEE_CATEGORIES = [
    kw.strip()
    for kw in os.getenv('SHOPEE_CATEGORIES',
        'Tủ lạnh,Bếp,Máy giặt,Quạt,Ấm siêu tốc,Nồi cơm điện,Bàn ủi,Máy hút bụi,Tivi,Lò nướng'
    ).split(',')
]

SHOPEE_HEADLESS = os.getenv('SHOPEE_HEADLESS', 'true').lower() == 'true'
SHOPEE_VARIANTS_PER_CATEGORY = int(os.getenv('SHOPEE_VARIANTS_PER_CATEGORY', '10'))
SHOPEE_MAX_PAGES_PER_VARIANT = int(os.getenv('SHOPEE_MAX_PAGES_PER_VARIANT', '2'))
SHOPEE_TARGET_PER_CATEGORY = int(os.getenv('SHOPEE_TARGET_PER_CATEGORY', '500'))

# ============================================
# TikTok Configuration
# ============================================
TIKTOK_KEYWORDS = [
    kw.strip()
    for kw in os.getenv('TIKTOK_KEYWORDS',
        'Tủ lạnh,Bếp,Máy giặt,Quạt,Ấm siêu tốc,Nồi cơm điện,Bàn ủi,Máy hút bụi,Tivi,Lò nướng'
    ).split(',')
]

TIKTOK_HEADLESS = os.getenv('TIKTOK_HEADLESS', 'true').lower() == 'true'
TIKTOK_TARGET_PER_CATEGORY = int(os.getenv('TIKTOK_TARGET_PER_CATEGORY', '100'))

# ============================================
# Crawler Settings
# ============================================
MAX_SCROLLS = int(os.getenv('MAX_SCROLLS', '5'))
SCROLL_DELAY = int(os.getenv('SCROLL_DELAY', '2500'))

# ============================================
# Directories
# ============================================
DATA_DIR = PROJECT_ROOT / os.getenv('DATA_DIR', 'data')
LOG_DIR = PROJECT_ROOT / os.getenv('LOG_DIR', 'logs')

# Create directories if not exist
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# ============================================
# Logging
# ============================================
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()


# ============================================
# Validation
# ============================================
def validate_config(platforms: list = None):
    """
    Validate required configuration for specified platforms

    Args:
        platforms: List of platforms to validate (e.g., ['facebook', 'youtube'])
                  If None, validates all platforms
    """
    errors = []

    if not MONGO_URI:
        errors.append('MONGO_URI is required')

    # Validate Facebook config if needed
    if platforms is None or 'facebook' in platforms:
        if not FACEBOOK_COOKIE:
            errors.append('FACEBOOK_COOKIE is required for Facebook crawler')

    # Validate YouTube config if needed
    if platforms is None or 'youtube' in platforms:
        if not YOUTUBE_API_KEYS:
            errors.append('YOUTUBE_API_KEYS is required for YouTube crawler')
        elif len(YOUTUBE_API_KEYS) < 1:
            errors.append('At least one YouTube API key is required')

    # TikTok doesn't require special validation (no API keys needed)
    # Shopee doesn't require special validation (no API keys needed)

    if errors:
        raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

    return True


if __name__ == '__main__':
    # Test configuration
    print("Configuration loaded successfully!")
    print(f"\nMongoDB URI: {MONGO_URI}")
    print(f"\nDatabases:")
    print(f"  - Facebook: {FACEBOOK_DB}")
    print(f"  - YouTube: {YOUTUBE_DB}")
    print(f"  - Shopee: {SHOPEE_DB}")
    print(f"  - TikTok: {TIKTOK_DB}")
    print(f"\nFacebook Keywords: {FACEBOOK_KEYWORDS}")
    print(f"YouTube API Keys: {len(YOUTUBE_API_KEYS)} keys")
    print(f"YouTube Keywords: {YOUTUBE_KEYWORDS}")
    print(f"Shopee Categories: {SHOPEE_CATEGORIES}")
    print(f"Shopee Headless: {SHOPEE_HEADLESS}")
    print(f"Shopee Target per Category: {SHOPEE_TARGET_PER_CATEGORY}")
    print(f"TikTok Keywords: {TIKTOK_KEYWORDS}")
    print(f"TikTok Headless: {TIKTOK_HEADLESS}")
    print(f"TikTok Target per Category: {TIKTOK_TARGET_PER_CATEGORY}")
    print(f"\nData dir: {DATA_DIR}")
    print(f"Log dir: {LOG_DIR}")