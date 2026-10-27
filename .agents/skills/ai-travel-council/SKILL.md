---
name: ai-travel-council
description: Conversationally consult and collaborate with external AIs (Anthropic Claude and DeepSeek) to cross-check trip data, debate itinerary choices, ask logistical questions, and maintain multi-turn co-planning dialogues.
---

# Conversational AI Travel Council Skill

This skill enables Antigravity to actively converse and collaborate with a **Council of External AI Advisors** (Anthropic Claude and DeepSeek). Rather than relying on static one-shot audit reports, Antigravity engages in a dynamic, multi-turn conversational exchange with Claude and DeepSeek to cross-check itinerary data, ask specific questions about the trip, debate trade-offs, and synthesize verified recommendations for the user.

---

## 1. When to Use This Skill

Activate this skill when:
- **Planning or modifying an itinerary**: Bounce ideas off Claude and DeepSeek before presenting proposals to the user.
- **Cross-checking trip data**: Verifying transit times, opening hours, dining quality/authenticity, and lodging continuity.
- **Addressing user uncertainties**: When the user asks *"Is Day 4 too rushed?"*, *"Should we take the train or fly?"*, or *"Can we double check this with Claude and DeepSeek?"*.
- **Debating itinerary dilemmas**: Weighing experiential appeal vs logistical efficiency.
- **Multi-turn dialogue**: Asking follow-up questions while maintaining conversation context across turns.

---

## 2. Model Roles & Specializations

| Advisor | Specialization | Focus Areas |
| :--- | :--- | :--- |
| **Anthropic Claude** | Culture, Dining & Experience | Pacing, atmosphere, ambiance, holiday/museum closures (e.g. Tết, Monday closures), authentic local dining, and avoiding traveler burnout. |
| **DeepSeek** | Logistics, Transit & Geometry | Travel times, rush-hour traffic buffers, geographic clustering vs zigzagging/backtracking, airport check-in margins (2-3 hrs), and lodging continuity. |
| **Antigravity (Lead)** | Synthesis & Live Execution | Facilitates dialogue, evaluates trade-offs, verifies Wanderlog MCP data, and proposes vetted mutations for user confirmation. |

---

## 3. Conversational CLI Commands

Antigravity executes `scripts/ai_council.py` using `run_command`:

### A. Ask a Targeted Question (Conversational Co-Planning)
```bash
uv run scripts/ai_council.py "Should we visit West Lake or Train Street at sunset on Day 1?" --trip <trip_id_or_file> --day 1 --format json
```

### B. Multi-Turn Conversational Session
Retain conversational memory across turns so Claude and DeepSeek remember previous points and react to each other:
```bash
# Turn 1:
uv run scripts/ai_council.py "Can we fit Cu Chi tunnels and War Remnants Museum in the same morning?" --trip <trip_id_or_file> --session trip_hcmc --format json

# Turn 2 (Follow-up):
uv run scripts/ai_council.py "DeepSeek suggested shifting the museum to afternoon. Claude, does that leave enough time for Ben Thanh market?" --session trip_hcmc --format json
```

### C. Mutual Data Cross-Check (Two-Round Peer Review)
Performs a deep 2-round cross-check: Round 1 independent audits, followed by Round 2 where DeepSeek cross-examines Claude's suggestions for transit bottlenecks, and Claude cross-examines DeepSeek's suggestions for cultural flow:
```bash
# Full trip cross-check
uv run scripts/ai_council.py --trip <trip_id_or_file> --crosscheck --format json

# Specific day and aspect cross-check
uv run scripts/ai_council.py --trip <trip_id_or_file> --crosscheck --day 3 --aspect dining --format json
# Aspects: all | transit | dining | hours | hotels
```

### D. Structured Itinerary Debate
Have Claude and DeepSeek debate an itinerary dilemma with opening arguments, cross-talk rebuttals, and consensus:
```bash
uv run scripts/ai_council.py --trip <trip_id_or_file> --debate "Overnight sleeper train vs morning flight from Hanoi to Da Nang" --format json
```

### E. Interactive Live Terminal Chat
For the user to chat directly with both models in real time:
```bash
uv run scripts/ai_council.py --trip <trip_id_or_file> --interactive
```
Interactive commands:
- `/crosscheck [day]` - Run two-round data cross-check
- `/debate <topic>` - Debate a choice
- `/history` - View previous conversational turns
- `/clear` - Reset session memory

---

## 4. Conversational Synthesis Format

When presenting council insights back to the user in chat, synthesize the conversational exchange naturally:

```markdown
### 🏛️ Council Co-Planning: [Topic / Question]

> *I conferred with Claude and DeepSeek to cross-check this decision.*

#### 🎭 Claude's Take (Experience & Culture)
[Concise summary of Claude's perspective, emphasizing cultural nuances, opening hours, or pacing]

#### 🧠 DeepSeek's Take (Logistics & Transit)
[Concise summary of DeepSeek's perspective, emphasizing transit buffers, routing logistics, or timing conflicts]

#### ⚔️ Cross-Talk & Peer Review
- **Points of Agreement**: Where both models verified the data.
- **Key Divergence / Trade-offs**: Nuances where their perspectives differed.

#### ⚖️ Antigravity Recommendation
[Specific vetted recommendation for the Wanderlog itinerary]
```

---

## 5. Important Safety Invariant

> [!IMPORTANT]
> **Trip Mutation Confirmation**:
> External AIs may suggest changes (e.g., swapping activities, moving dates, adjusting dining).
> **Always ask the user for confirmation** before making any mutations to the Wanderlog trip via MCP tools!
