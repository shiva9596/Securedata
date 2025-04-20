# utils/logger.py
import logging
import os
from app.config import LOG_FILE, LOG_LEVEL

# Ensure log directory exists
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# Configure logging
logging.basicConfig(
    filename=LOG_FILE,
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Create a console handler for immediate feedback during development
console = logging.StreamHandler()
console.setLevel(getattr(logging, LOG_LEVEL))
console.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logging.getLogger('').addHandler(console)

logger = logging.getLogger('legal_assistant')

def log_event(message, level="info"):
    """
    Log an event with the specified level
    
    Args:
        message: The message to log
        level: The log level (info, warning, error, debug)
    """
    level = level.lower()
    
    if level == "info":
        logger.info(message)
    elif level == "warning":
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    elif level == "debug":
        logger.debug(message)
    else:
        logger.info(message)
