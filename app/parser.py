"""
parser.py — Extract Listing objects from RockAuto HTML pages or RSS feeds.

Two entry-points:
  parse_html(html: str)  → list[Listing]
  parse_rss(url: str)    → list[Listing]
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

from app.models import Listing
from app.utils import get_logger, normalize_text

logger = get_logger("parser")

_ROCKAUTO_BASE = "https://www.rockauto.com"


# ---------------------------------------------------------------------------
# RSS parsing
# ---------------------------------------------------------------------------

def parse_rss(url: str, timeout: int = 15, user_agent: str = "") -> list[Listing]:
    """
    Fetch and parse a RockAuto RSS/Atom feed.

    Returns a (possibly empty) list of Listings on any error so the watcher
    can keep running.
    """
    logger.info("Fetching RSS feed: %s", url)
    headers = {"User-Agent": user_agent} if user_agent else {}

    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("RSS fetch failed: %s", exc)
        return []

    feed = feedparser.parse(resp.text)
    listings: list[Listing] = []

    for entry in feed.entries:
        listing = _entry_to_listing(entry)
        if listing:
            listings.append(listing)

    logger.info("RSS: parsed %d listing(s) from %s", len(listings), url)
    return listings


def _entry_to_listing(entry: feedparser.FeedParserDict) -> Optional[Listing]:
    """Convert a single feedparser entry to a Listing."""
    try:
        title = getattr(entry, "title", "") or ""
        link = getattr(entry, "link", "") or "unknown"
        summary = getattr(entry, "summary", "") or ""
        published = getattr(entry, "published_parsed", None)

        ts = datetime(*published[:6]) if published else datetime.utcnow()

        # Try to extract price from summary/title
        price = _extract_price(f"{title} {summary}")
        brand = _extract_brand(title)
        side = _extract_side(f"{title} {summary}")

        return Listing(
            title=title.strip(),
            brand=brand,
            price=price,
            url=link,
            description=_strip_html(summary),
            side=side,
            timestamp=ts,
            source="rss",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to parse RSS entry: %s", exc)
        return None


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

def parse_html(html: str, base_url: str = _ROCKAUTO_BASE) -> list[Listing]:
    """
    Parse listings from a RockAuto closeout HTML page (live or saved file).

    RockAuto's HTML structure changes occasionally, so we use multiple
    heuristics to stay resilient.
    """
    soup = BeautifulSoup(html, "html.parser")
    listings: list[Listing] = []

    # Strategy 1 — table rows that look like part listings
    listings += _parse_table_rows(soup, base_url)

    # Strategy 2 — div/span blocks labelled as part descriptions
    if not listings:
        listings += _parse_div_blocks(soup, base_url)

    # Strategy 3 — fallback: any element with a part number pattern
    if not listings:
        listings += _parse_fallback(soup, base_url)

    logger.info("HTML: parsed %d listing(s)", len(listings))
    return listings


def parse_html_file(path: str) -> list[Listing]:
    """Read a local HTML file and parse it."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        html = fh.read()
    return parse_html(html)


def _parse_table_rows(soup: BeautifulSoup, base_url: str) -> list[Listing]:
    """Parse part rows from RockAuto's main table layout."""
    listings: list[Listing] = []

    # RockAuto uses nested tables; rows with class "listing-final-product"
    # or similar contain individual parts.
    rows = soup.find_all("tr", class_=re.compile(r"(listing|part|product)", re.I))
    if not rows:
        # Broader fallback: any <tr> that contains a price-looking cell
        rows = soup.find_all("tr")

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        row_text = row.get_text(separator=" ", strip=True)
        if not any(w in row_text.lower() for w in ("caliper", "brake", "rotor", "pad")):
            continue

        listing = _cells_to_listing(cells, row_text, base_url)
        if listing:
            listings.append(listing)

    return listings


