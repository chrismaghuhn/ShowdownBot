# 2b-5a Part A — VGC-Bench Ingestion Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.
> Steps use checkbox (`- [ ]`) syntax.

**Goal:** An isolated, fail-closed, fixture-tested foundation that snapshots + parses + format-
gates VGC-Bench Open-Team-Sheet logs, re-deriving winner/turns from the log and never trusting
external fields. Perspective/leakage (Part B) and real-data + downstream (Part C) come later.

**Architecture:** New isolated package `showdown_bot/src/showdown_bot/research/vgc_bench_ingest/`
(live-path-guarded), reusing `eval/battle_parse` + `eval/room_dump` for the inner Showdown
protocol. Spec: `docs/superpowers/specs/2026-07-11-2b5a-vgc-bench-ingest-partA-design.md`.

**Tech stack:** existing repo (pytest). **Constraint:** no battles, no HF download (fixtures
only); run only touched test files per task; full suite once at closeout (1 strict-xfail known;
calc tests need `npm ci --prefix tools/calc` to have run — irrelevant here).

---

### Task 1: package skeleton + snapshot + raw loader/parser (Sonnet)

**Files:** Create `research/vgc_bench_ingest/__init__.py` (live-path-guard docstring like
`eval/opponents/__init__.py`), `schema.py`, `snapshot.py`, `load_raw.py`, `parse_log.py`,
`fixtures/` (hand-authored), and `tests/` — put tests in `showdown_bot/tests/test_vgc_bench_ingest.py`.

- [ ] Study `eval/battle_parse.parse_battle_result` (input = frames list, returns
  winner/turns/end_reason/…) and `eval/room_dump.normalize_battle_log`/`GAUNTLET_NAME_SUBS` +
  `read_room_log_frames`/`normalized_room_log_sha256` (the sha recipe). Reuse them; do not
  reimplement protocol parsing.
- [ ] `schema.py`: frozen `VgcBenchRawBattle` (battle_id, epoch_seconds:int, raw_log_sha256,
  normalized_log_sha256, format_name, gametype, players:tuple, rules:tuple, log_lines:tuple),
  `VgcBenchParseError(Exception)`.
- [ ] `snapshot.py`: `sha256_file(path)`; `build_sample_manifest(*, source, source_revision,
  dataset_file, dataset_file_sha256, format_filter, sample_size, license, created_at, purpose)
  -> dict` (sorted keys, purpose defaults "ingestion_prototype_only"). Pure; created_at injected.
- [ ] `load_raw.py`: `load_raw(json_text) -> dict[str, tuple[int, str]]` — parse JSON; each value
  must be a 2-element `[epoch, log]` with int-coercible epoch + str log, else raise
  `VgcBenchParseError` naming the battle_id. Never silently skip.
- [ ] `parse_log.py`: `parse_battle(battle_id, epoch, log) -> VgcBenchRawBattle`. Split log into
  frames (lines); raw_log_sha256 = sha256 of the raw log bytes; normalized_log_sha256 via the
  room_dump recipe; extract format_name (`|player|`? no — format is in `|tier|`/`|gametype|`; grep
  a real protocol: `|gametype|doubles`, `|player|p1|Name|…`, `|teamsize|`, `|gen|9`, `|tier|…`,
  `|rule|…`). Winner + turns RE-DERIVED via `parse_battle_result(frames)`. Store on the dataclass.
- [ ] Failing tests first, then implement: valid fixture parses; malformed entry (value not a
  2-list) raises VgcBenchParseError naming it; raw+normalized sha stable across two parses;
  winner/turns match the fixture log's actual outcome; manifest keys sorted + purpose default.
- [ ] Run `tests/test_vgc_bench_ingest.py`. Commit `feat(2b-5a): vgc-bench ingest foundation — snapshot + raw parser`.

### Task 2: format/regulation gate + isolation guard (Sonnet)

**Files:** Create `research/vgc_bench_ingest/format_gate.py`; extend `test_vgc_bench_ingest.py`.

- [ ] `format_gate.py`: `gate_format(format_name) -> FormatGateResult` (frozen: source_format,
  inferred_regulation:str|None, is_bo3:bool|None, compatibility Literal, reason). Logic:
  - normalize the format string (lowercase, strip). Detect gen9 VGC via a `gen9vgc` substring +
    a year + a reg letter (e.g. `gen9vgc2025regi`, `gen9vgc2025regibo3`). BO3 detected via a
    `bo3` suffix/marker → is_bo3=True.
  - Reg I (2025 or 2026) → TARGET_COMPATIBLE. Other gen9 VGC regs → MECHANICALLY_SIMILAR_BUT_NOT_TARGET.
    Non-gen9-VGC (e.g. gen9ou, gen8vgc) → REJECT_FORMAT_MISMATCH. Unparseable/empty →
    REJECT_UNKNOWN_FORMAT. `reason` is a short human string.
  - **HARD RULE (test it explicitly): MA/MB (`regma`/`regmb`) → MECHANICALLY_SIMILAR, NEVER
    TARGET_COMPATIBLE.** This is the load-bearing guard (MA/MB has zero Reg I data).
- [ ] Isolation guard test: assert that importing `battle.decision`, `learning.reranker_shadow`,
  `learning.export_runtime`, `client.gauntlet` does NOT transitively import
  `showdown_bot.research.vgc_bench_ingest` (check `sys.modules` before/after, or scan those
  modules' import graph). If a clean runtime check is awkward, assert via source grep that no
  live-path file contains `vgc_bench_ingest`.
- [ ] Tests: Reg I → TARGET_COMPATIBLE; Reg I BO3 → TARGET_COMPATIBLE + is_bo3; regma/regmb →
  MECHANICALLY_SIMILAR (explicit "not Reg I" assertion); gen9ou → REJECT_FORMAT_MISMATCH;
  garbage → REJECT_UNKNOWN_FORMAT; the isolation guard.
- [ ] Run tests. Commit `feat(2b-5a): format/regulation gate + live-path isolation guard`.

### Task 3: README + closeout (controller)

- [ ] `research/vgc_bench_ingest/README.md`: the invariant (external human data, must not mix
  with seeded/teacher data unless the 6 conditions hold — copy from the banked plan), Part A
  scope (snapshot/parse/gate), what's deferred (Part B perspective+leakage, Part C real data +
  downstream), and the verified data status (Reg I in `-sv` archive: 16,359 BO1 + 183,267 BO3).
- [ ] Full suite once: green + 1 xfailed (known). `git diff main --stat` → merge decision.

## Self-review (writing-plans)

- Spec coverage: Phase 0→Task 1 snapshot, Phase 1→Task 1 parser, Phase 2→Task 2 gate. ✓
- Isolation (INV-1) enforced by the guard test + docstring. ✓
- No external field trusted (winner/turns re-derived from log). ✓
- No HF download; fixtures only; real-data sample is an explicit Part-C follow-up. ✓
- MA/MB-not-Reg-I guard has a dedicated test. ✓
