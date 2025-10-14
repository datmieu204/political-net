# ./src/utils/queue_based_async_logger.py

import logging
import logging.handlers
from queue import Queue
from typing import Optional

def get_async_logger(
    name: str="project_name", 
    log_file: str="logs/project_async.log",
    level: int=logging.INFO,
    fmt: str="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt: str="%Y-%m-%d %H:%M:%S",
    queue: Optional[Queue]=None
) -> logging.Logger:
    """
    Logging with QueueHandler + QueueListener for asynchronous logging.
    """

    log_queue = queue or Queue(-1)

    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    if log_file:
        import os
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    listener = logging.handlers.QueueListener(log_queue, file_handler, console_handler)
    listener.start()

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(logging.handlers.QueueHandler(log_queue))

    return logger

# ------- Test -----------------------
# if __name__ == "__main__":
#     log = get_async_logger()

#     for i in range(10):
#         log.info(f"Log message {i}")

#     print("Logging complete.")

