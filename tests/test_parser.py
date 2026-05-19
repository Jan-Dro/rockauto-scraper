"""
tests/test_parser.py — Unit tests for the HTML/RSS parser.

Run with:  pytest tests/
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from app.parser import (
    _extract_brand,
    _extract_price,
    _extract_side,
    parse_html,
)


# ---------------------------------------------------------------------------
# Price extraction
# ---------------------------------------------------------------------------

class TestExtractPrice:
    def test_dollar_amount(self):
        assert _extract_price("Caliper $45.99 each") == "$45.99"

    def test_no_price(self):
        assert _extract_price("No price here") is None

    def test_price_with_comma(self):
        assert _extract_price("Price: $1,299.00") == "$1,299.00"

    def test_price_no_cents(self):
        assert _extract_price("$89 shipped") == "$89"


# ---------------------------------------------------------------------------
# Brand extraction
# ---------------------------------------------------------------------------

class TestExtractBrand:
    def test_cardone(self):
        assert _extract_brand("CARDONE Front Right Caliper") == "Cardone"

    def test_akebono(self):
        assert _extract_brand("Akebono Sport Caliper") == "Akebono"

    def test_centric(self):
        assert _extract_brand("Centric Parts Caliper") == "Centric"

    def test_unknown_brand(self):
        assert _extract_brand("Completely unknown part") is None


# ---------------------------------------------------------------------------
# Side extraction
# ---------------------------------------------------------------------------

class TestExtractSide:
    def test_front_right(self):
        assert _extract_side("Front Right Brake Caliper") == "front right"

    def test_right_front(self):
        assert _extract_side("Right Front Caliper") == "front right"

    def test_passenger(self):
        assert _extract_side("Passenger Side Caliper") == "front right"

    def test_front_left(self):
        assert _extract_side("Front Left Caliper") == "front left"

    def test_driver(self):
        assert _extract_side("Driver Side Caliper") == "front left"

    def test_rear_right(self):
        assert _extract_side("Rear Right Caliper") == "rear right"

    def test_no_side(self):
        assert _extract_side("Brake Caliper") is None


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

SAMPLE_HTML_WITH_CALIPER = """
<html><body>
<table>
  <tr class="listing-final-product">
    <td><a href="/en/catalog/123">CARDONE Front Right Brake Caliper w/ Sport Brakes</a></td>
    <td>$45.99</td>
  </tr>
  <tr class="listing-final-product">
    <td><a href="/en/catalog/456">Front Left Brake Caliper</a></td>
    <td>$42.00</td>
  </tr>
</table>
</body></html>
"""

SAMPLE_HTML_NO_CALIPERS = """
<html><body>
<p>No parts here.</p>
</body></html>
"""


class TestParseHtml:
    def test_parses_listings(self):
        listings = parse_html(SAMPLE_HTML_WITH_CALIPER)
        assert len(listings) >= 1

    def test_extracts_price(self):
        listings = parse_html(SAMPLE_HTML_WITH_CALIPER)
        prices = [l.price for l in listings if l.price]
        assert len(prices) >= 1

    def test_empty_html_returns_empty_list(self):
        listings = parse_html(SAMPLE_HTML_NO_CALIPERS)
        assert listings == []

    def test_listing_has_url(self):
        listings = parse_html(SAMPLE_HTML_WITH_CALIPER)
        for listing in listings:
            assert listing.url  # not None or empty

    def test_listing_source_is_html(self):
        listings = parse_html(SAMPLE_HTML_WITH_CALIPER)
        for listing in listings:
            assert listing.source == "html"


# ---------------------------------------------------------------------------
# Listing model dedup key
# ---------------------------------------------------------------------------

class TestListingDedupKey:
    def test_url_dedup_key(self):
        from app.models import Listing
        l = Listing(title="Test", url="https://example.com/part/123", source="html")
        assert l.dedup_key == "https://example.com/part/123"

    def test_hash_dedup_key_when_url_unknown(self):
        from app.models import Listing
        l1 = Listing(title="Front Right Caliper", price="$45", url="unknown", source="html")
        l2 = Listing(title="Front Right Caliper", price="$45", url="unknown", source="html")
        assert l1.dedup_key == l2.dedup_key

    def test_different_titles_different_keys(self):
        from app.models import Listing
        l1 = Listing(title="Caliper A", price="$45", url="unknown", source="html")
        l2 = Listing(title="Caliper B", price="$45", url="unknown", source="html")
        assert l1.dedup_key != l2.dedup_key
