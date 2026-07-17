# VERDICT: I8 MICROPROFILE — CLEAN EXECUTION (450/450 rows, cost-mechanism only)

The single separately-authorized offline Champions I8 microprofile ran once on the fixed
Windows measurement host, produced exactly 450 validated rows, and was independently
re-validated. **This is a measurement/validation record and a cost-mechanism localization — it
is NOT a live latency-gate result, and it makes no Strength claim.** I8-D remains separately
gated; Champions Strength remains NO-GO.

Frozen evidence (this directory / `data/eval/champions-panel-v0/i8-microprofile/`):

| file | sha256 | bytes |
|---|---|---|
| `profile.jsonl` | `5d330af597888adcfe5688cf408d9efca792a0ac69f35809e777fd7e57d527e3` | 471855 |
| `profile_manifest.json` | `3531b3b8f8cfe1f8017cd42add7829708f3ef2b17577cbb68355d5b038875d84` | 7047 |

Both are stored byte-exact (`.gitattributes: data/eval/champions-panel-v0/** -text`); the git
blob sha256 equals the file sha256. LF-only (0 CRLF).

## Provenance

| field | value |
|---|---|
| git_sha | `0730a18815ad1241713ab8002ce1d08e82f85c8d` (merge of PR #21) |
| dirty | `false` |
| format_id | `gen9championsvgc2026regma` (Champions Reg-MA) |
| profile_manifest_hash | `fdc3706038fde45f` |
| calc_pin_hash | `79a4877538c8740f` |
| format_config_hash | `fa8eb689e95c03c6` |
| speciesdata_hash | `b6e121e58c592056` |
| itemdata_hash | `c5b00bfb5f093e98` |
| reps | 30 (15 arms × 30 = 450 rows) |
| agent / config_id | `heuristic` / `champions-i8-microprofile` |

## Execution

| field | value |
|---|---|
| host | Windows NT 10.0.26200.0 |
| python | 3.14.5 (`pythoncore-3.14-64`) |
| node / npm | v24.16.0 / 11.13.0 |
| driver | `scripts/run_champions_i8_microprofile.py --reps 30` (provenance-locked public API) |
| worktree | fresh detached worktree at `0730a18`, tracked tree clean, `git_sha_and_dirty()==(0730a18, false)` |
| output | scratch-only during the run, then frozen here after review PASS |
| start → end | 2026-07-17T23:56:17+02:00 → 2026-07-18T00:15:09+02:00 |
| wall-clock | 1132.24 s (≈18.9 min) |
| exit code | 0 |

## Independent validation — 20/20 gates PASS

Manifest reads + validates (`read_profile_manifest`); canonical hash reproduces
(`fdc3706038fde45f`); `validate_decision_profile_dataset` passes; raw JSONL LF-only; exactly
450 non-empty rows; exactly 15 `PROFILE_ARMS` ids; every arm `rep 0..29`; no duplicate
`(arm_id, rep)`; every row joins the manifest and carries `source=="microprofile"`, the manifest
`git_sha`, its own arm's `effective_config_hash`, and its manifest-pinned `timer_scope`; manifest
`git_sha==0730a18`, `dirty==false`, Champions Reg-MA, provenance hashes match an independent
recompute; output dir holds only `profile.jsonl` + `profile_manifest.json`; no `.staging`
remains; no tracked repository file changed by the run; no server/battle artifact created.

**Outcomes: 450/450 `ok`. Contaminated rows: 0. Transport retries: 0. Crashes: 0.**
Backend-class counts: `oneshot 390`, `clean_cold 30`, `clean_warm 30` (the 390 `oneshot` rows
are correctly outside the persistent cold/warm contrast — by design, not contamination).

## Per-arm analysis (descriptive)

`measured_ms` uses the project's nearest-rank percentile convention (`gauntlet._latency_p95`;
no interpolation). Per-decision counters are constant across the 30 reps of each arm. **Rows of
different `timer_scope` are never pooled** — narrow = `score_evaluated_variants`, wide =
`contexts_and_score`.

