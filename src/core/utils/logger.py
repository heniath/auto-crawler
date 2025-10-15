"""
Logging Module - Centralized logging configuration
"""
import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(name: str, log_dir: Path = None, level: str = 'INFO'):
    """
    Setup logger with both file and console handlers

    Args:
        name: Logger name (e.g., 'facebook_crawler')
        log_dir: Directory to store log files
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        logging.Logger instance
    """
    # Get or create logger
    logger = logging.getLogger(name)

    # Clear existing handlers to avoid duplicates
    if logger.handlers:
        logger.handlers.clear()

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        fmt='[%(levelname)s] %(message)s'
    )

    # Console handler (simple format)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)

    # File handler (detailed format)
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f'{name}_{datetime.now().strftime("%Y%m%d")}.log'
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str):
    """Get existing logger by name"""
    return logging.getLogger(name)