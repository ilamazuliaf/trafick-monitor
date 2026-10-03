"""
Logging Configuration Module (prd.md Section 39 & 40)
Configures standard Python logging for console stdout and file logging (logs/app.log).
"""
import logging
import os
import sys


def setup_logging(log_level: str = "INFO", log_file: str = "logs/app.log") -> logging.Logger:
    """
    Sets up and returns application root logger with StreamHandler and FileHandler.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    root_logger = logging.getLogger("mikrotik_monitor")
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to prevent duplicate log lines
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Stream Handler (console)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    # File Handler (logs/app.log)
    try:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        sys.stderr.write(f"Failed to setup file logging to {log_file}: {e}\n")

    return root_logger


logger = setup_logging()
