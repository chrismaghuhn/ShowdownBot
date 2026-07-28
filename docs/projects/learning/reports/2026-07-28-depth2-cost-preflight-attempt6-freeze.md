# Depth-2 Cost Preflight — Attempt 6 Freeze

**Spec:** `docs/projects/learning/specs/2026-07-28-depth2-cost-preflight-amendment.md` (Appendix A.6)
**Parent spec:** `docs/projects/learning/specs/2026-07-27-depth2-accuracy-stage3-readiness-design.md` §11–§12
**Candidate SHA:** `d64982ae9fdba6a877c8c2b7e804923ebcc7fec4`
**Date:** 2026-07-28
**Verdict:** **VALID MATRIX** — all four arms completed, all post-arm gates and the
cross-arm validation passed.

Attempt 6 is the first valid execution of the Depth-2 Cost Preflight. Attempts 1–5 are
invalidated; see Appendix A.1–A.5 of the amendment. **No data from any earlier attempt is
reused, pooled, or cited here.**

---

## 1. What this establishes

A depth-2 search was **actually executed** for the first time in this series: both
depth-2 arms have `depth2_frontier > 0` on every profile row (`max_frontier = 9`, matching
the requested `SHOWDOWN_SEARCH_TOPN` × `SHOWDOWN_SEARCH_TOPM` = 3 × 3), and non-zero
`depth2_candidates_selected` / `depth2_response_slots_eligible`. In Attempt 4 all four arms
reported `depth2_frontier = 0`, so no depth-2 cost had ever been measured.

The frontier evidence is a **three-part chain**, and no part carries it alone:

1. The profile rows report the *resolved* `search_topn_requested = 3` /
   `search_topm_requested = 3`.
2. The defined N×M frontier semantics predict an upper bound of 9.
3. The observed frontier actually reaches 9.

`max_frontier = 9` in isolation is not an independent provenance proof for the two
environment variables — the value is equally consistent with other factorisations. Only
the combination establishes that the caps were effective in these arms.

---

## 2. Quantile convention

All percentiles below use the project's existing convention, imported directly from
`showdown_bot/scripts/run_cap_latency_sweep.py` rather than re-implemented:

```python
def _percentile(sorted_ms: list[float], q: float) -> float:
    idx = min(len(sorted_ms) - 1, max(0, int(round(q * (len(sorted_ms) - 1)))))
    return sorted_ms[idx]
```

Note `int(round(...))` uses Python's banker's rounding, so `round(14.5) == 14`. An
independent re-derivation must use this exact formula; an "upper middle" convention
(`int(n * q)`) yields different p50 values at even `n` — for these data it shifts every
`clean_cold` p50 (n = 30) upward by one rank.

---

## 3. Evidence per arm × `backend_class` stratum (§12)

Strata are the actual `backend_class` values on each profile row — `clean_cold` and
`clean_warm` — never battle ordinal. No `contaminated` row exists in any arm.

`measured_ms` is per-decision, from the profile rows.

### 3.1 `d1_acc_off` — `config_hash 03d2d5ee27911fc4`

30 battles, 0 timeouts (`end_reason == "timeout"`), 0 crashes, 0 invalid choices.

| Stratum | obs | battles | p50 | p95 | max |
|---|---:|---:|---:|---:|---:|
| `clean_cold` | 30 | 30 | 215.9 | 240.3 | 254.2 |
| `clean_warm` | 241 | 30 | 31.3 | 54.6 | 79.1 |

| Stratum | chooser fallback | degradation | cap_fallback | topn | topm | frontier > 0 | max frontier |
|---|---:|---:|---:|---:|---:|---:|---:|
| `clean_cold` | 0 | 0 | 0 | 2 | 2 | 0 | 0 |
| `clean_warm` | 0 | 0 | 0 | 2 | 2 | 0 | 0 |

| Stratum | acc_leaf t1 | acc_leaf t2 | cap_hits t1 | cap_hits t2 | d2_cand | d2_slots |
|---|---:|---:|---:|---:|---:|---:|
| `clean_cold` | 0 | 0 | 0 | 0 | 0 | 0 |
| `clean_warm` | 0 | 0 | 0 | 0 | 0 | 0 |

