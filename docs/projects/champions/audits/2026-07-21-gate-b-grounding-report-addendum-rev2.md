# Gate B Grounding Report — Rev. 2 Addendum

**Status:** supporting evidence for `docs/projects/champions/plans/2026-07-21-gate-b-independent-strength-holdout.md` Rev. 2
**Purpose:** the base grounding report covered Rev. 1. This addendum covers the additional research done in response to Rev. 1's CHANGES REQUESTED review, so every Rev. 2 fix traces to a source, not to the review's own prose.

All findings below are `[reported]` (three parallel research subagents, each reading full files, not excerpts) unless marked `[verified]` (I re-checked the specific claim myself against the same file).

## Finding 1 addendum — McNemar's real `_paired_verdict` body

`eval/report.py:856-877`, read in full, confirms the exact two extra NO-GO branches Rev. 1's `cell_flips=[]`/`strength_delta=counts.delta` shortcut bypassed:
```python
if cell_flips:
    named = ", ".join(f"{c[0]} x {c[1]}" for c in cell_flips)
    reasons.append(f"cell flip winning->losing: {named}")
if strength_delta <= 0:
    reasons.append("weak-policy-only improvement (flat/negative delta on heuristic+max_damage cells)")
```
A "cell" is `(opp_policy, opp_team_hash)` (`report.py:482-486`, `pairing.py:83,179`) — confirmed by two independent code sites, not just a docstring claim. `_build_cells`/`_find_cell_flips`/`_strength_delta`/`_build_aggregates` were read in full and confirmed generic over whatever `(opp_policy, opp_team_hash)` pairs actually appear — no report.py change needed for Gate B to call them.

`safety_pass`'s real source, `report.py:939-944`: `all(g.status != "FAIL" for g in gates_a ∪ gates_b)` from a ~15-gate `run_safety_gates` table, whose two most directly relevant gates check `invalid_choices == 0` and `crashes == 0` per run (`report.py:401-405`). Task 8's `compute_safety_pass` is a disclosed narrower mirror of just these fields plus `end_reason`, not a claim of full parity with `run_safety_gates`'s complete table (which needs a `RunBundle` — panel hashes, manifest, schedule row count — Gate B's simpler two-row-list shape doesn't produce).

## Finding 2 addendum — full `coverage_runner.py` (627 lines) and Coverage's own verdict schema

The I8-D-verdict check Gate B needs to mirror is `coverage_runner.py:175-457`, roughly 23 distinct checks in fixed order: not-a-dict guard, exact-field-set (missing AND extra), per-counter type/non-negativity, `scored_overshoot` formula cross-check, `active_valid_decisions <= scored_decisions`, `distinct_active_battles <= battles_played`, `panel_hash`/`seed_base`/`seed_log_verified` pins, four pinned-constant checks (`min_active_decisions`, `min_distinct_battles`, `max_scored_decisions`, `budget_ms`), five identity-field binds (`git_sha`, `config_hash`, `hero_agent`, `candidate_identity`, `calc_backend` separately), a freshly-rebuilt canonical `schedule_hash` bind (never the artifact's own claim), `hero_team_hash`/`opp_team_hashes` binds, `verdict=="PASS"`, `p95_is_gate_value`, `exposure_floor_met`, a cross-check that the floor-claim is actually backed by the counters, `stop_reason=="exposure_floor_met"`, and a NaN-safe `p95_ms` range check (`0 <= p95_ms <= budget_ms` as a closed range, specifically because `p95_ms > budget_ms` alone is `False` for a forged `NaN` under IEEE 754 — this exact rationale is in the real code's own review-round comment).

**Coverage's own verdict.json is a structurally different 20-field schema**, confirmed from `coverage_verdict.py` (full file) and `coverage_runner.py:607-623`'s report-assembly dict: no `scored_overshoot`, no latency/exposure fields at all; instead per-cell floors (`COVERAGE_CELL_FLOORS = {"slot0": (30,10), "slot1": (30,10), "both_foe_slots": (15,6), "order_tie": (15,6)}`) each independently required to clear via `cell_counts`, `stop_reason` values unique to Coverage (`"safety_violation"`, `"coverage_floor_met"`, `"schedule_exhausted"`, `"max_battles"`, `"max_scored_decisions"` — no `"exposure_floor_met"`), and its own pinned `COVERAGE_EXPECTED_PANEL_HASH`/`COVERAGE_SEED_BASE` distinct from I8-D's. `build_coverage_live_schedule` (`coverage_runner.py:116-126`) and `build_i8d_canonical_schedule` (`coverage_runner.py:129-136`) already exist as the two canonical-schedule rebuilders Task 7 imports.

