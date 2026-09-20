---
name: lodging-search
description: Search and compare lodging and hotel accommodations across Wanderlog (Google Lodging rates), Apify Agoda scraper, and Google Maps, and manage bookings for trips.
---

# Lodging Search Skill

This skill guides Antigravity on searching, comparing, and organizing hotel and lodging accommodations across multiple data sources:
1. **Wanderlog (Built-in Google Lodging Engine)**: Live hotel data, Google ratings, property IDs, and direct itinerary integration.
2. **Agoda (via Apify)**: Room rates, special deals, availability, and direct booking URLs from Agoda.
3. **Google Maps Places (via Apify or Wanderlog)**: Verified addresses, amenities, exact coordinates, and Google Place IDs.

---

## 1. Credentials & Configuration

- **Wanderlog**: Handled via session cookie (`WANDERLOG_AUTH_SESSION_COOKIE`) or native MCP tools (`search_hotels`, `get_hotel_rates`, `add_lodging`).
- **Apify**: Requires an API Token (`APIFY_TOKEN`) from [Apify Console](https://console.apify.com/account/integrations).
  - Setup helper: `./scripts/login_apify.sh`
  - Config storage: `/root/.config/apify/credentials.json` and `.env` (`APIFY_TOKEN`, `APIFY_AGODA_ACTOR`, `APIFY_GMAPS_ACTOR`)

---

## 2. Searching for Accommodations

### Method A: Unified Search Script (Recommended)

Run the unified lodging search CLI:
```bash
# Search across all available providers (Wanderlog + Agoda + Google Maps)
./scripts/search_lodging.sh -l "Tokyo" -i 2026-10-01 -o 2026-10-05 -g 2 -s all

# Search only Wanderlog (Google rates)
./scripts/search_lodging.sh -l "Paris" -s wanderlog

# Search only Agoda (via Apify)
./scripts/search_lodging.sh -l "Bangkok" -s agoda --limit 10

# Output as JSON for automated parsing
./scripts/search_lodging.sh -l "Kyoto" -s all --output json
```

### Method B: Native MCP Tools (Wanderlog)

Antigravity can directly call the Wanderlog MCP tools:
- `search_hotels`: Search for hotels in any destination with check-in, check-out, and guest count.
- `get_hotel_rates`: Get Google lodging price rates for a given `property_id`.

---

## 3. Adding Lodging to Wanderlog Trips

> [!IMPORTANT]
> **Trip Mutation Rule**:
> ALWAYS ask the user for confirmation before mutating trips (e.g. adding lodging).
> Provide the hotel name, check-in date, check-out date, and price/notes clearly, and wait for user approval before applying changes.

Once the user approves:
```bash
wanderlog trips lodging add <trip-id> \
  --name "Palace Hotel Tokyo" \
  --check-in 2026-10-01 \
  --check-out 2026-10-05 \
  --address "1-1-1 Marunouchi, Chiyoda-ku, Tokyo"
```
Or use the MCP tool `add_lodging` with the specified trip ID.