| Stratum | transport_calls | transport_attempts | spawn_calls | requests_total | requests_unique | cache_hits |
|---|---:|---:|---:|---:|---:|---:|
| `clean_cold` | 90 | 90 | 30 | 59490 | 610 | 43570 |
| `clean_warm` | 432 | 432 | 0 | 114087 | 2063 | 94927 |

### 3.2 `d1_acc_on` — `config_hash 50cf67d5b04a1b04`

30 battles, 0 timeouts, 0 crashes, 0 invalid choices.

| Stratum | obs | battles | p50 | p95 | max |
|---|---:|---:|---:|---:|---:|
| `clean_cold` | 30 | 30 | 437.0 | 553.8 | 558.9 |
| `clean_warm` | 263 | 30 | 56.7 | 162.4 | 203.9 |

| Stratum | chooser fallback | degradation | cap_fallback | topn | topm | frontier > 0 | max frontier |
|---|---:|---:|---:|---:|---:|---:|---:|
| `clean_cold` | 0 | 0 | 20 | 2 | 2 | 0 | 0 |
| `clean_warm` | 0 | 0 | 91 | 2 | 2 | 0 | 0 |

| Stratum | acc_leaf t1 | acc_leaf t2 | cap_hits t1 | cap_hits t2 | d2_cand | d2_slots |
|---|---:|---:|---:|---:|---:|---:|
| `clean_cold` | 40910 | 0 | 6490 | 0 | 0 | 0 |
| `clean_warm` | 75833 | 0 | 5856 | 0 | 0 | 0 |

| Stratum | transport_calls | transport_attempts | spawn_calls | requests_total | requests_unique | cache_hits |
|---|---:|---:|---:|---:|---:|---:|
| `clean_cold` | 90 | 90 | 30 | 201870 | 610 | 185950 |
| `clean_warm` | 471 | 471 | 0 | 308417 | 2296 | 288643 |

### 3.3 `d2_acc_off` — `config_hash b4c98c07c32f3f9f`

30 battles, 0 timeouts, 0 crashes, 0 invalid choices.

| Stratum | obs | battles | p50 | p95 | max |
|---|---:|---:|---:|---:|---:|
| `clean_cold` | 30 | 30 | 239.6 | 297.8 | 320.7 |
| `clean_warm` | 269 | 30 | 50.6 | 80.2 | 111.3 |

| Stratum | chooser fallback | degradation | cap_fallback | topn | topm | frontier > 0 | max frontier |
|---|---:|---:|---:|---:|---:|---:|---:|
| `clean_cold` | 0 | 0 | 0 | 3 | 3 | 30 | 9 |
| `clean_warm` | 0 | 0 | 0 | 3 | 3 | 269 | 9 |

| Stratum | acc_leaf t1 | acc_leaf t2 | cap_hits t1 | cap_hits t2 | d2_cand | d2_slots |
|---|---:|---:|---:|---:|---:|---:|
| `clean_cold` | 0 | 0 | 0 | 0 | 90 | 360 |
| `clean_warm` | 0 | 0 | 0 | 0 | 748 | 2922 |

| Stratum | transport_calls | transport_attempts | spawn_calls | requests_total | requests_unique | cache_hits |
|---|---:|---:|---:|---:|---:|---:|
| `clean_cold` | 230 | 230 | 30 | 66390 | 610 | 50470 |
| `clean_warm` | 681 | 681 | 0 | 192264 | 2741 | 166645 |

### 3.4 `d2_acc_on` — `config_hash 68e04be0173586b2`

30 battles, 0 timeouts, 0 crashes, 0 invalid choices.

| Stratum | obs | battles | p50 | p95 | max |
|---|---:|---:|---:|---:|---:|
| `clean_cold` | 30 | 30 | 470.8 | 657.1 | 764.6 |
| `clean_warm` | 246 | 30 | 85.5 | 205.0 | 261.0 |

