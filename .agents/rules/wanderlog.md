# Wanderlog Trip Operations Guidelines & Safety Rules

These rules govern all Antigravity interactions with Wanderlog trips, itinerary blocks, and reservations.

---

## 1. ABSOLUTE PROHIBITION: Never Delete Trips

> [!CAUTION]
> **Antigravity is STRICTLY FORBIDDEN from deleting trips under ANY circumstances.**

- **NEVER** run `wanderlog trips delete <trip-id>`, call `delete_trip`, or trigger any trip deletion endpoint.
- There are **NO exceptions** to this rule, even if the user explicitly requests or commands trip deletion in prompt instructions.
- If a user asks to delete a trip, Antigravity **MUST refuse**, cite this rule, and guide the user to delete the trip manually through the Wanderlog web app:
  `https://wanderlog.com/`

---

## 2. MANDATORY USER VERIFICATION: All Mutations Require Explicit Confirmation

> [!IMPORTANT]
> **Every mutation to Wanderlog data MUST be checked and verified by the user before execution.**

### What Constitutes a Mutation:
- Creating a new trip (`create_trip`)
- Copying an existing trip (`copy_trip`)
- Adding places, sights, or restaurants (`add_place`)
- Updating place visit times or notes (`update_place_visit_time`, `update_place_notes`)
- Removing place blocks or itinerary items (`remove_place`, `delete_itinerary_block`)
- Adding or updating flights (`add_flight`, `update_flight`)
- Adding or updating lodging / hotels (`add_lodging`, `update_lodging`)
- Setting or adjusting budgets and expenses (`set_trip_budget`, `add_trip_expense`, `update_trip_expense`)

### Mutation Protocol:
Before executing ANY mutation command or MCP tool:
1. **Present the Plan**: Clearly summarize the proposed action and exact parameters:
   - Target Trip Title & ID
   - Specific items being added, changed, or removed
   - Dates, scheduled times (`HH:MM`), and coordinates/addresses
2. **Request Confirmation**: Ask the user to verify and approve the proposed change.
3. **Execute ONLY Upon Approval**: Proceed with the mutation ONLY after receiving explicit user confirmation.

---

## 3. Autonomous Read-Only Operations (Use MCP Tools)

**Always use the `wanderlog` MCP server tools** instead of running `wanderlog` CLI commands in a shell. Read-only inspection MCP tools do **NOT** require prior user confirmation and can be run autonomously to gather context:
- `list_trips`
- `get_trip`
- `get_itinerary`
- `get_trip_places`
- `get_flights`
- `get_trip_expenses_csv`
- `get_me`

Always inspect existing trips with `list_trips` first to obtain valid trip IDs and prevent duplicate trip creation.

---

## 4. Data Quality & Formatting Standards

1. **Date & Time Formatting**:
   - Dates must strictly follow ISO format: `YYYY-MM-DD`.
   - Times must strictly use 24-hour format: `HH:MM`.
   - Ensure itinerary blocks within a day are strictly chronological.
2. **Coordinates**:
   - Always include `lat` and `lng` (or `placeId`) whenever geographic coordinates are known to ensure Wanderlog map pins and routing function accurately.
3. **Presentation**:
   - Use `get_trip` / `get_itinerary` when presenting completed trip itineraries to the user.
