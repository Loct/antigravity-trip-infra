---
name: ai-travel-council
description: Conversationally consult and leverage multiple external AIs (Anthropic Claude, DeepSeek, Groq) to double-check Wanderlog itineraries, debate route pacing, audit specific days, and cross-examine dining and transit logistics.
---

# Conversational AI Travel Council Skill

This skill enables Antigravity to consult a **Council of External AI Advisors** (Anthropic Claude and DeepSeek) during conversation with the user. Instead of relying on a single model's reasoning, Antigravity can ping Claude, DeepSeek, or both in real time to double-check travel decisions, verify feasibility, and debate alternatives.

---

## 1. When to Use This Skill

Activate this skill when:
- The user asks to **"double check this with other AIs"**, **"ask Claude and DeepSeek"**, or **"get a second opinion"**.
- The user is uncertain about a specific day or route (e.g., *"Is Day 4 too rushed?"*, *"Will we have enough time to catch the ferry?"*).
- Cross-checking dining recommendations or authentic local food suggestions.
- Finalizing a complex itinerary and running a multi-perspective consensus audit.

---

## 2. Querying the Travel Council via CLI

Antigravity executes `scripts/ai_council.py` using `run_command`:

### Double-Check a Specific Question Across Both AIs (Claude + DeepSeek)
```bash
uv run scripts/ai_council.py "Is the schedule on Day 3 feasible with afternoon traffic?" --trip <trip_id_or_file> --day 3 --format json
```

### Consult Specifically with Claude
```bash
uv run scripts/ai_council.py "Evaluate museum opening hours and cultural flow for Days 1-3" --trip <trip_id_or_file> --days 1,2,3 --ai claude --format json
```

### Consult Specifically with DeepSeek
```bash
uv run scripts/ai_council.py "Calculate driving buffers and backtracking between these sights" --trip <trip_id_or_file> --ai deepseek --format json
```

### Full Conversational Multi-AI Audit
```bash
uv run scripts/ai_council.py --trip <trip_id_or_file> --audit --format json
```

### User Interactive Terminal Council Mode
When the user wants to chat live with the models in their own terminal:
```bash
uv run scripts/ai_council.py --trip <trip_id_or_file> --interactive
```

---

## 3. Conversational Synthesis Format

When presenting council insights back to the user in chat, structure your response cleanly:

```markdown
### 🏛️ Travel Council Consultation: [Topic / Question]

#### 🎭 Claude's Take
[Concise summary of Claude's perspective, emphasizing cultural nuances, opening hours, or pacing]

#### 🧠 DeepSeek's Take
[Concise summary of DeepSeek's perspective, emphasizing transit buffers, routing logistics, or timing conflicts]

#### ⚖️ Antigravity Synthesis & Recommendation
- **Consensus**: Points where both models agree.
- **Key Divergence / Trade-offs**: Nuances where their suggestions differ.
- **Recommended Next Step**: Concrete proposed adjustment to the Wanderlog plan.
```

---

## 4. Important Safety Invariant

> [!IMPORTANT]
> **Trip Mutation Confirmation**:
> External AIs may suggest changes (e.g., moving activities, changing dates, deleting duplicate notes).
> **Always ask the user for confirmation** before making any mutations to the Wanderlog trip via MCP tools!
