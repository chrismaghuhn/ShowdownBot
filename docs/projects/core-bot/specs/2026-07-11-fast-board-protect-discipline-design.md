# Fast-Board Protect Discipline — a play-quality lever attempt aimed by the disagreement atlas

**Status:** acting on the teacher-disagreement atlas finding (merged `5830e9e`). The atlas found
the heuristic disagrees with the rollout teacher **92%** of the time in `tailwind_both`
(both-sides-Tailwind) boards, highest regret — confirmed from the dataset actions to be residual
**over-defensiveness**: Protect-spam (`protect+protect → aggressive line`) and failure to pivot
(`stay+knockoff → switch to the best attacker`) in FAST boards. See memory
`tailwind-both-overdefensiveness.md` + `play-quality-levers.md` (the historic Protect-stall
penalty was the single biggest lever, 0→8/16).

## What this slice attacks — and what it does NOT

The disagreements split into two mechanisms:
1. **Protect-spam in fast boards** — TUNABLE via valuation (this slice). A fast board (both sides
   accelerated) makes a wasted Protect turn more costly; the heuristic over-values Protect safety.
2. **Failure to pivot to the best attacker** (`stay+move → switch to Flutter Mane`) — a one-ply
   DEPTH gap (the switch costs tempo now, pays over later turns the one-ply resolver can't see).
   NOT tunable with a valuation tweak; belief/search territory. Explicitly out of scope.

This slice is a **bounded attempt at mechanism 1**, with an honest either-way outcome: if it
reduces the atlas's tailwind_both disagreement (and the over-defensive habit) it is a real lever
like the historic one; if it barely moves, that is strong evidence the tailwind_both gap is
depth-bound → concrete motivation for belief/search. Both results are worth having.

## Change (mirrors the existing `endgame` Protect mechanism exactly)

`battle/evaluate.py::score_outcome_with_breakdown` already takes a contextual `endgame: bool` and
applies `endgame_protect` when we Protect in the endgame. Add a parallel **`fast_board: bool`**
context + a `fast_board_protect` weight: when we Protect on a fast board AND the Protect blocked
nothing (the same "wasted tempo" condition the existing `protect_stall` uses), apply the extra
penalty. `fast_board` = both sides have Tailwind up (from `state.field.tailwind`), computed by the
caller (`battle/decision.py`, where `endgame` is already computed) and threaded through
`evaluate_line`/`score_outcome` like `endgame`.

**Env-gated, off = byte-identical.** New weight defaults to 0.0 (no effect) unless
`SHOWDOWN_FAST_BOARD_PROTECT_PENALTY` sets it (classified in `config_env.py`, like the historic
`SHOWDOWN_PROTECT_PENALTY`). With the env unset, every score is unchanged → the 2b-2.5a dataset,
the atlas, and all recorded runs stay valid; every existing test stays green.

## Measurement (aimed by the atlas — the principled gauge, chosen by the user)

Winrate-vs-max_damage is a CONFOUNDED gauge here (play-quality-levers: that benchmark rewards
recklessness, so "be more aggressive" spuriously wins). The teacher-disagreement atlas is the
principled gauge — the teacher is a fixed reference of better play, not a reckless opponent.

1. **Behavioral cross-check (light):** a Kaggle A/B gauntlet (flag off vs on) over a
   both-Tailwind-inducing panel; use the diagnostics-v0 `bucket_delta` (does the hero's Protect /
   over-defensive habit drop?) + winrate as a sanity signal.
2. **Atlas re-measure (principled):** a focused both-Tailwind datagen re-label with the flag ON,
   re-run `teacher_disagreement` on it, and compare the `tailwind_both` disagreement rate / mean
   regret against the committed 92% / 9.19 baseline. A drop = the lever works; flat = depth-bound.

## Non-goals

The pivot-depth mechanism (mechanism 2); any change when the env is unset; touching the committed
dataset/atlas (they are the fixed baseline). No new features for the reranker.

## Testing strategy

Unit tests (local, no battles): on a both-Tailwind fixture outcome where we Protect and block
nothing, `score_outcome(..., fast_board=True)` with the weight set scores strictly lower than with
it unset; single-Tailwind / no-Tailwind boards are unchanged; a Protect that BLOCKS a hit on a
fast board is NOT extra-penalized (only wasted Protects); env unset → byte-identical scores
(golden). The `fast_board` derivation (both sides Tailwind) unit-tested from a FieldState fixture.
The Kaggle A/B + atlas re-measure are controller-orchestrated (battles).
