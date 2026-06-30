# Phase 3, Slice 1c: internal turn-simulator (for real counterfactual labels) — Design

**Goal:** Build the internal turn-simulator that lets the slice-1a teacher run a real
fixed-horizon counterfactual rollout, producing **trainable** silver labels (replacing
the `stub-h0` placeholder from 1b). Decomposed hard into 4 subslices; this spec details
**1c-A** (the foundational state primitive) and sketches 1c-B/C/D.

**Status:** brainstorming, 2026-06-30, branch `phase3-1c-simulator-teacher`. Baseline:
`main` has 1a (`learning/schema.py`, injectable `teacher.py`) + 1b (DecisionTrace
capture, `features.py`, deterministic `DatasetExporter`, env-gated JSONL).

## Decomposition (hard cut)
- **1c-A — `apply_outcome_to_state` + state clone** (this spec, in detail).
- **1c-B — state-driven `decide` adapter:** run the heuristic from a raw `BattleState`
  (not a server `BattleRequest`) for BOTH sides → the rollout primitive `decide(state, side)`.
- **1c-C — H-step rollout wiring:** bind the 1a teacher's injectable `decide`/`resolve`/
  `leaf` to the real simulator (resolve_turn → apply → next state, H follow-ups), feed
  `counterfactual_value` + `label_decision`.
- **1c-D — limited-view boundaries + safety tests:** the opponent plays its
  realistically-limited view in the rollout; the opp roster/bench is the believed team
  (curated likely_sets), never ground truth.

Each subslice is its own plan + TDD cycle. No model / training / reranker in any of 1c.

---

## 1c-A: `apply_outcome_to_state` + state clone

**Location + dependency:** new `src/showdown_bot/learning/simulator.py` — depends on
`battle/` types (`BattleState`, `TurnOutcome`, `PokemonState`, `FieldState`) and reuses
`battle/resolve.resolve_turn` (NOT rebuilt). `learning → battle` (allowed); rollout-only
mechanics stay out of the live battle path.

**`clone_state(state: BattleState) -> BattleState`** — `copy.deepcopy`. Correct + simple
(`BattleState` is nested dataclasses). Deterministic (no RNG). Perf optimized later only
if the rollout proves slow.

### PINNED: `TurnOutcome.hp_delta` is a FRACTION in `[-1.0, 1.0]`
Verified against the source, not assumed: `resolve.py:311`
`outcome.hp_delta[key] = cur_frac[key] - start_frac[key]`, where `cur_frac` is fractional
HP and `damage_fn` returns `roll / max_hp ∈ [0,1]` (`evaluate.py`). So
`apply_outcome_to_state` does **one** normalization: `new_frac = clamp(cur_frac + delta,
0.0, 1.0)`. A unit test pins it: `hp_fraction=0.75, hp_delta=-0.40 ⇒ hp_fraction=0.35`.

### `apply_outcome_to_state(state, outcome, actions_by_side, *, roster_by_side) -> BattleState`
Returns a **new** state (clone first); the input `state` is never mutated. Applies ONLY
what `TurnOutcome` explicitly encodes:

| Step | Source | Rule |
|---|---|---|
| **HP** | `outcome.hp_delta` (fraction, pinned above) | `new_frac = clamp(cur_frac + delta, 0.0, 1.0)`; set `mon.hp = round(new_frac * mon.max_hp)` when `max_hp` is known. |
| **Faints** | resulting `hp_frac <= 0` and/or explicit faint flags `resolve_turn` emits | `hp <= 0 ⇒ fainted=True`; explicit faint flags also set `fainted=True`. |
| **Field** | ONLY the exact flag strings `resolve_turn` currently emits (`status:<move_id>:<owner>`) | supported field move_ids (tailwind / trickroom / weather / terrain, resolved via `MoveMeta`) mutate `FieldState`; **unknown flags are ignored** (no invented parsing). |
| **Switch** | `actions_by_side` (which active slot switches + `target_ident`) + `roster_by_side` (authoritative lookup) | place the roster's target mon into the switching active slot; **deep-copy the mon on switch-in** so later mutations can't corrupt the roster; `moved_since_switch=False`. |

