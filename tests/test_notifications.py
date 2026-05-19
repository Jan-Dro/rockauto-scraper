"""
tests/test_notifications.py — Unit tests for the Discord notifier.

These tests do NOT make real HTTP calls — they use monkeypatching to verify
that the correct payload is constructed and that dry_run mode skips the POST.

Run with:  pytest tests/
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from app.models import Listing, MatchResult
from app.notifier import (
    _COLOUR_GREEN,
    _COLOUR_YELLOW,
    _build_embed,
    send_match_alert,
    send_test_message,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_result(confidence: str = "confirmed") -> MatchResult:
    listing = Listing(
        title="CARDONE Front Right Brake Caliper w/ Sport Brakes",
        brand="Cardone",
        price="$45.99",
        url="https://www.rockauto.com/en/catalog/123",
        source="html",
    )
    return MatchResult(
        listing=listing,
        is_match=True,
        confidence=confidence,
        matched_keywords=["caliper", "front", "right", "sport"],
    )


# ---------------------------------------------------------------------------
# Embed construction
# ---------------------------------------------------------------------------

class TestBuildEmbed:
    def test_confirmed_uses_green(self):
        result = _make_result("confirmed")
        payload = _build_embed(result)
        assert payload["embeds"][0]["color"] == _COLOUR_GREEN

    def test_possible_uses_yellow(self):
        result = _make_result("possible")
        payload = _build_embed(result)
        assert payload["embeds"][0]["color"] == _COLOUR_YELLOW

    def test_title_contains_match_found(self):
        result = _make_result()
        payload = _build_embed(result)
        assert "Match Found" in payload["embeds"][0]["title"]

    def test_fields_contain_part_name(self):
        result = _make_result()
        payload = _build_embed(result)
        field_names = [f["name"] for f in payload["embeds"][0]["fields"]]
        assert any("Part" in name for name in field_names)

    def test_fields_contain_price(self):
        result = _make_result()
        payload = _build_embed(result)
        price_fields = [
            f for f in payload["embeds"][0]["fields"]
            if "Price" in f["name"]
        ]
        assert len(price_fields) == 1
        assert "$45.99" in price_fields[0]["value"]

    def test_footer_present(self):
        result = _make_result()
        payload = _build_embed(result)
        assert "footer" in payload["embeds"][0]
        assert "rockauto-closeout-watcher" in payload["embeds"][0]["footer"]["text"]


# ---------------------------------------------------------------------------
# send_match_alert
# ---------------------------------------------------------------------------

class TestSendMatchAlert:
    def test_dry_run_skips_post(self):
        result = _make_result()
        with patch("app.notifier.requests.post") as mock_post:
            send_match_alert(result, "https://discord.com/api/webhooks/fake", dry_run=True)
            mock_post.assert_not_called()

    def test_dry_run_returns_true(self):
        result = _make_result()
        ok = send_match_alert(result, "https://discord.com/api/webhooks/fake", dry_run=True)
        assert ok is True

    def test_missing_webhook_returns_false(self):
        result = _make_result()
        ok = send_match_alert(result, "", dry_run=False)
        assert ok is False

    def test_unconfigured_placeholder_returns_false(self):
        result = _make_result()
        ok = send_match_alert(result, "${DISCORD_WEBHOOK_URL}", dry_run=False)
        assert ok is False

    def test_successful_post_returns_true(self):
        result = _make_result()
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        with patch("app.notifier.requests.post", return_value=mock_resp) as mock_post:
            ok = send_match_alert(result, "https://discord.com/api/webhooks/fake")
            assert ok is True
            mock_post.assert_called_once()

    def test_failed_post_returns_false(self):
        result = _make_result()
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        with patch("app.notifier.requests.post", return_value=mock_resp):
            ok = send_match_alert(result, "https://discord.com/api/webhooks/fake")
            assert ok is False

    def test_request_exception_returns_false(self):
        import requests as req
        result = _make_result()
        with patch("app.notifier.requests.post", side_effect=req.RequestException("timeout")):
            ok = send_match_alert(result, "https://discord.com/api/webhooks/fake")
            assert ok is False


# ---------------------------------------------------------------------------
# send_test_message
# ---------------------------------------------------------------------------

class TestSendTestMessage:
    def test_unconfigured_returns_false(self):
        ok = send_test_message("")
        assert ok is False

    def test_successful_test_returns_true(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        with patch("app.notifier.requests.post", return_value=mock_resp):
            ok = send_test_message("https://discord.com/api/webhooks/fake")
            assert ok is True
