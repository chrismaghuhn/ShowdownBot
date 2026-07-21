# Viewer v0 — Plan B: Godot Shell and Bundle Loader

**Status:** APPROVED — 2026-07-21 (Rev. 6). Authorizes this plan’s document/pin scope only.
Self-contained; supersedes Rev. 2–5 text (no cross-rev references).
**Does not authorize code.** Implementation starts only after (1) Plan A / PR **#41** is
**merged**, and (2) a separate implementation go-ahead is given.
**Date:** 2026-07-21 · **Rev.:** 6
**Depends on:** APPROVED index; APPROVED bundle contract; Plan A fixtures **1, 4, 5, 6** (merged);
ADR-001 Godot 4.5.2
**Unblocks:** Plans C–E planning after their own approvals; Plan B code only after merge + go-ahead

**Authority:** [`../specs/viewer-v0-design.md`](../specs/viewer-v0-design.md) §5.4 / §7 / §9.1,
[`../specs/viewer-v0-bundle-contract-design.md`](../specs/viewer-v0-bundle-contract-design.md)
§6 / §8.6 / §10 / §11.1 / §13.2, [`../decisions/ADR-001-godot-ui-technology.md`](../decisions/ADR-001-godot-ui-technology.md),
[`../research/2026-07-license-data-audit.md`](../research/2026-07-license-data-audit.md),
[`2026-07-21-viewer-v0-implementation-index.md`](2026-07-21-viewer-v0-implementation-index.md) §3 / §5

> **For agentic workers:** after APPROVED + merge gate + go-ahead, execute task-by-task with TDD
> (gdUnit4 headless + PowerShell pin tests). No Python exporter changes. No edits under
> `showdown_bot/`, `data/eval/`, `config/eval/`, or `reports/`. No network in Godot runtime or tests
> after pins are vendored. Engine binaries are **not** committed. This document is the sole Plan B
> text — do not look up prior draft revisions.

---

## 0. Closed decisions

### 0.1 Engine pin (binding)

| Item | Decision |
|---|---|
| Engine | **Godot 4.5.2-stable** (ADR-001). Not 4.6.x / 4.7.x |
| Official ZIP | `Godot_v4.5.2-stable_win64.exe.zip` (`godotengine/godot-builds` tag `4.5.2-stable`) |
| ZIP SHA-256 | `3766090865330ab2a0ed33594520394b711c620b1378f9223904faeef60f2f14` |
| Editor EXE SHA-256 | `a2a2eb7eae9ce159042f6dc3aca89f6d0e4cccb92d3a4892cc8128c958b1d466` |
| Console EXE SHA-256 | `446e08f71624052572f96de9031850ba96382ce6752adde38bb955b0a49bed01` |
| Digest file | `godot/tools/ENGINE_SHA256SUMS` (committed) |
| Local dir | `godot/tools/engine/` (gitignored): ZIP + editor EXE + console EXE |
| Install | verify ZIP → extract staging → verify **editor + console** EXE digests → install both → delete staging |
| Runtime pin | `verify_engine_pin.ps1` requires **editor EXE and console EXE** digests always; ZIP digest required when ZIP file is present in `tools/engine/` |
| Headless invoke | editor or console EXE may be used; both must be pin-valid before either is launched |
| Wrong local binary | `godot/Godot_v4.7.1-*.exe` gitignored; never used |

### 0.2 gdUnit4 pin (binding)

| Item | Decision |
|---|---|
| Addon | **gdUnit4 v6.1.3** @ commit `1579130d73f15f628fd0cfdbf7d60bdc39144a26` (MIT) |
| Vendor | `godot/addons/gdUnit4/` committed; `THIRD_PARTY_NOTICES.md` + `addons/gdUnit4/LICENSE` |
| Inventory | artifact row in license-audit §3 |
| Headless | pinned 4.5.2 only |

### 0.3 Scripts / CI / bridges

| Item | Decision |
|---|---|
| Pin verify | `godot/tools/verify_engine_pin.ps1` (`-EngineDir` injectable for tests) |
| Pin unit test | `godot/tools/test_verify_engine_pin.ps1` (no Godot; pure PowerShell) |
| Install | `godot/tools/install_engine.ps1` |
| Headless | `godot/tools/run_gdunit_headless.ps1` (calls verify first) |
| CI matrix | Plan F |
| Worker→main | Mutex queue drained on main (`_process`). Worker never `call_deferred`, never holds `Node`, never emits signals |

### 0.4 Path containment (binding)

Before opening or hashing any payload file named in `files.*`:

1. Confirm the directory entry’s basename equals the canonical filename.
2. Open a `DirAccess` on the bundle root; call `DirAccess.is_link(filename)`.
3. If `is_link` is true → refuse `symlink_or_reparse_refused` (covers symlinks, Windows junctions,
   and other reparse points per Godot 4.5 `DirAccess` docs).
