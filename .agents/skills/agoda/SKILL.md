---
name: agoda
description: Search and compare hotel and lodging accommodations via Agoda (using RapidAPI, Apify scraper actor, or direct web search) with AgodaVIP loyalty discounts, and add selected stays to Wanderlog trip itineraries.
---

# Agoda Lodging Search & Wanderlog Integration Skill

This skill guides Antigravity on searching, filtering, and comparing hotel and lodging accommodations using Agoda, applying AgodaVIP loyalty discounts, and linking selected stays to Wanderlog trip itineraries.

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

## 2. AgodaVIP Loyalty Discounts & Valid URLs

### AgodaVIP Loyalty Tiers
Agoda provides VIP tiers with automatic discounts applied to hotel searches:
- **Level 1 (VIP Bronze)**: ~5% discount
- **Level 2 (VIP Silver)**: ~12% discount
- **Level 3 (VIP Gold)**: ~18% discount
- **Level 4 (VIP Platinum)**: ~25% discount *(Default)*
- **Level 0**: Standard public pricing (no discount)

Configured via `AGODA_VIP_LEVEL` in `.env` or `--vip <0-4>` CLI argument.

### Personal Account & Auto-Tier Detection
You can use your personal Agoda account to automatically detect your real VIP tier:
- Pass `--personal-account` or `--vip auto` during search.
- Or set `AGODA_AUTO_DETECT_VIP=true` or `AGODA_VIP_LEVEL=auto` in `.env`.
- When linked, the CLI connects via `AGODA_SESSION_COOKIE`, resolves your tier (Bronze, Silver, Gold, or Platinum), and applies the exact loyalty discount with member badges.
- **If not linked yet**: The CLI automatically displays a helpful setup prompt guiding you to run `./scripts/login_agoda.sh` (Option 3) to extract and paste your session cookie, gracefully falling back to standard rates without breaking.

### Valid Direct URL Requirements
Never generate broken placeholder URLs such as `agoda.com/hotel/<id>.html`. The integration uses `build_agoda_hotel_url` to construct canonical URLs with pre-populated check-in/check-out dates, guest counts, room counts, and property search parameters.

---

## 3. Checking Status & Credentials

Check the current status of all Agoda providers, VIP level, and Wanderlog CLI:

```bash
uv run scripts/agoda.py status
```

To configure or update credentials, use the interactive wizard:
```bash
./scripts/login_agoda.sh
```

---

## 4. Searching for Accommodations

Run `scripts/agoda.py search` with `uv run`:

### Basic Search
```bash
# Search hotels in Tokyo for 2 guests (defaults to +14 to +18 days from today)
uv run scripts/agoda.py search -l "Tokyo"
```

### Specific Dates, Guests & VIP Level
```bash
uv run scripts/agoda.py search \
  -l "Kyoto" \
  -i 2026-11-01 \
  -o 2026-11-05 \
  -g 2 \
  -c USD \
  --vip 4 \
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

### Web App Slash Command
In the Chainlit web interface, search Agoda directly using:
```text
/agoda Tokyo 2026-12-01 2026-12-05
```

---

## 5. Mandatory Dual-OTA Comparison (Agoda & Booking.com)

> [!IMPORTANT]
> **Always Search Both Platforms**:
> Whenever the user asks for hotels or accommodation options in any destination, Antigravity **MUST ALWAYS** query both Agoda and Booking.com in parallel (`-f json`), then present a unified comparative overview table comparing rates (AgodaVIP vs. Genius Lv3), ratings, perks, and verified links.

When comparing across booking platforms:
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
4. Synthesize results side-by-side in a comparative overview table with links, ratings, key amenities, and always display both the price per night in euros (€/night) and total price in euros (€ total) with loyalty discounts applied strictly based on the credentials/account associated with the session cookie (auto-detecting AgodaVIP and Genius tiers).

---

## 6. Adding Accommodations to Wanderlog Trips

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
