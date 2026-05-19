"""
storage.py — JSON-based persistence for seen (already-alerted) listings.

Listings are stored by their dedup key (URL or title+price hash) so we never
send a duplicate Discord notification.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Set

from app.utils import get_logger

logger = get_logger("storage")


class SeenItemsStore:
    """
    A simple set-backed JSON store.

    Thread-safety is NOT a concern here because the watcher runs as a single
    process.  Atomic-ish writes (write-then-rename) are used to avoid
    corrupting the file on crash.
    """

    def __init__(self, filepath: str | Path) -> None:
        self._path = Path(filepath)
        self._seen: Set[str] = set()
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_seen(self, key: str) -> bool:
        """Return True if the key has already been alerted."""
        return key in self._seen

    def mark_seen(self, key: str) -> None:
        """Persist a key so it is never alerted again."""
        self._seen.add(key)
        self._save()
        logger.debug("Marked as seen: %s", key)

    def count(self) -> int:
        return len(self._seen)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            logger.debug("No seen-items file at %s — starting fresh.", self._path)
            return
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                self._seen = set(data)
            else:
                logger.warning("Unexpected format in %s — resetting.", self._path)
                self._seen = set()
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load seen-items: %s", exc)
            self._seen = set()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(sorted(self._seen), fh, indent=2)
            tmp.replace(self._path)
        except OSError as exc:
            logger.error("Failed to save seen-items: %s", exc)
