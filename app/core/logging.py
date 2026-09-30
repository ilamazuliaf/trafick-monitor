"""
Logging Configuration Module (prd.md Section 39 & 40)
Configures standard Python logging for the application without leaking sensitive information.
"""
import logging
import sys

def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Sets up and returns application root logger.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger("mikrotik_monitor")
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers to prevent duplicate log lines
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    root_logger.addHandler(handler)
    return root_logger

logger = setup_logging()
