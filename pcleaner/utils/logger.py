"""Centralised logging for PCleaner."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from pcleaner.utils.config import LOG_PATH


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("pcleaner")
    if logger.handlers:
        return logger

    logger.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler (5 MB × 3 backups)
    try:
        fh = RotatingFileHandler(LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        pass

    # Console handler for errors only
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


log = setup_logging()
