# 2b-3.5 T1b — Per-Battle Seed Reproduction Proof (2026-07-01)

T1a proved a *single* fixed seed reproduces a battle. T1b makes each battle get a **distinct,
reproducible** seed (Channel A: server base + process-local counter) and proves it with a **direct**
seed-log gate, not just a `room_raw` inference. Branch: `feat/slice-2b35-t1b-perbattle-seed`.

## What was built
- **Python** `eval/seeding.py`: `derive_battle_seed(base, i) = "sodium," + sha256(f"{base}:{i}")[:32]`
  (pinned known vectors) + `verify_seed_log` (the PRIMARY gate: logged seed == derive, `battle_index`
  contiguous-from-0, exact count — any retry/extra battle → `SeedLogError`). 8 tests.
- **Server patch** (`ladders.ts`, re-exported to [the artifact](tools/eval/patches/pokemon-showdown-seeded-battle.patch)):
  `SHOWDOWN_BATTLE_SEED_BASE` mode derives `seed_i` from a process-local counter (mirrors the Python
  formula character-for-character); `SHOWDOWN_EVAL_SEED_LOG` appends the **actual** seed used per battle
  as JSONL. Build clean; round-trip `git apply` verified.
- **Comparator** `eval/room_dump.py`: `name_subs`/`GAUNTLET_NAME_SUBS` canonicalize the per-run random
  bot-name suffix for **cross-run** comparison (a session label, like the room id; not a sim output).

## Method
- Two **fresh** servers A and B (T1-CC-B), same `SHOWDOWN_BATTLE_SEED_BASE=run2026`, each with its own
  `SHOWDOWN_EVAL_SEED_LOG`. `PYTHONHASHSEED=0` set **before** each Python gauntlet launched (T1-CC-E).
  `gauntlet --games 4 --villain heuristic` (heuristic-vs-heuristic mirror; sim seed = only randomness),
  persistent calc, `SHOWDOWN_ROOM_RAW_DUMP` on. Servers restarted between runs so each counter starts 0.

## Results

**① PRIMARY gate — server-logged seed == Python `derive_battle_seed` (T1-CC-D):**

| battle_index | server-logged seed | `== derive_battle_seed("run2026", i)` |
|---|---|---|
| 0 | `sodium,a32cceab439a5fa3fd603bb706de835a` | ✅ |
| 1 | `sodium,cf62088cdab12fe1542792e890d9bf9f` | ✅ |
| 2 | `sodium,63e9c2738061c183413c87a4ddfd4806` | ✅ |
| 3 | `sodium,a1c63d0ede4412ff8b2927e867d5012f` | ✅ |

`battle_index` contiguous 0–3, count == 4, **seedsA ≡ seedsB** (same base + order → same sequence). The
first two also equal the unit-test pinned vectors → Python↔server derivation confirmed (T1-CC-A).

**② Cross-run reproduction — fresh server A vs fresh server B (name-canonicalized):**

| battle_index | identical | sim-lines | winner (A ≡ B) |
|---|---|---|---|
| 0 | ✅ | 187 | HeuristicBot |
| 1 | ✅ | 190 | BaselineBot |
| 2 | ✅ | 183 | BaselineBot |
| 3 | ✅ | 529 | HeuristicBot |

Every battle reproduced **byte-identical** across two independent fresh-server runs. (Before name
canonicalization the only diff was the random bot-name suffix `HeuristicBot5519` vs `…1044`, which the
tested `GAUNTLET_NAME_SUBS` strips; a control test confirms it does **not** hide real divergence.)

**③ Within-run distinctness:** all 4 battles pairwise **distinct** — distinct per-index seeds produce
distinct battles (not one seed repeated).

**Safety:** run A `2/4`, run B `2/4`; both `invalid_choices=0 crashes=0`, p95 200/191 ms. Suite **green**.

## Hard rule — no battle-level retry (Channel A)
`verify_seed_log` requires exactly `expected_count` records with contiguous `battle_index` from 0. A
retry/extra battle shifts the counter → non-contiguous log → `SeedLogError` (fail fast). Both runs
produced exactly 4 contiguous records; no retries occurred.

## Channel-A caveat (travels forward, T1-CC-B)
`seed_index` is **not** transmitted through `/challenge`; it aligns with the server's process-local
counter **only because** each run used a **fresh server** and created battles in order. Any paired eval
run MUST honor this (fresh server, sorted contiguous `seed_index`, no retry) — enforced by the seed-log
gate.

## VERDICT: **per-battle-reproducible — PASS**
Distinct per-battle seeds, server-used seeds proven equal to the Python derivation, and every battle
reproduces across fresh servers. The seed mechanism is ready for a schedule.

## Reproduce
```bash
cd ~/.cache/showdownbot/pokemon-showdown   # patch applied + built
SHOWDOWN_BATTLE_SEED_BASE=run2026 SHOWDOWN_EVAL_SEED_LOG=/tmp/seedsA.jsonl \
  node pokemon-showdown start --no-security --skip-build 8000    # fresh server, then again for run B
cd <repo>/showdown_bot
PYTHONHASHSEED=0 SHOWDOWN_CALC_BACKEND=persistent SHOWDOWN_ROOM_RAW_DUMP=/tmp/runA \
  python -m showdown_bot.cli gauntlet --games 4 --villain heuristic --format gen9vgc2025regi
# verify: eval.seeding.verify_seed_log(...) + eval.room_dump.compare_battle_logs(..., name_subs=GAUNTLET_NAME_SUBS)
```

**STOP** — T1b done (per-battle seed + reproduction proof). **Do not start T1c** (non-mirror
scheduling) until this report is reviewed.