| Stratum | chooser fallback | degradation | cap_fallback | topn | topm | frontier > 0 | max frontier |
|---|---:|---:|---:|---:|---:|---:|---:|
| `clean_cold` | 0 | 0 | 20 | 3 | 3 | 30 | 9 |
| `clean_warm` | 0 | 0 | 113 | 3 | 3 | 246 | 9 |

| Stratum | acc_leaf t1 | acc_leaf t2 | cap_hits t1 | cap_hits t2 | d2_cand | d2_slots |
|---|---:|---:|---:|---:|---:|---:|
| `clean_cold` | 40910 | 6060 | 6490 | 240 | 90 | 360 |
| `clean_warm` | 67038 | 33570 | 4968 | 3483 | 673 | 2654 |

| Stratum | transport_calls | transport_attempts | spawn_calls | requests_total | requests_unique | cache_hits |
|---|---:|---:|---:|---:|---:|---:|
| `clean_cold` | 230 | 230 | 30 | 227190 | 610 | 211270 |
| `clean_warm` | 663 | 663 | 0 | 413455 | 2445 | 391742 |

`turn2_accuracy_leaf_count > 0` occurs **only** in `d2_acc_on` — the one arm where depth 2
and accuracy are both on. This is an internal consistency check, not a separate claim.

---

## 4. Pooled values — reported, not interpreted

| Arm | pooled obs | pooled p50 | pooled p95 | pooled max |
|---|---:|---:|---:|---:|
| `d1_acc_off` | 271 | 33.0 | 217.0 | 254.2 |
| `d1_acc_on` | 293 | 71.1 | 446.2 | 558.9 |
| `d2_acc_off` | 299 | 52.6 | 240.5 | 320.7 |
| `d2_acc_on` | 276 | 95.0 | 481.5 | 764.6 |

> The pooled p95 describes the cold/warm mixture distribution and is dominated by the
> share of cold rows. It must not be interpreted as warm tail latency or as an isolated
> treatment effect.

There is exactly one `clean_cold` row per battle, so cold is 10–11 % of rows in every arm.
The strata do **not overlap** in any arm (smallest margin: `d2_acc_on`, cold min 346.0 vs.
warm max 261.0), so all cold values sort to the top and the pooled p95 rank falls inside
the cold block — near its median. Non-overlap is an observed property of these four arms,
not a property of the metric.

No pooled value is interpreted anywhere in this document.

---

## 5. Cross-arm validation (§11.3)

Exact per-arm assignment, not merely distinctness — a run with two arms' hashes swapped
would pass a distinctness test and fail this one.

| Arm | manifest `config_hash` | all profile rows | expected |
|---|---|---|---|
| `d1_acc_off` | `03d2d5ee27911fc4` | `03d2d5ee27911fc4` | ✓ |
| `d1_acc_on` | `50cf67d5b04a1b04` | `50cf67d5b04a1b04` | ✓ |
| `d2_acc_off` | `b4c98c07c32f3f9f` | `b4c98c07c32f3f9f` | ✓ |
| `d2_acc_on` | `68e04be0173586b2` | `68e04be0173586b2` | ✓ |

4/4 distinct. None equals `594295543f13a55d`, the empty-`behavior_env` hash that all four
Attempt-4 arms carried.

Shared values, each checked against its **pre-registered** value rather than only for
mutual agreement — four matching but wrong values would pass a consistency test and still
be an invalid run:

| Field | Value (identical across all four manifests) |
|---|---|
| `git_sha` | `d64982ae9fdba6a877c8c2b7e804923ebcc7fec4` (also on every profile row; `dirty = false`) |
| `showdown_commit` | `f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5` |
| `server_patch_hash` | `86e31891547e87da` |
| `pythonhashseed` | `0` |
| `schedule_hash` | `b6f5910e4bc3c584` |
| `panel_hash` | `aac1ea30446fde88` |
| `seed_base` | `champions-panel-v0-d2-cost-preflight` |

Battle-id sets are identical across all four arms (30 each). Seed-log alignment verified
per arm: 30 entries, `seed_i == derive_battle_seed(base, seed_index)`.

---

## 6. Commands and environment

