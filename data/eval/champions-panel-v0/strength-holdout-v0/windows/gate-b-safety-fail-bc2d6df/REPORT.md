# Gate B (Independent Strength Holdout) -- frozen evidence: SAFETY-FAIL

HELD-OUT RUN -- these numbers must never inform tuning. This is NOT a Strength result and makes
NO Strength claim. Champions Strength remains NO-GO.

## Verdict
- verdict = SAFETY-FAIL (safety_pass = false).
- Cause: invalid_choices -- Arm A (heuristic, the candidate) = 1, Arm B (max_damage, baseline) = 0.
  The candidate emitted one illegal action across the 180 held-out matchups; the Gate B safety gate
  is fail-closed, so any illegal action by the candidate fails the gate regardless of win margin.
- The log content behind that invalid choice is deliberately NOT analysed here -- per the agreed
  contract, the affected log may only be examined after Freeze -> Review -> Merge.

## Identity / provenance (one shared candidate)
- candidate_identity = 32f79b8e52444aa3
- git_sha = bc2d6df1fcfa61c7a8bda9fe52a6899f93d27aee
- panel_hash = 122764211b6db3ba, schedule_hash = 37df91c10c24801d
- config_hash_a (heuristic) = 594295543f13a55d, config_hash_b (max_damage) = ccac8a92bc71ee80
- stratum = windows, date_stratum_id = 2026-07-23-windows-gate-b-bc2d6df, PYTHONHASHSEED = 0
- Upstream (same identity, both PASS, both verified by the combine): I8-D latency PASS and
  opponent-Mega coverage PASS.

## Paired comparison (descriptive only -- NOT a strength/variance/causal claim)
- n_total = 180, n_discordant = 100 (b=54, c=46), delta = strength_delta = +0.044444.
- Raw head-to-head over the 180 seed-fixed holdout matchups: heuristic 89 wins / max_damage 81 wins.
- Descriptive context for the frozen record only; NO strength meaning (the run is a SAFETY-FAIL).

## What is frozen (closed inventory -- see inventory.json)
- combine/verdict.json, combine/cells.json -- the combine bundle's own outputs.
- arm-a-heuristic/ and arm-b-max-damage/ -- each: arm_manifest.json, rows.jsonl, seeds.jsonl.
  The combine bundle's own arm_a/, arm_b/ copies are byte-identical to these (verified, not
  duplicated). NOTE (P2b path-only transform): in these FROZEN rows.jsonl copies, ONLY the
  `room_raw_path` field is rewritten from the original absolute external path to the relative frozen
  log path `hero-logs/<arm>/<name>.log.gz`; every other byte of every row is unchanged. The
  byte-exact published arm outputs (carrying the original absolute paths) remain external, unfrozen.
- hero-logs/arm-a/*.log.gz (180) and hero-logs/arm-b/*.log.gz (180) -- exactly the 360 hero logs
  bound through rows.jsonl.room_raw_path, NORMALIZED via
  normalize_battle_log(frames, name_subs=GAUNTLET_NAME_SUBS) (the canonical production recipe) and
  gzip-compressed deterministically (mtime=0). Each carries raw + normalized SHA-256 and byte size in
  inventory.json. Every log's decompressed content hashes to its declared normalized_sha256, which
  equals the row's recorded normalized_room_log_sha256 (360/360).
- inventory.json -- the closed manifest (records every frozen file incl. REPORT.md; the only
  self-exception is inventory.json itself, which cannot contain its own hash).
- The one appended held-out ledger entry, committed in config/eval/heldout_ledger.jsonl
  (result_sha256 = 0dd2e8305f40df34f669dccdc3d28e32459fc5e71e1413bc4aa0bd058ebcbe52,
  justification = null). This consumes the one-attempt budget for config_hash 594295543f13a55d.

## Kept external (not frozen)
The unmodified raw room logs (both client perspectives) remain external under the run-local room-raw
directories. Only the normalized hero logs are frozen; the other client's raw logs may remain
externally but are not part of this frozen evidence.

## Re-run constraint (recorded for the later decision)
A code fix for the invalid-choice defect produces a new git_sha but likely the same config_hash. The
ledger has already consumed that config_hash, and Gate B currently passes justification=None. A
further Strength execution is therefore NOT automatically permitted; after diagnosis, a separate
decision is required between a documented, justified repeat run and a new independent holdout.
Champions Strength stays NO-GO.
