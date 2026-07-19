# Champions Panel v0 — I6 Live-Damage Gen-0 Smoke

**Date:** 2026-07-14
**Verdict:** **I6 LIVE-DAMAGE GEN-0 PASS · 2-BATTLE SAFETY-PASS · NO STRENGTH CLAIM**
**Git @ run:** `3bcd4b3` (`dirty=false`) on branch `main`

## Question

After wiring `CalcProfile` through live heuristic, `max_damage`, and export/rollout paths (I6),
does a minimal 2-battle Champions schedule complete with zero safety violations and pass standard
gate checks — without claiming strength?

This run is **not** a strength gate. Hero win counts are not interpreted.

## Run configuration

| Field | Value |
|-------|-------|
| Schedule | `config/eval/schedules/champions_v0_smoke_i6_2battle.yaml` |
| Panel | `config/eval/panels/panel_champions_v0.yaml` |
| `panel_hash` | `aac1ea30446fde88` |
| `schedule_hash` | `b67a851881d76918` |
| Battles | 2 (seed_index 0–1: heuristic + max_damage opponents) |
| `seed_base` | `champions-panel-v0-smoke-i6` |
| Showdown | `f8ac140` + seeded-battle patch (fresh server) |
| `PYTHONHASHSEED` | `0` |
| `SHOWDOWN_CALC_BACKEND` | `persistent` |
| `run_id` | `8a2ec9133cfe83ac` |
| Gauntlet cwd | `showdown_bot/` (team paths relative to this root) |
| Worktree | detached @ `3bcd4b3` (`.worktrees/i6-smoke-rerun`) |

Committed artefacts (eval record commit):
`data/eval/champions-panel-v0/smoke-i6-damage-gen0/{results.jsonl,results.jsonl.manifest.json,seeds.jsonl,report.json,report.md}`.

Raw gauntlet log archived locally at
`%USERPROFILE%\.cache\showdownbot\measurements\champions-panel-v0-smoke-i6-damage-gen0\run.log`
(not in repo).

## Verdict breakdown

| Axis | Result |
|------|--------|
| **I6 gen-0 damage wiring** | **PASS** — hermetic gates G2–G11 (`test_i6_damage_gen.py`, 18/18) |
| **Harness completion** | **PASS** — 2/2 rows, `crashes=0`, `invalid_choices=0`, `dirty=false` |
| **Standard safety (`eval-report --mode gate`)** | **PASS** — worst p95 **331 ms** vs **1000 ms** budget |
| **Strength** | **NO CLAIM** — 0/2 hero wins not interpreted |

## Per-battle summary

| seed_index | opp_policy | opp_team | turns | p95 (ms) | winner |
|-----------:|------------|----------|------:|---------:|--------|
| 0 | heuristic | goodstuff (dev) | 6 | 331 | villain |
| 1 | max_damage | rain_offense (heldout) | 6 | 267 | villain |

## Hermetic evidence

Implementation commits `ff3772f`…`3bcd4b3` (5 commits). Audit:
`docs/projects/champions/audits/2026-07-14-champions-live-damage-gen0-i6-audit.md`.

## Reproduction

```powershell
# Terminal 1 — fresh server
cd $env:USERPROFILE\.cache\showdownbot\pokemon-showdown
$env:SHOWDOWN_BATTLE_SEED_BASE = "champions-panel-v0-smoke-i6"
$env:SHOWDOWN_EVAL_SEED_LOG = "<repo>\data\eval\champions-panel-v0\smoke-i6-damage-gen0\seeds.jsonl"
node pokemon-showdown start --no-security

# Terminal 2 — gauntlet (must run from showdown_bot/)
cd <repo>\showdown_bot
$env:PYTHONHASHSEED = "0"
$env:SHOWDOWN_BATTLE_SEED_BASE = "champions-panel-v0-smoke-i6"
$env:SHOWDOWN_CALC_BACKEND = "persistent"
python -m showdown_bot.cli gauntlet `
  --schedule "..\config\eval\schedules\champions_v0_smoke_i6_2battle.yaml" `
  --panel "..\config\eval\panels\panel_champions_v0.yaml" `
  --result-out "..\data\eval\champions-panel-v0\smoke-i6-damage-gen0\results.jsonl"

python -m showdown_bot.cli eval-report `
  --run-a "..\data\eval\champions-panel-v0\smoke-i6-damage-gen0\results.jsonl" `
  --seedlog-a "..\data\eval\champions-panel-v0\smoke-i6-damage-gen0\seeds.jsonl" `
  --schedule "..\config\eval\schedules\champions_v0_smoke_i6_2battle.yaml" `
  --panel "..\config\eval\panels\panel_champions_v0.yaml" `
  --out "..\data\eval\champions-panel-v0\smoke-i6-damage-gen0" `
  --mode gate
```

Expected gate readout: **`SINGLE-RUN SAFETY-PASS`**, worst p95 ≤ **1000 ms** (budget; observed **331 ms** on the frozen run).
