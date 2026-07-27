# VERDICT: I8-D LIVE LATENCY GATE (post-guard-hardening) — PASS (active foe-Mega p95 890.608 ms ≤ 1000 ms)

Gate 1 of 3. Run **exactly once**, **unchanged**, on candidate `0390668` — the first gate of the
separately-authorised three-gate sequence. The 1000 ms budget was not moved, and no decision
behaviour, cap, click-rate or threshold was touched.

**This is a latency verdict, not a strength claim. Champions Strength remains NO-GO.**

## Why this run was necessary

An I8-D PASS binds to the `candidate_identity` that produced it and does not transfer to a new
`git_sha`. The four prior runs belong to earlier candidates; `0390668` had no I8-D result at all.

| field | value |
|---|---|
| `git_sha` | `0390668ed5656b9eae600d4c3d76733616a7c16c` |
| `candidate_identity` | `111cf0d16a4f8a59` |
| `config_hash` | `594295543f13a55d` |
| `schedule_hash` | `a1192d9dde4c65df` |
| `panel_hash` | `aac1ea30446fde88` |
| `calc_backend` | `oneshot` |
| `hero_agent` | `heuristic` |

## Verdict

| field | value |
|---|---|
| `verdict` | **PASS** |
| `p95_ms` | **890.6084999907762** |
| `budget_ms` | 1000 |
| `p95_is_gate_value` | `true` |
| `exposure_floor_met` | `true` (60 active-valid ≥ 60; 45 distinct ≥ 20) |
| `stop_reason` | `exposure_floor_met` |
| `battles_played` | 75 |
| `scored_decisions` | 679 (cap 2000, `scored_overshoot` 0) |
| `active_valid_decisions` | 60 |
| `distinct_active_battles` | 45 |
| `seed_log_verified` | `true` |

### Runtime environment (new since PR #107)

This is the first gate verdict to carry the runtime that produced its p95 — previously a latency
number was frozen against a fixed budget with no record of the Node/Python it was measured on.

```
python    3.14.5
node      v24.16.0
platform  Windows-11-10.0.26200-SP0
deps      pydantic 2.13.4, websockets 16.0, lightgbm 4.6.0
```

## Degradation — what is proven, and what this gate does not capture

**Hero-side decision degradation: 0.** All 679 live rows carry `outcome == "ok"`. That field is
produced by `classify_live_outcome`, which takes the same inputs and the same dominance order as
the production `is_degraded_decision` predicate over the domain `{ok, crash, fallback,
degraded_state}`. Zero `crash`, zero `fallback`, zero `degraded_state`. Supporting signals from the
same bytes: `backend_class == "oneshot"` on every row, `transport_retried == 0` on every row, and
1306 calc spawn calls across the run — the calculator demonstrably ran rather than silently falling
back. A calc probe returning a real damage number was asserted before battle 1.

**Not captured by this gate — stated plainly rather than reported as clean.** The per-seat counters
`hero_degraded_decisions` / `villain_degraded_decisions` and `hero_invalid_choices` /
`villain_invalid_choices` are per-battle fields delivered through `run_local_gauntlet`'s
`on_battle_result` callback. **`run_i8d_live_gate` passes no such callback**, so those four values
never reach any artifact of this run. They exist on the Gate B arm path, not here.

So: hero-side degradation is proven zero from the run's own recorded bytes; the villain side and
the per-seat invalid-choice split are **unrecorded**, not verified-zero. The p95 above is reported
with that limitation attached. Closing it is a separate slice on the I8-D runner, not something to
retrofit onto this frozen run.

## Independent re-verification — from the frozen bytes

Recomputed reading only the committed copies, reusing the production validator, predicate and p95:

