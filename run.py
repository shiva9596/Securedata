# run.py
import os
import logging
import uvicorn
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
from app.config import LOG_LEVEL

# Configure logging
logging_level = getattr(logging, LOG_LEVEL)
logging.basicConfig(
    level=logging_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

if __name__ == "__main__":
    # Get host and port from environment variables or use defaults
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5000))
    
    # Run the application with Uvicorn
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level=LOG_LEVEL.lower()
    )
