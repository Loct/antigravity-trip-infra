---
name: booking
description: Search and compare hotel and lodging accommodations via Booking.com (using RapidAPI, Apify scraper actor, or session cookies) and add selected stays to Wanderlog trip itineraries.
---

# Booking.com Lodging Search & Wanderlog Integration Skill

This skill guides Antigravity on searching, filtering, and comparing hotel and lodging accommodations using Booking.com, and linking selected stays to Wanderlog trip itineraries.

---

## 1. Architecture & Provider Modes

The integration script (`scripts/booking.py`) uses a **hybrid multi-provider strategy**:

1. **RapidAPI / Booking.com REST API** (`rapidapi` mode):
   - Fast, structured hotel search and location lookup.
   - Configured via `BOOKING_API_KEY` or `RAPIDAPI_KEY`.
   - Default host: `booking-com15.p.rapidapi.com` (customizable via `RAPIDAPI_HOST`).

2. **Apify Booking Scraper** (`apify` mode):
   - Uses residential proxies and cloud actors (`voyager/booking-scraper` or `apify/booking-scraper`).
   - Reliable fallback when direct access is blocked.
   - Configured via `APIFY_TOKEN`.

3. **Direct Web Search & Session Cookies** (`scrape` mode):
   - Direct web queries using `BOOKING_SESSION_COOKIE` (`bkng_sso_session`).

4. **Auto Hybrid Mode** (`auto`, default):
   - Attempts RapidAPI first, then Apify, then direct scrape.

---

## 2. Checking Status & Credentials

Check the current status of all Booking.com providers and Wanderlog CLI:

```bash
uv run scripts/booking.py status
```

To configure or update credentials, use the interactive wizard:
```bash
./scripts/login_booking.sh
```

---

## 3. Searching for Accommodations

Run `scripts/booking.py search` with `uv run`:

### Basic Search
```bash
# Search hotels in Tokyo for 2 guests (defaults to +14 to +18 days from today)
uv run scripts/booking.py search -l "Tokyo"
```

### Specific Dates & Guests
```bash
uv run scripts/booking.py search \
  -l "Kyoto" \
  -i 2026-11-01 \
  -o 2026-11-05 \
  -g 2 \
  -c EUR \
  --limit 10
```

### Genius Loyalty Discounts
```bash
# By default, GENIUS_LEVEL=3 applies 20% loyalty discounts to eligible properties.
# Specify --genius 0 to disable, or --genius [1|2|3] to override tier:
uv run scripts/booking.py search -l "Barcelona" --genius 3
```

### Filtering by Rating
```bash
# Only show properties with review score >= 8.5
uv run scripts/booking.py search -l "Paris" --min-rating 8.5
```

### JSON Output for Agent Parsing
```bash
uv run scripts/booking.py search -l "Rome" -f json
```

---

## 4. Adding Accommodations to Wanderlog Trips

> [!IMPORTANT]
> **Trip Mutation Policy**:
> For any trip mutation (including adding lodging), you **MUST** ask for user confirmation before applying it.
> Present the exact changes to be made (Hotel Name, Check-in/Check-out dates, Price, Address, and Trip Key) and wait for explicit user approval.

### Method A: Direct CLI Selection
When searching, specify `--add-to-trip <trip-key>`:
```bash
uv run scripts/booking.py search -l "Tokyo" -i 2026-11-01 -o 2026-11-05 --add-to-trip "oocqlrcxztnlvaic"
```
The CLI will display the hotel options, prompt you to pick a property number, display the exact mutation command, and require confirmation before applying.

### Method B: Wanderlog CLI
Once the user confirms the selection:
```bash
wanderlog trips lodging add <trip-key> \
  --name "Hotel The Celestine Kyoto Gion" \
  --check-in 2026-11-01 \
  --check-out 2026-11-05 \
  --lat 34.9984 \
  --lng 135.7745 \
  --notes "Booked via Booking.com. Rating: 9.1/10. Price: $220/night."
```

### Method C: Native Wanderlog MCP Tool
Alternatively, call the native MCP tool `add_lodging` with:
- `trip_id`: `<trip-key>`
- `name`: Hotel name
- `check_in_date`: `YYYY-MM-DD`
- `check_out_date`: `YYYY-MM-DD`
- `notes`: Booking notes / details
