"""
matcher.py — Keyword-based matching engine.

A listing is a confirmed match when it:
  1. Contains a required keyword (e.g. "caliper")
  2. Contains a front keyword (e.g. "front")
  3. Contains a right-side keyword (e.g. "right", "passenger", "rh")
  4. Does NOT contain any reject keyword (e.g. "left", "rear", "driver")
  5. If it also matches a sport keyword → confidence = "confirmed"
     otherwise                           → confidence = "possible"
"""

from __future__ import annotations

from app.config import MatchingConfig
from app.models import Listing, MatchResult
from app.utils import get_logger, normalize_text

logger = get_logger("matcher")


class Matcher:
    """Stateless keyword matcher.  Instantiate once, reuse many times."""

    def __init__(self, cfg: MatchingConfig) -> None:
        self._cfg = cfg

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def match(self, listing: Listing) -> MatchResult:
        """Evaluate a listing and return a fully-populated MatchResult."""
        text = normalize_text(listing.full_text())
        result = self._evaluate(text, listing)

        if logger.isEnabledFor(10):  # DEBUG
            logger.debug(
                "match(%r) → is_match=%s confidence=%s",
                listing.title,
                result.is_match,
                result.confidence,
            )
        return result

    def debug_text(self, text: str) -> MatchResult:
        """
        Evaluate a raw string and return a MatchResult.

        Used by --debug-item and --calibrate modes.
        """
        from datetime import datetime

        listing = Listing(
            title=text,
            url="debug",
            source="debug",
            timestamp=datetime.utcnow(),
        )
        return self.match(listing)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evaluate(self, text: str, listing: Listing) -> MatchResult:
        cfg = self._cfg

        # ---- collect which keywords actually fired ----
        matched: list[str] = []
        rejected: list[str] = []

        # Required (caliper)
        has_caliper = self._any_match(text, cfg.required_keywords, matched)

        # Front
        has_front = self._any_match(text, cfg.front_keywords, matched)

        # Right / passenger / RH
        has_right = self._any_match(text, cfg.right_keywords, matched)

        # Sport / Akebono
        has_sport = self._any_match(text, cfg.sport_keywords, matched)

        # Reject keywords
        has_reject = self._any_match(text, cfg.reject_keywords, rejected)

        # ---- decision logic ----
        reasoning: list[str] = []

        if not has_caliper:
            reasoning.append("SKIP: no required keyword (caliper)")
        if not has_front:
            reasoning.append("SKIP: no front keyword")
        if not has_right:
            reasoning.append("SKIP: no right/passenger/RH keyword")
        if not has_sport:
            reasoning.append("SKIP: no sport/4-piston/akebono keyword (required)")
        if has_reject:
            reasoning.append(f"SKIP: reject keyword(s) found → {rejected}")

        is_match = has_caliper and has_front and has_right and has_sport and not has_reject

        if is_match:
            confidence = "confirmed"
            reasoning.append(f"MATCH: confidence={confidence}")
        else:
            confidence = "none"

        return MatchResult(
            listing=listing,
            is_match=is_match,
            confidence=confidence,
            matched_keywords=matched,
            rejected_keywords=rejected,
            has_caliper=has_caliper,
            has_front=has_front,
            has_right=has_right,
            has_sport=has_sport,
            has_reject=has_reject,
            reasoning=reasoning,
        )

    @staticmethod
    def _any_match(text: str, keywords: list[str], collected: list[str]) -> bool:
        """
        Check if *any* keyword from the list appears in the normalized text.

        Matched keywords are appended to *collected* for later reporting.
        Note: keywords are also normalized so the comparison is fair.
        """
        hit = False
        for kw in keywords:
            if normalize_text(kw) in text:
                collected.append(kw)
                hit = True
        return hit


# ---------------------------------------------------------------------------
# Calibration / debug pretty-printer
# ---------------------------------------------------------------------------

def format_calibration_report(result: MatchResult) -> str:
    """
    Return a human-readable calibration report for a single MatchResult.

    This is what --calibrate and --debug-item print.
    """
    sep = "=" * 50
    thin = "-" * 50

    lines = [
        sep,
        f"ITEM:",
        f"  {result.listing.title}",
        sep,
        "",
    ]

    if result.is_match:
        lines += [
            f"MATCH: YES",
            f"CONFIDENCE: {result.confidence.upper()}",
            "",
            "MATCHED KEYWORDS:",
        ]
        for kw in result.matched_keywords:
            lines.append(f"  + {kw}")

        lines += [
            "",
            "REJECTED KEYWORDS FOUND:",
        ]
        if result.rejected_keywords:
            for kw in result.rejected_keywords:
                lines.append(f"  - {kw}")
        else:
            lines.append("  none")

        lines += [
            "",
            "FINAL DECISION:",
            "  SEND ALERT",
        ]
    else:
        lines += [
            "MATCH: NO",
            "",
            "MATCHED KEYWORDS:",
        ]
        for kw in result.matched_keywords:
            lines.append(f"  + {kw}")

        lines += [
            "",
            "REJECTED KEYWORDS FOUND:",
        ]
        if result.rejected_keywords:
            for kw in result.rejected_keywords:
                lines.append(f"  - {kw}")
        else:
            lines.append("  none")

        lines += [
            "",
            "REASONING:",
        ]
        for r in result.reasoning:
            lines.append(f"  {r}")

        lines += [
            "",
            "FINAL DECISION:",
            "  IGNORE",
        ]

    lines.append(thin)
    return "\n".join(lines)