Per arm, **one PowerShell process** sets the complete environment and launches both Python
children — verification first, gauntlet second, with no assignment between them (§6.4).
Process-tree observation during `d1_acc_on` confirmed the server (node) and the gauntlet
(python) as simultaneous direct children of PowerShell PID 14744. That snapshot cannot
retroactively prove the verifier child's parentage — it had already exited — which is
carried instead by the immutable `operator-server-<arm>.json` and the contiguous arm block.

Shared environment (all arms):

```text
PYTHONPATH                    = <candidate>\showdown_bot\src   (exclusive)
PYTHONHASHSEED                = 0
SHOWDOWN_CALC_BACKEND         = persistent
SHOWDOWN_BATTLE_SEED_BASE     = champions-panel-v0-d2-cost-preflight
SHOWDOWN_DECISION_PROFILE_OUT = <output-root>\cost_preflight_<arm>_profile.jsonl
SHOWDOWN_EVAL_SEED_LOG        = <output-root>\cost_preflight_<arm>_seedlog.jsonl
SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S = unset (effective 180 s)
CWD                           = <candidate>\showdown_bot
```

Arm-specific environment — full `SHOWDOWN_`-prefixed names:

| Arm | `SHOWDOWN_SEARCH_DEPTH` | `SHOWDOWN_ACCURACY_MODE` | `SHOWDOWN_ACCURACY_BRANCH_CAP` | `SHOWDOWN_SEARCH_TOPN` | `SHOWDOWN_SEARCH_TOPM` |
|---|---|---|---|---|---|
| `d1_acc_off` | `1` | `0` | (unset) | (unset) | (unset) |
| `d1_acc_on` | `1` | `1` | `6` | (unset) | (unset) |
| `d2_acc_off` | `2` | `0` | (unset) | `3` | `3` |
| `d2_acc_on` | `2` | `1` | `6` | `3` | `3` |

Server, started fresh per arm and stopped after it:

```text
node pokemon-showdown start --no-security
```

in `~/.cache/showdownbot/pokemon-showdown`, port 8000, endpoint
`ws://localhost:8000/showdown/websocket`. Server PIDs: 16808, 8876, 19796, 3280 — each
stopped before the next arm, port 8000 confirmed free each time.

Gauntlet:

```text
python -m showdown_bot.cli gauntlet
  --schedule <repo>\config\eval\schedules\cost_preflight_d2_30.yaml
  --result-out <output-root>\cost_preflight_<arm>_result.jsonl
```

Toolchain: node `v24.16.0`, npm `11.13.0`, calc lockfile SHA-256
`c03c577c3e62c7c1de12ba74ac60ca311bf3dd077e37e09c30d5269f2b61dabe`, `npm ci` exit 0
before `operator-preflight.json` was written.

---

## 7. Frozen output — 21 files

