# /common/logging_setup.py
import logging
import sys
from . import config

def setup_logging(log_file_name: str):
    """Configures a standardized logger."""
    # This handler writes to the log file
    file_handler = logging.FileHandler(log_file_name, mode='w', encoding='utf-8')
    
    # This prevents logs from interfering with the tqdm progress bars
    stream_handler = logging.StreamHandler(sys.stderr)
    
    logging.basicConfig(
        level=config.LOG_LEVEL,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        handlers=[file_handler, stream_handler]
    )
    
    return logging.getLogger(__name__)