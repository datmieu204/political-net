# ./utils/_logger.py

import logging
import os
from typing import Optional

def get_logger(
    name: str = "project_name",
    log_file: Optional[str] = "logs/project.log",
    level: int = logging.INFO,
    fmt: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt: str = "%Y-%m-%d %H:%M:%S",
    reset_handlers: bool = True,
) -> logging.Logger:
    """
    Simple synchronous logger.

    - Logs to console + optional file.
    - No QueueHandler / QueueListener, everything is written directly.
    - By default clears old handlers for this logger to avoid duplicate logs.
    """

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Clear existing handlers to prevent duplicate logs in long-running apps
    if reset_handlers:
        logger.handlers.clear()
        logger.propagate = False  # avoid double logging via root

    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if path provided)
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# ------- Test -----------------------
# if __name__ == "__main__":
#     log = get_logger()
#     for i in range(5):
#         log.info(f"Log message {i}")
#     print("Done.")