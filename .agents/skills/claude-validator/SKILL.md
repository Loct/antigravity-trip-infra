---
name: claude-validator
description: Validate, audit, and double-check Wanderlog itineraries and travel plans using Anthropic Claude (with extended thinking) and run dual AI cross-checks alongside DeepSeek to detect schedule conflicts, geographic backtracking, lodging gaps, and flight buffers.
---

# Claude Wanderlog Itinerary Validator Skill

This skill guides Antigravity on using **Anthropic Claude** (Claude 3.7 Sonnet, Claude 3.5 Sonnet, or Claude 3.5 Haiku) to audit Wanderlog travel plans and execute **Dual AI Cross-Checking** with DeepSeek to catch logistical blindspots with maximum confidence.

---

## 1. When to Use This Skill

Activate this skill when:
- The user asks to **"check this with claude"**, **"audit with claude"**, or **"cross check with claude and deepseek"**.
- Before finalizing a complex, multi-day itinerary in Wanderlog, to verify timing, geographic flow, and hotel coverage.
- The user wants a second perspective to compare against DeepSeek or an expert review with extended reasoning.

---

## 2. Validation Scope

Claude audits itineraries across 6 core dimensions:
1. ⏱️ **Schedule Feasibility & Timing**: Activity durations, opening hours, holiday closures (e.g., Tết New Year), meal buffers, time conflicts.
2. 🗺️ **Geographic Routing & Backtracking**: Neighborhood clustering vs zigzagging across cities or provinces.
3. 🏨 **Lodging Continuity**: Guaranteed hotel/stay for every single night, check-in/out gap logistics.
4. ✈️ **Transit & Flight Buffers**: 2–3 hour airport buffers, realistic transfer connections.
5. 🏃 **Pacing & Sanity**: Overloaded vs empty days.
6. 🍽️ **Dining Notes Audit**: Unified single lunch and dinner note per day, flagging missing or duplicate notes.

---

## 3. Running the Claude Validator

### Validate a Wanderlog Trip by ID or URL
```bash
uv run scripts/claude_validator.py <trip_id_or_url>
```

### Validate a Local Trip File (e.g. JSON export)
```bash
uv run scripts/claude_validator.py trips/southern_italy.json
```

### Fast Check Mode (using `claude-3-5-haiku` with thinking off)
```bash
uv run scripts/claude_validator.py <trip_id> --quick
```

### Save Audit Report as Markdown
```bash
uv run scripts/claude_validator.py <trip_id> --save-report trips/claude_report.md
```

### Cross-Check with DeepSeek (Dual AI Verification)
Run both Claude and DeepSeek simultaneously to compare findings and consensus:
```bash
uv run scripts/cross_check_validator.py <trip_id_or_url>
# or via flag:
uv run scripts/claude_validator.py <trip_id> --cross-check
```

### Save Cross-Check Consensus Report
```bash
uv run scripts/cross_check_validator.py <trip_id> --save-report trips/cross_check_report.md
```

### Test Connectivity
```bash
uv run scripts/claude_validator.py --test
# Test both Claude & DeepSeek:
uv run scripts/cross_check_validator.py --test
```

---

## 4. Setup & Credentials

To configure or test Anthropic Claude credentials:
```bash
./scripts/login_claude.sh
```

Supported Providers:
- **Anthropic Official (Recommended)**: Direct API key (`ANTHROPIC_API_KEY=sk-ant-...`) with Claude 3.7 Sonnet (supports extended thinking budget), Claude 3.5 Sonnet, or Claude 3.5 Haiku.
- **OpenRouter**: Route Claude requests through OpenRouter (`OPENROUTER_API_KEY=sk-or-...`, `CLAUDE_PROVIDER=openrouter`).

---

## 5. Reviewing Findings with the User

After running the validator:
1. Highlight any `[CRITICAL]` or `[WARNING]` findings directly in your response.
2. In cross-check mode, clearly distinguish:
   - **Consensus Findings**: Issues flagged by both Claude and DeepSeek (highest confidence fixes).
   - **Model-Specific Findings**: Nuances unique to Claude or DeepSeek.
3. **Always ask for user confirmation** before making any mutations to the Wanderlog trip based on the validation results.
