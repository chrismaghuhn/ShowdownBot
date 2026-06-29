# Merge description — HeuristicBot: move/condition system, correct models, play-quality

_Branch `docs/heuristic-moves-conditions-spec` → `main`. Use as the PR body._

## Summary

Brings the one-ply HeuristicBot from "loses every game to a damage-maximizer
(0/16)" to a coherent bot with **principled, correct models on both sides**
(own real sets + opponent likely-sets + speed truth) and no visible decision
pathologies. Built via spec → plan → TDD, full suite green (259). Performance is
~30–37% vs `max_damage` in the local mirror — a guardrail, not a rating (see
[benchmarking.md](benchmarking.md)). Also lands **Phase 3 slice 1a** — an
isolated `learning/` package (ML data contract + counterfactual teacher) with **no
`battle/` changes** (see below).

## What changed

- **Move/condition system** — data-driven `MoveMeta`/`ItemMeta` generated from
  `@pkmn/dex`, a decoupled `ConditionEngine`, and a bounded multi-turn condition
  rollout (ratio model, no double-counting).
- **Own-team truth** — `apply_own_team_knowledge` (item precedence: live request
  tri-state > protocol events / `item_lost` > packed-team fallback), real own
  spreads in the `DamageModel`, **speed truth** (`SpeedOracle.likely_speed`;
  Choice Scarf now actually known), speed ties as expected value.
- **Opponent realism** — curated `likely_sets.yaml` → `opp_sets`: realistic
  damage spread *and* speed instead of worst-case in every dimension at once;
  revealed-info precedence; worst-case fallback for un-curated species.
- **Play-quality fixes** — contextual Protect stall/endgame/abandon penalty;
  prune dead Fake Out; opponent best-move by damage (type-aware).
- **Tooling** — decision diagnostics (metrics + turn trace), local gauntlet and
  heuristic-vs-heuristic self-play, A/B env knobs.
- **Phase 3 slice 1a (ML foundation, isolated)** — new `src/showdown_bot/learning/`:
  `schema.py` (frozen 4-group feature/metadata/label contract + strict
  validate-on-write JSONL) and `teacher.py` (fixed-horizon counterfactual rollout
  teacher: no-double-count return, H=0==one-ply, within-decision dual
  heuristic/teacher labels). Pure + injectable (`decide`/`resolve`/`leaf`) →
  unit-tested with fakes, **no Node/calc, no `battle/` or `decision.py` changes**.
  The invasive slice 1b (real feature extraction + self-play export) is a separate,
  design-first follow-up.

## Bugs found & fixed

- `merge_request` never set our own item despite its docstring — so our **Choice
  Scarf was never known** and our speed was under-rated 1.5×. Fixed (now owned by
  `apply_own_team_knowledge`).
- The bot chose **dead Fake Out** in the endgame (`moved_since_switch`) — a
  guaranteed wasted turn every other turn. Pruned.
- A fainted active slot with no replacement stalled the game ("more choices than
  unfainted Pokemon"); side-only moves (Tailwind) were given an illegal foe
  target. Both fixed.
- Targeting was *verified correct* against the server source (`getAtLoc`) — a
  suspected mirror bug was refuted.

## Benchmarks (final test matrix)

| Check | Result |
|---|---|
| `pytest` (full suite) | **259 passed** (237 heuristic + 22 learning slice-1a) |
| learning slice-1a units | schema 10 + teacher 12, pure/fake (no Node/calc) |
| lint | no linter configured in `pyproject` (tests are the gate) |
| gauntlet vs `max_damage` (full stack) | 4–6/16, **invalid_choices=0, crashes=0** |
| 30-game confirm (earlier stack) | 9/30 ≈ 30% (small-N) |
| self-play (heuristic-vs-heuristic) | ~50% symmetric (18/38), no crashes |
| A/B knobs on/off | all bit-identical-when-off, clean |

Key A/B levers: Protect penalty (4→8/16, endgame-Protect 46%→17%); opponent
likely-sets (0→6/16, predicted-incoming −40%, AHEAD 0%→32%). Non-lever: MUST_REACT
λ tuning. See [benchmarking.md](benchmarking.md) for the full levers table.

## Why `max_damage` is not optimized further

The mirror-vs-`max_damage` benchmark **rewards recklessness** — correct, cautious
modeling can lose it (a crude over-confident proxy *beat* correct real spreads
11/24 vs 2/24). It is a great **bug detector** but a misleading **fine-tuning
target**. Further scalar tuning against it is explicitly out of scope.

## Deliberately open

- The one-ply heuristic + worst-case-ish eval has a ceiling here; the path past
  ~37% is **structural** (learn the caution-vs-aggression balance from outcomes).
- Further hand-built heuristic slices (opponent moves, team preview) would be
  *modest* like the speed slice.
- See [next_steps.md](next_steps.md): consolidate/merge, **Phase 3 learned
  reranker**, or finalize the brain document.

## Test plan

- [ ] `cd showdown_bot && python -m pytest -q` → 259 passed.
- [ ] `node pokemon-showdown start --no-security` on :8000, then a 2-game gauntlet
      `--format gen9vgc2024regg` → completes, `invalid_choices=0 crashes=0`.
