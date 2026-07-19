# VERDICT: I8-D LIVE LATENCY GATE (post-Lever-A rerun) — FAIL (active foe-Mega p95 1160.515 ms > 1000 ms budget)

The single separately-authorized I8-D live latency gate was re-run **exactly once**,
**unchanged**, after the merged Lever A latency-reduction slice. It ran on the fixed Windows
host, against the pinned patched server, under the **original stratum** (`oneshot`, standard
180 s per-battle timeout, `config_hash 594295543f13a55d`, seed 0, identical schedule / panel /
teams). It created 75 real battles, scored 679 live decisions, **met the D-1 exposure floor**
(60 active-valid foe-Mega decisions from 45 distinct battles), stopped on the exposure floor,
and **atomically published** a verdict.

The verdict is **`FAIL`**: the active foe-Mega decision p95 is **1160.515 ms**, over the
**1000 ms** budget. This is a **load-bearing latency verdict, not a Strength claim.** The
1000 ms budget is *not* moved after the fact. Champions Strength remains **NO-GO**; live
decision latency remains the load-bearing blocker.

## Relationship to the pre-Lever-A FAIL (kept strictly separate, never pooled)

This is a **distinct verdict**, frozen under a **new, clearly-separated directory**:

| | pre-Lever-A FAIL | this run (post-Lever-A) |
|---|---|---|
| git_sha | `9fc0f36…` (team-path fix, PR #26) | `9d915f2…` (Lever A merged) |
| frozen dir | `data/eval/champions-panel-v0/i8d-live/` | `data/eval/champions-panel-v0/i8d-live-post-lever-a/` |
| report | `reports/champions-panel-v0-i8d-live.md` | `reports/champions-panel-v0-i8d-live-post-lever-a.md` (this file) |
| stratum | `oneshot`, `config_hash 594295543f13a55d` | `oneshot`, `config_hash 594295543f13a55d` (same) |
| active foe-Mega p95 | 1110.213 ms | **1160.515 ms** |
| verdict | FAIL | **FAIL** |

The two runs share the **same stratum** (identical `config_hash`, backend, budget, D-1/D-2,
schedule, panel, teams) and differ only in the **code** (`git_sha`) — that is the entire point
of the rerun. They are **not merged**; each is a single, independently-frozen run. The earlier
freeze under `i8d-live/` and all aborted-attempt artifacts are untouched.

## Frozen evidence (`data/eval/champions-panel-v0/i8d-live-post-lever-a/`)

| file | sha256 | bytes |
|---|---|---|
| `profile.jsonl` | `c8501ef43fed606fb7fcb5a683ca0867289c8d50f0c2d09dd12c17b18cad2a40` | 690032 |
| `verdict.json` | `175b345a010bbaf9cb6f5d7af134be810a3590624d8be309d1c10feb9da4c0b8` | 700 |
| `seeds.jsonl` | `4d4ad59c2f78a938ce531670f45b4b7fd2371daae11fbb7b66a283b2edb76c6b` | 8540 |

Stored byte-exact under `.gitattributes: data/eval/champions-panel-v0/** -text` (no newline
normalization). Each git-stored blob is byte-identical to the working file, which is
byte-identical to the run output at `<external-run-root>/{out/profile.jsonl, out/verdict.json,
seeds.jsonl}` (source held outside the repository, unchanged). The frozen bytes are the run
bytes.

## Verdict

| field | value |
|---|---|
| **verdict** | **`FAIL`** |
| gate value | active foe-Mega decision **p95 = 1160.515 ms** (`1160.5149999959394`) |
| budget | **1000 ms** (`p95_is_gate_value: true`) |
| margin | +160.515 ms (≈ +16.1 %) over budget |
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
| git_sha | `9d915f2d35a1354ad78f54f151e4d97613485855` (Lever A merged via PR #30 @ `6b2f955`; status docs reconciled via PR #31) |
| dirty | `false` (fresh detached worktree at `9d915f2`, tracked tree clean) |
| format_id | `gen9championsvgc2026regma` (Champions Reg M-A) |
| config_hash | `594295543f13a55d` (the original stratum, unchanged) |
| calc_backend | `oneshot` |
| `SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S` | **unset** — standard/default per-battle timeout (BEHAVIOR_AFFECTING; its absence is part of `config_hash 594295543f13a55d`) |
| schema_version | `decision-profile-v1` (uniform across all 679 rows) |
| server | patched `pokemon-showdown` pinned at `f8ac140` + seed-patch, `--no-security` on port 8000 |
| host | fixed Windows host |

All of `git_sha`, `config_hash`, `calc_backend`, `schedule_hash`, `format_id`, `source`, and
`schema_version` are single-valued across every one of the 679 rows — one run, no pooling of
strata.

## Content-lock hashes

| artifact | hash |
|---|---|
| seed namespace (`seed_base`) | `champions-panel-v0-i8d-latency` |
| `schedule_hash` | `a1192d9dde4c65df` |
| `panel_hash` (content-derived) | `aac1ea30446fde88` |
| `hero_team_hash` | `1d3a4cf5a4042532` |
| `opp_team_hashes` | `0054b6894af7215a`, `64ecc8fb2e6da7f1`, `ea99dd840d0adce2` |

Every profile `battle_id` is `make_battle_id(schedule_hash, index, seed)`-derivable, binding the
schedule to the played battles.

## Independent re-verification — from the frozen bytes, all gates PASS

Re-checked reading only the frozen copies, reusing the production predicate, validator, and p95
(no re-derivation):

- `validate_live_profile_dataset(profile.jsonl)` → `{rows: 679, active_valid_rows: 60, distinct_active_battle_ids: 45}`.
- **679** rows, all `(battle_id, decision_index)` pairs unique.
- Verdict population recomputed independently via `is_active_valid_live_row`: **exactly 60**
  active-valid decisions from **exactly 45** distinct battles.
- p95 recomputed via `gauntlet._latency_p95` over the 60 active `measured_ms`:
  **`1160.5149999959394`** — bit-identical to `verdict.json.p95_ms`, and `> 1000` ⇒ `FAIL`.
- `seeds.jsonl`: exactly **75** rows, single `seed_base`, contiguous `battle_index` 0..74,
  every seed equals `derive_battle_seed(base, index)`; every profile `battle_id` is a logged,
  `schedule_hash`-derivable battle.
- Hygiene: every row carries the identical canonical schema; provenance fields single-valued
  (one run); **no local filesystem path, username, or host name leaked** into any row.

## Descriptive comparison (NOT a causal or Strength claim)

- pre-Lever-A (git `9fc0f36`) active foe-Mega p95: **1110.213 ms**
- this run (git `9d915f2`, Lever A merged) active foe-Mega p95: **1160.515 ms**
- budget: **1000 ms** — both **FAIL**; this run is **+50.302 ms** relative to the pre-Lever-A
  run and **+160.515 ms** over budget.

This comparison is **purely descriptive**. It does **not** establish a causal latency effect of
Lever A, in either direction:

- it is a **single** `oneshot` gate run, and `oneshot` carries real run-to-run variance
  (process-start jitter, host scheduling); a two-point difference sits within that noise band,
  not a controlled measurement;
- Lever A is a **behavior-neutral** fold (proven byte-identical decision output offline), so it
  does not change *which* decisions are taken or *how many* — only where the game-mode incoming
  calc is transported. Isolating its latency effect requires a controlled, repeated A/B, which
  this gate is not.

**No causal Lever-A latency effect is derivable from this run.**

## The model projection did not materialize

The latency-reduction design's `968.513 ms` figure was always framed as a **conservative point
projection in a constant-141.7-ms-per-spawn model, not an upper bound**. Empirically it **did
not occur**: the observed active foe-Mega p95 is **1160.515 ms**, well above the `968.513 ms`
projection. The projection is not evidence; only this unchanged rerun is, and it is a `FAIL`.

## Explicit non-claims and status

This record establishes only that, at `git_sha 9d915f2`, under `oneshot` on the fixed Windows
host, the active foe-Mega decision p95 (1160.515 ms) does **not** meet the 1000 ms live budget.
It does **not** establish, and must not be read as:

- any **Strength** result — Champions Strength remains **NO-GO**;
- any **cross-platform** latency figure, any **persistent-backend** figure, or a claim about a
  different `config_hash` (this is `oneshot` / `594295543f13a55d` only);
- a **causal** verdict on Lever A's latency effect (see the descriptive comparison above).

**Latency remains the load-bearing blocker.** The next step is a new, separately-authorized
latency diagnosis/design slice — no further spontaneous gate run. The budget is not moved.
