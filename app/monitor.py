"""
monitor.py — CLI entry-point for rockauto-closeout-watcher.

Usage:
  python monitor.py --once                        Run a single check
  python monitor.py --watch                       Run forever (daemon mode)
  python monitor.py --calibrate samples/sample.html  Debug HTML file matching
  python monitor.py --test-discord                Send a test Discord message
  python monitor.py --debug-item "some text"      Debug a single item string
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure the project root is on sys.path so `app.*` imports work when the
# script is executed directly (e.g. `python monitor.py --once`).
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.config import load_config
from app.matcher import Matcher, format_calibration_report
from app.models import Listing
from app.notifier import send_match_alert, send_test_message
from app.parser import parse_html_file, parse_rss
from app.storage import SeenItemsStore
from app.utils import get_logger

logger = get_logger("monitor")


# ---------------------------------------------------------------------------
# Core check logic
# ---------------------------------------------------------------------------

def run_check(
    cfg,
    matcher: Matcher,
    store: SeenItemsStore,
    *,
    html_path: str | None = None,
) -> int:
    """
    Fetch/read listings, match them, and alert on new matches.

    Returns the number of new alerts sent.
    """
    # ---- fetch listings ----
    if html_path:
        logger.info("Reading HTML file: %s", html_path)
        listings = parse_html_file(html_path)
    elif cfg.rockauto.source_mode == "rss" and cfg.rockauto.rss_url:
        listings = parse_rss(
            cfg.rockauto.rss_url,
            timeout=cfg.rockauto.request_timeout,
            user_agent=cfg.rockauto.user_agent,
        )
    elif cfg.rockauto.page_url:
        import requests
        from app.parser import parse_html
        try:
            resp = requests.get(
                cfg.rockauto.page_url,
                headers={"User-Agent": cfg.rockauto.user_agent},
                timeout=cfg.rockauto.request_timeout,
            )
            resp.raise_for_status()
            listings = parse_html(resp.text, base_url=cfg.rockauto.page_url)
        except Exception as exc:
            logger.error("Failed to fetch page_url: %s", exc)
            listings = []
    else:
        logger.warning(
            "No source configured. Set rockauto.rss_url or rockauto.page_url in config.yaml."
        )
        return 0

    logger.info("Fetched %d listing(s).", len(listings))
    alerts_sent = 0

    for listing in listings:
        result = matcher.match(listing)

        if cfg.monitor.debug_matching:
            logger.debug(format_calibration_report(result))

        if not result.is_match:
            continue

        key = listing.dedup_key
        if store.is_seen(key):
            logger.info("Already seen — skipping: %s", listing.title)
            continue

        logger.info(
            "NEW MATCH [%s]: %s — %s",
            result.confidence.upper(),
            listing.title,
            listing.price or "no price",
        )

        sent = send_match_alert(
            result,
            cfg.discord.webhook_url,
            dry_run=cfg.monitor.dry_run,
        )

        if sent:
            store.mark_seen(key)
            alerts_sent += 1

    return alerts_sent


# ---------------------------------------------------------------------------
# CLI modes
# ---------------------------------------------------------------------------

def mode_once(cfg, matcher, store) -> None:
    """Run one check and exit."""
    logger.info("=== Running single check ===")
    count = run_check(cfg, matcher, store)
    logger.info("=== Done. %d alert(s) sent. ===", count)


def mode_watch(cfg, matcher, store) -> None:
    """Run forever, sleeping between checks."""
    interval = cfg.monitor.interval_minutes * 60
    logger.info(
        "=== Watch mode started. Interval: %d min ===",
        cfg.monitor.interval_minutes,
    )
    while True:
        try:
            count = run_check(cfg, matcher, store)
            logger.info("Check complete. %d new alert(s). Sleeping %ds…", count, interval)
        except KeyboardInterrupt:
            logger.info("Interrupted by user — exiting watch mode.")
            break
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error during check: %s", exc, exc_info=True)
            logger.info("Recovering — will retry after %ds.", interval)
        time.sleep(interval)


def mode_calibrate(cfg, matcher, html_path: str) -> None:
    """Parse an HTML file and print a calibration report for each listing."""
    from app.parser import parse_html_file

    logger.info("=== Calibration mode: %s ===", html_path)
    listings = parse_html_file(html_path)

    if not listings:
        print(f"\n[!] No listings found in {html_path}\n")
        print("    Tips:")
        print("    • Make sure the file contains RockAuto HTML with caliper/brake listings.")
        print("    • Try saving the full page (Ctrl+S → 'Web Page, Complete') in your browser.")
        return

    print(f"\nFound {len(listings)} listing(s)\n")

    for listing in listings:
        result = matcher.match(listing)
        print(format_calibration_report(result))
        print()


def mode_test_discord(cfg) -> None:
    """Send a test Discord message to verify webhook configuration."""
    logger.info("=== Discord test ===")
    ok = send_test_message(cfg.discord.webhook_url)
    if ok:
        print("✅  Test message sent successfully!")
    else:
        print("❌  Failed to send test message. Check DISCORD_WEBHOOK_URL in your .env file.")
        sys.exit(1)


def mode_debug_item(cfg, matcher, text: str) -> None:
    """Run the matcher against a single arbitrary string and print results."""
    result = matcher.debug_text(text)
    print()
    print(format_calibration_report(result))
    print()


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="monitor.py",
        description="rockauto-closeout-watcher — monitor RockAuto closeout listings",
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--once",
        action="store_true",
        help="Fetch listings once and exit",
    )
    group.add_argument(
        "--watch",
        action="store_true",
        help="Poll continuously at the configured interval",
    )
    group.add_argument(
        "--calibrate",
        metavar="HTML_FILE",
        help="Parse a local HTML file and show matching reasoning",
    )
    group.add_argument(
        "--test-discord",
        action="store_true",
        help="Send a test message to the configured Discord webhook",
    )
    group.add_argument(
        "--debug-item",
        metavar="TEXT",
        help="Show how the matcher interprets a given string",
    )
    p.add_argument(
        "--config",
        metavar="PATH",
        default=None,
        help="Path to config.yaml (default: config.yaml next to this script)",
    )
    return p


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Load configuration
    config_path = Path(args.config) if args.config else None
    try:
        cfg = load_config(config_path)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    matcher = Matcher(cfg.matching)
    store = SeenItemsStore(cfg.storage.seen_items_file)

    if args.once:
        mode_once(cfg, matcher, store)

    elif args.watch:
        mode_watch(cfg, matcher, store)

    elif args.calibrate:
        mode_calibrate(cfg, matcher, args.calibrate)

    elif args.test_discord:
        mode_test_discord(cfg)

    elif args.debug_item:
        mode_debug_item(cfg, matcher, args.debug_item)


if __name__ == "__main__":
    main()