4. Only then open/hash the real file. No GDExtension.

Skipped privilege tests documented for Plan F re-run.

### 0.5 Fixtures

| Role | Path | Owner |
|---|---|---|
| Trusted replay+trace | `fixtures/viewer-v0/bundles/fixture-01/` | Plan A |
| Replay-only | `fixtures/viewer-v0/bundles/fixture-04/` | Plan A |
| Trace-only | `fixtures/viewer-v0/bundles/fixture-05/` | Plan A |
| Hash refuse | `fixtures/viewer-v0/sources/fixture-06/bundle/` | Plan A |
| Unit refuse / types / links | `godot/tests/fixtures/unit/` | Plan B |
| Fixtures 7, 12 | Plan F only | out of B |

### 0.6 Implementation gate

This plan is **APPROVED** (docs/pin only). Coding still requires PR #41 merged + separate
go-ahead. Planning for C–E may proceed; Plan B coding may not until both remaining gates clear.

---

## 1. Goal / non-goals

**Goal:** Godot 4.5.2 shell + worker `BundleLoader` validating local bundles per contract §8.6 /
§13.2 and publishing sealed typed DTOs on the main thread.

**Non-goals:** board/candidates/full docks; in-process Python; network; Plan F CI; fixtures 7/12;
Gate 26.

---

## 2. Architecture

```text
BundleLoader (Node, main)
  load_async(path)                 # never blocks on a live worker
    → if Thread alive: store pending={path}; cancel(); return
    → else: request_id++; state=LOADING; start Thread(worker)
  _process: drain queue
    → on terminal/finished: wait_to_finish() on main; clear Thread
    → if pending set: start that load; clear pending
    → emit progress/completed/refused/cancelled
  cancel(): mark cancel; never publish DTO
  _exit_tree(): cancel + synchronous wait_to_finish (allowed to block)

Worker (no Node): explicit Result at every step (no try/catch)
  → enqueue terminal envelope{request_id, kind=ok|refuse|cancelled, payload}
  → if Thread ends with no terminal envelope: main publishes internal_loader_error
```

---

## 3. File map

```text
showdownbot_studio/godot/
  .gitignore
  project.godot
  README.md
  THIRD_PARTY_NOTICES.md
  addons/gdUnit4/
  tools/
    ENGINE_SHA256SUMS
    verify_engine_pin.ps1
    test_verify_engine_pin.ps1
    install_engine.ps1
    run_gdunit_headless.ps1
    engine/                         # gitignored
  src/bundle/
    json_numbers.gd                 # parse_json_int / parse_json_float
    bundle_mode.gd                  # class_name BundleMode (+ mode string constants)
    file_entry_dto.gd               # class_name FileEntryDTO
    files_table_dto.gd              # class_name FilesTableDTO
    privacy_dto.gd                  # class_name PrivacyDTO
    source_provenance_dto.gd        # class_name SourceProvenanceDTO
    bundle_manifest_dto.gd          # class_name BundleManifestDTO
    candidate_dto.gd                # class_name CandidateDTO
    decision_row_dto.gd             # class_name DecisionRowDTO
    battle_event_dto.gd             # class_name BattleEventDTO
    exporter_warning_dto.gd         # class_name ExporterWarningDTO
    config_manifest_raw_dto.gd      # class_name ConfigManifestRawDTO
    bundle_dto.gd                   # class_name BundleDTO
    refuse_diagnostic.gd            # class_name RefuseDiagnostic  (B1)
    validation_result.gd            # class_name ValidationResult  (B1)
    path_containment.gd             # DirAccess.is_link gate (B2)
    bundle_validator.gd             # (B2)
    bundle_loader.gd                # (B3)
    bundle_worker.gd                # (B3)
  src/workspace/
    app_shell.tscn
    app_shell.gd
  tests/
    fixtures/unit/
    bundle/test_*.gd
    workspace/test_*.gd
```

---

## 4. Mode model (binding)

| Field | Meaning |
|---|---|
| `declared_mode` | From manifest `files` truth table only |
| `effective_mode` | After safe downgrades; drives UI surfaces |

Nullability (contract §11.1.2) checked against **`declared_mode` only**.

| Inputs | `declared_mode` | `effective_mode` | `trace_trusted` | `replay_trusted` |
|---|---|---|---|---|
| Valid replay + v2/v3 trace | `REPLAY_TRACE` | `REPLAY_TRACE` | true | true |
| Valid replay + unsupported trace version | `REPLAY_TRACE` | `REPLAY_ONLY` | false | true |
| Unsupported trace, no valid replay | — | refuse `unsupported_trace_schema_version` | — | — |
| Manifest replay-only | `REPLAY_ONLY` | `REPLAY_ONLY` | false | true |
| Manifest trace-only v2/v3 | `TRACE_ONLY` | `TRACE_ONLY` | true | false |

