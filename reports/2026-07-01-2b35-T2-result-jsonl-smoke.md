# 2b-3.5 T2 — Per-Battle-Result-JSONL Smoke (2026-07-01)

T2 emits **one validated JSONL row per battle** — the pairing substrate for later reporting (T5).
Branch: `feat/slice-2b35-t2-result-jsonl`.

## What was built (TDD)
- **`eval/result_jsonl.py`** — frozen row schema + `validate_battle_row` (fail-fast missing/None/unknown;
  `winner` ∈ {hero,villain,tie}) + `make_battle_id`/`make_config_hash` + append-only `BattleResultWriter`
  (validate-on-write). Config provenance split (Fix 1): `config_id` = bot version, `format_id` = format,
  `config_hash` required. (23 tests.)
- **`eval/battle_parse.py`** — side-agnostic `parse_battle_result(frames)` → `{winner_name, is_tie,
  turns, players, hp_by_slot}`; HP best-effort, null on surprise. (4 tests.)
- **`client/gauntlet.py`** — optional `on_battle_result` callback (default None → bit-identical) +
  pure `_battle_result_record` with **explicit** hero/villain/tie mapping (unknown → `ResultRowError`)
  and hero-side-minus-villain-side `end_hp_diff` via the `|player|` slot map (null if unreliable — Fix 2).
  (5 tests.)
- **`cli.py`** — `gauntlet --schedule … --result-out <path>`: assembles + writes one row per schedule
  row; `--result-out` must be missing/empty (Fix 3) and requires `SHOWDOWN_BATTLE_SEED_BASE`.

## Method
Fresh seeded server (`SHOWDOWN_BATTLE_SEED_BASE=smoke2026` + `SHOWDOWN_EVAL_SEED_LOG`), `PYTHONHASHSEED=0`,
persistent calc. `gauntlet --schedule config/eval/schedules/smoke_nonmirror.yaml --result-out …`.

## Results — 2 rows, one per schedule row (`schedule_hash=00b028b08e714b62`, `config_hash=4ce08b3f69a850f9`)

| seed_index | opp_team | winner | turns | end_hp_diff | seed (== server log) | invalid/crash |
|---|---|---|---|---|---|---|
| 0 | opp_variant_a | villain | 10 | 0.0 | `sodium,7da8bf3b…` ✅ | 0 / 0 |
| 1 | opp_variant_b | hero | 11 | 0.019802 | `sodium,c05a8644…` ✅ | 0 / 0 |

- **Config provenance (Fix 1):** every row has `config_id="heuristic"` (bot version) **distinct from**
  `format_id="gen9vgc2025regi"`, plus `config_hash` and `git_sha`. `panel_hash`/`timeouts`/`room_raw_path`
  are `null` (nullable, as designed).
- **Schema:** all rows pass `validate_battle_row` on write **and** on re-read; every row joins to its
  schedule row by `seed_index`; each `seed` equals the server seed log (T2's seed == T1c's seed).
- **Winner mapping (Fix 2):** `villain`/`hero` (roles), not suffixed names. `end_hp_diff` = hero-side −
  villain-side (row 0 = 0.0 is a genuine mutual-wipeout; the documented reserve-undercount limit does
  not affect these — all brought mons appeared).
- **Row-count gate (T2-CC-4):** `wrote 2 rows == 2 schedule rows`; seed-log alignment OK.

## Fail-fast guards (both exit 1)
- **Empty-file-required (Fix 3, T2-CC-2):** re-running with the same non-empty `--result-out` →
  `already has rows; must be non-existing or empty`.
- **Seed-base-required:** `--result-out` without `SHOWDOWN_BATTLE_SEED_BASE` →
  `requires SHOWDOWN_BATTLE_SEED_BASE (the 'seed' field must be meaningful)`.

## Safety / bit-identical
`--result-out` unset / `on_battle_result=None` → the gauntlet path is unchanged (T2-CC-3). Full suite
**526 passed** (494 → +32 T2 tests). 0 invalid / 0 crashes in the smoke.

## VERDICT: **per-battle result JSONL — PASS**
One validated row per battle, joinable by `(schedule_hash, seed_index)`, `seed` == server log, config
provenance disambiguated, explicit winner/side mapping. The pairing substrate is ready for T5.

## Out of scope (unchanged)
No T3 panel / `panel_hash` population, no report generator, no Wilson/McNemar, no override. `battle/`
untouched.

## Reproduce
```bash
cd ~/.cache/showdownbot/pokemon-showdown   # patched + built
SHOWDOWN_BATTLE_SEED_BASE=smoke2026 SHOWDOWN_EVAL_SEED_LOG=/tmp/seeds.jsonl \
  node pokemon-showdown start --no-security --skip-build 8000   # fresh server
cd <repo>/showdown_bot
PYTHONHASHSEED=0 SHOWDOWN_CALC_BACKEND=persistent SHOWDOWN_BATTLE_SEED_BASE=smoke2026 \
  SHOWDOWN_EVAL_SEED_LOG=/tmp/seeds.jsonl \
  python -m showdown_bot.cli gauntlet --schedule <repo>/config/eval/schedules/smoke_nonmirror.yaml \
  --result-out /tmp/results.jsonl
```

**STOP** — T2 done (4 tasks + smoke). Awaiting review; **not merged**. No T3/T5/override.
