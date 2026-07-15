import logging
import os
import sys
from typing import Optional
from rich.logging import RichHandler


def setup_logger(
    name: str = "cloud-auditor",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """Sets up a structured logger. Uses RichHandler for terminal output."""
    if not log_level:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    level = getattr(logging, log_level, logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate handlers if logger is re-initialized
    if logger.handlers:
        logger.handlers.clear()

    # Create console handler using Rich
    console_handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        show_path=False,
    )
    console_handler.setLevel(level)
    logger.addHandler(console_handler)

    # Optional file handler for persistent logs
    if log_file:
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Global logger instance
logger = setup_logger()
