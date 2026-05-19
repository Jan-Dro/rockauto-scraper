"""
models.py — Pydantic data models for the rockauto-closeout-watcher.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Listing(BaseModel):
    """Represents a single RockAuto closeout listing."""

    title: str
    brand: Optional[str] = None
    price: Optional[str] = None
    url: str
    description: Optional[str] = None
    side: Optional[str] = None  # e.g. "front right", "rear left"
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)
    source: Literal["rss", "html", "debug"] = "html"

    @property
    def dedup_key(self) -> str:
        """Return a deduplication key based on URL or title+price hash."""
        if self.url and self.url != "unknown":
            return self.url
        import hashlib

        raw = f"{self.title}{self.price or ''}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def full_text(self) -> str:
        """Return a single normalized string for matching."""
        parts = [self.title, self.description or "", self.side or ""]
        return " ".join(parts)


class MatchResult(BaseModel):
    """Result of running the matcher against a Listing."""

    listing: Listing
    is_match: bool
    confidence: Literal["confirmed", "possible", "none"] = "none"

    matched_keywords: list[str] = Field(default_factory=list)
    rejected_keywords: list[str] = Field(default_factory=list)

    has_caliper: bool = False
    has_front: bool = False
    has_right: bool = False
    has_sport: bool = False
    has_reject: bool = False

    reasoning: list[str] = Field(default_factory=list)
