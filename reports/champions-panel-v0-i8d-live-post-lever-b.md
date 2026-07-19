# VERDICT: I8-D LIVE LATENCY GATE (post-Lever-B rerun) — PASS (active foe-Mega p95 850.245 ms ≤ 1000 ms budget)

The single separately-authorized I8-D live latency gate was re-run **exactly once**,
**unchanged**, after the merged Lever B latency-reduction slice. It ran on the fixed Windows
host, against the pinned patched server, under the **original stratum** (`oneshot`, standard
per-battle timeout, `config_hash 594295543f13a55d`, seed 0, identical schedule / panel /
teams). It created 72 real battles, scored 651 live decisions, **met the D-1 exposure floor**
(60 active-valid foe-Mega decisions from 44 distinct battles), stopped on the exposure floor,
and **atomically published** a verdict.

The verdict is **`PASS`**: the active foe-Mega decision p95 is **850.245 ms**, at or under the
**1000 ms** budget. This is a **load-bearing latency verdict, not a Strength claim.** The
1000 ms budget is *not* moved after the fact. **Champions Strength remains `NO-GO`**: a latency
PASS alone does not authorize a Strength run; the separate opponent-Mega coverage gate and an
independent Strength holdout must still be designed and satisfied.

## Relationship to the prior FAIL runs (kept strictly separate, never pooled)

This is a **distinct verdict**, frozen under a **new, clearly-separated directory**. The three
runs are **never merged** — each is a single, independently-frozen run under its own directory:

