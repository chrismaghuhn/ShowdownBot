# Accuracy / Hit-Probability-Weighted Move Evaluation — Design

**Status:** spec-ready (post 5-correction revision, then a second review pass replacing the
one-shot discovery/fixed-branch-set design with a recursive expansion, fixing the Thunder/
Hurricane-in-sun mechanic against the pinned server source, and closing the branch-cap
provenance gap)
**Scope:** `resolve_turn`/`apply_hit`/`evaluate_line` only. `rollout.py` (the fixed-policy
multi-turn condition engine used by `_rollout_value`) is explicitly OUT of scope — it does no
damage calc and stays pure ratio arithmetic.
**Sequence:** this slice sits between Config/Model/Meta-Provenance fixes and the Depth-2 Stage 3
re-baseline: Action-ID → Audit-Gate → Dataset/Split decisions → Config/Model/Meta-Provenance →
**this slice** → new baseline → Depth-2 Stage 3.

## 1. Problem

`resolve_turn`/`apply_hit` (`battle/resolve.py`) has zero hit/miss modeling — every damaging move
is treated as guaranteed to connect. This is wrong standalone (a 70%-accurate OHKO move is
evaluated as a guaranteed KO) and compounds under multi-ply search: Depth-2's turn-2 evaluation
reuses the same always-hit `evaluate_line` seam, so a risky line's unreliability is invisible at
*both* plies, systematically over-crediting lines that depend on a move connecting twice.

## 2. Data layer: `accuracy` becomes a first-class move field

**Generator (`tools/gen/gen_movedata.mjs`):** `moveRecord()` currently has no `accuracy` key at
all. Add:

```js
function accuracyRecord(m) {
  if (m.accuracy === undefined) {
    throw new Error(`move ${m.id} has no accuracy field from @pkmn/dex`);
  }
  return m.accuracy === true ? null : m.accuracy;
}
```

and `accuracy: accuracyRecord(m)` in `moveRecord()`. `@pkmn/dex` represents "always hits" moves
(Swift, Aura Sphere, Aerial Ace, etc.) as `accuracy === true`; everything else is a number 1-100.
The generator normalizes `true` → JSON `null` (the project's "always hit" sentinel) and **fails
the build** if `m.accuracy` is `undefined` for any move — a missing field is a data error, not a
default. This directly implements the addendum: *"Fehlendes Feld muss ein Datenfehler sein; `None`
darf nur das normalisierte „always hit" bedeuten."*

**`movedata.json`:** gains `moves.<id>.accuracy: number | null` for every move. Regenerated via
the existing `node gen_movedata.mjs` / `--check` staleness gate (already wired, `gen_movedata.mjs:89-100`).

**`MoveMeta` (`engine/moves.py`):** gains `accuracy: int | None = None`. The loophole to close:
`_meta_from_record` currently reads every field via `rec.get(...)`, which cannot distinguish "key
present, value `null`" (legitimate always-hit) from "key absent" (data error — the exact gap the
generator fix above is supposed to prevent from ever reaching Python, but the Python loader must
not silently paper over it if it does). `_move_table()` must assert `"accuracy" in rec` per move
when building the table and raise if absent, instead of `_meta_from_record` using `.get()` for
this specific field.

## 3. `hit_probability()` — core function

Lives in `engine/moves.py`, next to `blocks_move`/`can_redirect`/`move_priority` — same dependency
shape (`MoveMeta` + `FieldState`), extended with boost-stage dicts (`PokemonState.boosts`,
`state.py:52`, already tracks `"accuracy"`/`"evasion"` via `_BOOST_KEYS`, `state.py:9` — unused
today, this is its first consumer).

```python
def hit_probability(
    meta: MoveMeta, attacker: PokemonState, target: PokemonState, field: FieldState | None,
) -> float | None:
    """None = always hits (meta.accuracy is None, or a weather guarantee applies).
    Otherwise a value in (0, 1]."""
```

Takes full `PokemonState` objects (reading `.boosts` internally), not raw boost dicts — consistent
with `can_redirect(redirect_move_id, attacker_mon, attacker_types)`'s existing pattern of taking
the mon object rather than pre-extracted fields, and leaves room for the v1.1 ability-modifier
items in §3 to read `attacker.ability`/`target.ability` off the same parameter without a signature
change.

**v1 rule scope** (per the accepted AskUserQuestion answer — accuracy/evasion boost stages +
weather-guaranteed hits, nothing else):