| Arm | Scope | p50/p95 ms (min–max) | batches dmg/stat/typ | spawn | twins/br/wld/d2f | backend_class |
|---|---|---|---|---|---|---|
| A01 no_foe_mega | narrow | 1005 / 1114 (992–1124) | 1/6/1 | 8 | 0/0/1/0 | oneshot |
| A02 click_rate_zero | narrow | 1009 / 1060 (980–1065) | 1/6/1 | 8 | 0/0/1/0 | oneshot |
| A03 click_rate_default | narrow | 2369 / 2456 (2300–2466) | 1/16/2 | 19 | 24/3/1/0 | oneshot |
| A04 foe_mega_slot0 | narrow | 2310 / 2368 (2293–2376) | 1/16/2 | 19 | 24/3/1/0 | oneshot |
| A05 foe_mega_slot1 | narrow | 5474 / 5750 (5430–5798) | 1/41/3 | 45 | 12/3/1/0 | oneshot |
| A06 own_mega_no_foe | narrow | 974 / 1023 (966–1034) | 1/6/1 | 8 | 0/0/1/0 | oneshot |
| A07 foe_mega_no_own | narrow | 1362 / 1373 (1345–1374) | 1/8/2 | 11 | 8/1/1/0 | oneshot |
| A08 dual_mega_unequal | narrow | 998 / 1008 (992–1010) | 1/5/2 | 8 | 16/2/1/0 | oneshot |
| A09 dual_mega_tie | narrow | 2363 / 2436 (2348–2439) | 1/16/2 | 19 | 24/3/1/0 | oneshot |
| A10 trick_room | narrow | 1002 / 1023 (992–1027) | 1/5/2 | 8 | 16/2/1/0 | oneshot |
| A11 depth1 | narrow | 2456 / 2476 (2359–2485) | 1/16/2 | 19 | 24/3/1/0 | oneshot |
| A12 depth2_frontier | narrow | 12119 / 12287 (11967–12384) | 3/88/3 | 94 | 24/3/1/**8** | oneshot |
| A13a oneshot | narrow | 2440 / 2467 (2407–2469) | 1/16/2 | 19 | 24/3/1/0 | oneshot |
| A13b persistent_cold | **wide** | 138 / 144 (132–146) | 1/17/2 | **1** | 24/3/1/0 | clean_cold |
| A14 persistent_warm | **wide** | **8.7 / 10.0** (8–10) | 0/15/0 | **0** | 24/3/1/0 | clean_warm |

Request accounting corroborates the work-set shape (e.g. A14 warm: `requests_total 156 /
unique 0 / cache_hits 156`, `planned/implicit damage 0/0` — pure cache reuse; A13b cold:
`unique 12`, one spawn). Full per-decision counters are in `profile.jsonl`.

## Causal vs descriptive contrasts

Causal only when the two arms share `fixture_input_hash` **and** `timer_scope` and differ only in
the intended factor.

| Contrast | Arms | same fixture / scope | Verdict | Observation (descriptive) |
|---|---|---|---|---|
| zero-click vs active foe-Mega | A02 / A03 | yes / yes | CAUSAL | +11 batches (8→19), ≈2.35× at narrow scope — batch-count driven |
| depth-1 vs depth-2 | A11 / A12 | yes / yes | CAUSAL | depth-2 frontier reached (`d2f=8`): +75 batches (19→94), ≈4.9× |
| persistent cold vs warm | A13b / A14 | yes / yes | CAUSAL | spawn + first-fill ≈130 ms; warm steady-state ≈9 ms |
| oneshot vs persistent | A13a / A13b | yes / **no** (narrow vs wide) | DESCRIPTIVE | different boundary + backend; not causally comparable, not pooled |

## Cost mechanism (the load-bearing finding)

At the **narrow** scope every arm runs the **oneshot** backend and `spawn == transport_attempts
== logical batch count`, so narrow-scope `measured_ms` scales almost entirely with the number of
Node process spawns (one per batch): ≈1.0 s at 8 batches, ≈2.4 s at 19, ≈5.5 s at 45, and ≈12.3 s
p95 at 94 (depth-2). At the **wide** scope the **persistent** backend spawns once (A13b ≈144 ms
p95 cold) or not at all (A14 ≈10 ms p95 warm). The microprofile localizes *where* offline cost
originates (process starts / batch count under oneshot; first-fill under persistent); it is not a
measurement of the live decision path.

## Explicit non-claims

This record establishes only that the offline microprofile executed cleanly and where its
measured cost originates. It does **not** establish, and must not be read as:

- the final **live latency gate** (the live path times `agent_choose`, a boundary not measured
  here);
- any result against the pinned **1000 ms live budget** — that budget must **not** be
  reinterpreted as a per-arm microprofile threshold (e.g. A12's 12.3 s p95 is a narrow-scope
  oneshot spawn-per-batch cost at a different boundary, not a budget breach);
- **D-1** exposure sufficiency; **opponent-Mega coverage**; **outcome quality**; **Strength**;
  **cross-platform** latency; any **Kaggle** comparison or pooling; any **optimization** decision.

**I8-D remains separately gated. Champions Strength remains NO-GO.**
