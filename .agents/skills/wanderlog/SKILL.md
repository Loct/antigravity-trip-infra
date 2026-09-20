---
name: wanderlog
description: Manage Wanderlog trips, build day-by-day travel itineraries, add places, flights, hotels, transit, and budgets using the Wanderlog CLI and MCP tools.
---

# Wanderlog Trip Management Skill

This skill equips Antigravity with complete knowledge and actionable workflows to create, inspect, and update trips on [Wanderlog](https://wanderlog.com) using the `wanderlog` CLI and native Model Context Protocol (MCP) server.

---

## 1. Authentication & Health Check

The CLI authenticates via the `WANDERLOG_AUTH_SESSION_COOKIE` environment variable or stored session tokens in `~/.config/wanderlog/credentials.json`.

Check authentication status at any time:
```bash
wanderlog status
```

If not logged in, user credentials can be set via:
```bash
export WANDERLOG_AUTH_SESSION_COOKIE="<session-cookie>"
# or run interactive login
wanderlog login
```

---

## 2. Model Context Protocol (MCP) Server

The CLI includes a built-in MCP server. When enabled in `mcp_config.json`:
```bash
wanderlog mcp --enable-write
```
Antigravity can directly invoke structured tool calls:
- `create_trip`: Create a new trip with title, dates, and destination
- `list_trips`: List user's existing trips
- `get_trip`: Fetch full itinerary blocks and metadata
- `add_place`: Add places/attractions/restaurants with optional coordinates and time slots
- `update_place_visit_time`: Set arrival/departure times on an itinerary block
- `delete_itinerary_block`: Remove a place, flight, or lodging block
- `add_flight`: Add flight numbers, dates, departure/arrival times
- `add_lodging`: Add hotel/Airbnb bookings with check-in/out dates

---

## 3. CLI Command Reference

### Reading Trips
```bash
# List all trips
wanderlog trips list

# View summary of a trip
wanderlog trips show <trip-id>

# View detailed day-by-day itinerary
wanderlog trips show <trip-id> --details

# Output in LLM-friendly Markdown
wanderlog trips show <trip-id> --details --output markdown

# Output structured JSON
wanderlog trips show <trip-id> --output json

# List places with addresses, ratings, and coordinates
wanderlog trips places <trip-id> --output json
```

### Creating & Managing Trips
```bash
# Create a new trip
wanderlog trips create --title "Trip to Tokyo" --geo-id 1 --start 2026-10-10 --end 2026-10-18

# Copy an existing trip (requires user verification)
wanderlog trips copy <trip-id>

# NOTE: Trip deletion is STRICTLY PROHIBITED by rule. Antigravity may never delete trips.
```

### Adding Places to Itinerary
```bash
# Add a place by name
wanderlog trips edit add-place <trip-id> --name "Senso-ji Temple"

# Add a place with coordinates and scheduled start time
wanderlog trips edit add-place <trip-id> --name "Tsukiji Outer Market" --lat 35.6655 --lng 139.7708 --start-time 08:30

# Update scheduled visit time for a place block
wanderlog trips edit set-place-time <trip-id> <block-id> --start-time 10:00 --end-time 12:00

# Remove a place block
wanderlog trips edit remove-place <trip-id> <block-id>
```

### Flights, Lodging & Transit
```bash
# Add flight
wanderlog trips flight add <trip-id> \
  --flight-number JL005 \
  --departure-date 2026-10-10 \
  --departure-time 11:30

# Update flight details
wanderlog trips flight update <trip-id> <flight-block-id> --confirmation ABCXYZ --arrival-time 15:45

# Add lodging
wanderlog trips lodging add <trip-id> \
  --name "Shinjuku Granbell Hotel" \
  --check-in 2026-10-10 \
  --check-out 2026-10-15

# Add train/rail transit
wanderlog trips train add <trip-id> \
  --carrier "Shinkansen Nozomi" \
  --departure-date 2026-10-15 \
  --departure-name "Tokyo Station" --departure-lat 35.6812 --departure-lng 139.7671 \
  --arrival-name "Kyoto Station" --arrival-lat 34.9858 --arrival-lng 135.7588
```

### Budgets & Expenses
```bash
# Set trip budget
wanderlog trips budget set <trip-id> --amount 3000 --currency USD

# Add expense
wanderlog trips expenses add <trip-id> \
  --description "Bullet train tickets" \
  --amount 280 \
  --currency USD \
  --category transit

# List trip expenses (or export to CSV)
wanderlog trips expenses <trip-id> > expenses.csv
```

---

## 4. Trip Planning Workflow & Safety Rules

> [!CAUTION]
> **Antigravity may NEVER delete trips.** Do not execute any deletion command.

> [!IMPORTANT]
> **All mutations MUST be checked and verified by the user before execution.**

When a user asks to plan or update a trip:
1. **Discover & Inspect (Autonomous)**: Run `wanderlog trips list` to check if a relevant trip already exists. Retrieve details via `wanderlog trips show <trip-id> --details --output json`. Read-only commands run autonomously.
2. **Propose Plan & Get User Verification**: Before creating or modifying any trip data, present the exact plan (title, dates, places, times, flight/lodging info) to the user and request explicit confirmation.
3. **Execute Mutation Only After Approval**:
   - Create trip or add blocks once the user approves.
   - Group places geographically by day to minimize transit time.
   - Assign reasonable visit times (`--start-time` and `--end-time`).
4. **Final Verification**: Run `wanderlog trips show <trip-id> --details --output markdown` and present a clean summary to the user.