- `validate_live_profile_dataset` → `{rows: 679, active_valid_rows: 60, distinct_active_battle_ids: 45}`
- verdict population recomputed via `is_active_valid_live_row`: exactly **60** from exactly **45** distinct battles
- p95 recomputed via `gauntlet._latency_p95`: **`890.6084999907762`** — **bit-identical** to `verdict.json.p95_ms`, and `≤ 1000` ⇒ PASS
- all 679 `(battle_id, decision_index)` pairs unique
- `seeds.jsonl`: exactly **75** records, single `seed_base`, contiguous `battle_index` 0..74, every seed equal to `derive_battle_seed(base, index)`

## Frozen evidence (`data/eval/champions-panel-v0/i8d-live-post-guard-hardening/`)

| file | sha256 | bytes |
|---|---|---|
| `profile.jsonl` | `64d1479a806c650c78a4593e975fd65a727b3888b9be3871e3a62127df1e1395` | 736714 |
| `verdict.json` | `b5ebe03c895b73b21d36892e69162476ec52e32ddac0ae9add5375b23742542c` | 1114 |
| `seeds.jsonl` | `4d4ad59c2f78a938ce531670f45b4b7fd2371daae11fbb7b66a283b2edb76c6b` | 8540 |

Closed inventory: those three files plus `sha256.txt`. Each stored blob's SHA-256 was verified
equal to the external run output before the freeze commit — the frozen bytes are the run bytes.
Stored byte-exact under `.gitattributes: data/eval/champions-panel-v0/** -text`.

## Execution

| field | value |
|---|---|
| host | fixed Windows host (Windows 11) |
| server | patched `pokemon-showdown` pinned at `f8ac140` + `pokemon-showdown-seeded-battle.patch`, `--no-security` on port 8000, started fresh; seeding patch verified present in the **built** `dist/` output, not only in the `.ts` source |
| gate command | `python -m showdown_bot.cli i8d-live-gate --out-dir <run-root>/out --teams-root showdown_bot`, from the repo root, `PYTHONPATH=showdown_bot/src`, `SHOWDOWN_CALC_BACKEND=oneshot` |
| seed pairing | `SHOWDOWN_BATTLE_SEED_BASE` + `SHOWDOWN_EVAL_SEED_LOG` on **both** the server and the client |
| run output | `<run-root>` outside the repository; `seeds.jsonl` / `out` / `out.staging` all absent before the run |
| policy | ran **once**; fail-closed; **no retry**; server stopped and port 8000 freed afterwards |

The half-configured-pairing guard (PR #102) was deliberately exercised first: invoking the gate with
the client half of the seed-log pairing missing aborted with
`i8d-live-gate requires SHOWDOWN_EVAL_SEED_LOG …` **before battle 1**, burning zero battles. The
real run then followed with both halves set.

## Descriptive comparison (NOT a causal, variance or strength claim)

Each I8-D run belongs to a different candidate and is frozen separately; they are never pooled.

| | pre-Lever-A | post-Lever-A | post-Lever-B | post-coverage-harness | this run |
|---|---|---|---|---|---|
| candidate | `9fc0f36` | `9d915f2` | `3db4ac7` | `bd590c1` | `0390668` |
| battles / decisions | 75 / 679 | 75 / 679 | 72 / 651 | 75 / 679 | 75 / 679 |
| active / distinct | 60 / 45 | 60 / 45 | 60 / 44 | 60 / 45 | 60 / 45 |
| p95 | 1110.213 ms | 1160.515 ms | 850.245 ms | 864.94 ms | **890.608 ms** |
| verdict | FAIL | FAIL | PASS | PASS | **PASS** |

No claim is made that any code change caused any difference between these numbers, and none about
run-to-run variance. They measured different code on different candidates.

## Non-claims and status

No ledger entry. No strength claim. No evidence merged to `main` — this freeze lives on an evidence
branch until after Gate B, because merging would move `main` and void the shared candidate identity
the remaining two gates must run on.

This PASS closes the latency precondition **for candidate `111cf0d16a4f8a59` only**. The coverage
gate and the independent Strength holdout are separately authorised and have not run.
**Champions Strength remains NO-GO.**
