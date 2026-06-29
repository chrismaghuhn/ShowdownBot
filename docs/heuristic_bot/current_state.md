# HeuristicBot — current state

_As of 2026-06-29, branch `docs/heuristic-moves-conditions-spec`. Companion docs:
[benchmarking.md](benchmarking.md) (how to measure), [next_steps.md](next_steps.md)._

## Architecture (one-ply heuristic)

Per decision: `enumerate_my_actions` (candidate joint actions) →
`predict_responses` (a small set of plausible opponent responses) + `DamageModel`
(prefetched `@smogon/calc` via a Node bridge) → `evaluate_line` (`resolve_turn` +
`score_outcome`, optional condition rollout) → `pick_best` (game-mode-aware:
MUST_REACT / NEUTRAL / AHEAD). A belief layer supplies spreads, protect priors,
and the curated opponent likely-sets.

## What is built

- **Move/condition system** — data-driven `MoveMeta`/`ItemMeta` (generated from
  `@pkmn/dex`), `ConditionEngine`, a bounded multi-turn condition rollout (ratio
  model, no double-count).
- **Own-team truth** — `apply_own_team_knowledge` (item precedence: live request
  tri-state > protocol events / `item_lost` > packed-team fallback, never
  resurrecting a lost item); real own spreads in the `DamageModel`; **speed
  truth** (`SpeedOracle.likely_speed` + our own Choice Scarf finally known, which
  `merge_request` never set — a fixed bug); speed-tie expected value.
- **Opponent realism** — curated `config/formats/meta/likely_sets.yaml` →
  `opp_sets`: realistic damage spread *and* speed instead of worst-case in every
  dimension; revealed-info precedence; worst-case fallback for un-curated species.
- **Play-quality fixes** — contextual Protect stall/endgame/abandon penalty;
  prune dead Fake Out when `moved_since_switch`; fainted-slot-passes and
  side-move-targeting fixes; opponent best-move by damage (type-aware).
- **Tooling** — decision diagnostics (metrics + readable turn trace), a local
  gauntlet and a heuristic-vs-heuristic self-play harness.

## A/B knobs (env)

`SHOWDOWN_OPP_SETS`, `SHOWDOWN_OPP_SPEED`, `SHOWDOWN_PROTECT_PENALTY`,
`SHOWDOWN_REAL_SPREADS`, `SHOWDOWN_OUR_DEF_PRESET`, `SHOWDOWN_MUST_REACT_LAMBDA`,
`SHOWDOWN_OUR_ROLL`, `SHOWDOWN_ROLLOUT_HORIZON`, `SHOWDOWN_TURN_TRACE`,
`SHOWDOWN_DECISION_DIFF`. Each gates one change so on/off is bit-identical except
that change.

## Tests & performance

- Full suite green (237 tests at time of writing).
- ~30–37% vs `max_damage` in the local mirror gauntlet with **principled correct
  models on both sides** — but this number is a **guardrail, not a rating**
  ([benchmarking.md](benchmarking.md) explains why the mirror benchmark rewards
  recklessness). No visible pathologies remain.

## Deliberately open

The one-ply heuristic with a worst-case-ish eval has a ceiling here. The next
gains are structural (learning the caution-vs-aggression balance from outcomes),
not more eval hand-tuning — see [next_steps.md](next_steps.md).