- **Base accuracy:** `meta.accuracy is None` → always hits, return `None` immediately (no stage/
  weather adjustment needed or applied).
- **Accuracy/evasion stages:** `stage = clamp(attacker_boosts.get("accuracy", 0) - target_boosts.get("evasion", 0), -6, 6)`,
  standard Gen 3+ multiplier: `stage >= 0 → (3 + stage) / 3`, `stage < 0 → 3 / (3 - stage)`.
  Applied as `meta.accuracy/100 * multiplier`, clamped to `[0, 1]`.
- **Weather-guaranteed hits**, checked against the real `FieldState.weather` token convention
  (verified via `battle/evaluate.py:20-22`'s `_WEATHER_MAP` and `battle/rollout_adapter.py`'s
  parallel `_WEATHER_IDS`/`_match` — both do a `field.weather.lower()` substring-token match, not
  exact-string):
  - Blizzard (`meta.id == "blizzard"`) hits 100% when `"snow" in field.weather.lower()`. Gen 9
    renamed Hail → Snow; this project targets Gen 9 only (`gen9vgc2024regg`/`gen9vgc2025regi`), so
    "snow" is the correct and only token checked — "hail" is not tested against for this rule.
  - Thunder/Hurricane (`meta.id in ("thunder", "hurricane")`): verified against the actual pinned
    server source (`config/eval/provenance.yaml`'s `showdown_commit: f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5`,
    `data/moves.ts:9037-9048`/`19458-19469`, `sim/battle-actions.ts:685-733`), **not assumed**:
    `onModifyMove` sets `move.accuracy = true` in rain (`raindance`/`primordialsea`) — this is the
    real always-hit sentinel, and `hitStepAccuracy` (`battle-actions.ts:708`) skips the entire
    stage/evasion block when `accuracy === true`, so rain is a genuine unconditional 100%, no stage
    interaction. In sun (`sunnyday`/`desolateland`) it instead sets `move.accuracy = 50` — a plain
    **number**, which `hitStepAccuracy` feeds through the *normal* stage-multiplier pipeline
    exactly like any other numeric base accuracy (`battle-actions.ts:709-722`). The original design
    claim that sun is a hard override ignoring stages was **wrong** — corrected:
    `"rain" in field.weather.lower()` → return `None` (unconditional always-hit, matching
    `move.accuracy = true`'s bypass of the stage block); `"sun" in field.weather.lower()` →
    substitute `50` for `meta.accuracy` and then apply the **same** stage/evasion multiplier as the
    base-accuracy path above (`50/100 * multiplier`), not a hard-pinned 0.5.
  - **Known gap, not new to this slice:** PS's rain/sun weather IDs also include the primal-ability
    forms `primordialsea`/`desolateland`, which contain neither `"rain"` nor `"sun"` as a
    lowercase substring, so the token check above would miss them. `_WEATHER_MAP`
    (`evaluate.py:20-22`) has the same gap already, project-wide, predating this slice. Primal Orbs
    are not legal held items in any VGC-regulation format this bot targets, so this is accepted as
    zero real-world materiality rather than fixed here — noted so it isn't a silent repeat.
  - These are the only two field-rule branches in v1, per the accepted answer.

**Explicitly out of v1** (documented limitation, not silently ignored): ability modifiers
(Compound Eyes, Hustle, Sand Veil, No Guard, Victory Star, ...), item modifiers (Wide Lens, Zoom
Lens, Bright Powder), Gravity, Micle Berry, semi-invulnerable-turn interactions (Dig/Fly/etc. vs.
tracking moves), and multi-hit-specific accuracy quirks. These all bias `hit_probability` toward
the move's nominal/weather-adjusted rate — a conservative, documented direction, not silently
wrong. Tracked as a named v1.1 candidate list, not built here.

**Multi-hit moves:** real Showdown mechanics roll accuracy **once** per move use (Gen 6+), not
once per individual hit — a hit multi-hit move's later hits don't re-check accuracy. `MoveMeta`
already carries `multihit` separately from `accuracy`; no special-casing is needed — one
`hit_probability` check per `(attacker, target)` pair, exactly like a single-hit move, is already
correct.

## 4. Miss identity, ordering, and `apply_hit`

`forced_miss: frozenset[tuple[SlotId, SlotId]]` — pairs of `(attacker_key, resolved_target_key)`,
**not** attacker-only. Verified against `apply_hit`'s actual signature (`resolve.py:173`):
`apply_hit(attacker_key, attacker_action, tgt_key, spread)` is **already** called once per
resolved target for spread moves (the fan-out loop is at `resolve.py:274-275`), so a spread move
like Heat Wave hitting slot A but missing slot B is representable today without restructuring —
`forced_miss` just needs to carry both slots of the pair, not a single attacker-keyed set.

**Ordering**, verified against the current body of `apply_hit` (`resolve.py:173-186`):

```python
def apply_hit(attacker_key, attacker_action, tgt_key, spread):
    move = attacker_action.move
    if tgt_key in protected and blocks_move(move, field):          # 1. protect (unchanged, stays first)
        outcome.protected_hits.append(ProtectedHit(...)); return
    tgt_mon = state.sides.get(tgt_key[0], {}).get(tgt_key[1])
    if tgt_mon is None:
        return
    outcome.attempted_hits.append(AttemptedHit(attacker_key, tgt_key, move.id))  # NEW: 2. record attempt
    if (attacker_key, tgt_key) in forced_miss:                      # NEW: 3. miss check
        outcome.missed_hits.append(MissedHit(attacker_key, tgt_key, move.id)); return
    ...                                                             # 4. damage/hit-effects (unchanged)
```

`tgt_key` arrives already redirection-resolved (redirection is handled by the caller before
`apply_hit` is invoked, `resolve.py:278-296`), so the required order — redirection → protect →
accuracy → hit-effects — falls out of this insertion point without moving any existing code. A
Protect-blocked attack still returns at step 1 and appears as `protected_hits`, never reaching the
miss check, so it can't be misclassified as a miss.

Two new `TurnOutcome` fields (mirroring the existing `protected_hits`/`redirected_hits` pattern,
`resolve.py:80-81`): `attempted_hits: list[AttemptedHit]`, `missed_hits: list[MissedHit]`.
`AttemptedHit` is recorded **unconditionally** (even when `forced_miss` is empty, i.e. today's
legacy always-hit call path). It is consumed by the recursive branch expansion in §5, which calls
`resolve_turn` repeatedly with a *growing* `forced_miss` set and re-reads `attempted_hits` after
every call — not by a single one-shot discovery pass (see §5 for why one pass is insufficient).

`resolve_turn` gains `forced_miss: frozenset[tuple[SlotId, SlotId]] = frozenset()` as a new
keyword-only parameter, threaded through to `apply_hit`'s closure. Default empty set = today's
exact hit/damage/KO behavior, unchanged bit-for-bit.

**Scope of "byte-identical" for this slice:** `attempted_hits`/`missed_hits` are new `TurnOutcome`
fields that did not exist before this slice — `TurnOutcome` necessarily changes shape as part of
adding this feature. `apply_hit` appends to `attempted_hits` unconditionally (cheap O(1)
bookkeeping, no effect on `hp_delta`/KOs/score), independent of whether accuracy branching is
enabled, so the discovery reuse in §5 needs no mode-conditional code path inside the low-level
resolver — only `evaluate_line` decides whether to *act* on that list (§9). "Byte-identical when
off" therefore means: the **decision output** (`config_hash`, chosen candidate, numeric score,
`/choose` bytes) is unchanged — not that `TurnOutcome`'s field set is frozen, since this slice is
exactly what's adding fields to it.