def _parse_div_blocks(soup: BeautifulSoup, base_url: str) -> list[Listing]:
    """Parse part blocks from div-based RockAuto layouts."""
    listings: list[Listing] = []

    # Look for divs that mention "caliper" or "brake" prominently
    for div in soup.find_all("div"):
        text = div.get_text(separator=" ", strip=True)
        if len(text) < 10 or len(text) > 500:
            continue
        if "caliper" not in text.lower() and "brake" not in text.lower():
            continue
        if not _looks_like_part_block(div):
            continue

        price = _extract_price(text)
        brand = _extract_brand(text)
        side = _extract_side(text)
        url = _extract_url(div, base_url)

        listings.append(
            Listing(
                title=text[:200],
                brand=brand,
                price=price,
                url=url,
                description=text,
                side=side,
                source="html",
            )
        )

    return listings


def _parse_fallback(soup: BeautifulSoup, base_url: str) -> list[Listing]:
    """Last-resort: grab anything that looks like a part listing."""
    listings: list[Listing] = []
    seen_texts: set[str] = set()

    for el in soup.find_all(string=re.compile(r"caliper", re.I)):
        parent = el.find_parent()
        if parent is None:
            continue
        text = parent.get_text(separator=" ", strip=True)
        norm = normalize_text(text)
        if norm in seen_texts or len(text) > 600:
            continue
        seen_texts.add(norm)

        listings.append(
            Listing(
                title=text[:200],
                brand=_extract_brand(text),
                price=_extract_price(text),
                url=_extract_url(parent, base_url),
                description=text,
                side=_extract_side(text),
                source="html",
            )
        )

    return listings


# ---------------------------------------------------------------------------
# Helper extractors
# ---------------------------------------------------------------------------

def _cells_to_listing(
    cells: list, row_text: str, base_url: str
) -> Optional[Listing]:
    """Turn a list of <td> cells into a Listing."""
    try:
        title = cells[0].get_text(separator=" ", strip=True) if cells else row_text
        price = None
        url = "unknown"

        for cell in cells:
            t = cell.get_text(strip=True)
            if _looks_like_price(t):
                price = t
            a = cell.find("a", href=True)
            if a:
                url = urljoin(base_url, a["href"])

        return Listing(
            title=title[:200],
            brand=_extract_brand(title),
            price=price,
            url=url,
            description=row_text,
            side=_extract_side(row_text),
            source="html",
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("_cells_to_listing error: %s", exc)
        return None


_PRICE_RE = re.compile(r"\$\s?\d+[\d,]*\.?\d*")
_BRAND_TOKENS = [
    "cardone", "akebono", "centric", "raybestos", "acdelco", "bosch",
    "ate", "brembo", "ebc", "hawk", "wilwood", "nichibo", "dorman",
    "oe", "oem", "napa", "autozone", "advance",
]
_SIDE_TOKENS = {
    "front right": "front right",
    "right front": "front right",
    "passenger": "front right",
    "passenger side": "front right",
    " rh ": "front right",
    "front left": "front left",
    "left front": "front left",
    "driver": "front left",
    "driver side": "front left",
    " lh ": "front left",
    "rear right": "rear right",
    "rear left": "rear left",
}


def _extract_price(text: str) -> Optional[str]:
    m = _PRICE_RE.search(text)
    return m.group(0).strip() if m else None


def _extract_brand(text: str) -> Optional[str]:
    lower = text.lower()
    for brand in _BRAND_TOKENS:
        if brand in lower:
            # Return title-cased version
            idx = lower.find(brand)
            return text[idx : idx + len(brand)].title()
    return None


def _extract_side(text: str) -> Optional[str]:
    lower = f" {text.lower()} "
    for token, side in _SIDE_TOKENS.items():
        if token in lower:
            return side
    return None


def _extract_url(el, base_url: str) -> str:
    a = el.find("a", href=True)
    if a:
        return urljoin(base_url, a["href"])
    return "unknown"


def _looks_like_price(text: str) -> bool:
    return bool(_PRICE_RE.match(text.strip()))


def _looks_like_part_block(el) -> bool:
    """Heuristic: does this element look like it wraps a single part?"""
    text = el.get_text(separator=" ", strip=True)
    # Must mention a price OR have an anchor link
    has_price = bool(_PRICE_RE.search(text))
    has_link = bool(el.find("a", href=True))
    return has_price or has_link


def _strip_html(html_text: str) -> str:
    """Remove HTML tags from a string."""
    return BeautifulSoup(html_text, "html.parser").get_text(separator=" ", strip=True)
