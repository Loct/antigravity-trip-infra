---
name: agoda
description: Search and compare hotel and lodging accommodations via Agoda (using RapidAPI, Apify scraper actor, or direct web search) and add selected stays to Wanderlog trip itineraries.
---

# Agoda Lodging Search & Wanderlog Integration Skill

This skill guides Antigravity on searching, filtering, and comparing hotel and lodging accommodations using Agoda, and linking selected stays to Wanderlog trip itineraries.

---

## 1. Architecture & Provider Modes

The integration script (`scripts/agoda.py`) uses a **hybrid multi-provider strategy**:

1. **RapidAPI / Agoda REST API** (`rapidapi` mode):
   - Fast, structured hotel search, autocomplete, and location lookup.
   - Configured via `AGODA_API_KEY` or `RAPIDAPI_KEY`.
   - Default host: `agoda-com.p.rapidapi.com` (customizable via `AGODA_RAPIDAPI_HOST`).

2. **Apify Agoda Scraper** (`apify` mode):
   - Uses cloud scraping actors (`tri_angle/agoda-scraper` or configured `APIFY_AGODA_ACTOR`).
   - Reliable fallback when direct access is blocked.
   - Configured via `APIFY_TOKEN`.

3. **Direct Web Search & Session Cookies** (`scrape` mode):
   - Direct web queries and public suggestion/search endpoints.
   - Optional `AGODA_SESSION_COOKIE` for authenticated web sessions.

4. **Auto Hybrid Mode** (`auto`, default):
   - Attempts RapidAPI first, then Apify actor, then direct web scrape.

---

## 2. Checking Status & Credentials

Check the current status of all Agoda providers and Wanderlog CLI:

```bash
uv run scripts/agoda.py status
```

To configure or update credentials, use the interactive wizard:
```bash
./scripts/login_agoda.sh
```

---

## 3. Searching for Accommodations

Run `scripts/agoda.py search` with `uv run`:

### Basic Search
```bash
# Search hotels in Tokyo for 2 guests (defaults to +14 to +18 days from today)
uv run scripts/agoda.py search -l "Tokyo"
```

### Specific Dates & Guests
```bash
uv run scripts/agoda.py search \
  -l "Kyoto" \
  -i 2026-11-01 \
  -o 2026-11-05 \
  -g 2 \
  -c USD \
  --limit 10
```

### Filtering by Rating & Max Price
```bash
# Only show properties with review score >= 8.5 and max price $300
uv run scripts/agoda.py search -l "Bangkok" --min-rating 8.5 --max-price 300
```

### JSON Output for Agent Parsing
```bash
uv run scripts/agoda.py search -l "Singapore" -f json
```

---

## 4. Multi-OTA Comparison (Agoda vs. Booking.com vs. Wanderlog)

When the user asks for comparison across booking platforms:
1. Search Agoda:
   ```bash
   uv run scripts/agoda.py search -l "Osaka" -i 2026-11-10 -o 2026-11-14 -f json
   ```
2. Search Booking.com:
   ```bash
   uv run scripts/booking.py search -l "Osaka" -i 2026-11-10 -o 2026-11-14 -f json
   ```
3. Check native Wanderlog Google lodging rates:
   - Call Wanderlog MCP tool `search_hotels` or `get_hotel_rates`.
4. Synthesize results side-by-side in a comparative table with links, ratings, and rates per night.

---

## 5. Adding Accommodations to Wanderlog Trips

> [!IMPORTANT]
> **Trip Mutation Policy**:
> For any trip mutation (including adding lodging), you **MUST** ask for user confirmation before applying it.
> Present the exact changes to be made (Hotel Name, Check-in/Check-out dates, Price, Address, and Trip Key) and wait for explicit user approval.

### Method A: Direct CLI Selection
When searching, specify `--add-to-trip <trip-key>`:
```bash
uv run scripts/agoda.py search -l "Tokyo" -i 2026-11-01 -o 2026-11-05 --add-to-trip "oocqlrcxztnlvaic"
```
The CLI will display the hotel options, prompt you to pick a property number, display the exact mutation command, and require confirmation before applying.

### Method B: Wanderlog CLI
Once the user confirms the selection:
```bash
wanderlog trips lodging add <trip-key> \
  --name "Hotel Gracery Shinjuku" \
  --check-in 2026-11-01 \
  --check-out 2026-11-05 \
  --lat 35.6953 \
  --lng 139.7022 \
  --notes "Booked via Agoda. Rating: 8.8/10. Price: $185/night."
```

### Method C: Native Wanderlog MCP Tool
Alternatively, call the native MCP tool `add_lodging` with:
- `trip_id`: `<trip-key>`
- `name`: Hotel name
- `check_in_date`: `YYYY-MM-DD`
- `check_out_date`: `YYYY-MM-DD`
- `notes`: Agoda booking notes / details
