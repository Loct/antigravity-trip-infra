# Wanderlog Trip Operations Guidelines

When executing tasks related to Wanderlog:

1. **Verify Trip ID First**:
   - Always run `wanderlog trips list` to obtain existing trip IDs and avoid duplicate trips.
   - For any action on an existing trip, confirm the `trip-id` before running edit commands.

2. **Safety on Deletions**:
   - Never delete trips or itinerary items without user confirmation unless explicitly requested with confirmation.

3. **Time Formatting & Validation**:
   - Dates must be formatted in ISO format `YYYY-MM-DD`.
   - Times must use 24-hour format `HH:MM`.
   - Ensure itinerary blocks are chronologically ordered.

4. **Coordinate Accuracy**:
   - When adding places, include latitude and longitude when known to help Wanderlog calculate optimal routes and display map pins accurately.

5. **LLM Output Integration**:
   - Use `wanderlog trips show <trip-id> --details --output markdown` when presenting full trip summaries to the user, as it provides a clean, well-formatted itinerary.