## 5. Branch enumeration inside `evaluate_line`

**Why a one-shot discovery pass is wrong.** An earlier revision of this design ran
`resolve_turn(forced_miss=∅)` once, read `attempted_hits` as a *fixed* event list, and generated
`2^k` branches as subsets of that one list. This is incorrect whenever a hit/miss outcome changes
*who gets to act at all*: if fast attacker X's uncertain move KOs slower Y in the all-hit run, Y
never reaches `apply_hit` (`resolve.py:210-214`, `fainted_before_acting`) and so never appears in
`attempted_hits` — but in the branch where X's move *misses*, Y survives and takes its own action,
which may itself be an uncertain-accuracy move against some target. That event is invisible to a
list built from the all-hit run alone, so the miss-branch's score would silently treat Y's action
as guaranteed-hit. The same problem applies to redirection: which mon is targeted (and therefore
which accuracy check applies) can depend on whether an earlier Follow-Me/Rage-Powder user is still
alive, which is itself hit/miss-dependent. A fixed pre-enumerated event list cannot see this.

**Fix: recursive expansion that re-discovers events after every resolve.** `evaluate.py` gains
`resolve_turn_branches(state, actions, damage_fn, *, our_side, field, tie_break, branch_cap) ->
list[tuple[float, TurnOutcome]]` (placed next to `resolve_turn` in `resolve.py`, since it's a
resolution primitive, not a scoring one). `resolve_turn` itself is untouched beyond §4's
`forced_miss` parameter — it stays a single deterministic pass for a *given* `forced_miss` set.
`resolve_turn_branches` is the new orchestrator that calls it repeatedly, forking exactly at the
point a genuinely new uncertain event is revealed:

```python
def resolve_turn_branches(state, actions, damage_fn, *, our_side, field, tie_break, branch_cap):
    calls = 0
    fallback_leaves = 0

    def expand(miss_set, decided_hit, weight):
        nonlocal calls, fallback_leaves
        calls += 1
        out = resolve_turn(state, actions, damage_fn, our_side=our_side, field=field,
                            tie_break=tie_break, forced_miss=miss_set)
        decided = miss_set | decided_hit
        pending = []
        for ah in out.attempted_hits:
            pair = (ah.attacker, ah.target)
            if pair in decided:
                continue
            attacker_mon = state.sides[ah.attacker[0]][ah.attacker[1]]
            target_mon = state.sides[ah.target[0]][ah.target[1]]
            move = _move_for(actions, ah.attacker, ah.move_id)  # PlannedAction.move lookup
            p = hit_probability(move, attacker_mon, target_mon, field)
            if p is not None and 0.0 < p < 1.0:
                pending.append((pair, p))
        if not pending:
            return [(weight, out)]
        if calls >= branch_cap:
            fallback_leaves += 1
            return [(weight, out)]  # remaining `pending` events stay implicitly hit in `out`
        pair, p = pending[0]  # deterministic: first attempted-hit order
        return (
            expand(miss_set, decided_hit | {pair}, weight * p)
            + expand(miss_set | {pair}, decided_hit, weight * (1 - p))
        )

    leaves = expand(frozenset(), frozenset(), 1.0)
    return leaves, fallback_leaves
```

`decided_hit` tracks pairs whose "hits" side has already been explored by an ancestor fork, so a
pair already forked on is never re-forked when it resurfaces in a descendant's `attempted_hits`
(it necessarily will, since `out` always reflects *some* concrete resolution). Because
`hit_leaves` (weight × `p`) is always computed before `miss_leaves` (weight × `1-p`) and recursion
is depth-first, `leaves[0]` is always the fully-resolved "everything hits" leaf — the same
representative-outcome property the original design relied on. Leaf weights sum to 1.0 by
induction regardless of where the cap triggers (a capped leaf just stops subdividing further; it
keeps its accumulated weight and treats its own still-`pending` events as hit, i.e. exactly
today's legacy resolution for whatever wasn't explored — see §6 for why this is now a *per-branch*
fallback, not a whole-line one).

**Composition with tie-averaging.** `evaluate_line`'s `_one(tb)` (`evaluate.py:384-392`) becomes:
when `SHOWDOWN_ACCURACY_MODE` is off, call `resolve_turn` exactly as today (byte-identical, zero
overhead). When on, call `resolve_turn_branches(..., tie_break=tb)`, then
`score = Σ weight_i × (score_outcome(out_i, ...) + rollout(out_i) if horizon>0 else 0)`, returning
`(score, leaves[0][1])` as the representative outcome — same external `(float, TurnOutcome)`
contract `_one(tb)` had before, so the outer tie-break wrapper (`evaluate.py:396-400`, averaging
`_one("ours_first")`/`_one("ours_last")` 0.5/0.5) needs **no change** and composes correctly:
it calls `_one(tb)` twice, and each call now internally does its own full accuracy expansion.

**This means the real worst-case cost is the *product*, not a sum** — up to `2 ×
2^branch_cap` total `resolve_turn` calls per `evaluate_line` invocation in the tie+accuracy case
(one full `resolve_turn_branches` expansion per tie-break ordering). There is no merged
`2 × 2^branch_cap`-cell data structure to build (each `_one(tb)` reduces its own expansion to a
single scalar before the outer average touches it), but the *call count* is multiplicative and
must be measured as such — §6's latency gate is written against this real number, not the smaller
`2^branch_cap` figure alone.