Downgrade case (`declared_mode=REPLAY_TRACE`, `effective_mode=REPLAY_ONLY`): keep manifest
`trace_schema_version` string as recorded; do not load trusted decisions; record
`downgrade_warnings`; do not rewrite manifest nullability.

---

## 5. JSON number model (binding)

Godot `JSON.parse` yields floating-point numbers for JSON numbers. Helpers in `json_numbers.gd`:

### 5.1 `parse_json_int(value, field_name) -> int`

Refuse `malformed_type` / `malformed_integer` unless **all** hold:

1. `typeof(value)` is `TYPE_FLOAT` or `TYPE_INT`.
2. Finite: not NaN, not ±Inf (`is_finite()`).
3. Integral: `value == floor(value)` (no fractional part).
4. Exact/safe range: `value >= -9007199254740991` and `value <= 9007199254740991`
   (IEEE-754 binary64 integer-exact range).
5. Return `int(value)`.

### 5.2 `parse_json_float(value, field_name) -> float`

Refuse unless finite `TYPE_FLOAT`/`TYPE_INT`; return `float(value)`. No integer-integral requirement.

### 5.3 Field classification

**Must use `parse_json_int`:**
`viewer_bundle_schema.major`, `viewer_bundle_schema.minor`, `source_provenance.seed_index`,
`decision_index`, `turn_number`, `candidates[].rank`, `chosen_rank` (when non-null),
`chosen_tera_slot` / `chosen_mega_slot` (when non-null), `request_protocol_index` (when non-null),
`protocol_index`, `warning_count`, `pokemon_slot`/`target_slot` if encoded as numbers,
`hp.current` / `hp.maximum` when present as numbers that the contract treats as integer HP,
`amount` when present as integer stages/turn.

**Must use `parse_json_float`:**
`decision_latency_ms`, `candidates[].aggregate_score`, `top1_top2_margin` (when non-null),
other genuine floats.

Boolean fields require JSON bool (`TYPE_BOOL`), not 0/1 numbers.

---

## 6. DTO compile contract (binding for Plans C/D)

### 6.0 File model (binding; Godot `class_name` rule)

GDScript registers **one** global `class_name` per `.gd` file (the script’s primary class).
Inner classes are **not** global compile names for Plans C/D.

**Binding choice:** one public type → one `.gd` file → one top-level `class_name` (extends
`RefCounted`, except `BundleMode` which may be a thin constants/`Object` helper). Do **not**
pack `CandidateDTO`, `DecisionRowDTO`, etc. into a single `bundle_dto.gd`.

After publish: deep-copy (no worker alias) → recursive `make_read_only()` on containers →
`seal()` on every DTO (setters refuse when `_sealed`).

`RefuseDiagnostic` and `ValidationResult` are part of this compile surface and ship in **B1**
(so B2 can type `ValidationResult.diagnostic: RefuseDiagnostic` without inventing owners).

### 6.1 Constants

- `BundleMode` (`bundle_mode.gd`): `REPLAY_TRACE`, `REPLAY_ONLY`, `TRACE_ONLY`
- Supported major: `1`
- Trusted trace versions: `decision-trace-v2`, `decision-trace-v3`
- Closed `DecisionPhase`: `team_preview`, `forced_replacement`, `regular_turn`
- Canonical paths: `battle_log→battle.jsonl`, `decision_trace→decisions.jsonl`,
  `warnings→warnings.json`, `config_manifest→config-manifest.json`
- Exactly four `files` keys; no others
- Open vocabularies (plain `String`, not enum-checked): `selection_stage`, `fallback_reason`,
  battle `type`, free-text status/item strings

### 6.2 `FileEntryDTO`

| Field | Type | Rules |
|---|---|---|
| `path` | `Variant` (String\|null) | present ⇒ exact canonical name; else null |
| `present` | `bool` | JSON bool only |
| `required` | `bool` | JSON bool; mode keys: `required==present`; optional keys: `required==false` |
| `sha256` | `Variant` (String\|null) | null iff not present |

### 6.3 `FilesTableDTO`

Always exactly: `battle_log`, `decision_trace`, `warnings`, `config_manifest` → each `FileEntryDTO`.

### 6.4 `PrivacyDTO`

| Field | Type | 1.0 value |
|---|---|---|
| `profile` | `String` | `portable-pseudonymous-v1` |
| `chat` | `String` | `excluded` |
| `private_messages` | `String` | `excluded` |
| `player_names` | `String` | `seat-pseudonyms` |
| `source_url` | `String` | `excluded` |
| `raw_source_included` | `bool` | `false` |

### 6.5 `SourceProvenanceDTO`

| Field | Type | Nullability |
|---|---|---|
| `dirty` | `Variant` (bool\|null) | tri-state |
| `our_side` | `Variant` (String\|null) | null when `declared_mode==REPLAY_ONLY` |
| `config_id` | `String` | never null |
| `schedule_hash` | `String` | never null |
| `seed_index` | `int` | via `parse_json_int` |
| `showdown_commit` | `Variant` (String\|null) | optional |
| `server_patch_hash` | `Variant` (String\|null) | optional |
| `unknown_fields` | `Dictionary` | sealed read-only |

