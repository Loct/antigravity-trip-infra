---
name: deepseek-validator
description: Validate, audit, and double-check Wanderlog itineraries and travel plans using free DeepSeek (via OpenRouter or custom endpoints) to detect schedule conflicts, geographic backtracking, lodging gaps, and flight buffers.
---

# DeepSeek Wanderlog Itinerary Validator Skill

This skill guides Antigravity on using **DeepSeek** (via free OpenRouter tier or direct endpoints) to double-check travel itineraries, review Wanderlog trips, and catch logistical errors before finalizing plans.

---

## 1. When to Use This Skill

Activate this skill when:
- The user asks to **"double check your work"**, **"validate the wanderlog"**, or **"audit this trip"**.
- After creating or significantly modifying a complex day-by-day itinerary in Wanderlog, to ensure there are no hidden scheduling, transit, or lodging bugs.
- The user asks for a second opinion on travel feasibility, geographic route clustering, or day-by-day pacing.

---

## 2. Validation Scope

DeepSeek audits itineraries across 5 core dimensions:
1. ⏱️ **Schedule Feasibility & Timing**: Activity durations, opening hours (e.g. museum closures), meal buffers, overlapping events.
2. 🗺️ **Geographic Routing & Backtracking**: Neighborhood clustering vs erratic criss-crossing across a city.
3. 🏨 **Lodging Continuity**: Booked accommodation for every night, luggage storage during check-in/out gaps.
4. ✈️ **Transit & Flight Buffers**: 2–3 hour airport arrival margins, realistic transfer buffers.
5. 🏃 **Pacing & Sanity**: Overloaded days vs underutilized days.

---

## 3. Running the Validator

### Validate a Wanderlog Trip by ID or URL
```bash
uv run scripts/deepseek_validator.py <trip_id_or_url>
```

### Validate a Local Trip File (e.g. JSON export)
```bash
uv run scripts/deepseek_validator.py trips/southern_italy.json
```

### Fast Check Mode (using `deepseek-chat` instead of `deepseek-r1`)
```bash
uv run scripts/deepseek_validator.py <trip_id> --quick
```

### Save Audit Report as Markdown
```bash
uv run scripts/deepseek_validator.py <trip_id> --save-report trips/audit_report.md
```

### Cross-Check with Claude (Dual AI Verification)
```bash
uv run scripts/deepseek_validator.py <trip_id> --cross-check
# or directly:
uv run scripts/cross_check_validator.py <trip_id>
```

### Test Connectivity
```bash
uv run scripts/deepseek_validator.py --test
```

---

## 4. Setup & Credentials

To configure or test OpenRouter / DeepSeek credentials:
```bash
./scripts/login_deepseek.sh
```

Supported Providers:
- **OpenRouter (Default & Free)**: Free `deepseek/deepseek-r1:free` or `deepseek/deepseek-chat:free`.
- **Groq**: Free `deepseek-r1-distill-llama-70b`.
- **DeepSeek Official**: `deepseek-reasoner` or `deepseek-chat`.
- **Ollama**: Local and offline inference.

---

## 5. Reviewing Findings with the User

After running the validator:
1. Highlight any `[CRITICAL]` or `[WARNING]` findings directly in your response.
2. Explain the suggested fixes (e.g., swapping Day 2 and Day 3 stops to eliminate 2 hours of transit).
3. **Always ask for user confirmation** before making any mutations to the Wanderlog trip based on the validation results.
