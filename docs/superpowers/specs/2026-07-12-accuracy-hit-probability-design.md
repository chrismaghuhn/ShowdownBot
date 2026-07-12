# Accuracy / Hit-Probability-Weighted Move Evaluation — Design

**Status:** spec-ready (post 5-correction revision)
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
  - Thunder/Hurricane (`meta.id in ("thunder", "hurricane")`): `"rain" in field.weather.lower()` →
    100% (overrides stage-adjusted value); `"sun" in field.weather.lower()` → exactly 0.5
    (overrides stage-adjusted value, does **not** compose with it — this matches real Showdown,
    where the sun penalty is an absolute replacement, not a multiplier on the boosted accuracy).
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
legacy always-hit call path) — this makes the very first, zero-`forced_miss` `resolve_turn` call
double as event *discovery* for the branch enumeration in §5, with no extra resolve pass needed.

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

**Where hit/miss branching composes with the existing tie-break averaging:** `evaluate_line`'s
`_one(tb)` closure (`evaluate.py:384-392`) today does exactly one `resolve_turn` → `score_outcome`
→ optional `_rollout_value`. The genuine-tie wrapper outside it (`evaluate.py:396-400`) averages
`_one("ours_first")` and `_one("ours_last")` 0.5/0.5. Hit/miss branching is nested **strictly
inside** `_one(tb)`, not as an outer loop alongside tie-averaging: for a fixed tie-break ordering,
`_one(tb)` now enumerates its own weighted hit/miss branches, each a full
`resolve_turn`+`score_outcome`+`_rollout_value` pass, and returns their probability-weighted score.
The tie-break wrapper is untouched and composes automatically — two independent axes (tie-order,
hit/miss), each fully resolved before the other combines them, so nothing is double-counted and
no combinatorial cross-product between the two axes is ever materialized (2 tie-orderings × up to
`2^B` hit/miss branches stays additive, not multiplicative, because each `_one(tb)` call owns its
own hit/miss average internally).

**Discovery + branch construction**, inside the new `_one(tb)`:

1. Call `resolve_turn(..., forced_miss=frozenset())` once — this is both the "all-hit" branch AND
   the discovery pass, reading `outcome.attempted_hits` for the candidate event list.
2. For each `AttemptedHit(attacker_key, tgt_key, move_id)`, compute
   `p = hit_probability(move.meta, attacker_mon, target_mon, field)` (the two `PokemonState`
   objects resolved from `state.sides` via `attacker_key`/`tgt_key`). Events where `p is None`
   (always hits) or `p >= 1.0` are dropped — they contribute no uncertainty, so they never enter
   the combinatorial set. This is what keeps the practical branch count well below the worst-case
   8/256: status moves, always-hit moves, and any move already fully guaranteed by a weather rule
   cost nothing.
3. The remaining "uncertain events" list (size `k`, worst case 8 per §6) generates up to `2^k`
   branches, each a specific `forced_miss` subset with probability
   `∏(uncertain, missed) (1 - p) × ∏(uncertain, hit) p`.
4. Every branch beyond the first (`forced_miss=∅`, already computed in step 1) requires its own
   `resolve_turn`+`score_outcome`(+`_rollout_value`) call. `_one(tb)` returns
   `(Σ branch_prob × branch_score, representative_outcome)` — the representative `TurnOutcome` is
   the all-hit (`forced_miss=∅`) branch's outcome, mirroring how the tie-average case already
   picks one representative outcome (`out_last`) for diagnostics rather than trying to merge two
   `TurnOutcome`s.

`damage_fn` calls across branches for the same `(attacker, target, move)` triple are identical in
every branch that doesn't force-miss that specific pair — the existing oracle/damage cache (the
same one `_has_genuine_tie`'s docstring references: *"Same prefetched oracle cache -> no new
calcs"*) absorbs the repetition, so the added cost of branching is dominated by branch **count**
(cheap, pure-Python `score_outcome`/rollout work), not by re-hitting `@smogon/calc`.

## 6. Branch budget: cap, fallback, telemetry

Worst case (verified arithmetic): 2 actors per side, both sides using a 2-target spread move
against an opponent with 2 alive targets → 4 attacker×target pairs per side × 2 sides = 8
independent uncertain-accuracy events → `2^8 = 256` combinations before tie-averaging/rollout.