### 6.6 `BundleManifestDTO`

| Field | Type | Notes |
|---|---|---|
| `schema_major` / `schema_minor` | `int` | `parse_json_int` |
| `required_capabilities` | `PackedStringArray` | |
| `exporter_name` / `exporter_version` | `String` | |
| `battle_id` / `format_id` / `git_sha` / `config_hash` | `String` | |
| `trace_schema_version` | `Variant` (String\|null) | null iff `declared_mode==REPLAY_ONLY` |
| `privacy` | `PrivacyDTO` | |
| `source_hashes_battle_log` | `Variant` (String\|null) | null in `TRACE_ONLY` |
| `source_hashes_decision_trace` | `Variant` (String\|null) | null in `REPLAY_ONLY` |
| `files` | `FilesTableDTO` | |
| `source_provenance` | `SourceProvenanceDTO` | |
| `unknown_fields` | `Dictionary` | |

### 6.7 `CandidateDTO`

| Field | Type |
|---|---|
| `candidate_id` | `String` |
| `rank` | `int` (`parse_json_int`) |
| `aggregate_score` | `float` (`parse_json_float`) |
| `candidate_key` | `Variant` (opaque String\|null) |
| `unknown_fields` | `Dictionary` |

### 6.8 `DecisionRowDTO`

| Field | Type |
|---|---|
| `decision_index` | `int` |
| `turn_number` | `int` |
| `decision_phase` | `String` (closed) |
| `decision_latency_ms` | `float` |
| `observable_state_hash` / `request_hash` | `String` |
| `state_summary` / `normalized_action` | `Dictionary` (read-only) |
| `actual_choose_string` | `String` |
| `candidates` | `Array[CandidateDTO]` (may be empty) |
| `chosen_candidate_key` / `chosen_candidate_id` | `Variant` |
| `chosen_rank` / `chosen_tera_slot` / `chosen_mega_slot` | `Variant` (int via parse when non-null) |
| `selection_stage` / `fallback_reason` | `Variant` (open String\|null) |
| `aggregation_mode` / `aggregation_risk_lambda` / `aggregation_must_react_lambda` | `Variant` (null at 1.0) |
| `request_protocol_index` | `Variant` (int\|null) |
| `top1_top2_margin` | `Variant` (float\|null) |
| `fallback_used` | `bool` |
| `warning_count` | `int` |
| `decision_valid` | `bool` |
| `unknown_fields` | `Dictionary` |

### 6.9 `BattleEventDTO`

| Field | Type |
|---|---|
| `protocol_index` | `int` |
| `type` | `String` (open) |
| `pokemon_side` / `pokemon_slot` / `pokemon_species` | `Variant` |
| `target_side` / `target_slot` | `Variant` |
| `details` / `value` / `side` | `Variant` |
| `amount` | `Variant` (int via parse when non-null) |
| `hp_current` / `hp_maximum` | `Variant` (int when non-null) |
| `hp_fainted` | `Variant` (bool\|null) |
| `hp_status` | `Variant` |
| `tags` | `PackedStringArray` |
| `unknown_fields` | `Dictionary` |

No `raw`. No nickname field.

### 6.10 `ExporterWarningDTO`

Matches Plan A `warnings.json` object shape (`code` + `decision_index` only in fixture 1).

| Field | Type | Nullability |
|---|---|---|
| `code` | `String` | mandatory |
| `decision_index` | `Variant` (int\|null) | mandatory key; value may be null |
| `message` | `Variant` (String\|null) | **optional**; absent or null is OK — never invent text |
| `unknown_fields` | `Dictionary` | sealed read-only |

### 6.11 `ConfigManifestRawDTO`

| Field | Type |
|---|---|
| `root` | `Dictionary` | sealed read-only open pre-image; never reinterpret keys |

### 6.12 `BundleDTO`

| Field | Type |
|---|---|
| `declared_mode` / `effective_mode` | `BundleMode` |
| `trace_trusted` / `replay_trusted` | `bool` |
| `manifest` | `BundleManifestDTO` |
| `decisions` | `Array[DecisionRowDTO]` | empty if not `trace_trusted` |
| `battle_events` | `Array[BattleEventDTO]` | empty if not `replay_trusted` |
| `warnings` | `Array[ExporterWarningDTO]` |
| `config_manifest` | `ConfigManifestRawDTO` or null |
| `downgrade_warnings` | `Array[RefuseDiagnostic]` |

### 6.13 `RefuseDiagnostic` (`refuse_diagnostic.gd`, B1)

| Field | Type |
|---|---|
| `reason` | `String` |
| `message` | `String` | loader/validator diagnostic text (not from `warnings.json`) |
| `offender` | `String` |

