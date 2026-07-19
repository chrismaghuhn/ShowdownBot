> Independent T4 smoke-schedule design by Fable 5. Non-binding review artifact; accepted findings are promoted into the T4 implementation plan separately.

# T4 — First Real Smoke Schedule: Design

**Verdict:** T4 is ready to plan as soon as T3f lands, with two small preconditions (listed in §10): the schedule generator currently only supports a *uniform* `seeds_per_cell`, and the T4 weighted matrix needs per-policy seed counts; and the repo needs a one-time decision on where result JSONLs live (committed vs. gitignored + sha256). Everything else T4 needs already exists or arrives with T3f. The design below is a **51-game weighted dev matrix with a stratified 10-row reproduction prefix** — that prefix trick is the main design idea worth adopting, because it makes fresh-server reproduction evidence cheap.

---

## 1. T4 purpose

**T4 proves exactly four things, all about the pipeline, none about strength:**

1. **Counter integrity at scale.** T1's Channel-A contract (contiguous server counter, no retries, seed-log alignment) has only ever been proven at 2–4 battles. Fifty sequential battles is where a stray reconnection, a slow battle, or an unnoticed server hiccup would surface.
2. **Row pipeline at scale.** 51 validated rows with the full T3e/T3f provenance stack (per-battle counter deltas, effective config_hash, seed_base, run_id + manifest, panel_split, end_reason, dirty flag, team hashes) — one row per scheduled battle, no gaps, no schema drift across a long run.
3. **Operational stability.** Latency stays under the pinned budget across 50 games; no battle approaches the timeout; the T3e-hardened policies stay non-degenerate over many games (activation telemetry confirms the type-aware and HP-gate paths fire in real battles, not just unit tests).
4. **T5 input readiness.** The output JSONL + seed log + manifest are, verbatim, a valid future input to the T5 report generator — T4 is the fixture T5 will be developed against.

**T4 must not claim:** anything about playing strength, reranker readiness, or config comparison; no "the bot is good/bad vs X" conclusions; no equivalence claims; and explicitly **no input to the 2b-4 unblock decision**. T4's win rates are *reference numbers recorded for later context*, labeled non-evidentiary. (Pinning a baseline is T6's job — T4 numbers are "informal pre-baseline," nothing more.)

## 2–3. Schedule shape and exact matrix

Yes — weight `heuristic` and `max_damage` heavily. They are the only opponents that measure anything; the T3c/T3e policies are calibration rungs and mechanics coverage, and spending equal seeds on them wastes half the run on cells whose outcome is nearly predetermined.

**Recommended matrix (panel_v001, panel_hash `760c1e5935fe0474`, all 3 dev teams, hero = fixed_team heuristic):**

| opp_policy | trickroom | sun | rain | seeds/cell | games |
|---|---|---|---|---|---|
| heuristic | 5 | 5 | 5 | 5 | 15 |
| max_damage | 5 | 5 | 5 | 5 | 15 |
| simple_heuristic | 3 | 3 | 3 | 3 | 9 |
| greedy_protect | 2 | 2 | 2 | 2 | 6 |
| scripted_vgc | 2 | 2 | 2 | 2 | 6 |
| **Total** | | | | | **51** |

- 30 of 51 games (59%) go to the two informative policies; the three weak policies get enough games to confirm they behave (legal, non-degenerate, distinct) without pretending their cells measure strength.
- `random` excluded — non-reproducible by design, stays out of any seeded schedule.
- All rows `panel_split: dev`; no held-out team anywhere.
- **Row ordering (the one non-obvious design point):** `seed_index` must be contiguous from 0, but the *assignment* of cells to indices is free. Order the schedule so that **rows 0–9 form a stratified reproduction prefix**: all 5 policies and all 3 teams represented (e.g. one heuristic, one max_damage per team = 6 rows, plus one row each of the three weak policies + one extra). Because `seed_i` depends only on `(seed_base, index)`, a separate 10-row prefix schedule re-run with the same seed_base reproduces exactly those seeds — making fresh-server reproduction evidence cheap (§5).
- Runtime estimate: ~15–25 turns/game, heuristic decisions with persistent calc ~0.2–2 s → very roughly 1–2 hours for the full run. The existing per-run timeout budget (`games × 150 s`) covers it; one degenerate stall battle still invalidates the run, which is intentional.

## 4. Safety gates — T4 PASS/FAIL

T4 **PASSES** only if *all* of the following hold; any single failure = FAIL, no partial credit:

| Gate | Condition |
|---|---|
| Invalid choices | total = 0 (per-battle deltas, summed) |
| Crashes | total = 0 |
| end_reason | `normal` on all 51 rows |
| p95 latency | under the T3f-pinned budget, on every row and overall |
| Seed-log alignment | `verify_schedule_alignment` green: 51 records, contiguous 0–50, every seed == derivation |
| Row count | exactly 51 rows == schedule rows; no duplicate (battle_id, config_hash) |
| panel_hash | present on all rows and == `760c1e5935fe0474` == the loaded panel file |
| Dirty flag | tree clean; `dirty = false` on all rows (a dirty T4 run is void, not warned) |
| Team hashes | hero_team_hash + opp_team_hash present on all rows; opp hashes ⊆ panel dev team hashes |
| Held-out exclusion | no held-out team_id/path/hash anywhere in schedule or rows; all rows `panel_split: dev` |
| Reproducible-only | schedule contains no non-reproducible policy; `Schedule.reproducible == true` |
| Activation telemetry | T3e counters > 0 for both the type-aware path (simple_heuristic cells) and the HP-gate path (greedy_protect cells) — the live-activation proof must hold at scale, not just in the T3e smoke |
| Config constants | one config_hash, one schedule_hash, one seed_base, one run_id across all rows; manifest fields match rows |

