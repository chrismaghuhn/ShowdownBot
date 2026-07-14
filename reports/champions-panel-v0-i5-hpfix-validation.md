# Champions Panel v0 — I5 HP-Fix Revalidation

**Date:** 2026-07-14
**Verdict:** **HP-SUFFIX STATE-DEGRADATION PASS · STANDARD SAFETY PASS (this run) · NO STRENGTH CLAIM**
**Git @ run:** `62117b5` (`dirty=false`) on branch `main` (PR #6 merged)

## Question

After merging the HP color-suffix parser fix (`62117b5`), does the same I5 10-row schedule
(`champions-panel-v0-smoke-i5` seed base) still expose real `/100r|y|g` tokens and run every
hero non-preview decision through the heuristic ranker — with zero state-degraded random-legal
fallback?

This run is **not** a strength gate. Latency readouts are observational only; they do not
establish causal improvement and do not by themselves replace the prior I5 latency baseline.

## Run configuration

| Field | Value |
|-------|-------|
| Schedule | `config/eval/schedules/champions_v0_smoke_i5.yaml` |
| Panel | `config/eval/panels/panel_champions_v0.yaml` |
| `panel_hash` | `aac1ea30446fde88` |
| `schedule_hash` | `d6fba5070cd7cb49` |
| Battles | 10 (5 teams × heuristic + max_damage × 1 seed) |
| `seed_base` | `champions-panel-v0-smoke-i5` |
| Showdown | `f8ac140` + seeded-battle patch (fresh server) |
| `PYTHONHASHSEED` | `0` |
| `SHOWDOWN_CALC_BACKEND` | `persistent` |
| `run_id` | `92e9ad03a1a13327` |

Committed artefacts:
`data/eval/champions-panel-v0/smoke-i5-hpfix-validation/{results.jsonl,results.jsonl.manifest.json,results.jsonl.config-manifest.json,seeds.jsonl,decision_trace.jsonl,suffix-evidence.json,report.json,report.md}`.

Committed `results.jsonl` rows carry `room_raw_path=null` (provenance boundary). Suffix exposure
is recorded in **`suffix-evidence.json`** (committed). Raw room logs and the gauntlet run log
remain local-only at `%USERPROFILE%\.cache\showdownbot\measurements\champions-panel-v0-i5-hpfix-validation\`.

## Seed parity (I5 baseline vs revalidation)

Both runs used `SHOWDOWN_BATTLE_SEED_BASE=champions-panel-v0-smoke-i5`. The seed JSONL files
differ in whitespace formatting but are **semantically identical**: all 10 `(battle_index, seed,
seed_base)` tuples match between `smoke-i5/seeds.jsonl` and `smoke-i5-hpfix-validation/seeds.jsonl`.

## Verdict breakdown

| Axis | Result |
|------|--------|
| **HP-suffix state degradation** | **PASS** — 0 degraded non-preview; 0 `state build failed`; 3 suffix events in `suffix-evidence.json` |
| **Harness completion** | **PASS** — 10/10 rows, `crashes=0`, `invalid_choices=0`, `dirty=false` |
| **Standard safety (`eval-report --mode gate`)** | **PASS (this run)** — worst p95 **429 ms** vs **1000 ms** budget |
| **Strength** | **NO CLAIM** — 3/10 hero wins not interpreted |

## Suffix exposure (`suffix-evidence.json`)

Committed file: `data/eval/champions-panel-v0/smoke-i5-hpfix-validation/suffix-evidence.json`
(`schema_version=champions-hp-suffix-evidence-v1`).

| Marker | Count |
|--------|------:|
| Total | **3** |
| `y` | **2** |
| `g` | **1** |
| `r` | **0** |

| seed_index | Panel match-up | Turn | Token | `normalized_room_log_sha256` (prefix) |
|-----------:|----------------|-----:|-------|---------------------------------------|
| 1 | goodstuff × max_damage (dev) | 2 | `50/100y` | `3a97ab09…` |
| 1 | goodstuff × max_damage (dev) | 10 | `20/100y` | `3a97ab09…` |
| 8 | disruption × heuristic (held-out) | 8 | `50/100g` | `5a700f92…` |

Note: seed_index=1 was the primary degradation locus in the pre-fix I5 trace (4/5 degraded rows).

## Decision trace accounting

| Bucket | Pre-fix I5 (`4da007b`) | Post-fix validation (`62117b5`) |
|--------|----------------------:|--------------------------------:|
| Trace lines total | 104 | 109 |
| Team preview | 10 | 10 |
| Non-preview | 94 | 99 |
| `regular_turn` | 81 | 86 |
| `forced_replacement` | 13 | 13 |
| Heuristic (`selection_stage=heuristic` + candidates) | 89 | **99** |
| State-degraded (no `selection_stage`, no candidates) | **5** | **0** |
| Other fallback reasons | — | none |

Non-preview count differs (94 → 99) because fixed state changes battle trajectories (e.g.
seed_index=1: 5 → 10 turns). The acceptance criterion is **0 degraded**, not identical turn counts.

## Log search (local run log)

Local gauntlet log at the measurement path above; not committed.

| Pattern | Hits |
|---------|-----:|
| `state build failed` | 0 |
| `invalid literal for int` | 0 |
| `100y` / `100g` / `100r` | 0 |
| `choose_for_request` | 0 |
| Invalid Choice | 0 |
| Exception / Traceback | 0 |

## Standard safety — latency (this run)

`eval-report --mode gate` → **SINGLE-RUN SAFETY-PASS**.

| Gate | Measured | Budget |
|------|----------|--------|
| `latency_p95` | **429 ms** (seed_index=2, tailwind × heuristic) | **1000 ms** |

**Latency context (non-causal):** Prior I5 @ `4da007b` also contained state-degradation and
measured worst p95 **3235 ms** (`eval-report --mode gate` SAFETY-FAIL). This revalidation run
measured worst p95 **429 ms** and passes the Reg-I gate. The two numbers are **not comparable as
a before/after latency fix** — trajectories differ, sample is n=10, and no causal link between
HP-suffix degradation and the I5 p95 measurement has been established. **Champions latency remains
an open product decision** until a dedicated profile or pre-justified budget is agreed.

## Explicit non-claims

- **No strength claim** — 3/10 hero wins is not interpreted.
- **No causal latency claim** — 429 ms vs 3235 ms is observational only.
- **Live damage path still gen-9** — speed oracle is gen-0 (I4); live damage scoring unchanged.
- **Mega overlay** not modeled.

## Reproduction

Fresh server (Channel A):

```powershell
cd $env:USERPROFILE\.cache\showdownbot\pokemon-showdown
$env:SHOWDOWN_BATTLE_SEED_BASE = "champions-panel-v0-smoke-i5"
$env:SHOWDOWN_EVAL_SEED_LOG = "...\smoke-i5-hpfix-validation\seeds.jsonl"
node pokemon-showdown start --no-security
```

Gauntlet (single process; **`SHOWDOWN_ROOM_RAW_DUMP` required** for suffix-exposure verification — write to a local path outside the repo, then derive `suffix-evidence.json`):

```powershell
cd showdown_bot
$env:PYTHONHASHSEED = "0"
$env:SHOWDOWN_BATTLE_SEED_BASE = "champions-panel-v0-smoke-i5"
$env:SHOWDOWN_CALC_BACKEND = "persistent"
$env:SHOWDOWN_ROOM_RAW_DUMP = "$env:USERPROFILE\.cache\showdownbot\measurements\champions-panel-v0-i5-hpfix-validation\room_raw"
python -m showdown_bot.cli gauntlet `
  --schedule ..\config\eval\schedules\champions_v0_smoke_i5.yaml `
  --result-out ..\data\eval\champions-panel-v0\smoke-i5-hpfix-validation\results.jsonl `
  --decision-trace-out ..\data\eval\champions-panel-v0\smoke-i5-hpfix-validation\decision_trace.jsonl
```

After the run: set all `room_raw_path` values to `null` in the committed `results.jsonl`, derive
`suffix-evidence.json` from the raw dumps, and move raw logs out of the repo tree.

Report:

```powershell
python -m showdown_bot.cli eval-report `
  --run-a ..\data\eval\champions-panel-v0\smoke-i5-hpfix-validation\results.jsonl `
  --seedlog-a ..\data\eval\champions-panel-v0\smoke-i5-hpfix-validation\seeds.jsonl `
  --schedule ..\config\eval\schedules\champions_v0_smoke_i5.yaml `
  --panel ..\config\eval\panels\panel_champions_v0.yaml `
  --out ..\data\eval\champions-panel-v0\smoke-i5-hpfix-validation `
  --mode gate
```

## Next (ordered)

1. **Live damage → calc gen-0** (Champions profile).
2. **Mega** modeling overlay.
3. **Latency** profile / Champions budget decision (I5 baseline: **3235 ms** worst p95).
4. Only then: Champions **strength** / decision-quality eval (T6 paired baseline).