### 6.14 `ValidationResult` (`validation_result.gd`, B1)

Return type of `BundleValidator.validate_dir` (implemented in B2; type owned by B1).

| Field | Type |
|---|---|
| `ok` | `bool` |
| `diagnostic` | `RefuseDiagnostic` \| null | set when `ok==false` |
| `declared_mode` | `BundleMode` \| null |
| `effective_mode` | `BundleMode` \| null |
| `trace_trusted` | `bool` |
| `replay_trusted` | `bool` |
| `bundle` | `BundleDTO` \| null |
| `downgrade_warnings` | `Array[RefuseDiagnostic]` |

### 6.15 Seal tests (required)

- `test_sealed_rejects_field_assignment`
- `test_sealed_nested_dict_rejects_mutation`
- `test_sealed_nested_array_rejects_mutation`
- `test_published_dto_not_aliased_to_worker_buffer`

---

## 7. Validator contract (binding; complete)

`BundleValidator.validate_dir(path) -> ValidationResult` — pure, no `Node`, no threads.
Fail-closed; first failure wins. `ValidationResult` / `RefuseDiagnostic` types: §6.13–6.14 (B1).

### 7.1 Structural / types

Order is load-bearing for reparse points:

1. `manifest.json` parses as JSON **object**.
2. `files` object has **exactly** four logical keys.
3. Each `files.*` is an object; `present`/`required` are JSON **bool** → else `malformed_type`.
4. Canonical path map (§6.1); present path must equal canonical filename → else
   `noncanonical_path`. Present paths distinct → else `duplicate_path`.
5. Paths are single-segment; no `..`, drive, leading separator → `malformed_path`.
6. **For each present declared payload name first:** `DirAccess.is_link(name)` (§0.4). If true →
   refuse `symlink_or_reparse_refused` (covers file symlinks **and** directory junctions /
   reparse points named like `battle.jsonl`). Do this **before** generic subdirectory scans so a
   junction is not misclassified as `undeclared_subdirectory`.
7. Then open/hash each present real file → `missing_file` / `hash_mismatch`.
8. Bundle root has **no subdirectories** among remaining entries → `undeclared_subdirectory`.
9. Undeclared top-level files → `undeclared_file`.

### 7.2 Schema / capabilities / mode

10. `schema_major` via `parse_json_int` ∈ {1} → else `unsupported_major` (list supported).
11. Unknown `required_capabilities` entry → `unsupported_capability`.
12. Mode truth table (contract §11.1.1) → `declared_mode` or refuse `malformed_manifest` /
    `missing_mode`.
13. Nullability table (contract §11.1.2) against **`declared_mode`** → else `nullability`.

### 7.3 Trace version / effective mode

14. If `decision_trace` present and version ∈ {v2,v3}: `trace_trusted=true`;
    `effective_mode=declared_mode`.
15. If `decision_trace` present and version unsupported:
    - with valid replay → `ok=true`, `effective_mode=REPLAY_ONLY`, `trace_trusted=false`,
      `replay_trusted=true`, downgrade warning `unsupported_trace_schema_version`;
    - without valid replay → refuse `unsupported_trace_schema_version`.
16. If `decision_trace` absent: `trace_schema_version` must be JSON `null`.

### 7.4 Decisions (only when `trace_trusted`)

Presentation rows (Plan A `decisions.jsonl`) do **not** re-emit `battle_id` / `our_side`; the
exporter already enforced single-battle / single-side against the manifest. The reader therefore
**must not** require those keys on decision rows.

17. JSONL parse error → `jsonl_parse_error` (`decisions.jsonl`).
18. Duplicate `decision_index` → `duplicate_decision_index`.
19. Duplicate `candidate_key` within a decision → refuse.
20. Non-empty candidates and chosen key absent → row `decision_valid=false` (never label-match);
    bundle may still open.
21. Empty candidates with any `chosen_*` non-null → refuse.
22. Chosen key matches >1 candidate → refuse.
23. All integer/float fields via §5 helpers.
24. Unknown optional keys → `unknown_fields`.

### 7.5 Warnings object (when `warnings` present)

25. `warnings.json` parses as object with `warnings` array.
26. Each element is an object with mandatory `code: String` and `decision_index` (int via
    `parse_json_int`, or JSON `null`).
27. `message` if present must be String or null; if absent → DTO `message=null`. Never synthesize.
28. Unknown keys → `unknown_fields`. Malformed element → `malformed_warning`.

### 7.6 Battle (only when `replay_trusted`)

29. JSONL parse error → `jsonl_parse_error` (`battle.jsonl`).
30. `protocol_index` sparse strictly increasing → else `protocol_index_order`.
31. Integers via §5 helpers.

### 7.7 Named validator tests

