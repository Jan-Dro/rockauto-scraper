# rockauto-closeout-watcher

A production-quality Discord monitoring service that watches RockAuto Wholesaler
Closeout listings for a **Nissan 370Z Sport (Akebono) front-right brake caliper**
and sends an instant Discord notification when a valid match appears.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Project Structure](#project-structure)
3. [Setup](#setup)
4. [Discord Webhook Setup](#discord-webhook-setup)
5. [Finding the RockAuto RSS Feed](#finding-the-rockauto-rss-feed)
6. [Configuration](#configuration)
7. [Running the Watcher](#running-the-watcher)
   - [Once mode](#once-mode)
   - [Watch mode](#watch-mode)
   - [Calibrate mode](#calibrate-mode)
   - [Debug item](#debug-item)
   - [Test Discord](#test-discord)
8. [Docker Setup](#docker-setup)
9. [Matching Logic](#matching-logic)
10. [Troubleshooting](#troubleshooting)

---

## Project Overview

RockAuto periodically lists wholesaler closeout parts at heavily discounted
prices.  These listings appear briefly and sell out fast.  This watcher:

- Polls either an **RSS feed** or a **direct HTML page** on a configurable interval
- Parses every listing using BeautifulSoup / feedparser
- Runs each listing through a **keyword-based matching engine**
- Sends a **rich Discord embed** for any confirmed or possible match
- Persists seen items so you **never receive duplicate alerts**

---

## Project Structure

```
rockauto-closeout-watcher/
│
├── app/
│   ├── __init__.py
│   ├── monitor.py      ← Core orchestration + CLI modes
│   ├── parser.py       ← HTML & RSS parsing → Listing objects
│   ├── matcher.py      ← Keyword matching engine + calibration output
│   ├── notifier.py     ← Discord webhook notifications
│   ├── storage.py      ← JSON-based deduplication store
│   ├── config.py       ← Typed config loader (config.yaml + .env)
│   ├── models.py       ← Pydantic data models (Listing, MatchResult)
│   └── utils.py        ← Logging setup, text normalization
│
├── data/
│   ├── seen_items.json ← Persisted deduplication keys (auto-created)
│   └── logs/           ← Log files (auto-created)
│
├── samples/
│   └── sample.html     ← Drop your saved RockAuto HTML here
│
├── tests/
│   ├── test_matcher.py
│   ├── test_parser.py
│   └── test_notifications.py
│
├── config.yaml         ← All configuration
├── .env.example        ← Copy to .env and fill in secrets
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md           ← You are here
```

---

## Setup

### 1. Clone / open the project

```bash
cd rockauto-closeout-watcher
```

### 2. Create and activate a virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` and set your Discord webhook URL (see next section).

---

## Discord Webhook Setup

1. Open your Discord server
2. Go to **Server Settings → Integrations → Webhooks**
3. Click **New Webhook**
4. Give it a name (e.g. *RockAuto Watcher*) and choose the channel
5. Click **Copy Webhook URL**
6. Paste it into your `.env` file:

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/123456789/abcdefgh...
```

Test it immediately:

```bash
python monitor.py --test-discord
```

You should see a green embed in your Discord channel. ✅

---

## Finding the RockAuto RSS Feed

RockAuto does not publicly advertise RSS feeds, but they exist for closeout /
clearance sections.  Here are two ways to find the URL:

### Method A — Browser DevTools

1. Visit `https://www.rockauto.com/en/closeout/` (or the Wholesaler page)
2. Open **DevTools → Network tab**
3. Filter by `rss` or `feed`
4. Reload the page and look for any RSS/Atom feed requests

### Method B — Direct URL patterns

RockAuto RSS feeds commonly follow patterns like:

```
https://www.rockauto.com/en/closeout/?jsn=rss
https://www.rockauto.com/en/clearance.rss
```

Try these in your browser — if you see XML, it's a valid feed.  
Paste the working URL into `config.yaml → rockauto.rss_url`.

### Method C — Use `page_url` instead

If no RSS feed is available, set `source_mode: "html"` and provide the direct
page URL in `rockauto.page_url`.  The parser will scrape the HTML directly.

---

## Configuration

All configuration lives in **`config.yaml`**.  Secrets are kept out of the file
via `${ENV_VAR}` placeholders that resolve from your `.env` at runtime.

```yaml
rockauto:
  source_mode: "rss"      # "rss" or "html"
  rss_url: "https://..."  # RSS feed URL
  page_url: ""            # Direct HTML URL (used when source_mode = "html")

monitor:
  interval_minutes: 30    # How often to check (watch mode)
  dry_run: false          # true = log but don't actually POST to Discord
  debug_matching: true    # true = log full calibration output for every item

matching:
  required_keywords: [caliper]
  front_keywords: [front]
  right_keywords: [right, "front right", passenger, "passenger side", RH]
  sport_keywords: [sport, akebono, "4 piston", "4-piston", ...]
  reject_keywords: [left, rear, driver, LH, ...]
```

---

## Running the Watcher

All commands are run from the project root with the virtualenv active.

### Once mode

Fetch listings one time, send any new alerts, and exit.

```bash
python monitor.py --once
```

### Watch mode

Run forever, polling every `interval_minutes` minutes.

```bash
python monitor.py --watch
```

Press `Ctrl+C` to stop gracefully.

### Calibrate mode

Parse a local HTML file and print detailed match reasoning for every listing.
Drop your saved RockAuto HTML into `samples/sample.html` first.

```bash
python monitor.py --calibrate samples/sample.html
```

Example output:

```
==================================================
ITEM:
  CARDONE Front Right Brake Caliper w/ Sport Brakes
==================================================

MATCH: YES
CONFIDENCE: CONFIRMED

MATCHED KEYWORDS:
  + caliper
  + front
  + right
  + sport

REJECTED KEYWORDS FOUND:
  none

FINAL DECISION:
  SEND ALERT
--------------------------------------------------

==================================================
ITEM:
  Front Left Brake Caliper
==================================================

MATCH: NO

MATCHED KEYWORDS:
  + caliper
  + front

REJECTED KEYWORDS FOUND:
  - left

FINAL DECISION:
  IGNORE
--------------------------------------------------
```

### Debug item

Test how the matcher interprets a specific string without needing an HTML file.

```bash
python monitor.py --debug-item "CARDONE Front Right Caliper w/ Sport Brakes"
python monitor.py --debug-item "Rear Left Brake Caliper"
```

### Test Discord

Verify your Discord webhook is working.

```bash
python monitor.py --test-discord
```

---

## Docker Setup

### 1. Create your `.env` file

```bash
cp .env.example .env
# Edit .env and set DISCORD_WEBHOOK_URL
```

### 2. Build and start

```bash
docker compose up --build -d
```

The container starts in **watch mode** automatically.

### 3. View logs

```bash
docker compose logs -f
```

### 4. Run a single check inside the container

```bash
docker compose run --rm watcher python monitor.py --once
```

### 5. Calibrate with a local sample file

```bash
# Place your HTML file at samples/sample.html, then:
docker compose run --rm watcher python monitor.py --calibrate samples/sample.html
```

### 6. Stop

```bash
docker compose down
```

---

## Matching Logic

The matcher uses a multi-stage keyword approach.

### A match requires ALL of:

| Stage | Keywords checked |
|-------|-----------------|
| Required | `caliper` |
| Front | `front` |
| Right / Passenger | `right`, `front right`, `right front`, `passenger`, `passenger side`, `RH` |
| **NOT** any reject | `left`, `front left`, `left front`, `driver`, `driver side`, `LH`, `rear`, `rear left`, `rear right` |

### Confidence levels

| Confidence | Condition | Discord embed colour |
|-----------|-----------|----------------------|
| **confirmed** | All stages pass + sport/Akebono keyword found | 🟢 Green |
| **possible** | All stages pass, no sport keyword | 🟡 Yellow |

### Text normalization

Before matching, every listing is:
- Lowercased
- Whitespace collapsed to single spaces
- Stripped of leading/trailing whitespace

This means `"RH"`, `"rh"`, and `" R H "` all match the keyword `rh`.

---

## Troubleshooting

### "No listings found in sample.html"

- Make sure you saved the **full page** (browser → Save As → "Web Page, Complete")
- Check that the file actually contains part listings (open it in a browser)
- Try `--debug-item` to verify the matcher itself works independently of parsing

### Discord notification not sending

1. Run `python monitor.py --test-discord` — if it fails, your webhook URL is wrong
2. Check that `DISCORD_WEBHOOK_URL` is exported in your shell or in `.env`
3. Check `data/logs/notifier.log` for HTTP error details

### Seeing duplicate alerts after restart

- `data/seen_items.json` stores already-alerted keys
- If you deleted it, all previously seen items will re-alert on the next run
- This is intentional — if you want a clean slate, deleting the file is correct

### "Config file not found"

- The watcher expects `config.yaml` in the project root
- Use `--config /path/to/config.yaml` to specify an alternate location

### Watch mode not triggering at the expected time

- `interval_minutes` in `config.yaml` controls the sleep between checks
- The first check runs immediately on startup; then it sleeps

### All items show as "possible" (no confirmed matches)

- The listing may genuinely not mention "sport" or "akebono"
- Add the specific keyword you see in listings to `matching.sport_keywords` in `config.yaml`
- Run `--calibrate` to see exactly which keywords matched
