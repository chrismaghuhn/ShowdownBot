# 2b-3.5 T1a — Seeded Bit-Stability Proof (2026-07-01)

Resolves the terminal verdict deferred by T0. T0 proved the seed path is *feasible*
(`SEED_FEASIBILITY_PROVEN`); T1a **implements** the minimal server seed patch and
**empirically demonstrates** bit-stability. Branch: `feat/slice-2b35-t1-seed-patch-proof`.

## What was built (all versioned in this repo)
1. **Server patch** — `server/ladders.ts` `Ladder.match` → `Rooms.createBattle` now injects a
   sim PRNG seed from `SHOWDOWN_BATTLE_SEED` when set (unset → omitted → stock fresh-seed behavior).
   Versioned artifact: [pokemon-showdown-seeded-battle.patch](tools/eval/patches/pokemon-showdown-seeded-battle.patch)
   + [apply/verify README](tools/eval/patches/README.md). Applies on upstream `f8ac140`; the clone is
   never a silent undocumented state. Build clean (`node build`, exit 0).
2. **Capture** — env-gated `room_raw` dump in the gauntlet (`SHOWDOWN_ROOM_RAW_DUMP`; unset → no-op →
   bit-identical path). [gauntlet.py](showdown_bot/src/showdown_bot/client/gauntlet.py).
3. **Normalization + compare** — [eval/room_dump.py](showdown_bot/src/showdown_bot/eval/room_dump.py):
   strips only nondeterministic **server-session metadata**, keeps every sim-outcome line
   (4 unit tests, [test_room_dump.py](showdown_bot/tests/test_room_dump.py)).

## Method
- **Config:** `heuristic` vs `heuristic`, mirror `fixed_team`, `gen9vgc2025regi`, persistent calc backend.
  Heuristic-vs-heuristic deliberately (both bots deterministic, no Python `random`; the `max_damage`
  baseline has a `pick_random_pair` fallback) so the **sim seed is the only randomness source**.
- **Same-seed run:** one server started with a fixed `SHOWDOWN_BATTLE_SEED`, gauntlet `--games 2` in a
  single process (constant Python hash/set ordering across the pair). Each battle is independently
  created with the same seed → compare battle #1 vs battle #2.
- **Control:** repeat with a *different* seed; compare across seeds — a real divergence must appear
  (otherwise normalization could be hiding everything).
- **Normalization (disclosed):** dropped = room-id header (`>battle-…-N`), `|t:|`/`|:|` timestamps,
  `|inactive(off)|` timer, `|player|` (name/avatar/rating), join/leave/rename, chat, `|uhtml|`/`|html|`/
  `|raw|`, `queryresponse`. **Kept** = every sim line (`move`, `-damage`, `-crit`, `-miss`, `switch`,
  `-status`, `-boost`, `faint`, `turn`, `request`, `win`, …). A control run confirms real battle
  differences survive normalization.

## Results

| Run | Seed | Battle rooms | Same-seed identical? | Winner | Sim-lines / turns | Safety |
|---|---|---|---|---|---|---|
| A | `sodium,0123…cdef` | 145, 146 | **YES** (byte-identical normalized log) | BaselineBot (villain) | 227 / 13 | 0 invalid · 0 crash · p95 253 ms |
| B | `sodium,fedc…3210` | 156, 157 | **YES** | HeuristicBot (hero) | 188 / — | 0 invalid · 0 crash · p95 378 ms |
| A vs B | — | 145 vs 156 | **NO** — 231 differing sim-lines; **winner flips** | Baseline→Heuristic | 227 vs 188 | — |

- **Same seed → identical:** both seeds reproduced their battle **bit-for-bit** on the normalized
  protocol (identical winner + full move/damage/RNG trace) across two independently-created battles.
  Raw dumps were even byte-identical in size (46 101 bytes).
- **Different seed → different + causal:** the winner **flipped** (villain wins 0/2 under A → hero wins
  2/2 under B). The seed deterministically decides the mirror outcome. This is exactly the T0a finding
  (unseeded 3/6 split) now **brought under control**.

## VERDICT: **demonstrated PASS_STRONG**
`room_raw + result are bit-stable at a fixed seed` — the literal PASS_STRONG rubric, now shown
empirically (not just architecturally). The `SEED_FEASIBILITY_PROVEN` intermediate status from T0 is
**upgraded to demonstrated PASS_STRONG**.

- **Determinism status for later reports (CC-3):** **bit-reproducible (PASS_STRONG)** — the paired
  comparison is bit-reproducible, not merely variance-reducing. The PASS_WEAK caveat does **not** apply.
- **2b-4 gate:** the terminal verdict the gate reads (`T0 ∈ {PASS_STRONG, PASS_WEAK}`) is now
  **PASS_STRONG**.

## Honest scope limits (→ T1 proper, not T1a)
- The patch applies **one env seed to every battle** in a session. T1 proper needs a **distinct
  per-battle seed** from the schedule (e.g. base-seed + battle counter, or a seed column). The
  mechanism is proven; wiring a per-battle seed sequence is a small T1 extension of the same patch.
- Proof used **within-run** 2-game comparison (same process). Cross-process reproducibility depends on
  fixing `PYTHONHASHSEED` for the bot too if any set-ordered tie-break exists; T1's schedule runner
  should pin it. Not needed for the T1a claim (sim-seed determinism), flagged for T1.
- Config was **mirror** heuristic-vs-heuristic to isolate the seed. Non-mirror + diverse policies is
  T1+; the seed mechanism is policy-agnostic (it seeds the sim, not the bot).

## Reproduce
```bash
# 1) patch + build the local clone
cd ~/.cache/showdownbot/pokemon-showdown
git apply <repo>/tools/eval/patches/pokemon-showdown-seeded-battle.patch && node build
# 2) seeded server
SHOWDOWN_BATTLE_SEED='sodium,0123456789abcdef0123456789abcdef' \
  node pokemon-showdown start --no-security --skip-build 8000
# 3) seeded 2-game run + dump, then compare (see eval/room_dump.compare_battle_logs)
cd <repo>/showdown_bot
SHOWDOWN_CALC_BACKEND=persistent SHOWDOWN_ROOM_RAW_DUMP=/tmp/seedA \
  python -m showdown_bot.cli gauntlet --games 2 --villain heuristic --format gen9vgc2025regi
```

**STOP** — T1a scope done (patch + demonstrated PASS_STRONG). No T2–T6, no non-mirror scheduling, no
panel/policies. Awaiting review.
