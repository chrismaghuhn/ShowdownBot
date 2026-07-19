# VGC Showdown Bot — Plan Index

> **For agentic workers:** Start with Phase 0. Each phase plan is self-contained and produces testable software before the next phase begins.

**Goal:** Competitive VGC Doubles bot on Pokémon Showdown — fixed team MVP → imitation → self-play → multi-format.

**Architecture:** Custom protocol client + offline engine (calc/belief) + hybrid decision stack (preview, policy, search, fusion).

**Tech Stack:** Python 3.11+, PyTorch (Phase 3+), pytest, websockets, pydantic, PyYAML, Node.js + `@smogon/calc` (Phase 1+)

**Design spec:** `docs/projects/core-bot/specs/2026-06-29-vgc-showdown-bot-design.md`

---

## Phase Overview

| Phase | Plan | Duration | Exit criterion |
|-------|------|----------|----------------|
| **0** | [phase0-showdown-client.md](./2026-06-29-phase0-showdown-client.md) | 3–5 weeks | 10 ladder games, no illegal moves |
| **1** | [phase1-game-engine.md](./2026-06-29-phase1-game-engine.md) | 3–4 weeks | Calc matches logs in >95% obvious KOs |
| **2** | [phase2-heuristic-bot.md](./2026-06-29-phase2-heuristic-bot.md) | 4–6 weeks | Ladder ~1200–1400, debuggable turns |
| **3** | [phase3-imitation.md](./2026-06-29-phase3-imitation.md) | 6–8 weeks | Policy beats heuristic on hold-out replays |
| **4** | [phase4-self-play.md](./2026-06-29-phase4-self-play.md) | 8–12 weeks | Self-play improves win rate vs Phase 3 bot |
| **5** | [phase5-scale.md](./2026-06-29-phase5-scale.md) | ongoing | Multi-format + team pool + optional MCTS |

---

## Locked Decisions (all phases)

- Custom Showdown client (no poke-env as foundation)
- Mixed Worst-Case belief (`ahead` / `must_react` / `neutral`)
- Fusion: Bias + Conditional Override
- Protect in search: meta/replay priors with Fallback B
- Search evaluates **slot-pairs**, not independent slots

---

## Execution

**Phase 0 plan is ready for implementation.** Phases 1–5 plans define tasks; Phase 1+ code depends on Phase 0 interfaces.

**Recommended:** Subagent-driven development — one subagent per Phase 0 task, review between tasks.

**Which phase to implement?** → Always the lowest-numbered phase whose exit criterion is not yet met.