`damage_fn` calls across branches for the same `(attacker, target, move)` triple are identical in
every branch that doesn't force-miss that specific pair — the existing oracle/damage cache (the
same one `_has_genuine_tie`'s docstring references: *"Same prefetched oracle cache -> no new
calcs"*) absorbs the repetition, so the added cost is dominated by `resolve_turn` call **count**
and its own pure-Python work, not by re-hitting `@smogon/calc`.

## 6. Branch budget: cap, fallback, telemetry

Worst case (verified arithmetic): 2 actors per side, both sides using a 2-target spread move
against an opponent with 2 alive targets → 4 attacker×target pairs per side × 2 sides = 8
independent uncertain-accuracy events → `2^8 = 256` leaves in the deepest single `expand()` tree,
× 2 tie-break orderings (§5) before rollout.

**Mechanism defined now, magnitude tuned empirically at implementation time** (same pattern used
for Depth-2's `SHOWDOWN_SEARCH_TOPN`/`TOPM`: define the knob and fallback behavior in the spec,
measure the affordable value during the implementation's own latency-gate stage rather than
guessing a number here):

- A named config knob, `SHOWDOWN_ACCURACY_BRANCH_CAP` (int, suggested starting default `4` —
  bounding `resolve_turn_branches`'s own `expand()` to at most 4 `resolve_turn` calls before any
  further fork gets capped — to be confirmed or revised by a local micro-benchmark before
  shipping, exactly as Depth-2's N/M were).
- **Per-branch fallback, not whole-line.** Correction from an earlier revision: because forking
  now happens recursively at the point an event is actually revealed (§5), the cap is enforced
  per `expand()` call via its own `calls` counter — when a specific recursion path reaches the cap,
  *that path alone* stops subdividing and treats its own still-`pending` events as hit (the exact
  legacy behavior), while sibling paths that never approached the cap continue exploring normally.
  This is strictly more accurate than an earlier whole-line-reverts design (only the excess tail of
  the *specific* deep branch is approximated, not the entire turn) and falls out of the recursive
  structure for free — no risk-priority partial scheme is needed to get this improvement.
- **Telemetry, not silent truncation:** `resolve_turn_branches` returns `fallback_leaves` (count of
  `expand()` calls that hit the cap) alongside the leaf list; `_one(tb)` accumulates this onto the
  trace (e.g. `trace.accuracy_branch_cap_hits`), visible in existing report aggregation. A branch
  that hit the cap is fully auditable after the fact — this is what "keine stillschweigende
  Zweig-Trunkierung" requires, and what makes the cap number itself a decision the telemetry can
  later challenge.
- **Provenance:** `SHOWDOWN_ACCURACY_BRANCH_CAP` is behavior-affecting — a different cap value can
  change which lines hit the fallback and therefore which candidate scores highest, exactly the
  same class of effect `SHOWDOWN_SEARCH_DEPTH` has. It is added to `BEHAVIOR_AFFECTING`
  **unconditionally** (§9) rather than excluded-when-mode-is-off, deliberately avoiding the
  conditional-exclusion pattern that produced the `SHOWDOWN_SEARCH_TOPN`/`TOPM` bug the audit
  found. §10 requires a test proving two runs that differ only in this cap (with
  `SHOWDOWN_ACCURACY_MODE` on) produce different `config_hash`.

## 7. Derived diagnostics

Computed as a byproduct of the leaf list `resolve_turn_branches` already returns (§5) — no
separate code path, no extra `resolve_turn` calls:

- `ko_probability(target)` — sum of leaf weights in which `target` ends up fainted in that leaf's
  `TurnOutcome` (already known per leaf).
- `survival_probability(target) = 1 - ko_probability(target)`.
- `accuracy_required` — pass-through of the move's own `hit_probability` value, exposed for
  logging/search use, not recomputed.
- `miss_punish_value(pair)` — for each `pair` that was an actual fork point on the path to
  `leaves[0]` (the all-hit leaf), the weighted-average score of that fork's *miss* sibling subtree
  minus `score(leaves[0])`. This is well-defined directly from `expand()`'s recursion (each fork's
  two children are already separately computable) without needing a separate "only this one event
  missed, everything else held at hit" leaf to exist in the tree — for events that are the *last*
  fork before `leaves[0]`, the two coincide; for earlier forks, the miss-sibling subtree already
  correctly re-resolves any later events that only become live in that miss branch (§5), so this
  is if anything a more faithful marginal-cost figure than a naive single-event flip would be.

