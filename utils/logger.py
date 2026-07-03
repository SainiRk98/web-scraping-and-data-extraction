"""
utils/logger.py
---------------
Centralised logging setup.
Call `get_logger(__name__)` in every module to get a pre-configured logger
that writes to both the console and a rotating log file.
"""

import io
import logging
import sys
from logging.handlers import RotatingFileHandler

from config import LOG_LEVEL, LOG_FILE


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger with the given name.
    Handlers are added only once (idempotent).
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers when the function is called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler – wrap stdout in UTF-8 to avoid cp1252 errors on Windows
    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") \
        if hasattr(sys.stdout, "buffer") else sys.stdout
    ch = logging.StreamHandler(utf8_stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Rotating file handler (5 MB × 3 backups)
    fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger
