# vgc_bench_ingest — VGC-Bench Open-Team-Sheet log ingestion (research prototype)

**INV-1 / isolation invariant.** This package ingests EXTERNAL human-replay data. It MUST NOT be
imported by the live decision path (`battle/decision`), the teacher/reranker
(`learning/*`), or the eval dispatch (`client/gauntlet`). A test enforces this
(`test_vgc_bench_ingest.py::test_live_path_*`). External human-replay data must not be mixed with
our seeded self-play / rollout-teacher data unless ALL of the following hold:

1. source format is compatible (the format gate),
2. player perspective is reconstructed (Part B),
3. legal actions are verified (Part B),
4. leakage audit passes (Part B),
5. schema/provenance are kept separate,
6. an explicit downstream experiment enables it.

## Part A (this slice) — the fail-closed foundation

- `snapshot.py` — `sha256_file`, `build_sample_manifest` (records source/revision/file-sha256/
  format-filter/license; `purpose="ingestion_prototype_only"`).
- `load_raw.py` — `load_raw(json_text)`: strict parse of the VGC-Bench JSON wrapper
  (`battle-id -> [epoch_seconds, log_string]`); raises `VgcBenchParseError` naming a bad entry,
  never silently skips.
- `parse_log.py` — `parse_battle`: builds `VgcBenchRawBattle`; **winner/turns/end_reason are
  RE-DERIVED from the log** via our own `eval/battle_parse.parse_battle_result` (no external
  field trusted); raw + normalized log sha256 via the same recipe that binds our result rows to
  their room logs (`eval/room_dump`).
- `format_gate.py` — `gate_format`: TARGET_COMPATIBLE (Reg I 2025/2026) /
  MECHANICALLY_SIMILAR_BUT_NOT_TARGET (other gen9 VGC regs) / REJECT_FORMAT_MISMATCH /
  REJECT_UNKNOWN_FORMAT. **Hard rule: Reg M-A/M-B are NEVER accepted as Reg I** (the active
  `vgc-battle-logs` dataset is MA/MB-only with zero Reg I data).

## Deferred

- **Part B:** player-perspective reconstruction, availability tagging
  (known_at_decision / ots_known / revealed_by_log / derived_from_true_state / oracle_only / …),
  legal-action verification (via our own `enumerate_my_actions`), leakage audit. This is the
  hard, high-risk part.
- **Part C:** real HF download of a small sample, VGC-Bench pipeline comparison, downstream uses
  (opponent-response priors, diagnostic mining, archetype stats).

## Verified data status (2026-07-11)

`cameronangliss/vgc-battle-logs-sv` (archive, MIT, 6.78 GB) holds Reg I 2025 = **16,359 BO1 +
183,267 BO3** logs (+ Reg I 2026). The active `cameronangliss/vgc-battle-logs` has **zero Reg I**
(Champions MA/MB only) — hence the format gate is load-bearing, not a formality.