| Test | Expect |
|---|---|
| `test_fixture01_trusted` | ok; declared=effective=`REPLAY_TRACE`; warnings parse without `message` |
| `test_fixture04_replay_only` | declared=effective=`REPLAY_ONLY` |
| `test_fixture05_trace_only` | declared=effective=`TRACE_ONLY` |
| `test_fixture06_hash_mismatch` | `hash_mismatch` |
| `test_refuse_string_boolean_present` | `malformed_type` |
| `test_refuse_extra_files_key` | `unknown_logical_key` / `malformed_manifest` |
| `test_refuse_noncanonical_path` | `noncanonical_path` |
| `test_refuse_duplicate_path` | `duplicate_path` / `noncanonical_path` |
| `test_refuse_subdirectory` | `undeclared_subdirectory` |
| `test_refuse_symlink_or_junction_payload` | `symlink_or_reparse_refused` (skip if no privilege) |
| `test_junction_named_battle_jsonl_is_reparse_not_subdir` | `symlink_or_reparse_refused` (not `undeclared_subdirectory`) |
| `test_unsupported_trace_downgrades_effective_mode` | declared=`REPLAY_TRACE`, effective=`REPLAY_ONLY` |
| `test_unsupported_trace_without_replay_refuses` | `unsupported_trace_schema_version` |
| `test_refuse_duplicate_decision_index` | `duplicate_decision_index` |
| `test_refuse_jsonl_parse_error` | `jsonl_parse_error` |
| `test_refuse_non_integral_decision_index` | `malformed_integer` |
| `test_refuse_malformed_warning_object` | `malformed_warning` |
| `test_chosen_key_missing_marks_invalid` | ok + `decision_valid=false` |
| `test_unknown_optional_preserved` | key in `unknown_fields` |
| `test_decision_rows_do_not_require_battle_id_or_our_side` | fixture-01 decisions validate |

---

## 8. Worker lifecycle + queue (binding)

### 8.1 States

`IDLE → LOADING → {COMPLETED | REFUSED | CANCELLED}`.

### 8.2 Request IDs

Monotonic `request_id`. Envelopes carry id. Main publishes only if id == `_active_request_id`.

### 8.3 Non-blocking `load_async` + pending handoff

Loader owns at most one live `Thread` (`_worker_thread`) and at most one `pending_path`.

| Event | Action |
|---|---|
| `load_async(path)` while no live Thread | `request_id++`; `LOADING`; start Thread; return immediately |
| `load_async(path)` while Thread still alive | set `pending_path = path` (replace any prior pending); signal cancel to current worker; **return immediately without `wait_to_finish`** |
| Worker finishes / cancel ack / terminal envelope observed on main | on main: `wait_to_finish()`; `_worker_thread = null`; if `pending_path` set → start that load and clear pending; else transition terminal state |
| `cancel()` during LOADING | cancel active id; clear or keep pending per API (`cancel` clears pending); never publish DTO |
| `_exit_tree()` | cancel; clear pending; **synchronous** `wait_to_finish()` on owned Thread (blocking OK here); clear queue |

Godot requires `wait_to_finish()` on main even after the worker function has returned. The second
`load_async` must **not** block the main thread waiting on a barrier-held worker.

### 8.4 Errors without try/catch

GDScript has no general try/catch. Binding rules:

1. Worker code returns explicit `Result` / envelope kinds at every expected failure (`ok`, `refuse`,
   `cancelled`) — never relies on exception catching.
2. If main observes `_worker_thread` finished (`is_alive() == false`) **and** no terminal envelope
   was enqueued for `_active_request_id` → `wait_to_finish()`, then publish `REFUSED` /
   `internal_loader_error` (“worker returned without terminal envelope”).
3. Progress tokens queued; main emits `progress` only.
4. Publish path: deep-copy → freeze containers → `seal()` DTOs.

### 8.5 Required loader tests

| Test | Assert |
|---|---|
| `test_fixture01_load_completed_sealed` | COMPLETED + seal tests hold |
| `test_stale_result_dropped_after_cancel` | old id ignored |
| `test_cancel_never_publishes_partial_dto` | barrier before publish; cancel; no completed |
| `test_progress_emitted_only_on_main_thread` | handler thread id == main |
| `test_worker_returns_without_terminal_envelope_refuses` | finished Thread, no envelope → `internal_loader_error` |
| `test_worker_has_no_node_reference` | worker type is RefCounted job, not Node |
| `test_published_dto_not_aliased_to_worker_buffer` | mutate worker buffer; DTO unchanged |
| `test_finished_thread_wait_to_finish_on_main` | after complete, `_worker_thread` null and joined |
| `test_second_load_async_returns_before_prior_barrier_releases` | hold prior worker on barrier; call `load_async` again; call returns while barrier still held; after release, pending load runs |
| `test_exit_tree_cancels_and_joins_synchronously` | free loader mid-load; joined; no orphan Thread / no crash |

Barrier style: injectable `WorkerHooks` wait points — **no** wall-clock sleeps as the sole sync.

---