## 5. Reproducibility evidence

Full double runs of 51 games (~2–4 h total) are more than a smoke needs. **Minimum required evidence:**

1. **One full 51-game run** on a fresh seeded server, `PYTHONHASHSEED` pinned, passing all §4 gates.
2. **One fresh-server reproduction of the 10-row prefix** (separate prefix schedule, same seed_base): normalized `room_raw` byte-identical and winners identical for all 10 battles versus rows 0–9 of the full run. This exercises every policy and every team under reproduction, at ~20% of the cost.

If the full run comes in under ~90 minutes, run the full thing twice and diff everything — strictly better evidence, still bounded. But the prefix check is the *gate*; the full double run is opportunistic.

## 6. Result interpretation — mandatory phrasing rules

- **High win rates:** "Expected. The panel's weak policies exist for mechanics coverage and calibration; high win rates against them validate the pipeline and say nothing about strength." Never present a pooled all-policy win rate as a headline — per-policy numbers only.
- **Weak-policy wins:** report per-cell W/L only, in a table explicitly labeled "calibration cells — non-evidentiary."
- **Losses to heuristic/max_damage:** report them plainly and *without alarm framing*: "n losses in k games; at this sample size per cell this is noise-range and establishes reference numbers for T5/T6." A loss is not a bug signal unless accompanied by an invalid/crash/end_reason anomaly.
- **Mandatory ceiling/underpowered caveat (verbatim-class):** "T4 is a pipeline validation at ~50 games. No cell has enough games for a confidence interval that could support any strength claim. Nothing in this report is evidence for or against the reranker, and **this report does not contribute to the 2b-4 unblock decision** — that requires T5 statistics on T6's pinned baseline with the positive-evidence rule."
- **Why not 2b-4:** one sentence in the verdict block: 2b-4 requires paired McNemar vs a pinned baseline with n_discordant ≥ 10 and positive delta (T5/T6); T4 has no comparison config at all — it is a single-config run by design.

## 7. Required artifacts

| Artifact | Path (following existing conventions) |
|---|---|
| Schedule YAML | `config/eval/schedules/t4_smoke_v001.yaml` (+ `t4_smoke_v001_prefix.yaml` for the 10-row reproduction) |
| Result JSONL | `data/eval/t4/<date>-t4-smoke.jsonl` — 51 rows is tiny; commit it (it becomes T5's development fixture), sha256 in the report |
| Seed log | `data/eval/t4/<date>-t4-seedlog.jsonl` — commit alongside; the report's alignment check must be re-runnable |
| room_raw dumps | full run + prefix run, gzipped under `data/eval/t4/room_raw/` — needed as the reproduction evidence; if too bulky to commit, keep locally and commit only per-battle sha256s in the report |
| Run manifest (T3f) | emitted next to the JSONL, committed |
| Report | `reports/<date>-2b35-T4-smoke.md` |

## 8. T4 report outline

1. **Verdict line** — PASS/FAIL + one-sentence scope ("pipeline validation; non-evidentiary; does not touch 2b-4").
2. **Provenance block** — schedule_hash, panel_hash, config_id + effective config_hash, seed_base, run_id, git_sha + dirty, hero/opp team hashes, server patch hash + Showdown commit, PYTHONHASHSEED, JSONL/seed-log sha256s.
3. **Safety-gates table** — every §4 gate, PASS/FAIL, measured value.
4. **Reproduction evidence** — prefix run: per-battle identical/differing line counts, winner match, seed match.
5. **Activation telemetry** — type-aware and HP-gate counters, per policy.
6. **Per-cell results table** — policy × team: n, W/L/T, turns range, mean end_hp_diff; heuristic/max_damage rows visually separated from the calibration cells.
7. **Reference numbers** — per-policy win counts, labeled "informal pre-baseline; superseded by T6 pinning."
8. **Mandatory caveats** — the §6 ceiling/non-evidentiary/2b-4 text.
9. **Reproduction commands** — exact CLI + env for full run, prefix run, and gate verification.

## 9. Anti-scope-creep — explicitly out of T4

No Wilson/McNemar or any report *generator* (the T4 report is hand-assembled from gate outputs; T5 builds the generator against T4's committed JSONL); no T5 statistics of any kind; no T6 held-out gate, ledger, or baseline pinning; no held-out teams touched; no reranker/shadow/override involvement (shadow env OFF for the run — one config, minimal flags, all captured in effective config_hash); no panel growth; no policy tuning (if a weak policy behaves oddly, file it — do not touch policy code inside T4); no parallel battle execution; no battle-level retries under any circumstances.

## 10. Final decision

**Ready to plan/build once T3f is merged — with two small preconditions and one decision:**

1. **Generator capability (small, in-scope for the T4 slice):** `generate_dev_schedule` currently supports only a uniform `seeds_per_cell`; the weighted matrix needs per-policy seed counts (and the deliberate prefix-first row ordering). This is a bounded extension of the T3d generator plus tests — it belongs in the T4 slice itself, not a separate slice.
2. **T3f gates green specifically for:** effective config_hash (the §4 "config constants" gate references it), end_reason (the "all normal" gate), and the pinned latency number (the p95 gate needs a number, not prose).
3. **One-time decision:** commit result JSONL + seed log (recommended — 51 rows, and T5 needs a committed fixture) vs. gitignore + sha256-only. Decide before the run so the report's reproduction block is accurate.

Nothing else is missing. T4 needs no new statistics, no new policies, no panel changes — it is deliberately the first slice in a while that mostly *runs existing machinery* and proves it holds together at scale.