Output root: `C:\Users\chris\Documents\cost-preflight-d2-d64982a-attempt6\`
(outside the git tree). Inventory verified complete: 21 expected files present, no
unexpected extra files.

| File | SHA-256 |
|---|---|
| `cost_preflight_d1_acc_off_profile.jsonl` | `dcecd2beebe5338251e76e2251b1bd0e8eb26c37a8cbf7c48f3e8c0b1c40bec6` |
| `cost_preflight_d1_acc_off_result.jsonl` | `c2bf5198cb847253b048a35eaf96263dabcd7a36193195484a210d7bf45fde53` |
| `cost_preflight_d1_acc_off_result.jsonl.manifest.json` | `daea621611f4362849bf1db8f38082300e82d588477d25c8a69408c3961b9fe2` |
| `cost_preflight_d1_acc_off_seedlog.jsonl` | `3362a305c20ef53b8846564281cc76bcbc2373713a3d324c8b651b29bf6bae43` |
| `cost_preflight_d1_acc_on_profile.jsonl` | `bcf620bb6b0a61221bc214cc305b0de292c469f53e404106faa77f2319da6cd4` |
| `cost_preflight_d1_acc_on_result.jsonl` | `9242393e29875837364ec0e2007a2265d8578c0bf8056107931729011048e7a1` |
| `cost_preflight_d1_acc_on_result.jsonl.manifest.json` | `fa2748228c60c88723ffef2f118af8e57c8cffc97a43758f9696cc765ac6cb7a` |
| `cost_preflight_d1_acc_on_seedlog.jsonl` | `3362a305c20ef53b8846564281cc76bcbc2373713a3d324c8b651b29bf6bae43` |
| `cost_preflight_d2_acc_off_profile.jsonl` | `cde2f920e95a7485ba8529a18aec5773ec98698e26884b54577cf4ca9c52cd85` |
| `cost_preflight_d2_acc_off_result.jsonl` | `a6f03e6b2f5f910b875aee2bf638beaf07539abf5455105027cf289413b6a07f` |
| `cost_preflight_d2_acc_off_result.jsonl.manifest.json` | `6b9420186447b839d755eaab86dc1b710e19be0af4fb9c41103f234fde4bf004` |
| `cost_preflight_d2_acc_off_seedlog.jsonl` | `3362a305c20ef53b8846564281cc76bcbc2373713a3d324c8b651b29bf6bae43` |
| `cost_preflight_d2_acc_on_profile.jsonl` | `6bae75da96be6b6c2ff3243a719e1ac4ccfed3e3481841081d8181eedcffad5d` |
| `cost_preflight_d2_acc_on_result.jsonl` | `12672f53d291761c781607d009571c0a8a4226543f2fb72c8f940437cfc8b6ad` |
| `cost_preflight_d2_acc_on_result.jsonl.manifest.json` | `2bd27d38665b4d425af9e81edcc8838c66526f3aee021ba153fe39d4a933c2e6` |
| `cost_preflight_d2_acc_on_seedlog.jsonl` | `3362a305c20ef53b8846564281cc76bcbc2373713a3d324c8b651b29bf6bae43` |
| `operator-preflight.json` | `bc52182f657e6235adbeeb2d2281a9931dd099a8461776784b55950615e3942a` |
| `operator-server-d1_acc_off.json` | `8d3fb2635c031331eea3b508f5738dcf51d9ca198eda64db783448c58c03a702` |
| `operator-server-d1_acc_on.json` | `a3f50ba478fd717f221e7288c4bdde6d29b1b060a246ea247d1b38023bf22992` |
| `operator-server-d2_acc_off.json` | `4b698121541e25da259c45b1d18b377d11c6ea8937efbe0e380d690a8cc7c5fb` |
| `operator-server-d2_acc_on.json` | `da7e5b640923d4aa35ac71e4c47d91cb758b419a79fdda5bd42780930ef78ea5` |

The four seed logs share one hash: same seed base, same schedule, same 30 derived seeds.
That is expected and independently corroborates that each arm ran on a freshly started
server with its own seed-log path.

---

## 8. What this does NOT claim (§13, unchanged)

This preflight produces **cost and readiness evidence only**. It does not claim:

- Depth-2 is stronger.
- Depth-2 is production-ready.
- The live latency gate passed. The I8-D 1000 ms threshold is a **live-gate** criterion,
  not a microprofile threshold; that every value observed here falls below it is **not** a
  gate result and must not be reported as one.
- 1000 ms is a microprofile threshold.
- Accuracy on/off shows a causal effect.

Two further limits specific to this run:

**No causal or marginal treatment effect.** The four arms ran in a pre-registered fixed
order (§6.1), so arm and wall-clock time are inseparable and host drift cannot be
distinguished from the manipulation. No ratio between arms is reported, at either the
pooled or the stratum level.

**Decision sets are not paired.** All four arms share the same panel and the same 30
derived seeds, but the treatments change the bot's choices, so the games diverge and the
decision counts differ (271 / 293 / 299 / 276). Any cross-arm comparison is therefore a
comparison of distributions over **different, unpaired decision sets**, not a
before/after contrast on the same decisions.

The permissible framing is:

> Descriptive comparison of the observed decision-latency distributions of four sequential
> arms with the same panel and the same start seeds, but different, unpaired decision sets.

---

## 9. Completion

Amendment §15's condition "on a fully valid matrix" is met. The parent spec's §12 step 11
("Run and freeze the cost preflight") is satisfied by this document plus the frozen output
inventory in §7 above.
