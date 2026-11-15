# Workspace Rules

## Git Workflow & Branch Protection
- **Never Commit or Push Directly to Main**: You are STRICTLY FORBIDDEN from committing or pushing changes directly to `main` (or `master`).
- **Feature Branch & Pull Request Required**: Whenever creating, updating, or fixing code, skills, or documentation, always:
  1. Create and switch to a new descriptive feature branch (`git checkout -b feat/<name>` or `fix/<name>`).
  2. Commit changes only on the feature branch.
  3. Push the feature branch to remote origin (`git push -u origin <branch>`).
  4. Open a Pull Request using `gh pr create` for user review and merging.

## Hotel & Lodging Search & Booking Policies
- **Always Use Workspace CLIs**: When searching, comparing, pricing, or looking up accommodations/hotels/lodging, Antigravity MUST ALWAYS execute the workspace lodging scripts (`uv run scripts/booking.py` and `uv run scripts/agoda.py`) rather than relying on generic public web searches or external guesses. The user has active account credentials, session cookies, and Genius Level loyalty discounts configured in the workspace CLI.
- **Mandatory 3-Way Comparative Overview (Booking.com, Agoda & Hotel Direct)**: Whenever the user asks for hotels, accommodations, or lodging in any destination:
  1. Antigravity MUST ALWAYS search **BOTH** Booking.com (`uv run scripts/booking.py search -l <city> ...`) and Agoda (`uv run scripts/agoda.py search -l <city> ...`).
  2. Antigravity MUST ALSO retrieve the **Hotel Direct** option:
     - For candidate properties, look up official direct hotel rates and direct booking reservation URLs via Google Hotels / Search meta-aggregation (which aggregates the property's verified 'Official Site' direct rate and direct link).
     - **When direct rate is available**: Quote the exact verified live rate in EUR (€/night and € total) with direct link to the hotel's official booking engine.
     - **When direct rate is unindexed / requires direct form checkout**: Explicitly mark as `"Direct rate unlisted / Check official site"` with a direct link to the hotel's verified official website.
  3. **Property-Matched Comparative Overview Table**:
     Synthesize results side-by-side in a property-matched comparative table where each row is a specific hotel, comparing Booking.com vs. Agoda vs. Hotel Direct side-by-side:
     - Columns: `Property Name & Rating`, `Booking.com (€/night & € total, Genius)`, `Agoda (€/night & € total, VIP)`, `Hotel Direct (€/night & € total or Check Official Site)`, `Key Amenities / Perks`, and `Best Value / Direct Links`.
     - Always explicitly display both the price per night in euros (€/night) and the total price in euros (€ total for stay).
  4. Highlight which option offers the best value, lowest total price, or superior perks (e.g., free cancellation, complimentary breakfast, loyalty tier benefits).
- **Session Cookie Architecture & Fail-Fast Authentication**:
  - The repository's designated architecture for Booking.com and Agoda relies on authenticated browser session cookies (`BOOKING_SESSION_COOKIE` and `AGODA_SESSION_COOKIE`) managed via `./scripts/login_booking.sh` and `./scripts/login_agoda.sh`.
  - **Immediate Reporting of Expired/Missing Cookies**: If a session cookie is expired, challenged (HTTP 202/403), or unset, Antigravity MUST STOP IMMEDIATELY and inform the user in the very first response:
    - State clearly that the session cookie is expired/unset.
    - Provide the exact command to re-authenticate (`./scripts/login_booking.sh` or `./scripts/login_agoda.sh`).
    - **NEVER attempt to hide or paper over an expired cookie** by substituting estimated rates, guessing prices, or outputting mock/unverified comparison tables.
- **Cookie & Account-Based Loyalty Discounts**: Loyalty discounts (Booking.com Genius Level 1–3 and AgodaVIP Bronze–Platinum) MUST be applied strictly based on the credentials/account associated with the session cookie. Antigravity must auto-detect the user's actual loyalty tier from the authenticated session rather than assuming or hardcoding maximum tiers. If a session cookie is expired, challenged, or unconfigured, Antigravity must immediately report the authentication failure to the user so they can refresh it, rather than silently falling back to unverified numbers.
- **Mandatory Pre-Populated Query Parameters on ALL Links (No Bare URLs)**:
  - **Zero Tolerance for Bare URLs**: Every single accommodation link (Booking.com, Agoda, and Hotel Direct)—whether canonical property pages, search links, or official direct booking engines—MUST ALWAYS include query parameters pre-populating:
    1. Exact Check-in date (`checkIn=YYYY-MM-DD` on Agoda; `checkin=YYYY-MM-DD` on Booking and Google Hotels).
    2. Exact Check-out date (`checkOut=YYYY-MM-DD` on Agoda; `checkout=YYYY-MM-DD` on Booking and Google Hotels).
    3. Guest count (`adults=N` on Agoda/Google Hotels; `group_adults=N` on Booking).
    4. Room count (`rooms=N` on Agoda; `no_rooms=N` on Booking).
  - **Why this is strictly enforced**: Bare URLs cause booking engines to default to current dates or random defaults, displaying incorrect prices and wrong room availability.
  - For Booking.com: Format as `https://www.booking.com/hotel/{country_code}/{slug}.html?checkin={checkin}&checkout={checkout}&group_adults={guests}&no_rooms={rooms}` or `https://www.booking.com/searchresults.html?ss={hotel_name}&checkin={checkin}&checkout={checkout}&group_adults={guests}&no_rooms={rooms}`.
  - For Agoda: Format as `https://www.agoda.com/{slug}/hotel/{city}-{country}.html?checkIn={checkin}&checkOut={checkout}&adults={guests}&rooms={rooms}` or `https://www.agoda.com/search?city={city_id}&text={hotel_name}&checkIn={checkin}&checkOut={checkout}&adults={guests}&rooms={rooms}`.
  - For Hotel Direct: Format using Google Hotels meta-search link pre-populated with dates/guests (`https://www.google.com/travel/hotels?q={hotel_name_encoded}&checkin={checkin}&checkout={checkout}&adults={guests}`) and/or the hotel's official booking engine URL with dates pre-populated where supported.
- **Strict Verification of Live Availability & Live Pricing**:
  - **Definitive Verification Required**: Antigravity MUST NEVER present or recommend accommodations, hotels, or homestays unless their live calendar availability has been definitively verified for the user's exact check-in and check-out dates. Never return hypothetical, estimated, or unverified options that the user cannot actually book.
  - **Zero Tolerance for Estimated or Baseline Rates**: Prices quoted in any comparison table or recommendation MUST be the exact live rates for the user's specific travel dates and occupancy. NEVER use off-season, low-season, or approximate estimates as if they are live prices.
  - **Handling API / Session Failures**: If live rates or room availability cannot be verified in real time (e.g. due to bot challenges, expired session cookies, or missing API credentials), Antigravity MUST explicitly inform the user that live automated pricing could not be verified, state why, and provide the pre-populated deep links for direct verification, rather than inventing or estimating rates.

## Self-Update Disambiguation & Procedure
- **Workspace Script Priority**: When the user requests "self update", "run self update", or "update yourself", ALWAYS execute the workspace updater script (`/workspace/scripts/self_update.sh`). NEVER run `agy update` directly in isolation.
- **Branch Awareness**:
  1. If currently on a feature branch that has been merged or is clean, switch to `main` (`git checkout main`) prior to running the update script so upstream commits are fetched.
  2. First run `/workspace/scripts/self_update.sh --check` or execute `/workspace/scripts/self_update.sh` to pull changes, check `agy` CLI binary updates, and trigger Docker rebuilds/restarts if infrastructure files changed.

## Conversational AI Travel Council (Claude & DeepSeek)
- **Conversational Collaboration & Cross-Checking**:
  When planning, modifying, auditing, or discussing a trip, do not act in isolation or rely on rigid one-way audit dumps. Actively converse with Anthropic Claude and DeepSeek using `scripts/ai_council.py`:
  1. **Ask Targeted Questions**: Bounce ideas off the council (`uv run scripts/ai_council.py "<question>" --trip <id_or_file> --session <session_id> --format json`).
  2. **Cross-Check Itinerary Data**: Perform 2-round mutual peer review on transit, opening hours, dining authenticity, and hotel continuity (`uv run scripts/ai_council.py --trip <id_or_file> --crosscheck [--day <N>] [--aspect transit|dining|hours|hotels|all]`).
  3. **Debate Itinerary Options**: Run structured debates on travel dilemmas (`uv run scripts/ai_council.py --trip <id_or_file> --debate "<topic>"`).
- **Conversational Synthesis**:
  Present the dialogue naturally to the user: Claude's cultural/experiential view, DeepSeek's transit/logistics view, their cross-talk review of each other, and Antigravity's vetted recommendation.
- **Trip Mutation Confirmation**:
  Always ask for user confirmation before executing any mutations to Wanderlog trips.