## 9. Tasks (full RED → implement → GREEN → commit)

Cwd: `showdownbot_studio/godot/` unless noted.

---

### Task B0 — Engine pin scripts + project + gdUnit

**Files:** `tools/test_verify_engine_pin.ps1`, `tools/verify_engine_pin.ps1`,
`tools/install_engine.ps1`, `tools/run_gdunit_headless.ps1`, `tools/ENGINE_SHA256SUMS`,
`project.godot`, `THIRD_PARTY_NOTICES.md`, `addons/gdUnit4/**`, license-audit row,
`tests/workspace/test_engine_smoke.gd`

- [ ] **Step 1: Write** `tools/test_verify_engine_pin.ps1` that (editor and console each covered
  separately so “both always checked” is executable, not only textual):
  1. Temp `-EngineDir` with **editor EXE missing** (console present/valid) → exit `2` /
     `engine_missing`.
  2. Temp dir with **console EXE missing** (editor present/valid) → `engine_missing`.
  3. Editor present with **wrong digest**, console valid → `engine_pin_mismatch`.
  4. Console present with **wrong digest**, editor valid → `engine_pin_mismatch`.
  5. (Optional GREEN path later) both EXEs match digests → exit `0`.
  Initially **dotsource/calls** `Verify-EnginePin -EngineDir ...` which does not exist yet.
- [ ] **Step 2: RED**

```powershell
powershell -File .\tools\test_verify_engine_pin.ps1
```

Expected: FAIL — `Verify-EnginePin` / `verify_engine_pin.ps1` missing (`CommandNotFound` /
script exit ≠ 0 from missing implementation).

- [ ] **Step 3: Implement** `verify_engine_pin.ps1` (`-EngineDir`, checks editor+console always;
  ZIP if present) and `install_engine.ps1`.
- [ ] **Step 4: GREEN** — `test_verify_engine_pin.ps1` PASS (injected paths). Then
  `.\tools\verify_engine_pin.ps1` PASS on real `tools/engine/`.
- [ ] **Step 5:** Vendor gdUnit4; notices; audit row; `project.godot`; `test_engine_smoke.gd`
  (`test_truth`).
- [ ] **Step 6:**

```powershell
.\tools\run_gdunit_headless.ps1 -a "res://tests/workspace/test_engine_smoke.gd"
```

GREEN: 1 passed on pinned 4.5.2.

- [ ] **Commit** `chore(studio): pin Godot 4.5.2 digests and vendor gdUnit4 v6.1.3`

---

### Task B1 — JSON numbers + sealed DTOs + result types

**Files:** `src/bundle/json_numbers.gd`, `bundle_mode.gd`, every §6.0 `*_dto.gd` /
`refuse_diagnostic.gd` / `validation_result.gd` (one `class_name` per file),
`tests/bundle/test_json_numbers.gd`, `tests/bundle/test_bundle_dto.gd`

- [ ] **Step 1: Write tests** for `parse_json_int` (reject 1.5, Inf, >2^53, bool); each public
  DTO `class_name` resolves globally; seal / alias / `declared_mode`≠`effective_mode` /
  warning+config DTOs / unknown_fields; construct `ValidationResult` with
  `diagnostic: RefuseDiagnostic` (ok and refuse shapes).
- [ ] **Step 2: RED**

```powershell
.\tools\run_gdunit_headless.ps1 -a "res://tests/bundle/test_json_numbers.gd"
.\tools\run_gdunit_headless.ps1 -a "res://tests/bundle/test_bundle_dto.gd"
```

Expected: missing classes / parse helpers.

- [ ] **Step 3: Implement** helpers + full §6 types (**one `.gd` / `class_name` each**, including
  `RefuseDiagnostic` + `ValidationResult`) + `seal()`.
- [ ] **Step 4: GREEN** — both commands PASS.
- [ ] **Commit** `feat(studio): sealed viewer bundle DTOs and JSON int parsing`

---

### Task B2 — Validator + `DirAccess.is_link` containment

**Files:** `path_containment.gd`, `bundle_validator.gd`, `tests/bundle/test_bundle_validator.gd`,
`tests/fixtures/unit/**`
**Uses (already in B1):** `ValidationResult`, `RefuseDiagnostic`, all §6 DTOs.

- [ ] **Step 1: Write** unit fixtures + all §7.7 tests calling `BundleValidator.validate_dir`
  (incl. fixture-01 without row `battle_id`/`our_side`, warnings without `message`, junction
  classification; refuse paths assert typed `ValidationResult.diagnostic: RefuseDiagnostic`).
- [ ] **Step 2: RED**

```powershell
.\tools\run_gdunit_headless.ps1 -a "res://tests/bundle/test_bundle_validator.gd"
```

Expected: missing `BundleValidator.validate_dir` (DTO/result types already present from B1).

- [ ] **Step 3: Implement** validator + `is_link` on declared names **before** subdirectory scan;
  return `ValidationResult` (no new type files).
