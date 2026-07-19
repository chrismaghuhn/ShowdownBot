# VGC Showdown Bot — Design Spec

**Date:** 2026-06-29  
**Status:** Approved  
**Scope:** Solo hobby project, RTX 4060 Ti 8 GB, Python/PyTorch, custom Showdown protocol client

---

## Goal

Build a competitive Pokémon Showdown **VGC Doubles** bot with a fixed team MVP, ladder-testable, extensible to multiple formats and team switching. Long-term target: high ladder rating (e.g. Top 100). Quality over speed; 6+ month horizon.

---

## Architecture (Hybrid)

```
Preview Agent
        ↓
Battle Loop:
  Set-Belief-Tracker (mixed Worst-Case)
        ↓
  Policy Net (Imitation → Self-Play RL)
        ↓
  Local Search (Damage-Calc, depth 1–2)
        ↓
  Fusion (Bias + Conditional Override)
        ↓
  Showdown Client
```

### Module boundaries

| Module | Input | Output |
|--------|-------|--------|
| **Showdown Client** | Protocol messages | Parsed `BattleState`, legal actions, `/choose` commands |
| **Format Config** | Regulation ID | Legal species, mechanics, meta paths |
| **Preview Agent** | 6v6 visible teams | Bring 4 + lead order |
| **Belief Tracker** | Observations, damage, speed | Set hypotheses, `game_mode`, belief features |
| **Policy Net** | obs + belief_summary | Action logits over legal slot-pairs |
| **Search** | state, beliefs, legal pairs | `search_score` per pair |
| **Fusion** | policy scores + search scores | Final slot-pair action |

---

## Decisions (Locked)

| Topic | Decision |
|-------|------------|
| Base stack | Custom Showdown client; **no** poke-env / existing bot framework as foundation |
| Hidden info | **Mixed Worst-Case:** defensive spreads when ahead; offensive when must-KO |
| Fusion | **Bias** default + **Conditional Override** for clear must-KO |
| Protect in Search | **C with Fallback B:** replay/meta priors; fallback fixed penalty if no data |
| Search unit | **Slot-pairs**, Top-16 candidates, depth 1 (depth 2 later) |
| MVP team | **Fixed team**; preview/search/policy parameterized for later team swap |
| Training | **Replays first** (imitation), then **self-play** RL fine-tune |
| Multi-format | Shared engine + **format YAML** for rules and meta priors |

---

## Belief & Game Mode

- **`ahead`:** Max-defense opponent assumptions for survival; lower KO aggression
- **`must_react`:** Min-defense / max-offense for KO checks; override eligible
- **`neutral`:** Blended weights

Belief updates from: damage dealt/taken, move order, item triggers, revealed moves.

---

## Search Score (MVP Features)

Per legal slot-pair:

- `ko_value` (with `p_protect` adjustment)
- `survive_next`, `switch_safety`, `protect_value`
- `wasted_target`, `slot_conflict` (hard filter)
- Mode-specific linear combination (weights tunable from ladder/replays)

**Protect (`p_protect`):** battle observations → species/meta YAML → fallback (healthy + no priority → ~0.35, else ~0.15).

---

## Fusion Rules

**Default:**  
`final_score = w_policy * policy + w_search * search` (weights depend on `game_mode`)

**Override only if:**  
`game_mode == must_react` AND adjusted `ko_value > 0.9` AND clear margin vs #2 AND policy veto false.

---

## Training Plan

1. **Imitation:** VGC replays → `(state, action)`; 1–3M param policy; FP16 on 4060 Ti
2. **Self-play:** PPO (or similar) with fusion in the loop; win/loss primary reward
3. **No** LLM as primary agent; optional offline assist only

---

## Multi-Format

Shared: protocol client, state schema, action encoder, calc wrapper, belief logic, training infra.  
Per-format: regulation config, meta protect priors, preview heuristics, team pool.

---

## Out of Scope (MVP)

- MCTS-light (Phase 5 optional)
- Dynamic team building / multiple teams in production
- Top-100 as MVP exit criterion

---

## Phase Plans

| Phase | Plan file |
|-------|-----------|
| 0 — Showdown Client | `docs/projects/core-bot/plans/2026-06-29-phase0-showdown-client.md` |
| 1 — Game Engine | `docs/projects/core-bot/plans/2026-06-29-phase1-game-engine.md` |
| 2 — Heuristic Bot | `docs/projects/core-bot/plans/2026-06-29-phase2-heuristic-bot.md` |
| 3 — Imitation | `docs/projects/core-bot/plans/2026-06-29-phase3-imitation.md` |
| 4 — Self-Play RL | `docs/projects/core-bot/plans/2026-06-29-phase4-self-play.md` |
| 5 — Scale | `docs/projects/core-bot/plans/2026-06-29-phase5-scale.md` |

---

## References (External)

- [poke-env](https://github.com/hsahovic/poke-env) — observation/action reference only
- [Metamon](https://github.com/metamon-ai/metamon) — RL Showdown bot reference
- [Foul Play](https://github.com/pokebattler/foul-play) — heuristic bot (not VGC)
- PokéLLMon — LLM agent (not competitive ladder target)
- Smogon `@smogon/calc` — damage calculation