These populate a new, optional `AccuracyDiagnostics` structure attached to the trace only when
accuracy modeling is active (§9); `None`/absent when off, so the off-path stays byte-identical.

## 8. Provenance: wiring `movedata.json`'s content hash into `config_hash`

Verified: `movedata.json`'s embedded `data_hash` field (`gen_movedata.mjs:77-78`) has **zero**
Python consumers (`grep -rn "data_hash" src/showdown_bot/` returns nothing) — the original design
claim that this already flowed into eval provenance was wrong.

**Fix, mirroring the existing `priors_hash`/`spreads_hash` pattern exactly** (`cli.py:44-51`
`_file_content_hash`, `cli.py:141-142` computing `priors_hash`/`spreads_hash` via
`cfg.meta_path(...)`, `cli.py:145-149` passing them into `build_config_manifest`):

- `engine/moves.py` exposes a small public accessor, `movedata_path() -> Path`, returning the
  existing private `_MOVEDATA` constant's path — avoids reaching across modules for a private
  name.
- `cli.py` computes `movedata_hash = _file_content_hash(movedata_path())` alongside
  `priors_hash`/`spreads_hash` and passes it as a new keyword to `build_config_manifest`.
- `build_config_manifest` (`eval/config_env.py:167-185`) gains a `movedata_hash` parameter,
  included in the manifest **unconditionally** (like `priors_hash`/`spreads_hash`, not gated
  behind `SHOWDOWN_ACCURACY_MODE`). This is a deliberate choice to avoid repeating the exact bug
  class the audit just found with `SHOWDOWN_SEARCH_TOPN`/`TOPM` (conditionally excluded from the
  manifest based on another flag's value, causing identical `config_hash` for behaviorally
  different runs) — a content hash of the move-data file is cheap and unconditional inclusion
  can't silently collide two different accuracy datasets under one config lineage.

## 9. Ablation gate

New `SHOWDOWN_ACCURACY_MODE` env var (on/off), following the project's established pattern for
every behavior-affecting slice (`SHOWDOWN_SEARCH_DEPTH`, `SHOWDOWN_WORLD_SAMPLES`,
`SHOWDOWN_FAST_BOARD_PROTECT_PENALTY`, ...): off (default) = today's always-hit `resolve_turn`
path, byte-identical output. On = hit/miss branching per §4-§7 active. Added to
`BEHAVIOR_AFFECTING` in `eval/config_env.py` (unconditionally included in `behavior_env()`, same
as its siblings) — this is the single reproducible on/off ablation requested, distinct from the
always-included `movedata_hash` (§8), which changes with the *data* regardless of whether the
feature that consumes it is switched on. `SHOWDOWN_ACCURACY_BRANCH_CAP` (§6) is likewise added to
`BEHAVIOR_AFFECTING` unconditionally, for the same audit-precedent reason spelled out in §6 —
listing it here alongside `SHOWDOWN_ACCURACY_MODE` since both are read at the same call site.

## 10. Rollout gating: fallback-rate go/no-go before default-on

`SHOWDOWN_ACCURACY_MODE` ships **off by default** regardless of test results — this section is the
criterion for later flipping the default, not a condition on merging this slice. Before that
happens: run the mode on a representative battle panel (reusing existing gauntlet/eval-report
infrastructure) and measure the `accuracy_branch_cap_hits` rate (§6) over real decisions, broken
out by whether the affected line was actually the *chosen* candidate (a fallback on a
never-selected candidate is harmless; a fallback on the line the bot goes on to play is the case
that matters). Required before default-on: the report must state this rate explicitly (no silent
truncation applies to the aggregate report just as much as to a single trace), and a materially
non-zero rate on chosen lines blocks flipping the default until either the cap is raised (re-run
the latency gate) or the fallback behavior itself is revisited. This gate is deliberately separate
from the correctness/determinism tests in §11 — those must pass before merge; this one gates the
subsequent default-on decision.

## 11. Testing strategy

- **Generator:** fail-closed test asserting every move in a fresh `gen_movedata.mjs` run has an
  `accuracy` key (number or explicit `null`), and that a synthetic dex entry with
  `accuracy === undefined` raises.
- **`MoveMeta`/`_move_table`:** test that a record missing the `"accuracy"` key raises at load
  time, distinct from a record with `"accuracy": null` loading cleanly as `meta.accuracy is None`.
