# Champions Panel v0 — P4 Pilot Smoke Verdict

**Date:** 2026-07-14  
**Verdict:** **PIPELINE-READY** (dev-only P4 smoke)  
**Scope:** Harness plumbing only — not a strength or decision-quality gate.

## Question

Can the eval harness run schedule → gauntlet → results/seeds → eval-report on the
Champions M-A panel (`gen9championsvgc2026regma`) without crashes or invalid choices?

## Run configuration

| Field | Value |
|-------|-------|
| Schedule | `config/eval/schedules/champions_v0_smoke_pilot.yaml` (committed @ `e8a58dc`) |
| Panel | `config/eval/panels/panel_champions_v0.yaml` |
| `panel_hash` | `aac1ea30446fde88` |
| `schedule_hash` | `16ba86fd592d37e4` |
| Battles | 6 (3 dev teams × 2 policies × 1 seed) |
| `seed_base` | `champions-panel-v0-smoke` |
| Showdown | `f8ac140` + seeded-battle patch |
| Git @ run | `04b0eb7` (`dirty=false`) — includes schedule + harness row-count fix |

## P4 gate results

| Check | Result |
|-------|--------|
| Rows complete | 6/6 schedule rows → result rows |
| `crashes` | 0 |
| `invalid_choices` | 0 |
| `format_id` | constant `gen9championsvgc2026regma` (all rows) |
| `panel_hash` | rows match recomputed `aac1ea30446fde88` |
| `dirty` | `false` (all rows) |
| Seed log alignment | 6 contiguous, derived |
| `eval-report` | exit 0, `SINGLE-RUN SAFETY-PASS` |

Artefacts: `data/eval/champions-panel-v0/smoke/{results.jsonl,seeds.jsonl,report.md,report.json}`.

## Held-out follow-up (separate from P4 PASS)

**rain_offense held-out cell blocked** by a Champions move-request parser gap (Meganium
`Solar Beam` → missing `target` in `BattleRequest` pydantic validation → gauntlet timeout).
Observed during an exploratory 10-row probe; not a panel/team-validation failure. Held-out
rows were omitted from the committed 6-row pilot schedule.

## Harness note

Clean reruns initially hit intermittent missing result rows (duplicate `|win|` callback with
empty `room_frames`). Fixed in `04b0eb7` (`gauntlet`: skip empty duplicate win callbacks).

## Explicit non-claims

- **No strength claim** — 2/6 hero wins is not interpreted.
- **FormatConfig still missing** — gauntlet ran with `book=None` / `priors=None` (expected
  P4 non-blocker; hard blocker for later strength/decision-quality runs).
- **Mega-readiness** not assessed here.

## Next gates (out of P4 scope)

1. Champions `FormatConfig` yaml before strength or decision-quality eval.
2. Bot move-request parsing for Champions-only moves before held-out rain cells or larger schedules.
