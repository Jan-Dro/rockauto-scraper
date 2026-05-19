"""
tests/test_matcher.py — Unit tests for the matching engine.

Run with:  pytest tests/
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from app.config import MatchingConfig
from app.matcher import Matcher, format_calibration_report
from app.models import Listing


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def default_config() -> MatchingConfig:
    return MatchingConfig()


@pytest.fixture
def matcher(default_config) -> Matcher:
    return Matcher(default_config)


def make_listing(title: str, description: str = "", side: str = "") -> Listing:
    return Listing(title=title, url="http://example.com", description=description, side=side)


# ---------------------------------------------------------------------------
# Confirmed matches — should trigger alert with confidence="confirmed"
# ---------------------------------------------------------------------------

class TestConfirmedMatches:
    def test_front_right_sport_caliper(self, matcher):
        listing = make_listing("CARDONE Front Right Brake Caliper w/ Sport Brakes")
        result = matcher.match(listing)
        assert result.is_match is True
        assert result.confidence == "confirmed"

    def test_passenger_side_akebono(self, matcher):
        listing = make_listing("Akebono Passenger Side Front Brake Caliper")
        result = matcher.match(listing)
        assert result.is_match is True
        assert result.confidence == "confirmed"

    def test_rh_sport_caliper_uppercase(self, matcher):
        listing = make_listing("Centric Front RH Caliper Sport Package")
        result = matcher.match(listing)
        assert result.is_match is True
        assert result.confidence == "confirmed"

    def test_right_front_4_piston(self, matcher):
        listing = make_listing("Right Front 4-Piston Brake Caliper")
        result = matcher.match(listing)
        assert result.is_match is True
        assert result.confidence == "confirmed"

    def test_right_front_with_sport_brakes_keyword(self, matcher):
        listing = make_listing("Caliper Front Right with Sport Brakes")
        result = matcher.match(listing)
        assert result.is_match is True
        assert result.confidence == "confirmed"


# ---------------------------------------------------------------------------
# Possible matches — front/right/caliper but NO explicit sport keyword
# ---------------------------------------------------------------------------

class TestPossibleMatches:
    def test_front_right_caliper_no_sport(self, matcher):
        listing = make_listing("Front Right Brake Caliper")
        result = matcher.match(listing)
        assert result.is_match is True
        assert result.confidence == "possible"

    def test_passenger_front_caliper_no_sport(self, matcher):
        listing = make_listing("Passenger Front Brake Caliper")
        result = matcher.match(listing)
        assert result.is_match is True
        assert result.confidence == "possible"


# ---------------------------------------------------------------------------
# Non-matches — should be ignored
# ---------------------------------------------------------------------------

class TestNonMatches:
    def test_left_caliper_rejected(self, matcher):
        listing = make_listing("Front Left Brake Caliper")
        result = matcher.match(listing)
        assert result.is_match is False
        assert "left" in result.rejected_keywords

    def test_driver_side_rejected(self, matcher):
        listing = make_listing("Driver Side Front Brake Caliper")
        result = matcher.match(listing)
        assert result.is_match is False

    def test_rear_caliper_rejected(self, matcher):
        listing = make_listing("Rear Right Brake Caliper")
        result = matcher.match(listing)
        assert result.is_match is False

    def test_no_caliper_keyword(self, matcher):
        listing = make_listing("Front Right Brake Pad Set")
        result = matcher.match(listing)
        assert result.is_match is False

    def test_no_front_keyword(self, matcher):
        listing = make_listing("Right Brake Caliper Sport")
        result = matcher.match(listing)
        # "right" is present but "front" is absent
        assert result.is_match is False

    def test_empty_title(self, matcher):
        listing = make_listing("")
        result = matcher.match(listing)
        assert result.is_match is False

    def test_lh_reject(self, matcher):
        listing = make_listing("Front LH Caliper w/ Sport Brakes")
        result = matcher.match(listing)
        assert result.is_match is False

    def test_rear_right_reject(self, matcher):
        listing = make_listing("Rear Right Caliper Sport Akebono")
        result = matcher.match(listing)
        assert result.is_match is False


# ---------------------------------------------------------------------------
# Keyword collection
# ---------------------------------------------------------------------------

class TestKeywordCollection:
    def test_matched_keywords_populated(self, matcher):
        listing = make_listing("CARDONE Front Right Brake Caliper w/ Sport Brakes")
        result = matcher.match(listing)
        assert "caliper" in result.matched_keywords
        assert "front" in result.matched_keywords
        assert result.has_sport is True

    def test_rejected_keywords_populated(self, matcher):
        listing = make_listing("Front Left Brake Caliper Sport Akebono")
        result = matcher.match(listing)
        assert result.has_reject is True
        assert len(result.rejected_keywords) > 0


# ---------------------------------------------------------------------------
# Calibration report format
# ---------------------------------------------------------------------------

class TestCalibrationReport:
    def test_confirmed_match_report_contains_send_alert(self, matcher):
        listing = make_listing("CARDONE Front Right Brake Caliper w/ Sport Brakes")
        result = matcher.match(listing)
        report = format_calibration_report(result)
        assert "SEND ALERT" in report
        assert "confirmed" in report.lower()

    def test_non_match_report_contains_ignore(self, matcher):
        listing = make_listing("Front Left Brake Caliper")
        result = matcher.match(listing)
        report = format_calibration_report(result)
        assert "IGNORE" in report
        assert "MATCH: NO" in report


# ---------------------------------------------------------------------------
# debug_text helper
# ---------------------------------------------------------------------------

class TestDebugText:
    def test_debug_text_confirmed(self, matcher):
        result = matcher.debug_text("CARDONE Front Right Caliper w/ Sport Brakes")
        assert result.is_match is True
        assert result.confidence == "confirmed"

    def test_debug_text_ignore(self, matcher):
        result = matcher.debug_text("Front Left Caliper")
        assert result.is_match is False
