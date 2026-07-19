# Phase 3 Slice 1c-D: limited-view-safe opponent belief — Design

**Goal:** Give the rollout teacher (1c-C `rollout_labels`) a **limited-view-safe** way to
build the `roster`/`movesets`/`stats` a side needs, so the opponent in the rollout plays a
**prior-based belief** — never hidden ground-truth bench/sets. This turns 1c from "works if
the caller passes a fake belief" into "simulator teacher with a limited-view-safe opponent
belief", the proper merge point.

**Status:** brainstorming, 2026-06-30, branch `phase3-1c-simulator-teacher`. Baseline: 1c-A
(`apply_outcome_to_state`) + 1c-B (`decide`/`synthesize_request`) + 1c-C (`rollout_labels`
H-loop), suite 365 green. After 1c-D: review the whole branch + no-ff merge to `main`.

## The contract the rollout consumes
`synthesize_request`/`decide` (1c-B) take, **per side**: `roster` = `dict[ident ->
PokemonState]` (BENCH mons only; actives come from `state.sides[side]`), `movesets` =
`dict[ident|species -> list[str]]`, `stats` = `dict[ident|species -> dict[str,int]]` (≥
`{"spe": ...}`). 1c-D produces these for both sides — **ours from the known team, the
opponent's from belief**.

## Architecture — two explicit builders + a thin dispatcher (limited-view is *structural*)
The opponent builder is a separate function whose **parameter list proves** it cannot read
our team or hidden truth. A future refactor can't accidentally pull hidden data into the
opponent branch (the failure mode of a single shared function body).

```python
def build_known_side(team) -> BeliefSide:
    """Our side: the full known team (`team` = our real team data the bot already threads —
    our_sets/packed team). roster=bench, movesets, stats all from the known set."""

def build_opponent_belief(
    state, opp_side, *, likely_sets, move_priors,
    dex=None, book=None, speed_oracle=None,    # PUBLIC priors only
) -> BeliefSide:
    """Opponent side: active-only, prior-based. No known_team, no hidden bench."""

def build_belief_for_side(
    state, side, *, our_side, known_team, likely_sets, move_priors,
    dex=None, book=None, speed_oracle=None,
) -> BeliefSide:
    """Thin dispatcher: side == our_side -> build_known_side; else -> build_opponent_belief."""
```

**The safety invariant (one sentence):** *the opponent belief reads only revealed active
state + public priors.* It is NOT "no deps" — public `dex`/`book`/`speed_oracle` are fine;
the line is **no `known_team`, no hidden opponent bench/sets**.

## The `BeliefSide` DTO
```python
@dataclass(frozen=True)
class BeliefSide:
    roster: dict[str, PokemonState]        # bench (opponent: always {})
    movesets: dict[str, list[str]]         # ident|species -> ordered move ids
    stats: dict[str, dict[str, int]]       # ident|species -> {"spe": int, ...}
    quality: dict[str, tuple[str, ...]]    # ident -> belief-quality flags
```
- `quality` is a **cheap provenance hook**, not YAGNI: silver labels built on weak fallbacks
  must be distinguishable from confident ones later. Value is a **`tuple[str, ...]`** (not a
  single str) — a mon can carry several flags at once, e.g.
  `{"p2a": ("ok",), "p2b": ("no_move_prior", "weak_speed_fallback")}`. Tuple = deterministic +
  immutable. v1 flags: `"ok"`, `"no_move_prior"`, `"weak_speed_fallback"`. Nothing consumes
  `quality` in 1c-D (provenance only; a later export/debug slice may).
- **Immutability by convention:** `frozen=True` protects the attribute bindings, not the inner
  dicts/lists. The rule is **builders return fresh dict/list objects and nobody mutates a
  returned `BeliefSide`** — no shared mutation.

The caller assembles the per-side dicts trivially: `roster_by_side = {our_side: ours.roster,
opp_side: opp.roster}` (same for movesets/stats). The 1c-B/1c-C interface is untouched.

## Opponent belief rules (v1 — pinned)
**Roster (bench):**
- `roster = {}` — currently active **revealed** mons only; **empty bench**. No seen-memory, no
  curated full team. (The active mons live in `state.sides[opp_side]`, consumed by
  `synthesize_request`; the belief supplies their movesets/stats.)

