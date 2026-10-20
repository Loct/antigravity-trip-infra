---
name: hotel-search
description: Search, compare, and manage hotel accommodations across Wanderlog, Agoda, Booking.com, and Google Hotels. Use when the user asks to find hotels, compare prices across OTAs, or attach lodging to a trip.
---

# Hotel Search & Multi-OTA Comparison Skill

This skill guides Antigravity on searching, comparing, and scheduling hotel stays and lodging accommodations.

---

## Architecture: Two-Tier Strategy

We use a two-tier strategy to ensure stability, fast response times, and direct itinerary integration:

```
+-----------------------------------------------------------------------------+
| Tier 1: Wanderlog Native MCP (Core Itinerary & Fast Discovery)               |
| - Tools: search_hotels, get_hotel_rates, add_lodging, update_lodging         |
| - Cost: Free, zero latency overhead, native itinerary sync                  |
| - Best for: Initial property search, location mapping, and attaching stays  |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
| Tier 2: Apify MCP / Cloud Actors (Deep Agoda & Multi-OTA Price Comparison)  |
| - Actors: Google Hotels Scraper, Agoda Hotel API (johnvc/agoda-hotel-api)    |
| - Anti-bot: Cloud proxy rotation & Akamai/PerimeterX bypass                 |
| - Best for: Side-by-side price checks (Agoda vs. Booking.com vs. Expedia)   |
+-----------------------------------------------------------------------------+
```

---

## Workflow Guide

### Step 1: Initial Property Discovery & Baseline Rates
When the user asks for hotels in a destination (e.g. *"Find a 4-star hotel in Shinjuku for Oct 12-16"*):
1. Use Wanderlog MCP `search_hotels`:
   ```json
   {
     "location": "Shinjuku, Tokyo",
     "check_in": "2026-10-12",
     "check_out": "2026-10-16",
     "guests": 2
   }
   ```
2. Parse properties, review scores, price per night, and photos.
3. Recommend top options categorized by:
   - **Best Overall / Value**
   - **Luxury / Boutique**
   - **Budget-Friendly**

### Step 2: Multi-OTA & Agoda Rate Comparison
When the user wants to compare rates across platforms or specifically check Agoda:
1. If Apify MCP is configured (`APIFY_TOKEN`), query the Google Hotels Scraper or Agoda Hotel API Actor.
2. Present side-by-side pricing:
   - **Agoda**: Estimated rate + direct booking link
   - **Booking.com**: Estimated rate + direct booking link
   - **Expedia / Direct**: Comparison rate
3. Remind the user:
   > *💡 Tip: Open the booking link in your personal browser to ensure your personal member perks (Agoda VIP or Booking Genius) apply automatically.*

### Step 3: Attaching to Trip Itinerary
Once the user picks their hotel or confirms a reservation:
1. Always ask for confirmation before modifying the trip (as required by Trip Mutation rules).
2. Call Wanderlog's `add_lodging` tool:
   ```json
   {
     "trip_id": "<tripId>",
     "name": "Hotel Gracery Shinjuku",
     "check_in": "2026-10-12",
     "check_out": "2026-10-16",
     "address": "1-19-1 Kabukicho, Shinjuku, Tokyo"
   }
   ```
3. The stay is automatically plotted on the trip map, added to the timeline, and factored into the trip budget.
