# Champions Panel v0 — I5 Mixed Verdict

**Date:** 2026-07-14
**Verdict:** **I5 CONFIG/PROVENANCE PASS · STANDARD SAFETY FAIL (latency) · STATE-DEGRADATION FOUND**
**Git @ run:** `4da007b` (`dirty=false`) on branch `feat/champions-i5-smoke` (I4 merge base `f192aff`)

## Question

After I4 (Champions `FormatConfig`, vendored calc pin, speed-oracle gen-0), does the eval harness run a
**10-row** schedule (5 panel teams × 2 opponent policies; 6 dev + 4 held-out) with book/priors/spreads
loaded, clean provenance, and heuristic decisions on the happy path?

This run is **not** a strength gate and **not** a full standard safety pass.

## Run configuration

| Field | Value |
|-------|-------|
| Schedule | `config/eval/schedules/champions_v0_smoke_i5.yaml` |
| Panel | `config/eval/panels/panel_champions_v0.yaml` |
| `panel_hash` | `aac1ea30446fde88` |
| `schedule_hash` | `d6fba5070cd7cb49` |
| Battles | 10 (5 teams × heuristic + max_damage × 1 seed) |
| `seed_base` | `champions-panel-v0-smoke-i5` |
| Showdown | `f8ac140` + seeded-battle patch |
| `PYTHONHASHSEED` | `0` |

## Verdict breakdown

| Axis | Result |
|------|--------|
| **Config / provenance** | **PASS** — FormatConfig + calc pin + priors/spreads in `config_hash`; `dirty=false` |
| **Harness completion** | **PASS** — 10/10 rows, `crashes=0`, `invalid_choices=0`, dev + held-out complete |
| **Standard safety (`eval-report --mode gate`)** | **FAIL** — `latency_p95`: worst row **3235 ms** vs **1000 ms** budget (`config/eval/gates.yaml`) |
| **State fidelity** | **FAIL** — 5 hero decisions degraded to random-legal via `choose_for_request` after `100y`/`100g` HP-suffix state-build failures |

Artefacts: `data/eval/champions-panel-v0/smoke-i5/{results.jsonl,results.jsonl.manifest.json,results.jsonl.config-manifest.json,seeds.jsonl,decision_trace.jsonl,report.json,report.md}`.

## Config / provenance (PASS)

Row `config_hash` **`b8a0aa12b9f6c4de`**. Decomposed hashes (also in `results.jsonl.config-manifest.json`):

| Field | Hash |
|-------|------|
| `format_config_hash` | `cb7a785e79283ffa` |
| `calc_pin_hash` | `79a4877538c8740f` |
| `priors_hash` (protect_priors) | `62ab845d0dd64ff4` |
| `spreads_hash` (default_spreads book) | `ba6488a6d05a9975` |

P4 pilot used `config_hash=d2a17c7935c3ff77` with `book=None` / `priors=None`. The I5 hash change confirms FormatConfig + belief deps are in the behavior manifest.

## Decision trace accounting

| Bucket | Count |
|--------|------:|
| Trace lines total | 104 |
| Team preview | 10 |
| Non-preview decisions | 94 |
| True heuristic selections (`selection_stage=heuristic`, scored candidates) | 89 |
| — regular_turn heuristic | 77 |
| — forced_replacement heuristic | 12 |
| **State-degraded** (no `selection_stage`, no `candidates`) | **5** |

The 5 degraded rows correlate with gauntlet `state build failed: invalid literal for int() with base 10: '100y'/'100g'` on Champions HP suffixes. Those turns fell through to **`choose_for_request`** (random legal), not the heuristic ranker — so “heuristic on all non-preview decisions” does **not** hold.

## Decision spotcheck (happy path only)

**Repro:** `decision_trace.jsonl` where `seed_index=0`, `decision_phase=regular_turn`, `turn_number=1`.

| Field | Value |
|-------|-------|
| `selection_stage` | `heuristic` |
| `fallback_reason` | `null` |
| `chosen_candidate_id` | `(Fake Out->2, Tailwind)` |
| `chosen_rank` | `0` |
| `candidates` | 6 scored joint actions |
| `request_hash` | `99638fa2add70298a7e05163e95ad79ca148eecf8a179494af00ba0a4ea8fecd` |

This spotcheck proves the heuristic path on a clean state — not that every decision used it.

```powershell
cd showdown_bot
$env:PYTHONHASHSEED="0"
$env:SHOWDOWN_BATTLE_SEED_BASE="champions-panel-v0-smoke-i5"
python -m showdown_bot.cli gauntlet `
  --schedule ..\config\eval\schedules\champions_v0_smoke_i5.yaml `
  --result-out ..\data\eval\champions-panel-v0\smoke-i5\results.jsonl `
  --decision-trace-out ..\data\eval\champions-panel-v0\smoke-i5\decision_trace.jsonl
```

(Fresh Showdown server required for Channel A seeds.)

## Standard safety — latency (FAIL)

`eval-report --mode gate` → **`SINGLE-RUN SAFETY-FAIL`**.

| Gate | Measured | Budget |
|------|----------|--------|
| `latency_p95` | **3235 ms** (seed_index=1, goodstuff × max_damage) | **1000 ms** |

All other safety gates PASS (including `dirty=false`). P4 pilot reported p95=0 because latency was not measured on that path.

**Before Strength:** profile Champions decision latency and either optimize the calc/heuristic path or adopt a **pre-justified Champions-specific budget** — do not treat Reg-I 1000 ms as satisfied by assertion.

## State parser — HP suffix (BLOCKER)

Champions room lines carry HP values like `100y` / `100g`. The state builder still does `int(hp)` and fails; gauntlet logs warnings and the bot degrades to random-legal chooses for affected turns.

Battles can still complete (`crashes=0`, `end_reason=normal`), but **decision quality on those turns is wrong**. This is a **hard blocker** before strength or decision-quality claims — not a cosmetic warning.

## Explicit non-claims

- **No strength claim** — 3/10 hero wins is not interpreted.
- **Not STANDARD SAFETY-PASS** — official gate fails on latency.
- **Not full heuristic fidelity** — 5/94 non-preview decisions were random-legal degradation.
- **Live damage path still gen-9** — I4 wired speed oracle to calc gen-0; live damage scoring can still use gen-9 mechanics.
- **Mega overlay** not modeled.

## Next (ordered)

1. **Fix `100y`/`100g` HP-suffix state parser** (stop random-legal degradation).
2. Thread live **damage** through calc gen-0 (Champions profile).
3. **Mega** modeling overlay.
4. **Latency** profile / Champions budget decision.
5. Only then: Champions **strength** / decision-quality eval (T6 paired baseline).
