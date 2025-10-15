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
MONGO_DB = os.getenv('MONGO_DB', 'facebook_scraper')

# ============================================
# Facebook Configuration
# ============================================
FACEBOOK_COOKIE = os.getenv('FACEBOOK_COOKIE', '')
FACEBOOK_KEYWORDS = [
    kw.strip()
    for kw in os.getenv('FACEBOOK_KEYWORDS', 'tủ lạnh,máy giặt').split(',')
]

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
def validate_config():
    """Validate required configuration"""
    errors = []

    if not MONGO_URI:
        errors.append('MONGO_URI is required')

    if not FACEBOOK_COOKIE:
        errors.append('FACEBOOK_COOKIE is required')

    if errors:
        raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

    return True


if __name__ == '__main__':
    # Test configuration
    print("Configuration loaded successfully!")
    print(f"MongoDB: {MONGO_DB}")
    print(f"Keywords: {FACEBOOK_KEYWORDS}")
    print(f"Data dir: {DATA_DIR}")
    print(f"Log dir: {LOG_DIR}")