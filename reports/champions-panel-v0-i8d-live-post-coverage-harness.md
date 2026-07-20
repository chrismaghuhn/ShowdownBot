# VERDICT: I8-D LIVE LATENCY GATE (post-coverage-harness rerun) — PASS (active foe-Mega p95 864.94 ms ≤ 1000 ms budget)

The single separately-authorized I8-D live latency gate was re-run **exactly once**,
**unchanged**, on candidate `bd590c1` — after the opponent-Mega coverage-gate harness (Plan A)
merged via PR #37 @ `10f9adf`, then status docs reconciled via PR #38 @ `bd590c1`. A rerun was
required specifically because that merge changed the **live** decision-profile write path: every
live decision (I8-D and the coverage gate alike) now unconditionally stamps
`schema_version: decision-profile-v3` and two additional telemetry fields, so the prior PASS
(recorded under `decision-profile-v2`) does not carry over to this candidate — it measured
different code. This rerun used the **original stratum** (`oneshot`, standard per-battle
timeout, `config_hash 594295543f13a55d`, identical schedule / panel / teams). It created 75 real
battles, scored 679 live decisions, **met the D-1 exposure floor** (60 active-valid foe-Mega
decisions from 45 distinct battles), stopped on the exposure floor, and **atomically published**
a verdict.

The verdict is **`PASS`**: the active foe-Mega decision p95 is **864.94 ms**, at or under the
**1000 ms** budget. This is a **load-bearing latency verdict, not a Strength claim.** The
1000 ms budget is *not* moved after the fact. **Champions Strength remains `NO-GO`**: this
latency PASS closes the latency precondition for candidate `bd590c1` specifically — it does not
authorize a Strength run. The separate opponent-Mega coverage gate and an independent Strength
holdout must still be run and pass.

## Relationship to all prior I8-D runs (kept strictly separate, never pooled)

This is a **distinct verdict**, frozen under a **new, clearly-separated directory**. All four
runs are **never merged** — each is a single, independently-frozen run under its own directory:

| | pre-Lever-A FAIL | post-Lever-A FAIL | post-Lever-B PASS | this run (post-coverage-harness) |
|---|---|---|---|---|
| git_sha | `9fc0f36…` (team-path fix, PR #26) | `9d915f2…` (Lever A merged) | `3db4ac7…` (Lever B merged) | `bd590c1…` (coverage-gate harness + docs merged, PR #37/#38) |
| frozen dir | `data/eval/champions-panel-v0/i8d-live/` | `…/i8d-live-post-lever-a/` | `…/i8d-live-post-lever-b/` | `…/i8d-live-post-coverage-harness/` (this run) |
| report | `…/i8d-live.md` | `…/i8d-live-post-lever-a.md` | `…/i8d-live-post-lever-b.md` | `…/i8d-live-post-coverage-harness.md` (this file) |
| stratum | `oneshot`, `594295543f13a55d` | `oneshot`, `594295543f13a55d` | `oneshot`, `594295543f13a55d` | `oneshot`, `594295543f13a55d` (same throughout) |
| schema_version | `decision-profile-v1` | `decision-profile-v1` | `decision-profile-v2` | `decision-profile-v3` (coverage-gate telemetry) |
| battles / decisions | 75 / 679 | 75 / 679 | 72 / 651 | 75 / 679 |
| active / distinct | 60 / 45 | 60 / 45 | 60 / 44 | 60 / 45 |
| active foe-Mega p95 | 1110.213 ms | 1160.515 ms | 850.245 ms | **864.94 ms** |
| verdict | FAIL | FAIL | PASS | **PASS** |

All four runs share the **same stratum** (identical `config_hash`, backend, budget, D-1/D-2,
schedule, panel, teams) and differ in the **code** (`git_sha`, and consequently the emitted
telemetry `schema_version`) — that is the entire point of each rerun. They are **not pooled**;
every prior run's frozen directory and report are untouched by this one.

## Frozen evidence (`data/eval/champions-panel-v0/i8d-live-post-coverage-harness/`)

| file | sha256 | bytes |
|---|---|---|
| `profile.jsonl` | `739c05b39b5ebbedab80eaa33d7a368ffb91e05d6dfac428e20c2daefc4cc97e` | 736714 |
| `verdict.json` | `a021066a02dfea7d3b8edaabdd0c5269386582aee03e9f59b6acb6310f323543` | 699 |
| `seeds.jsonl` | `4d4ad59c2f78a938ce531670f45b4b7fd2371daae11fbb7b66a283b2edb76c6b` | 8540 |

Stored byte-exact under `.gitattributes: data/eval/champions-panel-v0/** -text` (no newline
normalization; all three are LF-only). Each git-stored blob's SHA-256 was verified equal to the
external run output (source held outside the repository, unchanged) before the freeze commit.
The frozen bytes are the run bytes.

## Verdict

| field | value |
|---|---|
| **verdict** | **`PASS`** |
| gate value | active foe-Mega decision **p95 = 864.94 ms** (`864.9399999994785`) |
| budget | **1000 ms** (`p95_is_gate_value: true`) |
| margin | −135.06 ms (≈ −13.5 %) under budget |
| `stop_reason` | `exposure_floor_met` — a clean D-1 stop, **not** a cap and **not** a timeout |
| `exposure_floor_met` | `true` |
| active-valid decisions | **60** (threshold `min_active_decisions` = 60) |
| distinct active battles | **45** (threshold `min_distinct_battles` = 20) |
| battles played | **75** |
| scored decisions | **679** (`scored_overshoot` = 0; cap `max_scored_decisions` = 2000 not reached) |
| `seed_log_verified` | `true` (server Channel-A seed log verified before the verdict) |

The verdict population is defined once, in production, as `is_active_valid_live_row`
(`decision_profile.py`): `source == "live"` ∧ `timer_scope == "agent_choose"` ∧
`outcome == "ok"` ∧ `foe_mega_active is True`. p95 uses the project nearest-rank convention
(`gauntlet._latency_p95`, no interpolation) — the same function the per-battle gate uses.

## Provenance

| field | value |
|---|---|
| git_sha | `bd590c13320627e2d03c86769257214fcf36d598` (opponent-Mega coverage-gate harness merged via PR #37 @ `10f9adf`; status docs reconciled via PR #38 @ `bd590c1`) |
| dirty | `false` (fresh detached worktree at `bd590c1`, tracked tree clean) |
| format_id | `gen9championsvgc2026regma` (Champions Reg M-A) |
| config_hash | `594295543f13a55d` (the original stratum, unchanged) |
| calc_backend | `oneshot` |
| `SHOWDOWN_CALC_BACKEND` | **unset** → `oneshot` (explicitly cleared before the run; its absence is part of `config_hash 594295543f13a55d`) |
| `SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S` | **unset** (explicitly cleared before the run — standard per-battle timeout, not the retracted 900 s stratum) |
| schema_version | `decision-profile-v3` (uniform across all 679 rows; the coverage-gate merge's live telemetry) |
| server | patched `pokemon-showdown` pinned at `f8ac140` + seed-patch, `--no-security` on port 8000 |
| host | fixed Windows host |

All of `git_sha`, `config_hash`, `calc_backend`, `schedule_hash`, `format_id`, `source`, and
`schema_version` are single-valued across every one of the 679 rows — one run, no pooling of
strata (the dataset validator also enforces a single schema version per file).

## Content-lock hashes

| artifact | hash |
|---|---|
| seed namespace (`seed_base`) | `champions-panel-v0-i8d-latency` |
| `schedule_hash` | `a1192d9dde4c65df` |
| `panel_hash` (content-derived) | `aac1ea30446fde88` |
| `hero_team_hash` | `1d3a4cf5a4042532` |
| `opp_team_hashes` | `0054b6894af7215a`, `64ecc8fb2e6da7f1`, `ea99dd840d0adce2` |

The `schedule_hash` / `panel_hash` are byte-identical to all three prior runs — the panel,
schedule, and teams are unchanged; only the code (`git_sha`) advanced, and with it the live
telemetry schema (v1/v2 → v3).

## Independent re-verification — from the frozen bytes, all gates PASS

Re-checked reading only the frozen copies, reusing the production predicate, validator, and p95
(no re-derivation):

- `validate_live_profile_dataset(profile.jsonl)` → `{rows: 679, active_valid_rows: 60, distinct_active_battle_ids: 45}` (closed-schema, single-version, and uniqueness checks all pass).
- **679** rows, all `(battle_id, decision_index)` pairs unique; single `schema_version` `decision-profile-v3`.
- Verdict population recomputed independently via `is_active_valid_live_row`: **exactly 60** active-valid decisions from **exactly 45** distinct battles.
- All three verdict-report fields (`scored_decisions`, `active_valid_decisions`, `distinct_active_battles`) cross-checked field-for-field against the independently-recomputed validator report — exact match on all three.
- `seeds.jsonl`: **75** rows, single `seed_base`, matching `battles_played` exactly.
- The v3-only fields (`foe_mega_slots`, `foe_mega_order_tie`) are present on every row and were confirmed, before this run, to be read by no part of the I8-D verdict population or p95 computation — `is_active_valid_live_row` and the p95 nearest-rank convention are schema-version-agnostic by construction.
- Hygiene: every row carries the identical canonical schema; provenance fields single-valued (one run); **no local filesystem path, username, or host name leaked** into any row.

## Descriptive comparison (NOT a causal, variance, or Strength claim)

- pre-Lever-A (git `9fc0f36`) active foe-Mega p95: **1110.213 ms** (FAIL)
- post-Lever-A (git `9d915f2`) active foe-Mega p95: **1160.515 ms** (FAIL)
- post-Lever-B (git `3db4ac7`) active foe-Mega p95: **850.245 ms** (PASS)
- post-coverage-harness (git `bd590c1`, this run) active foe-Mega p95: **864.94 ms** (PASS)
- budget: **1000 ms** — this run is **+14.695 ms** relative to the post-Lever-B run,
  **−135.06 ms** under budget.

This comparison is **purely descriptive**. The observed figures **close the gate contract for
this run**, but on their own they do **not** establish any of the following, and must not be read
as doing so:

- **not a variance claim.** This is a **single** `oneshot` gate run; run-to-run variance for this
  stratum has **not** been quantified (there is no multi-run distribution here). The +14.695 ms
  difference from the post-Lever-B run is **not** established to lie outside run-to-run noise —
  only that this one run's p95 is under budget.
- **not a causal claim about the coverage-gate merge.** The merge that motivated this rerun
  (PR #37) adds decision-profile telemetry fields on the live write path; it does not change
  *which* decisions are taken. Isolating any latency effect of that telemetry addition would
  require a controlled, repeated A/B, which this gate is not. **No causal latency effect is
  derivable from this run** — it establishes only that the candidate, as it now stands, still
  meets budget.
- **not a regression or improvement claim vs. post-Lever-B.** The two runs differ in code
  (`3db4ac7` vs `bd590c1`) and in schema version (v2 vs v3); a single-run-vs-single-run
  comparison under unquantified variance cannot distinguish "slightly slower" from "noise."

## Explicit non-claims and status

This record establishes only that, at `git_sha bd590c1`, under `oneshot` on the fixed Windows
host, on this single unchanged run, the active foe-Mega decision p95 (864.94 ms) **meets** the
1000 ms live latency budget with the exposure floor satisfied, **for this specific candidate**.
It does **not** establish, and must not be read as:

- any **Strength** result — Champions Strength remains **`NO-GO`**; a latency PASS does not
  authorize a Strength run;
- any **cross-platform** latency figure, any **persistent-backend** figure, or a claim about a
  different `config_hash` (this is `oneshot` / `594295543f13a55d` only);
- a **causal** verdict on the coverage-gate merge's latency effect, or a claim about run-to-run
  variance (see the descriptive comparison above);
- validity for any **other** candidate commit — this PASS is scoped to `bd590c1` exactly; a
  future code change again requires its own separately-authorized rerun.

**The latency gate PASSes for candidate `bd590c1`; Strength stays NO-GO.** The next front-track
step is the separately-authorized opponent-Mega coverage gate and independent Strength-holdout
design — neither is authorized here. The budget is not moved.
