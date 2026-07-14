# Champions Panel v0 — I5 Smoke Verdict

**Date:** 2026-07-14  
**Verdict:** **I5 SMOKE-PASS** (FormatConfig + belief deps wired; dev + held-out; not strength)  
**Git @ run:** `4da007b` (`dirty=false`) on branch `feat/champions-i5-smoke` (includes I4 merge base `f192aff`)

## Question

After I4 (Champions `FormatConfig`, vendored calc pin, speed-oracle gen-0), can the eval harness run a
**10-row** schedule (5 panel teams × 2 opponent policies; 6 dev + 4 held-out) with book/priors/spreads
loaded, clean provenance, and heuristic decisions (not random fallback)?

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

## I5 gate results (user scope)

| Check | Result |
|-------|--------|
| Rows complete | 10/10 schedule rows → result rows |
| `crashes` | 0 |
| `invalid_choices` | 0 |
| `dirty` | `false` (all rows + manifest) |
| Dev cells | 6/6 complete |
| Held-out cells | 4/4 complete (incl. rain_offense + disruption) |
| `format_id` | constant `gen9championsvgc2026regma` |
| `panel_hash` | rows match `aac1ea30446fde88` |
| Seed log alignment | 10 contiguous, derived (post-hoc `seeds.jsonl` from `derive_battle_seed`) |
| Heuristic path | decision trace: `selection_stage=heuristic`, populated `candidates`, no `fallback_reason` |

Artefacts: `data/eval/champions-panel-v0/smoke-i5/{results.jsonl,results.jsonl.manifest.json,seeds.jsonl,decision_trace.jsonl,report.json,report.md}`.

### Provenance hashes (recomputed from format yaml + calc pin)

Pinned in row `config_hash` **`b8a0aa12b9f6c4de`**:

| Artifact | Hash |
|----------|------|
| `format_config_hash` | `cb7a785e79283ffa` |
| `calc_pin_hash` | `79a4877538c8740f` |
| `priors_hash` (protect_priors) | `62ab845d0dd64ff4` |
| `spreads_hash` (default_spreads book) | `ba6488a6d05a9975` |

P4 used `book=None` / `priors=None` (`config_hash=d2a17c7935c3ff77`). I5 `config_hash` change confirms FormatConfig + belief deps are in the behavior manifest.

## Decision spotcheck (heuristic ≠ random fallback)

**Repro:** filter `decision_trace.jsonl` for `seed_index=0`, `decision_phase=regular_turn`, `turn_number=1`.

| Field | Value |
|-------|-------|
| `selection_stage` | `heuristic` |
| `fallback_reason` | `null` |
| `chosen_candidate_id` | `(Fake Out->2, Tailwind)` |
| `chosen_rank` | `0` |
| `candidates` | 6 scored joint actions (rank 0 score 4.49 … rank 5 score 2.39) |
| `request_hash` | `99638fa2add70298a7e05163e95ad79ca148eecf8a179494af00ba0a4ea8fecd` |
| `actual_choose_string` | `/choose move 3 2, move 3\|4` |

Across 89 regular-turn heuristic decisions: zero `fallback_reason` entries; random fallback would omit ranked candidates.

```powershell
cd showdown_bot
$env:PYTHONHASHSEED="0"
$env:SHOWDOWN_BATTLE_SEED_BASE="champions-panel-v0-smoke-i5"
python -m showdown_bot.cli gauntlet `
  --schedule ..\config\eval\schedules\champions_v0_smoke_i5.yaml `
  --result-out ..\data\eval\champions-panel-v0\smoke-i5\results.jsonl `
  --decision-trace-out ..\data\eval\champions-panel-v0\smoke-i5\decision_trace.jsonl
```

(Fresh Showdown server required for Channel A seeds; `seeds.jsonl` can be derived offline for eval-report alignment.)

## eval-report note (harness gate, not I5 scope)

`eval-report --mode gate` → **`SINGLE-RUN SAFETY-FAIL`** on **`latency_p95`** only: worst row p95 ≈ 2.3–3.1 s vs pinned budget 1000 ms (`config/eval/gates.yaml`, Reg-I baseline). P4 pilot reported p95=0 because latency was not measured on that path. Champions FormatConfig + calc-backed heuristic is slower; **not interpreted as a strength or regression signal** here.

All other safety gates PASS (including `dirty=false`).

## Harness warnings (non-blocking)

- Rain/disruption battles logged intermittent `state build failed: invalid literal for int() with base 10: '100y'/'100g'` (Champions HP suffix); battles completed with `end_reason=normal`, `crashes=0`.

## Explicit non-claims

- **No strength claim** — 3/10 hero wins is not interpreted.
- **Live damage path still gen-9** — I4 wired speed oracle to calc gen-0; damage scoring in live decisions can still use gen-9 mechanics until explicitly threaded.
- **Mega overlay** not modeled; strength runs would be hard to interpret until damage gen-0 + Mega are addressed.

## Next (post-I5, user-gated)

1. Thread live **damage** decisions through calc gen-0 (Champions profile).
2. Mega modeling overlay (open).
3. Only then: Champions **strength** / decision-quality eval (T6 paired baseline).
