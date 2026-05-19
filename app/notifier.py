"""
notifier.py — Send rich Discord embed notifications via webhook.

Uses direct POST requests (no third-party Discord library needed).
Embeds are coloured green for confirmed matches, yellow for possible.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import requests

from app.models import MatchResult
from app.utils import get_logger

logger = get_logger("notifier")

# Discord embed colour codes
_COLOUR_GREEN = 0x2ECC71   # confirmed match
_COLOUR_YELLOW = 0xF1C40F  # possible match
_COLOUR_RED = 0xE74C3C     # error / test


def send_match_alert(
    result: MatchResult,
    webhook_url: str,
    dry_run: bool = False,
) -> bool:
    """
    Post a Discord embed for a matched listing.

    Returns True on success, False on failure.
    When dry_run=True the payload is logged but NOT sent.
    """
    if not webhook_url or "${DISCORD_WEBHOOK_URL}" in webhook_url:
        logger.warning("Discord webhook URL is not configured — skipping notification.")
        return False

    payload = _build_embed(result)

    if dry_run:
        logger.info("[DRY RUN] Would send Discord alert:\n%s", payload)
        return True

    return _post_webhook(webhook_url, payload)


def send_test_message(webhook_url: str) -> bool:
    """
    Send a simple test message to verify the webhook is working.
    """
    if not webhook_url or "${DISCORD_WEBHOOK_URL}" in webhook_url:
        logger.error("Discord webhook URL is not configured.")
        return False

    payload = {
        "embeds": [
            {
                "title": "✅ rockauto-closeout-watcher — Test Message",
                "description": (
                    "If you see this, your Discord webhook is correctly configured!"
                ),
                "color": _COLOUR_GREEN,
                "footer": {"text": "rockauto-closeout-watcher"},
                "timestamp": _utc_now_iso(),
            }
        ]
    }
    return _post_webhook(webhook_url, payload)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_embed(result: MatchResult) -> dict:
    """Build the Discord webhook JSON payload for a MatchResult."""
    listing = result.listing
    colour = _COLOUR_GREEN if result.confidence == "confirmed" else _COLOUR_YELLOW
    confidence_label = result.confidence.upper()

    title_emoji = "🚨" if result.confidence == "confirmed" else "⚠️"

    fields = [
        {
            "name": "🔩 Part Name",
            "value": listing.title or "N/A",
            "inline": False,
        },
        {
            "name": "🏷️ Brand",
            "value": listing.brand or "Unknown",
            "inline": True,
        },
        {
            "name": "💰 Price",
            "value": listing.price or "N/A",
            "inline": True,
        },
        {
            "name": "📊 Confidence",
            "value": confidence_label,
            "inline": True,
        },
        {
            "name": "🔑 Matched Keywords",
            "value": ", ".join(result.matched_keywords) if result.matched_keywords else "N/A",
            "inline": False,
        },
        {
            "name": "🔗 URL",
            "value": listing.url if listing.url != "unknown" else "N/A",
            "inline": False,
        },
    ]

    if listing.description and listing.description != listing.title:
        fields.append(
            {
                "name": "📝 Description",
                "value": listing.description[:200],
                "inline": False,
            }
        )

    embed = {
        "title": f"{title_emoji} RockAuto Closeout Match Found",
        "color": colour,
        "fields": fields,
        "footer": {"text": "rockauto-closeout-watcher"},
        "timestamp": _utc_now_iso(),
    }

    return {"embeds": [embed]}


def _post_webhook(url: str, payload: dict) -> bool:
    """POST the payload to the Discord webhook URL."""
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code in (200, 204):
            logger.info("Discord notification sent successfully (HTTP %s).", resp.status_code)
            return True
        else:
            logger.error(
                "Discord webhook returned HTTP %s: %s",
                resp.status_code,
                resp.text[:300],
            )
            return False
    except requests.RequestException as exc:
        logger.error("Failed to POST to Discord webhook: %s", exc)
        return False


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
