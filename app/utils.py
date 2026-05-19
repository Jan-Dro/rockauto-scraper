"""
utils.py — Shared utility functions.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

_LOG_DIR = Path(__file__).parent.parent / "data" / "logs"


def get_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """
    Return a logger that writes to both stdout and a rotating log file.

    All log files land in data/logs/<name>.log.
    """
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        # Already configured — avoid adding duplicate handlers
        return logger

    logger.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # stdout handler
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # file handler
    log_file = _LOG_DIR / f"{name}.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """
    Lowercase, collapse whitespace, and strip a string.

    This is the canonical normalization used everywhere in the matcher and
    parser so comparisons are consistent.
    """
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def slugify(text: str) -> str:
    """Return a URL-safe slug from arbitrary text."""
    text = normalize_text(text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")
