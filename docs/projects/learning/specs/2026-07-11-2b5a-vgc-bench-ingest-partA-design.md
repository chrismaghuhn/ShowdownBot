# 2b-5a Part A — VGC-Bench Ingestion Foundation (snapshot + raw parser + format gate)

**Status:** first bounded chunk of the banked plan `TestBOtpläne/13-vgc-bench-ingestion-plan.md`
(user-approved). This is a fail-closed DATA/INGESTION PROTOTYPE — no training, no teacher mix, no
live override, no policy. Part A covers the plan's Phases 0-2: deterministically load a raw
VGC-Bench log, parse it, and strictly gate it by format/regulation. Perspective reconstruction +
legality + leakage audit (the hard part) are Part B; downstream uses are Part C.

## Isolation (INV-1)

New package `showdown_bot/src/showdown_bot/research/vgc_bench_ingest/` with a module-docstring +
README invariant: **external human-replay ingestion; MUST NOT be imported by the live decision
path, teacher, or reranker.** Mirror the `eval/opponents/__init__.py` live-path-guard docstring.
A test asserts no live-path module (`battle/decision`, `learning/*`, `client/gauntlet`) imports
this package.

## Input format (from the dataset card, verified 2026-07-11)

VGC-Bench logs (`cameronangliss/vgc-battle-logs-sv`, MIT) are JSON files mapping
`battle-id -> [epoch_seconds, battle_log_string]`. The `battle_log_string` is standard Pokémon
Showdown protocol (`|`-delimited lines) — the exact form we already parse in `eval/battle_parse`,
`eval/room_dump`, `eval/diagnostics`. So the outer wrapper is trivial; the inner log reuses our
existing parsing.

## Part A scope

**Phase 0 — Source snapshot.** `snapshot.py`: given a local sample file, compute its sha256,
record a manifest (source dataset name, revision if known, file name, file sha256, format_filter,
sample_size, license "MIT", created_at passed in, purpose "ingestion_prototype_only"). Pure +
deterministic; timestamp injected (no `Date.now`).

**Phase 1 — Raw log parser.** `load_raw.py` + `parse_log.py`:
- `load_raw(json_text) -> dict[battle_id -> (epoch:int, log:str)]` — strict: rejects malformed
  entries (raises `VgcBenchParseError` naming the bad battle_id; never silently skips).
- `parse_battle(battle_id, epoch, log) -> VgcBenchRawBattle` (frozen dataclass: battle_id,
  epoch_seconds, raw_log_sha256, normalized_log_sha256 [via our `normalize_battle_log`],
  format_name, gametype, players tuple, rules tuple, log_lines tuple). Winner + turn count
  RE-DERIVED from the log via our existing `battle_parse.parse_battle_result` (no trust of any
  external field). Deterministic; stable hashes.

**Phase 2 — Format/Regulation gate.** `format_gate.py`:
- `gate_format(format_name) -> FormatGateResult` (frozen: source_format, inferred_regulation,
  is_bo3, compatibility ∈ {TARGET_COMPATIBLE, MECHANICALLY_SIMILAR_BUT_NOT_TARGET,
  REJECT_FORMAT_MISMATCH, REJECT_UNKNOWN_FORMAT}, reason).
- Target = `gen9vgc2025regi` (Reg I). Reg I + Reg I BO3 → TARGET_COMPATIBLE (BO3 tagged
  separately via is_bo3). Other gen9 VGC regs (MA/MB/G/H…) → MECHANICALLY_SIMILAR_BUT_NOT_TARGET.
  Non-gen9-VGC → REJECT_FORMAT_MISMATCH. Unparseable → REJECT_UNKNOWN_FORMAT.
  **The gate MUST NOT accept MA/MB as Reg I** (the load-bearing guard: MA/MB has zero Reg I data).

## Non-goals (Part A)

Perspective reconstruction, availability tagging, legal-action check, leakage audit, decision
rows, downstream uses — all Part B/C. No real HF download in Part A (needs verified access /
user help); Part A is built + tested against hand-authored fixtures mimicking the documented
JSON+protocol form. A follow-up wires a real 10-battle sample once access is confirmed.

## Testing strategy

Fixtures under `research/vgc_bench_ingest/fixtures/`: a tiny valid VGC-Bench JSON (2-3 battles
with real Showdown-protocol logs, incl. one Reg I and one MA), a malformed-entry JSON. Tests:
load_raw strict-rejects malformed; parse re-derives winner/turns from log; raw+normalized hashes
stable + deterministic; format gate accepts Reg I, rejects MA-as-Reg-I (MECHANICALLY_SIMILAR),
tags BO3, rejects non-VGC. Live-path import-guard test.