| | pre-Lever-A FAIL | post-Lever-A FAIL | this run (post-Lever-B) |
|---|---|---|---|
| git_sha | `9fc0f36…` (team-path fix, PR #26) | `9d915f2…` (Lever A merged) | `3db4ac7…` (Lever B merged) |
| frozen dir | `data/eval/champions-panel-v0/i8d-live/` | `…/i8d-live-post-lever-a/` | `…/i8d-live-post-lever-b/` |
| report | `…/i8d-live.md` | `…/i8d-live-post-lever-a.md` | `…/i8d-live-post-lever-b.md` (this file) |
| stratum | `oneshot`, `594295543f13a55d` | `oneshot`, `594295543f13a55d` | `oneshot`, `594295543f13a55d` (same) |
| schema_version | `decision-profile-v1` | `decision-profile-v1` | `decision-profile-v2` (Lever B telemetry) |
| active foe-Mega p95 | 1110.213 ms | 1160.515 ms | **850.245 ms** |
| verdict | FAIL | FAIL | **PASS** |

The runs share the **same stratum** (identical `config_hash`, backend, budget, D-1/D-2,
schedule, panel, teams) and differ in the **code** (`git_sha`, and consequently the emitted
telemetry `schema_version` v1→v2) — that is the entire point of the rerun. They are **not
pooled**; the prior FAIL freezes under `i8d-live/` and `i8d-live-post-lever-a/` and all
aborted-attempt artifacts are untouched.

## Frozen evidence (`data/eval/champions-panel-v0/i8d-live-post-lever-b/`)

| file | sha256 | bytes |
|---|---|---|
| `profile.jsonl` | `759c1f7f182e231f81be2d5a29582eb2934ad91a24c59c8fcad8e93f6d8b2c53` | 675689 |
| `verdict.json` | `ade592fecc2d26da5319b47fcd6eb411dbd39268ea6f4696e885e43109c72b9b` | 699 |
| `seeds.jsonl` | `78d3dbe5a44fefbfb934b93abd0c65fe19a7e722507db986e753f141e2d46765` | 8198 |

Stored byte-exact under `.gitattributes: data/eval/champions-panel-v0/** -text` (no newline
normalization; all three are LF-only). Each git-stored blob is byte-identical to the working
file, which is byte-identical to the run output at `<external-run-root>/{profile.jsonl,
verdict.json, seeds.jsonl}` (source held outside the repository, unchanged). The frozen bytes
are the run bytes.

## Verdict

| field | value |
|---|---|
| **verdict** | **`PASS`** |
| gate value | active foe-Mega decision **p95 = 850.245 ms** (`850.2450999803841`) |
| budget | **1000 ms** (`p95_is_gate_value: true`) |
| margin | −149.755 ms (≈ −15.0 %) under budget |
| `stop_reason` | `exposure_floor_met` — a clean D-1 stop, **not** a cap and **not** a timeout |
| `exposure_floor_met` | `true` |
| active-valid decisions | **60** (threshold `min_active_decisions` = 60) |
| distinct active battles | **44** (threshold `min_distinct_battles` = 20) |
| battles played | **72** |
| scored decisions | **651** (`scored_overshoot` = 0; cap `max_scored_decisions` = 2000 not reached) |
| `seed_log_verified` | `true` (server Channel-A seed log verified before the verdict) |

The verdict population is defined once, in production, as `is_active_valid_live_row`
(`decision_profile.py`): `source == "live"` ∧ `timer_scope == "agent_choose"` ∧
`outcome == "ok"` ∧ `foe_mega_active is True`. p95 uses the project nearest-rank convention
(`gauntlet._latency_p95`, no interpolation) — the same function the per-battle gate uses.

## Provenance

| field | value |
|---|---|
| git_sha | `3db4ac7e71f6e3929b7c2cb43209cb4740dbdbd8` (Lever B merged via PR #33 @ `b192825`; status docs reconciled via PR #34 @ `3db4ac7`) |
| dirty | `false` (fresh detached worktree at `3db4ac7`, tracked tree clean) |
| format_id | `gen9championsvgc2026regma` (Champions Reg M-A) |
| config_hash | `594295543f13a55d` (the original stratum, unchanged) |
| calc_backend | `oneshot` |
| `SHOWDOWN_CALC_BACKEND` | **unset** → `oneshot` (the bound backend; its absence is part of `config_hash 594295543f13a55d`) |
| schema_version | `decision-profile-v2` (uniform across all 651 rows; Lever B added the `mixed_batch_calls` counter) |
| server | patched `pokemon-showdown` pinned at `f8ac140` + seed-patch, `--no-security` on port 8000 |
| host | fixed Windows host |

All of `git_sha`, `config_hash`, `calc_backend`, `schedule_hash`, `format_id`, `source`, and
`schema_version` are single-valued across every one of the 651 rows — one run, no pooling of
strata (the dataset validator also enforces a single schema version per file).

## Content-lock hashes

| artifact | hash |
|---|---|
| seed namespace (`seed_base`) | `champions-panel-v0-i8d-latency` |
| `schedule_hash` | `a1192d9dde4c65df` |
| `panel_hash` (content-derived) | `aac1ea30446fde88` |
| `hero_team_hash` | `1d3a4cf5a4042532` |
| `opp_team_hashes` | `0054b6894af7215a`, `64ecc8fb2e6da7f1`, `ea99dd840d0adce2` |

The `schedule_hash` / `panel_hash` are byte-identical to both prior FAIL runs — the panel,
schedule, and teams are unchanged; only the code (`git_sha`) advanced.

## Independent re-verification — from the frozen bytes, all gates PASS

Re-checked reading only the frozen copies, reusing the production predicate, validator, and p95
(no re-derivation):

- `validate_live_profile_dataset(profile.jsonl)` → `{rows: 651, active_valid_rows: 60, distinct_active_battle_ids: 44}` (closed-schema, single-version, and uniqueness checks all pass).
- **651** rows, all `(battle_id, decision_index)` pairs unique; single `schema_version` `decision-profile-v2`.
- Verdict population recomputed independently via `is_active_valid_live_row`: **exactly 60** active-valid decisions from **exactly 44** distinct battles.
- p95 recomputed via the nearest-rank convention over the 60 active `measured_ms`: **`850.2450999803841`** — bit-identical to `verdict.json.p95_ms`, and `≤ 1000` ⇒ `PASS`.
- `seeds.jsonl`: **72** rows, single `seed_base`, every profile `battle_id` is a logged, `schedule_hash`-derivable battle.
- Hygiene: every row carries the identical canonical schema; provenance fields single-valued (one run); **no local filesystem path, username, or host name leaked** into any row.

## Descriptive comparison (NOT a causal, variance, or Strength claim)

- pre-Lever-A (git `9fc0f36`) active foe-Mega p95: **1110.213 ms** (FAIL)
- post-Lever-A (git `9d915f2`) active foe-Mega p95: **1160.515 ms** (FAIL)
- post-Lever-B (git `3db4ac7`, this run) active foe-Mega p95: **850.245 ms** (PASS)
- budget: **1000 ms** — this run is **−310.270 ms** relative to the post-Lever-A run,
  **−259.968 ms** relative to the pre-Lever-A run, and **−149.755 ms** under budget.

This comparison is **purely descriptive**. The observed drop **closes the gate contract for
this run**, but on its own it does **not** establish either of the following, and must not be
read as doing so:

- **not a variance claim.** This is a **single** `oneshot` gate run; run-to-run variance for
  this stratum has **not** been quantified (there is no multi-run distribution here). It is
  therefore **not** established that the drop lies beyond the run-to-run noise band — only that
  this one run's p95 is under budget.
- **not a causal Lever-B claim.** Lever B is a **behavior-neutral** change (byte-identical
  decision output proven offline via the golden decision-equivalence suite), so it does not
  change *which* decisions are taken or *how many* — only how the early board stats/types are
  transported. Isolating its latency effect requires a controlled, repeated A/B, which this
  gate is not. **No causal Lever-B latency effect is derivable from this run.**

## Explicit non-claims and status

This record establishes only that, at `git_sha 3db4ac7`, under `oneshot` on the fixed Windows
host, on this single unchanged run, the active foe-Mega decision p95 (850.245 ms) **meets** the
1000 ms live latency budget with the exposure floor satisfied. It does **not** establish, and
must not be read as:

- any **Strength** result — Champions Strength remains **`NO-GO`**; a latency PASS does not
  authorize a Strength run;
- any **cross-platform** latency figure, any **persistent-backend** figure, or a claim about a
  different `config_hash` (this is `oneshot` / `594295543f13a55d` only);
- a **causal** verdict on Lever B's latency effect, or a claim about run-to-run variance (see
  the descriptive comparison above).

**The latency gate now PASSes for this run; Strength stays NO-GO.** The next front-track step
is the separately-authorized opponent-Mega coverage gate and independent Strength-holdout
design — neither is authorized here. The budget is not moved.
