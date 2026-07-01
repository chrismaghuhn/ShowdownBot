# 2b-3.5 T1c — Non-Mirror Scheduling Smoke (2026-07-01)

The last piece of T1: the gauntlet now plays **two different teams** driven by a versioned
schedule, with the per-battle seed (T1b) threaded by `seed_index`. Branch:
`feat/slice-2b35-t1c-nonmirror-scheduling`.

## What was built
- **Schedule loader** `eval/schedule.py`: `load_schedule` → versioned `Schedule` of rows
  `(config_id, hero_team_path, opp_policy, opp_team_path, seed_index)`; fail-fast on
  unknown/missing fields, unknown `opp_policy`, and `seed_index` not unique+contiguous-from-0;
  rows sorted by `seed_index`; stable `schedule_hash`. `verify_schedule_alignment` ties the
  schedule to the server seed log. **N1:** `verify_seed_log` now raises a clear `SeedLogError`
  on a missing log file. (10+1 tests.)
- **Per-side teams** `client/gauntlet.py`: `run_local_gauntlet(opp_team_path=None)` +
  `_resolve_side_teams` — villain fields a **different** packed team when given; `None` = mirror
  (back-compat). `battle/` untouched (INV-1). (3 tests.)
- **Two legal opponent teams** `teams/opp_variant_{a,b}`: same proven-legal
  species/moves/items/abilities as `fixed_team`, different EV spreads / natures / Tera →
  genuinely different packed teams. Both `validate-team gen9vgc2025regi` **clean**; packed via
  the clone's `pack-team`.
- **CLI** `gauntlet --schedule <path>`: runs each row as one battle in `seed_index` order; when
  `SHOWDOWN_BATTLE_SEED_BASE`+`SHOWDOWN_EVAL_SEED_LOG` are set, calls `verify_schedule_alignment`
  at the end (fail-fast on retry/extra battle or misalignment).
- **Smoke schedule** `config/eval/schedules/smoke_nonmirror.yaml`: 2 rows,
  `fixed_team` vs `opp_variant_a` (seed 0) and vs `opp_variant_b` (seed 1), `opp_policy=heuristic`.

## Method
Two **fresh** servers A and B, same `SHOWDOWN_BATTLE_SEED_BASE=smoke2026` + `SHOWDOWN_EVAL_SEED_LOG`,
`PYTHONHASHSEED=0` set before each Python launch, persistent calc, `SHOWDOWN_ROOM_RAW_DUMP` on.
`gauntlet --schedule config/eval/schedules/smoke_nonmirror.yaml` run once per server.

## Results — `schedule_hash=00b028b08e714b62`

| Gate | Result |
|---|---|
| **Both rows ran** | 2 battles (seed 0: fixed vs variant_a → villain; seed 1: fixed vs variant_b → hero); totals 1/1, `invalid=0 crashes=0` |
| **Non-mirror** | `hero_packed != villain_packed` for both rows (fixed vs variant_a; fixed vs variant_b) |
| **Seed-log alignment** | OK — `seed_i == derive_battle_seed("smoke2026", seed_index)` for both; seed logs **byte-identical A ≡ B** |
| **Cross-run reproduction** | both battles **byte-identical** across fresh servers A vs B (sim-lines 203, 198; name-canonicalized) |
| **Two distinct opp teams** | row 0 uses variant_a, row 1 uses variant_b (distinct packed) |
| **Mirror back-compat** | plain `gauntlet --games 1` (no `--schedule`) → 1/1, `invalid=0 crashes=0` |
| **Suite** | **494 passed** |

Seeds used: `sodium,7da8bf3bfcbd7ee7628d2323798ccb17` (seed_index 0), `sodium,c05a86444b2330ed3abc47c7cda8a861` (seed_index 1).

## Scope honesty (→ T3, not T1c)
The two opponent teams are **legal spread/nature/Tera variants** of the base team (same species).
This fully exercises the **non-mirror plumbing** — distinct packed teams → distinct in-battle stats
→ distinct, reproducible battles — with zero legality/heuristic-playability risk (both validate clean;
the heuristic played them with 0 invalid / 0 crashes). **Species-diverse archetype teams (~8–12) are
explicitly T3 Panel's deliverable** per the approved eval-harness plan; T1c only proves the scheduling
+ per-side-team mechanism.

## Channel-A caveat (T1-CC-B, travels forward)
`seed_index` is **not** transmitted through `/challenge`; it aligns with the server's process-local
counter only because the runner executes rows in `seed_index` order against a **fresh** server. The
runner enforces this via the final seed-log alignment gate — a retry/extra battle desyncs the counter
and fails fast. **No battle-level retry.**

## VERDICT: **non-mirror scheduling — PASS** (parent-plan T1 complete)
Two different teams, schedule-driven, per-battle-seeded, reproducible across fresh servers, safety
floor held, mirror path back-compatible. **Unlocks T2** (per-battle result JSONL) → T3 panel → T4/T5/T6.

## Reproduce
```bash
cd ~/.cache/showdownbot/pokemon-showdown   # patched + built
SHOWDOWN_BATTLE_SEED_BASE=smoke2026 SHOWDOWN_EVAL_SEED_LOG=/tmp/seedsA.jsonl \
  node pokemon-showdown start --no-security --skip-build 8000   # fresh server (again for run B)
cd <repo>/showdown_bot
PYTHONHASHSEED=0 SHOWDOWN_CALC_BACKEND=persistent SHOWDOWN_ROOM_RAW_DUMP=/tmp/runA \
  SHOWDOWN_BATTLE_SEED_BASE=smoke2026 SHOWDOWN_EVAL_SEED_LOG=/tmp/seedsA.jsonl \
  python -m showdown_bot.cli gauntlet --schedule <repo>/config/eval/schedules/smoke_nonmirror.yaml
```

**STOP** — T1c done (all 4 tasks + N1). Awaiting Plan-Claude report/code review; **not merged**.
No T2–T6.