**Mechanism defined now, magnitude tuned empirically at implementation time** (same pattern used
for Depth-2's `SHOWDOWN_SEARCH_TOPN`/`TOPM`: define the knob and fallback behavior in the spec,
measure the affordable value during the implementation's own latency-gate stage rather than
guessing a number here):

- A named config knob, `SHOWDOWN_ACCURACY_BRANCH_CAP` (int, suggested starting default `4` — i.e.
  up to `2^4 = 16` exact branches per `_one(tb)` call — to be confirmed or revised by a local
  micro-benchmark before shipping, exactly as Depth-2's N/M were).
- **Deterministic fallback, no partial/priority-ranked branching in v1:** if the uncertain-event
  count for a line exceeds the cap, that **one line** falls back entirely to the legacy always-hit
  behavior (`forced_miss=∅` only, i.e. step 1's branch alone, weight 1.0). No other line is
  affected. This is simpler and fully deterministic to verify versus a risk-priority partial
  scheme; a partial scheme (branch the `B` riskiest events by `1-p`, collapse the rest to their
  own expectation) is a documented, named v1.1 candidate if the fallback-rate telemetry below
  shows it matters in practice.
- **Telemetry, not silent truncation:** every fallback increments a counter exposed on the trace
  (e.g. `trace.accuracy_branch_cap_hits`), visible in existing report aggregation. A line that hit
  the cap is fully auditable after the fact — this is what "keine stillschweigende
  Zweig-Trunkierung" requires, and what makes the cap number itself a decision the telemetry can
  later challenge.

## 7. Derived diagnostics

Computed as a byproduct of the branch enumeration already done in §5 — no separate code path, no
extra `resolve_turn` calls:

- `ko_probability(target)` — sum of branch probabilities in which `target` ends up fainted in that
  branch's `TurnOutcome` (already known per branch).
- `survival_probability(target) = 1 - ko_probability(target)`.
- `accuracy_required` — pass-through of the move's own `hit_probability` value, exposed for
  logging/search use, not recomputed.
- `miss_punish_value` — `score(all-hit branch) - score(the branch where only this specific event
  is forced-missed, others held at all-hit)`, i.e. the marginal cost of *this* event missing,
  extracted from the already-enumerated branch scores.

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
feature that consumes it is switched on.

## 10. Testing strategy

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
  (100%) and Sun (exactly 0.5, not composed with boosts), always-hit moves (`None`, no stage/
  weather adjustment applied).
- **`apply_hit`/`resolve_turn`:** a Protect-blocked hit with a simultaneous forced-miss entry for
  the same pair still records `protected_hits`, never `missed_hits` (proves the ordering). A
  spread move forced-missing one target and hitting another produces exactly one `MissedHit` and
  one damaged target. `attempted_hits` is populated even when `forced_miss=∅` (proves the
  discovery-pass reuse in §5).
- **`evaluate_line` branch enumeration:** a synthetic two-branch case (one uncertain event) checks
  the weighted score equals `p * score(hit) + (1-p) * score(miss)` exactly. A synthetic case with
  events beyond the cap checks the whole-line fallback (`forced_miss=∅` only) and the telemetry
  counter increments. A combined tie+accuracy case checks the two axes compose additively (no
  cross-product blowup, exact expected weighted value computed by hand for a small fixture).
- **Provenance:** two runs differing only in `movedata.json` content (synthetic fixture) produce
  different `config_hash` even with `SHOWDOWN_ACCURACY_MODE` off; two runs differing only in
  `SHOWDOWN_ACCURACY_MODE` produce different `config_hash` with identical `movedata.json`.
- **Off-path byte-identity:** existing resolve/evaluate golden tests re-run with
  `SHOWDOWN_ACCURACY_MODE` unset/off must produce byte-identical output to pre-slice behavior.

## 11. Explicitly out of scope

- `rollout.py` / `_rollout_value`'s multi-turn condition engine (pure ratio arithmetic, no damage
  calc — confirmed twice by the user).
- Ability/item/field accuracy modifiers beyond the two weather rules in §3 (named v1.1 candidates).
- Partial/risk-priority branch collapsing above the cap (named v1.1 candidate, contingent on
  fallback-rate telemetry from §6).
- Any change to Depth-2 Stage 3 itself — this slice only fixes the shared 1-ply evaluation seam
  that both the primary decision and Depth-2's turn-2 backup consume; the re-baseline and Stage 3
  work follow this slice, not inside it.