## Finding 4 addendum — the seed/counter architecture (the most consequential single finding)

`eval/seeding.py:28-30`, `derive_battle_seed(base, index)`, is a pure function of a caller-supplied `index`. But the actual seed a battle gets is assigned server-side, not client-side — from `tools/eval/patches/pokemon-showdown-seeded-battle.patch`:
```js
let evalBattleCounter = 0;  // process-lifetime, resets only on a fresh server start
const battleIndex = evalBattleCounter++;
const digest = crypto.createHash('sha256').update(`${evalSeedBase}:${battleIndex}`).digest('hex');
```
`run_local_gauntlet` is a pure client (`client/gauntlet.py:1191`) — it never starts, stops, or resets a server. The original approved design for this exact mechanism, `docs/projects/evaluation/plans/2026-07-01-2b35-T1-proper-perbattle-seed-nonmirror.md` (T1-CC-B), states the fresh-server requirement as a hard correctness precondition, not an implementation nicety: *"the per-battle counter resets at process start, so the seed_index → seed alignment holds ONLY under a strict runner... Any paired/seeded run MUST start from a fresh server process."*

**Consequence, confirmed not assumed:** Rev. 1's interleaved A/B loop against one implicit server session gives arm A's battle for `key_i` and arm B's battle for the same `key_i` server counters `2i` and `2i+1` — never the same real seed, for any of the 180 keys, not just a whole-batch offset. This is deterministic given the architecture, not a probabilistic risk. `eval/schedule_2b4.py` (read in full) already solves an analogous problem for the determinism gate — same schedule, twice, on two fresh servers, same `seed_base` — which is the precedent Task 9/10's arm-then-combine split follows, not a novel design.

A second, related bug found independently (not in the original review, caught during this reverification): `BattleKey.seed` (0-14, Rev. 1) has no global contiguous index and repeats 12 times across the 180-key schedule (once per each of the 6×2 team/policy cells) — even with the two-fresh-server fix, passing raw `seed` to `derive_battle_seed` would still collide 12 keys onto the same real RNG seed. Task 1's `seed_index` field (0-179, the `enumerate()` position) closes this.

## Findings on `baseline.py`, `heldout_ledger.py`, `panel.py` — real APIs, not inferred ones

- `eval/baseline.py` (213 lines, full): real loader is `load_baseline(path) -> dict` (schema-only, `BaselineError`), drift-checking is the separate `verify_baseline(baseline, *, repo_root, teams_root=None) -> list[BaselineCheck]` (`BaselineDriftError`). `load_baseline_manifest` — Rev. 1's guessed name — does not exist anywhere in the source tree outside Rev. 1's own draft. Real required schema: 16 fields always, 5 more (`heldout_*`) all-or-nothing.
- `eval/heldout_ledger.py` (156 lines, full): three entry kinds, not two — `schedule` (7 fields), `run` (9 fields: adds `config_hash`, `result_sha256`), `generalisation_schedule` (10 fields, different tail). `date` and `purpose` are required on **every** kind. The real committed `config/eval/heldout_ledger.jsonl` (5 lines, shown complete by the agent) confirms this shape on every line — none of the 5 real lines match Rev. 1's 5-field draft entry.
- `eval/panel.py:51-69`: `team_content_hash(teams_root, team_path)` requires **both** `.txt` and `.packed` to exist and hashes a canonical JSON object of both files' text content together — confirmed by reading the function body directly, not inferred from a docstring. Rev. 1's plan-local `_team_content_hash(team_path)` was a different, single-file, incompatible function sharing the same name — a real collision risk if any Gate B code path had imported the wrong one, not merely an omission.
- `eval/result_jsonl.py` (111 lines, full): complete `REQUIRED_FIELDS` (19 fields) and `NULLABLE_FIELDS` (10 fields) enumerated; `validate_battle_row` rejects any field outside both sets. Task 9's row-building now matches this schema exactly, field-for-field.

## What this addendum does not cover

`_derive_config_hash`'s exact body (Task 9) still needs reconciliation against
`resolve_coverage_provenance`'s real config-hashing logic beyond its signature — flagged
explicitly in the plan itself (Task 9, Step 3) as unverified-in-full, not silently assumed
correct. This is the one remaining traced gap carried forward into Rev. 2 rather than closed.