- [ ] **Step 4: GREEN** — same command; non-skipped PASS; link skips documented.
- [ ] **Commit** `feat(studio): Godot bundle validator with DirAccess.is_link containment`

---

### Task B3 — Worker loader + thread lifecycle

**Files:** `bundle_loader.gd`, `bundle_worker.gd`, `tests/bundle/test_bundle_loader.gd`
**Uses (already in B1/B2):** `RefuseDiagnostic`, `ValidationResult`, `BundleValidator`, DTOs.

- [ ] **Step 1: Write** all §8.5 tests with `WorkerHooks` barriers (incl. non-blocking second
  `load_async` and “no terminal envelope” refuse).
- [ ] **Step 2: RED**

```powershell
.\tools\run_gdunit_headless.ps1 -a "res://tests/bundle/test_bundle_loader.gd"
```

Expected: missing `BundleLoader` lifecycle API.

- [ ] **Step 3: Implement** queue bridge + pending handoff + explicit Result envelopes +
  `wait_to_finish` only after terminal/finished on main (and sync join in `_exit_tree`).
- [ ] **Step 4: GREEN** — same command PASS.
- [ ] **Commit** `feat(studio): worker BundleLoader with join-safe thread lifecycle`

---

### Task B4 — Minimal shell UX

**Files:** `src/workspace/app_shell.tscn`, `app_shell.gd`,
`tests/workspace/test_app_shell_smoke.gd`

- [ ] **Step 1: Write tests:** open fixture 1 trusted; 4/5 effective modes; 6 refuse reason;
  downgrade warning when declared≠effective; CLI stub records `--decision` without navigating.
- [ ] **Step 2: RED**

```powershell
.\tools\run_gdunit_headless.ps1 -a "res://tests/workspace/test_app_shell_smoke.gd"
```

Expected: missing `AppShell`.

- [ ] **Step 3: Implement** minimal UI wired to loader.
- [ ] **Step 4: GREEN** — same command PASS.
- [ ] **Commit** `feat(studio): minimal Godot shell open/refuse UI`

---

## 10. Acceptance

1. `test_verify_engine_pin.ps1` + real `verify_engine_pin.ps1` green; editor **and** console
   digests always checked; 4.7.1 rejected.
2. Full gdUnit suite green on pinned 4.5.2.
3. Fixtures 1/4/5/6 behaviours per §7.7; no fixture 7/12 acceptance.
4. `declared_mode` / `effective_mode` downgrade case green.
5. JSON int rejects non-integral / out-of-range.
6. Seal + alias tests green.
7. `DirAccess.is_link` refuse green or skip→Plan F.
8. Thread lifecycle green: pending non-blocking second load; join after finish; sync `_exit_tree`;
   missing terminal envelope → `internal_loader_error`.
9. Queue-only bridge; notices + audit row; no engine binary committed.
10. Fixture 1 validates (no invented warning `message`; no decision-row `battle_id`/`our_side`).
11. Each public §6 type has its own `.gd` + global `class_name`; `ValidationResult` /
    `RefuseDiagnostic` compile in B1 before B2.
12. Code only after §0.6 gate.

---

## 11. Commits

| # | Message |
|---|---|
| B0 | `chore(studio): pin Godot 4.5.2 digests and vendor gdUnit4 v6.1.3` |
| B1 | `feat(studio): sealed viewer bundle DTOs and JSON int parsing` |
| B2 | `feat(studio): Godot bundle validator with DirAccess.is_link containment` |
| B3 | `feat(studio): worker BundleLoader with join-safe thread lifecycle` |
| B4 | `feat(studio): minimal Godot shell open/refuse UI` |

---

## 12. Handoff

- C/D use sealed getters; surfaces follow `effective_mode`.
- F: fixtures 7/12, privileged link re-run, GitHub CI, Gate 5 OS.
- Engine upgrades → ADR-001 revisit.

---

## 13. Approval checklist

- [x] Document self-contained (no prior-rev references)
- [x] One `.gd` / one `class_name` per public DTO (no multi-type `bundle_dto.gd`)
- [x] `RefuseDiagnostic` + `ValidationResult` owned by B1 (available before B2)
- [x] JSON int/float rules accepted
- [x] Pending non-blocking `load_async` + sync `_exit_tree` join accepted
- [x] Explicit Result envelopes + missing-terminal-envelope refuse accepted
- [x] `DirAccess.is_link` before subdirectory scan accepted
- [x] Decision-row identity check removed; warning `message` optional
- [x] Console EXE always in runtime pin check
- [x] B0 automated pin test RED→GREEN accepted (incl. per-EXE missing/mismatch cases)
- [x] DTO/validator/worker tables complete for C/D
- [x] Plan marked APPROVED 2026-07-21 (Rev. 6) — docs/pin only
- [ ] Code gate remaining: PR #41 merged + separate implementation go-ahead