- **`hit_probability`:** table-driven tests against real `FieldState.weather` string values
  (`"RainDance"`-shaped-if-that's-the-real-protocol-string vs. the `_WEATHER_MAP`-token
  convention — confirm exact protocol strings via existing `evaluate.py`/`rollout_adapter.py`
  fixtures rather than assuming) for: base accuracy only, boost-stage adjustment (both
  directions), Blizzard in Snow (100%), Blizzard outside Snow (nominal), Thunder/Hurricane in Rain
  (unconditional 100%, verified stage-independent), Thunder/Hurricane in Sun **with a non-zero
  accuracy/evasion stage** (must equal `trunc(50 * stage_multiplier)`, not a flat 0.5 — this is
  the specific case the earlier design got wrong and must be pinned against
  `sim/battle-actions.ts:709-722`'s actual formula at the pinned commit), always-hit moves (`None`,
  no stage/weather adjustment applied).
- **`apply_hit`/`resolve_turn`:** a Protect-blocked hit with a simultaneous forced-miss entry for
  the same pair still records `protected_hits`, never `missed_hits` (proves the ordering). A
  spread move forced-missing one target and hitting another produces exactly one `MissedHit` and
  one damaged target. `attempted_hits` is populated even when `forced_miss=∅`.
- **`resolve_turn_branches` (§5), the core correctness case:** a fixture with a fast attacker whose
  uncertain move KOs a slower defender that itself has a queued uncertain-accuracy move. Assert
  that the miss-branch's leaves correctly include the defender's own accuracy fork (i.e., the
  defender's move appears as a pending event *only* in the subtree reached after the attacker's
  miss, and the resulting weighted score reflects that move's own hit/miss uncertainty) — this is
  the regression test for the exact bug the one-shot-discovery design had.
- **`evaluate_line` branch composition:** a synthetic two-leaf case (one uncertain event) checks
  the weighted score equals `p * score(hit) + (1-p) * score(miss)` exactly. A synthetic case with
  events beyond `branch_cap` checks the per-branch fallback (only the specific over-cap subtree
  stops subdividing, sibling subtrees unaffected) and that `fallback_leaves`/the telemetry counter
  increments by the correct count. A combined tie+accuracy case measures and asserts the actual
  `resolve_turn` call count equals the `2 × leaf_count` product from §5 (not an assumed-additive
  smaller number), and separately checks the returned score is still the correct weighted average.
- **Provenance:** two runs differing only in `movedata.json` content (synthetic fixture) produce
  different `config_hash` even with `SHOWDOWN_ACCURACY_MODE` off; two runs differing only in
  `SHOWDOWN_ACCURACY_MODE` produce different `config_hash` with identical `movedata.json`; two runs
  with `SHOWDOWN_ACCURACY_MODE` on but different `SHOWDOWN_ACCURACY_BRANCH_CAP` values produce
  different `config_hash` (the TOPN/TOPM-class regression test §6/§9 call for).
- **Off-path byte-identity:** existing resolve/evaluate golden tests re-run with
  `SHOWDOWN_ACCURACY_MODE` unset/off must produce byte-identical output to pre-slice behavior.
- **Latency:** measure real wall-clock for the worst-case 8-event/`2 × 2^branch_cap`-call scenario
  (§5) at the chosen `branch_cap` default, per the Depth-2-precedent methodology (persistent calc
  backend, local micro-bench, no silent assumption of "cheap because cached").

## 12. Explicitly out of scope

- `rollout.py` / `_rollout_value`'s multi-turn condition engine (pure ratio arithmetic, no damage
  calc — confirmed twice by the user).
- Ability/item/field accuracy modifiers beyond the two weather rules in §3 (named v1.1 candidates).
- Risk-priority fork ordering: `expand()` (§5) forks on `pending[0]` in attempted-hit order
  (deterministic, but not ranked by `1-p`). If the cap-hit rate from §10's gate turns out to be
  material, forking the riskiest (`1-p` largest) pending event first — so a capped branch has
  already explored its highest-value uncertainty before giving up — is a named v1.1 candidate. The
  per-branch (not whole-line) fallback itself is already v1 baseline (§6), not deferred.
- Any change to Depth-2 Stage 3 itself — this slice only fixes the shared 1-ply evaluation seam
  that both the primary decision and Depth-2's turn-2 backup consume; the re-baseline and Stage 3
  work follow this slice, not inside it.