### Pinned precisifications (per review — for the plan)
1. **`actions_by_side` shape:** `dict[str, JointAction]` — a `JointAction` with
   `slot0`/`slot1` `SlotAction`s; `slot0` ↔ active slot `"a"`, `slot1` ↔ `"b"`. Only a
   `SlotAction.kind == "switch"` triggers switch application (move/pass don't).
2. **Missing roster target = fail-fast:** if a switch action's `target_ident` is not in
   `roster_by_side[side]`, `apply_outcome_to_state` **raises `ValueError`** (never silently
   ignores) — a mis-wired rollout roster/belief must surface immediately.
3. **HP representation stays consistent:** `PokemonState.hp_fraction` is a *derived
   property* (`hp / max_hp`), so updating `mon.hp` is sufficient when `max_hp` is known. If
   `max_hp` is `None`, set a synthetic `max_hp = 100` first so the fraction is representable
   (documented v1 approximation). After apply, `hp` and `hp_fraction` must agree.
4. **Field parsing stays minimal:** 1c-A supports ONLY the status flags actually emitted by
   `resolve_turn`/observed in source+tests. **Required: `tailwind`, `trickroom`.**
   weather/terrain are supported **only if** `resolve_turn` truly emits status flags for
   those move_ids AND `FieldState` already models them — no generic MoveMeta magic in 1c-A.

### Hard non-goals for 1c-A (NO end-of-turn simulation)
`apply_outcome_to_state` applies only what `TurnOutcome` contains — explicitly NOT:
no residual damage, no weather chip, no status tick, no duration decrement, no forced
replacement after a faint, no PP changes, no item consumption (unless the `TurnOutcome`
already encodes it). Those belong to a later simulator slice, not this primitive.

### Switch identity rule (pinned)
`actions_by_side[side]` identifies which active slot switches and which `target_ident` /
species comes in. `roster_by_side[side]` is the authoritative `ident/species ->
PokemonState` lookup (its SOURCE — our request vs the opponent's believed team — is 1c-D,
NOT here). The switched-in mon's own `fainted`/`hp`/`status` are preserved as-is from the
roster; only `moved_since_switch` is reset. The switch-in mon is deep-copied into the
state (no shared mutable ref with the roster).

### Tests (deterministic, hermetic — no Node)
1. **Clone independence / snapshot** — mutating the clone never touches the original (deep).
2. **No mutation of input** — `apply_outcome_to_state` returns a new state and leaves the
   input `state` byte-unchanged (compare a pre-snapshot).
3. **HP unit** — `hp_fraction=0.75 + hp_delta=-0.40 ⇒ 0.35`; clamp at `[0,1]`; faint at `<=0`.
4. **Field** — a `status:tailwind:p1a` flag sets `FieldState.tailwind["p1"]`; a
   `status:trickroom:*` flag toggles `trick_room`.
5. **Unknown flag ignored** — an unrecognized outcome flag neither crashes nor mutates state.
6. **Switch** — active slot `a` switches to bench ident `X`: new active mon is `X`,
   `moved_since_switch=False`, `X`'s hp/status preserved.
7. **Switch does not alias the roster** — mutating the switched-in mon in `next_state` does
   NOT mutate the `roster_by_side` entry (deep-copied on switch-in).
8. **Determinism** — identical `(state, outcome, actions, roster)` ⇒ identical `next_state`.

---

## 1c-B/C/D — outlook (separate specs/plans)
- **1c-B (state-driven decide):** the live heuristic is request-driven
  (`heuristic_choose_for_request(req, ...)`). The rollout needs `decide(state, side)`. 1c-B
  synthesizes the legal-action set + the per-side view from a raw `BattleState` (likely by
  building a minimal request-shaped view), so the heuristic can decide for either side at
  any rollout depth.
- **1c-C (H-loop):** bind the 1a teacher's injectable `decide`/`resolve`/`leaf` — `resolve`
  = `resolve_turn` + `apply_outcome_to_state`; `decide` = 1c-B; `leaf` = the one-ply
  aggregate. Drives `counterfactual_value` + `label_decision`; swaps `stub-h0` for the real
  label. Cost-managed (sampling, bounded H/K) — strictly offline.
- **1c-D (limited-view):** the opponent decides on its realistically-limited view; the opp
  `roster_by_side` is the believed team (curated likely_sets), never ground truth. Safety
  tests assert the rollout never reads hidden opponent info into our decision.
