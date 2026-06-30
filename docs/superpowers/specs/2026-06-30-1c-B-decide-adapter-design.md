# Phase 3 Slice 1c-B: state-driven `decide` adapter — Design

**Goal:** Let the rollout get a `JointAction` from the existing heuristic **for either
side, from a raw `BattleState`** — without duplicating decision logic and without
reverse-decoding the wire format. Two parts: (1) extract a behavior-preserving decision
core that returns the `JointAction`; (2) synthesize a minimal request-shaped view from a
`BattleState` (+ caller-supplied roster/movesets/stats) and call the core.

**Status:** brainstorming, 2026-06-30, branch `phase3-1c-simulator-teacher`. Baseline:
1c-A done (`learning/simulator.py` `clone_state` + `apply_outcome_to_state`). Do NOT touch
the H-loop (1c-C) or the opponent belief source (1c-D) here.

## Part 1 — extract a behavior-preserving decision core (`battle/decision.py`)
The heuristic computes `best_ja` (a `JointAction`) and only at the very end encodes it to
a wire string (`decision.py:441`). Extract that:

```
_choose_best_ja(req, *, state, ...) -> JointAction      # everything up to best_ja (incl. _maybe_tera + trace=)

heuristic_choose_for_request(req, ...):
    if req.team_preview:
        return encode_team_preview(...)                 # stays in the wrapper
    best_ja = _choose_best_ja(req, ...)
    return encode_choose(best_ja.as_pair(), rqid=req.rqid)
```

The heuristic stays the **single source of truth**; the wrapper only encodes. `decide`
later calls the same core and receives the `JointAction` directly — no wire decode, no
trace recovery.

**Equivalence gate (the most important test):** for representative requests,
`encode_choose(_choose_best_ja(req).as_pair(), rqid=req.rqid) == heuristic_choose_for_request(req)`,
and all existing decision/gauntlet tests stay green (behaviour identical before/after).

## Part 2 — `synthesize_request` (belief-agnostic, `learning/`)
`synthesize_request(state, side, *, roster, movesets, stats, move_meta) -> BattleRequest`.

**Minimal required request schema (pin — populate EXACTLY the fields the current heuristic
reads, not a full server request):** the fields consumed by `enumerate_my_actions`,
`_choose_best_ja`, target resolution, tera logic, and the speed/move-metadata hooks:
- `side.id = side`.
- `side.pokemon`: one `PokemonSlot` per active mon (`state.sides[side]`) + per bench mon
  (from `roster`, in the **caller-provided roster order** — deterministic). Each carries
  `details` (species), `condition` (from `hp`/`max_hp`/`fainted`, formatted `cur/max` or
  `0 fnt`), `active`, `stats.spe` (from `stats`), `moves` (ids).
- `active`: one `ActiveSlot` per active living mon — `moves` = `MoveSlot`s (each with the
  move id + `target` resolved via `move_meta`), `can_terastallize` (from the mon's tera
  availability), `trapped` (default False).
- `force_switch`: derived from fainted active slots (see rule below).
- `rqid`: a **deterministic synthetic** id (`f"rollout-{state.turn}-{side}"` or `0`) — the
  rollout doesn't talk to a server; only the wrapper/test encode needs it.
- `team_preview = False`.

**`force_switch` rule (pinned):** a fainted active slot sets `force_switch[slot]=True`; for
a force-switch slot the legal actions are **switch-only** (no normal move action for that
slot). If no legal switch exists, the existing enumeration's pass/no-op sentinel is allowed
**only if `enumerate_my_actions` already supports it** (we reuse its behaviour, not invent).

**Deterministic order:** bench/switch order comes from the caller-provided `roster` order;
switch `target_ident`s are stable across rollout steps ⇒ reproducible `JointAction`s
(stable `move_index`/switch choices).

## Part 3 — `decide` adapter (belief-agnostic, `learning/`)
```
decide(state, side, *, roster, movesets, stats, deps) -> JointAction:
    req = synthesize_request(state, side, roster=roster, movesets=movesets, stats=stats, ...)
    return _choose_best_ja(req, state=state, our_side=side, **deps)
```
Works for **both sides** immediately. The caller supplies roster/movesets/stats: for OUR
side these are the known team (from the real request); for the OPPONENT side they are the
belief (likely_sets/curated) — supplied later by 1c-C wiring / 1c-D.

## Negative scope (hard — protects limited-view)
- **1c-B NEVER sources opponent hidden bench/sets from `BattleState` ground truth.** The
  caller MUST pass `roster`/`movesets`/`stats`. For the opponent side these inputs come
  later from 1c-D (belief/likely_sets), not from hidden truth.
- No H-loop, no opponent belief source, no model/training/reranker here.

## Tests (hermetic, no Node)
- **Core equivalence (primary gate):** `encode(_choose_best_ja(req)) ==
  heuristic_choose_for_request(req)` on representative fixtures; existing tests stay green.
- **synthesize_request validity:** the synthesized request is accepted by the core —
  `enumerate_my_actions` yields ≥1 action; `decide` returns a `JointAction`.
- **decide returns a usable action:** `decide(state, side, roster=.., movesets=.., stats=..)`
  returns a `JointAction` **accepted by `resolve_turn`** (the simulator can consume it).
- **Both sides:** decide works for our side (known roster) and the opponent side (a fake
  roster), purely from passed-in inputs.
- **Determinism:** identical `(state, side, roster, movesets, stats)` ⇒ identical `JointAction`.
- **force_switch synthesis:** a fainted active slot produces `force_switch=True` and **no
  normal move action** for that slot (switch-only).
- **No hidden roster read:** `synthesize_request` for a side without caller-supplied
  roster/movesets/stats either raises or emits documented sentinels — it never reads a
  hidden opponent bench/set from the state.

## File structure
- Modify (behavior-preserving): `battle/decision.py` (extract `_choose_best_ja`, wrapper).
- Create: `learning/decide_adapter.py` (`synthesize_request`, `decide`).
- Tests: `tests/test_decide_core_equivalence.py`, `tests/test_decide_adapter.py`.