**Movesets (the 6-step merge):**
1. **Revealed moves win** — start from the mon's revealed moves (from `state`).
2. **Fill** missing slots from `move_priors[species]` (the curated ordered prior).
3. **Dedupe** (keep first occurrence).
4. **Deterministic order** (revealed-in-state order, then prior order).
5. **Cap at 4.**
6. If neither a prior nor revealed moves exist → an explicit **documented weak fallback**: a
   single placeholder move (a named constant pinned in the plan) so `enumerate_my_actions`
   yields exactly one legal move action; `quality` gets `"no_move_prior"`.

**Stats (`spe`):**
- `stats[ident] = {"spe": <likely speed>}` from the `likely_sets`/species hypothesis, computed
  via the **existing `SpeedOracle.likely_speed`** (single source — no drift vs the live
  heuristic's opponent-speed model).
- If unavailable → a deterministic species/base/default fallback + `quality`
  `"weak_speed_fallback"`.

## `move_priors` — a NEW, SEPARATE data source
Kept distinct from `likely_sets` (which stays the **spread** source: nature/EVs/item). Mixing
them would tangle two different belief dimensions.
- **`move_priors.yaml`** in the format meta dir: `species_id -> ordered list of move ids`.
- **`load_move_priors(path) -> dict[species_id -> list[move_id]]`**, mirroring
  `load_likely_sets`: keys + move ids canonicalized via `to_id`; duplicate moves deduped
  deterministically; **missing file → `{}`** (not a crash — a thin/empty prior just means more
  mons get the `"no_move_prior"` quality flag).
- `load_move_priors_for_format(format_id)` mirrors `load_opp_sets_for_format` (`meta_path`).

## Limited-view safety contract + tests
The opponent builder must consume only revealed active state + public priors. Concretely
(pins the otherwise-vague test): **`build_opponent_belief` reads only the active slots from
`state.side(opp_side)` (the active accessor); any extra non-active/bench-like entries injected
into `state.sides[opp_side]` are ignored.**

Required tests:
1. **API guard:** `"known_team" not in inspect.signature(build_opponent_belief).parameters`
   (also no `team`/`full_roster`) — a structural regression guard.
2. Opponent `roster == {}`; movesets/stats keyed only by the revealed active mons.
3. **Hidden-bench-not-read:** inject an extra bench-like entry into `state.sides[opp_side]`;
   `build_opponent_belief` ignores it (only `"a"`/`"b"` actives consumed).
4. Revealed moves are preserved (and ordered first) in the merged moveset.
5. `move_priors` fill missing slots → dedupe → cap 4 (deterministic order).
6. Missing prior AND no revealed → the documented weak fallback + `quality` `"no_move_prior"`.
7. `build_known_side` includes the full known team (bench present, real movesets/stats).
8. `build_belief_for_side` dispatches: `our_side` → known builder, opp side → opponent builder.
9. Determinism: repeated calls with identical inputs → identical `BeliefSide`.
10. **Integration:** the produced `{side: BeliefSide.*}` triple is accepted by `decide` /
    `rollout_labels` (the "deterministic belief source for `rollout_labels`" deliverable) —
    WITHOUT swapping the stub teacher into the export.

`move_priors` loader tests: `to_id` normalization, dedupe, missing-file → `{}`, unknown/invalid
entries handled per `load_likely_sets`'s precedent.

## Decomposition (the plan will cut it)
- **1c-D1:** `engine/belief/move_priors.py` — `load_move_priors` + `load_move_priors_for_format`
  + a small curated `move_priors.yaml` + loader tests.
- **1c-D2:** `learning/belief_builder.py` — `BeliefSide` + `build_known_side` +
  `build_opponent_belief` (roster `{}`, 6-step moveset merge, spe via `SpeedOracle`, `quality`).
- **1c-D3:** `build_belief_for_side` dispatcher + the limited-view safety tests + the
  `rollout_labels` integration test.

## Non-goals (hard)
No export-swap (`stub-h0` → real teacher stays its own later slice); no training; no
seen-mons memory; no curated full team; no hidden-state use. 1c-D delivers the belief builders
+ data source + safety tests only.
