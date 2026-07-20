# Viewer v0 — Plan A: Exporter and Fixtures

**Status:** APPROVED — 2026-07-21 (Rev. 6). Authorizes this plan’s document scope only.
**Does not authorize code.** Implementation starts only after a separate implementation go-ahead.
**Date:** 2026-07-21 · **Rev.:** 6
**Depends on:** APPROVED index + approved bundle contract (incl. §14.1 Amendment A) / viewer-v0 design
**Unblocks:** Plan B planning/review (fixture-01 still required before Plan B code); Plan A code blocked
until separate implementation authorization

**Authority:** [`../specs/viewer-v0-bundle-contract-design.md`](../specs/viewer-v0-bundle-contract-design.md)
(primary, **§14.1 Amendment A 2026-07-21**), [`../specs/viewer-v0-design.md`](../specs/viewer-v0-design.md) §5.2 / §9.1,
[`../research/2026-07-license-data-audit.md`](../research/2026-07-license-data-audit.md) §4,
[`2026-07-21-viewer-v0-implementation-index.md`](2026-07-21-viewer-v0-implementation-index.md) §3.3

> **For agentic workers:** after APPROVED, execute task-by-task with TDD. No Godot. No edits under
> `showdown_bot/`, `data/eval/`, `config/eval/`, or `reports/`. No network during tests or export.

---

## 0. Closed decisions

### 0.1 Package / install

| Item | Decision |
|---|---|
| Distribution | `showdownbot-studio-exporter` |
| Import | `showdownbot_studio_exporter` |
| Root | `showdownbot_studio/python/` (`src/` layout) |
| Project file | `showdownbot_studio/python/pyproject.toml` |
| Python | `>=3.11` |
| Console script | `showdownbot-studio-export` → `showdownbot_studio_exporter.cli:main` |
| Install | from `showdownbot_studio/python`: `python -m pip install -e ".[dev]"` |
| Test cwd | `showdownbot_studio/` |
| Test command | `python -m pytest tests/python -q` |
| pytest pythonpath | `python/src` |

### 0.2 JSON Schema under `schemas/`

**Deferred.** Bundle contract §10 is authority. `schemas/` stays placeholder-only in Plan A.

### 0.3 RFC 8785 / JCS

| Item | Decision |
|---|---|
| Library | `rfc8785==0.1.4` (Apache-2.0, Trail of Bits) |
| Upstream tag | `trailofbits/rfc8785.py` tag **`v0.1.4`** (commit `4d9b161f6054301d98d0566e813d020fb019ee10`) |
| Wrapper | `canonicalize.py` → `rfc8785.dumps`; never `json.dumps` for bundle bytes |
| Vectors | **Commit-only.** Exact files listed in §0.3.1. A1 copies those bytes into the tree; **no fetch**, no network in A1 or later |
| Non-finite | Refuse; never emit |

#### 0.3.1 Pinned JCS vector files (SHA-256 of file bytes)

Source path in upstream: `test/assets/{input,output,outhex}/<name>.{json,txt}` at tag `v0.1.4`.
Local path under `showdownbot_studio/`:

| sha256 | local path |
|---|---|
| `e503b6d71d1afa595b1c74b1016445c944cd89f90418066b23de1aeda7d17563` | `tests/python/jcs_vectors/input/arrays.json` |
| `099601b171cafed97c333f8878d68e7f8c8f795412adb34b2fdcf0e7c7beac42` | `tests/python/jcs_vectors/output/arrays.json` |
| `e306733ca0c4da9595ebde73ec072c295f0f9ef0ea4aafc4d267d4a04988ce51` | `tests/python/jcs_vectors/outhex/arrays.txt` |
| `03676a951cd8753ac62589f72eb2105cc782c33425418cfe1d517c111f6e5d5a` | `tests/python/jcs_vectors/input/french.json` |
| `d99d0ebdcb0033cb858cfa830ae46bc0fb3309413b271f1da828c89901a27ed5` | `tests/python/jcs_vectors/output/french.json` |
| `f9b3bfd02f4edb3d0a490703153d836db5ef0a2090a9d3357f8c3797e12d4043` | `tests/python/jcs_vectors/outhex/french.txt` |
| `d66893805be1784116af50af3110d08766c70a6b4aad93374723f72346e7aaa6` | `tests/python/jcs_vectors/input/structures.json` |
| `605f65004ec2db7692522a0852c22f1c989e036d547e88963d1a3143cf3195d5` | `tests/python/jcs_vectors/output/structures.json` |
| `063ee2bc6fa3f93b2a131841315f5c6bf0ea7488cc128ed50725cabf5592627b` | `tests/python/jcs_vectors/outhex/structures.txt` |
| `4621864e014d4a805a563f55b9ea20aba4a2d2dc09c7394f625496998c00702c` | `tests/python/jcs_vectors/input/unicode.json` |
| `0d99aad92a125196ff887876643fd3206786a84ddce2cee52ba4ad256d2381d3` | `tests/python/jcs_vectors/output/unicode.json` |
| `0471fea1ee0464e435a52510d2c187b216961a5e7e2665402ea9cb1cd04109ca` | `tests/python/jcs_vectors/outhex/unicode.txt` |
| `c4a041b503d6bc236036ef44db4dac499272f60fc22c40dc3b7a54870ba6f1c3` | `tests/python/jcs_vectors/input/values.json` |
| `2d5e01a318d0f0879ab568c4be289c8b1f64ef8921a53c6277d5e069978baacb` | `tests/python/jcs_vectors/output/values.json` |
| `b8b802e82c7bead71a7841e27fce6458854eb72ffd0eaa51474dacdfbdf3ab64` | `tests/python/jcs_vectors/outhex/values.txt` |
| `a3a905266bd4a49a969274ea69baa14ee0c4af0ead926d6fa2b7612b4af75387` | `tests/python/jcs_vectors/input/weird.json` |
| `6af595a9aa80110b964b4de3f82a05fa6ae7423005019bacfa2620dddc4e94d1` | `tests/python/jcs_vectors/output/weird.json` |
| `1061953c7129537722f9abd9de321c787120489d09f34ba58065bd77ba9a84b6` | `tests/python/jcs_vectors/outhex/weird.txt` |

Also commit `tests/python/jcs_vectors/SHA256SUMS` containing exactly these 18 lines (hash + relative path).
A1 GREEN requires `sha256sum -c` / equivalent Python check to pass. **Mismatch = fail closed.**

### 0.4 Fixture-01 = synthetic-coherent-v1 (binding; contract §14.1)

**Evidence survey (2026-07-21):** No committed coherent replay+trace pair was found.
Champions smokes (including `smoke-i7a-mega`) have `"room_raw_path": null`.
`data/eval/kaggle-validation/room_raw/` has logs without `decision_trace.jsonl`.
`data/eval/t4/rerun` and `data/eval/t6` have `room_raw/` without a Studio-usable
`decision_trace.jsonl` pair. Therefore Fixture 1 uses the contract’s **§14.1 exception**.

**Forbidden (unchanged):** inventing a battle log that “joins” real smoke `request_hash` values and
bundling it with smoke results/manifests/traces.

**Fixture 1** lives under `fixtures/viewer-v0/sources/fixture-01/` as a
`source_kind: synthetic-coherent-v1` set:

| file | Role |
|---|---|
| `battle.log` | protocol log with `|request|` payloads that hash to the synthetic trace |
| `decision_trace.jsonl` | v3 rows; all three `decision_phase` values; ≥1 non-empty chosen key |
| `results.jsonl` | single-battle row; sentinel provenance only |
| `results.manifest.json` | sentinel provenance only |
| `results.config-manifest.json` | sentinel config pre-image agreeing with row `config_hash` |
| `SOURCES.md` entry | must include `source_kind: synthetic-coherent-v1` and the sentinel table below |

**Documented sentinels** (must appear verbatim in `SOURCES.md`). Identity fields must not collide
with **any** committed eval artifact under `data/eval/` (not merely smoke-i7a-mega) — enforced by
`test_synthetic_sentinels_match_no_committed_eval_identity`.

| field | sentinel in synthetic **sources** | notes |
|---|---|---|
| `battle_id` | `synthetic00000001` | must not appear in `data/eval/**` |
| `run_id` | `syntheticrun00001` | must not appear in `data/eval/**` |
| `git_sha` | `unknown` | **required.** A fake 40-hex SHA is forbidden — §8.4 ties `dirty:false` to a real commit SHA |
| `config_hash` | `bbbbbbbbbbbbbbbb` | must not appear in `data/eval/**` |
| `schedule_hash` | `cccccccccccccccc` | must not appear in `data/eval/**` |
| `config_id` | `synthetic_fixture` | must not appear as a committed eval `config_id` identity pair with the above |
| `format_id` | `gen9championsvgc2026regma` | shared format id is allowed (not a run identity) |
| `dirty` (source row/manifest) | `false` | legacy producer shape may record boolean `false` even when git is unavailable |
| `seed_index` | `0` | — |
| `our_side` | `p1` | — |

**Bundle provenance after export (binding, §8.4):** because source `git_sha == "unknown"`, the
exporter **must** emit `manifest.source_provenance.dirty: null` (and top-level/`git_sha` remain
`"unknown"`). It must **not** emit `dirty: false`. Covered by
`test_synthetic_fixture_reports_git_and_dirty_unknown`.

Internal coherence: every decision `request_hash` matches a surviving `|request|` line; provenance
fields agree across the five inputs (including `git_sha: "unknown"` on trace/results/manifest).
Exporter still applies `portable-pseudonymous-v1`. Fixture 3 uses the same `git_sha`/`dirty` rules
with its own non-colliding identity sentinels.

**Smoke-trace suite (separate, not Fixture 1):** read-only
`data/eval/champions-panel-v0/smoke-i7a-mega/decision_trace.jsonl` (+ optional results/manifests)
for producer-integrity gates that do **not** claim a joined replay. Never pair smoke trace with a
synthetic battle log.

Frozen smoke hashes (smoke suite only):

| path | sha256 |
|---|---|
| `data/eval/champions-panel-v0/smoke-i7a-mega/decision_trace.jsonl` | `7070338b77425621b6c3720e1f5cea651dff832dc6a0a8884de047c6647ff197` |
| `data/eval/champions-panel-v0/smoke-i7a-mega/results.jsonl` | `f4da66b80d700343998da818cc3c89aa239fb8b3c3ecbd214930f209c8bd7cb0` |
| `data/eval/champions-panel-v0/smoke-i7a-mega/results.jsonl.manifest.json` | `1224ceac19eb7fa97e0b32bb844b9e95a9aa3eb97de2f1387c5a8a00a1cdf957` |
| `data/eval/champions-panel-v0/smoke-i7a-mega/results.jsonl.config-manifest.json` | `c953a619529338c8b3ed26d68042b5ee1a4de4323b94bba3324b847f408b70c7` |

### 0.5 Atomic export (binding)

Contract: export refuse means **no bundle is produced** (§13).

Implementation rules:

1. `--out` must not exist (refuse `output_exists` if it does). Resolve `out = Path(--out).resolve()`.
2. Staging **must** be a sibling on the same directory/filesystem:
   `staging = out.parent / f".{out.name}.staging-{uuid4()}"`.
   Do **not** use `tempfile.mkdtemp` on a different volume.
3. Write exclusively into `staging`. Run full bundle validation on `staging`.
4. Publish **only** via atomic directory rename: `os.replace(staging, out)`.
   - **No file-by-file publish. No fallback that creates `--out` before all content is final.**
   - If `os.replace(staging, out)` raises (directory rename unsupported / cross-device / etc.):
     delete `staging` (best effort), ensure `out` does not exist, refuse with
     `atomic_publish_unsupported`.
5. On any refuse or exception before successful replace: delete `staging` (best effort);
   `--out` must not exist; no partial tree under `--out`.

Required tests:

| Test | Asserts |
|---|---|
| `test_refuse_leaves_no_out_dir` | exit 2 → `out` absent; no `.*.staging-*` left |
| `test_exception_leaves_no_out_or_staging` | injected failure → same |
| `test_success_out_is_complete_bundle` | after success, `out` validates; no staging sibling remains |
| `test_no_file_by_file_publish_api` | export module exposes no public per-file publish helper; only directory replace path |
| `test_atomic_publish_unsupported_refuses_clean` | force `os.replace` failure → reason `atomic_publish_unsupported`; no `out` |

---

## 1. Goal / non-goals

**Goal:** deterministic exporter + Plan A fixtures **1, 3, 4, 5, 6, 10, 16** + smoke-trace integrity
suite + A-fix/A-unit gates in §5.

**Non-goals:** Godot; mutating bot/eval trees; ZIP; §16 producer gaps; v1→presentation migration;
Plan F catalogue fixtures; claiming Gate 5 cross-OS or Gate 26 visual distinctness.

---

## 2. Architecture

```text
coherent frozen sources (read-only)
  → validate → normalize v2|v3 (v1 refuse for trace)
  → privacy → join → rfc8785==0.1.4 → staging → validate → atomic publish
```

Mode derived from inputs (no `--mode` flag):

| `--battle-log` | `--decision-trace` | Mode |
|---|---|---|
| yes | yes | replay + trace |
| yes | no | replay-only |
| no | yes | trace-only |
| no | no | refuse `missing_mode_inputs` |

---

## 3. File map

```text
showdownbot_studio/
  python/
    pyproject.toml
    src/showdownbot_studio_exporter/
      __init__.py
      __main__.py
      cli.py
      canonicalize.py
      hashutil.py
      privacy.py
      provenance.py
      join.py
      export_battle.py
      export_decisions.py
      warnings_emit.py
      validate_bundle.py
      export_bundle.py
      errors.py
      pathsafety.py
  tests/python/
    conftest.py
    jcs_vectors/{input,output,outhex}/...
    jcs_vectors/SHA256SUMS
    test_a0_skeleton.py
    test_a1_canonicalize.py
    test_a2_manifest_hash.py
    test_a3_privacy.py
    test_a4_decisions_v3.py
    test_a4_decisions_v2.py
    test_a4_decisions_v1_refuse.py
    test_a4_smoke_trace_integrity.py
    test_a5_battle_join.py
    test_a5_request_hash_recipes.py
    test_a6_provenance_modes.py
    test_a7_cli.py
    test_a7_validate_bundle.py
    test_a7_atomic_export.py
    test_a7_pathsafety.py
    test_a8_fixtures.py
    test_source_immutability.py
    synthetic/
      trace_v1.jsonl
      trace_v2.jsonl
      nonfinite_trace.jsonl
      dup_identity.jsonl
      chosen_desync.jsonl
      sparse_protocol.log
      request_skip.log
      provenance_disagree_results.jsonl
  fixtures/viewer-v0/
    SOURCES.md
    sources/fixture-01/...
    sources/fixture-03/...
    sources/fixture-04/...
    sources/fixture-05/...
    sources/fixture-06/...
    sources/fixture-10/...
    sources/fixture-16/...
    bundles/fixture-01/...
    bundles/fixture-03/...
    bundles/fixture-04/...
    bundles/fixture-05/...
    bundles/fixture-06/...
    bundles/fixture-10/...
    bundles/fixture-16/...
```

---

## 4. CLI contract

```text
showdownbot-studio-export
  --out DIR
  [--battle-log PATH]
  [--decision-trace PATH]
  [--results PATH]
  [--run-manifest PATH]
  [--config-manifest PATH]
  [--battle-id ID]
```

Exit: `0` success; `2` refuse (stderr: `REASON_CODE: message`); `1` internal error.

Provenance resolution: bundle contract §11.1.3 exactly. `dirty` tri-state §8.4.

### 4.1 Output-path safety

Refuse `output_inside_protected_tree` if resolved `--out` is inside any resolved input parent, or
inside protected roots (`data/eval`, `config/eval`, `reports`,
`showdownbot_studio/fixtures/viewer-v0/sources`) after `Path.resolve()` including Windows
case-insensitivity.

Required counterexamples in `test_a7_pathsafety.py`:

| Test | Attack |
|---|---|
| `test_refuse_out_under_data_eval_case_variant` | `--out` under `DATA\EVAL\...` / `data/Eval/...` on Windows |
| `test_refuse_out_via_symlink_or_junction_to_sources` | junction/symlink from temp into `fixtures/viewer-v0/sources` |
| `test_refuse_out_via_symlink_to_data_eval` | link into `data/eval` |

If the host cannot create symlinks/junctions, those two tests **skip with explicit reason** and Plan F
must re-run them on a Windows agent with symlink privilege. Case-variant test is mandatory on
Windows (never skip on win32).

### 4.2 CLI tests

| Test | Expected |
|---|---|
| `test_cli_replay_trace_success` | exit 0; validates as replay+trace |
| `test_cli_replay_only_success` | exit 0; replay-only |
| `test_cli_trace_only_success` | exit 0; trace-only |
| `test_cli_refuse_neither_input` | exit 2; `missing_mode_inputs`; no `--out` |
| `test_cli_refuse_output_exists` | exit 2; `output_exists` |
| `test_cli_refuse_output_inside_sources` | exit 2; `output_inside_protected_tree` |
| `test_cli_refuse_provenance_disagreement` | exit 2; staging gone; no `--out` |
| `test_cli_require_battle_id_when_ambiguous` | exit 2 |

---

## 5. Gate matrix

| Gate | A class | Notes |
|---|---|---|
| 1–4, 6–7, 9–12 | **A-fix** | Fixture 1 and/or smoke-trace suite as specified below |
| 5 | **F-fix** | Cross OS/user matrix (Windows+Ubuntu). Dual-tmpdir alone does **not** close Gate 5 |
| 8 | **A-unit** | `synthetic/nonfinite_trace.jsonl` → F fixture 11 |
| 13 | **A-unit** | synthetics → F fixtures 9, 14 |
| 14 | **Not-A** | Godot Plan D/F |
| 15–17 | **A-unit** | crafted manifests → F fixtures 7, 12 where listed |
| 18–21 | **A-fix** | Fixture 10 (+ 1) |
| 22 | **A-unit** | synthetic unknown git_sha → F fixture 15 |
| 23–24 | **A-fix** | Fixture 1 |
| 25 | **A-unit** | no reverse-lookup API |
| 26 | **Not-A** | Visual distinctness is Godot E/F. Plan A only proves three **export modes** via fixtures 1/4/5 (`test_export_modes_replay_trace_replay_only_trace_only`) — that test must **not** be named as Gate 26 |
| 27–29 | **Not-A** | Godot |
| 30 | **A-fix** | Committed bot request fixtures only — see §5.1 |
| 31 | **A-fix** legal modes via 1/4/5; **A-unit** malformed 22a/22b/23 | F fixtures 20, 22, 23 |
| 32 | **A-fix** | Fixture 4 nullability asserts |
| 33 | **A-unit** | synthetic disagree → F 21 |
| 34–35 | **A-unit** | `sparse_protocol.log`, `request_skip.log` → F 17, 18 |
| 36 | **A-fix** | Fixture 16 |
| 37 | **A-unit** | `trace_v1.jsonl` (+ optional log) → F 13 |

### 5.1 Gate 30 — committed request payloads

Pin these **existing** bot fixtures (read-only; do not modify):

| path | sha256 |
|---|---|
| `showdown_bot/tests/fixtures/request_doubles_moves.json` | `31594636317e9438c8c52b4b6f49a4bf48a3d8c71146f2aa3cc66a62a3e283ae` |
| `showdown_bot/tests/fixtures/request_team_preview.json` | `9cb835c3253fb13f08d8cfdbec991fdbb05cc1fe303a6848b6bd04d1e3014e57` |
| `showdown_bot/tests/fixtures/i7a_scovillain_can_mega_request.json` | `443be11f769bc03f72ba75846d81805e18d9bf6dd0f7fb7399679a4e0e667bfe` |

Test `test_request_hash_live_offline_recipes_byte_identical` in `test_a5_request_hash_recipes.py`:

1. Verify each file’s sha256 matches the table (fail if upstream bytes moved).
2. `BattleRequest.model_validate` each payload.
3. **Live recipe** (byte-copy of `decision_capture.request_payload` + `decision_capture._sha256`).
4. **Offline recipe** (byte-copy of `room_raw_replay` hash input:
   `_sha256(_canonical_json(req.model_dump(mode="json", by_alias=True, exclude_none=False)))`).
5. Assert the two hex digests are identical per fixture.

No Studio-invented request JSON may satisfy Gate 30.

---

## 6. Plan A fixtures

### 6.1 Immutability

`test_all_plan_a_sources_unchanged_after_export`: for every path in `SOURCES.md`, sha256 before ==
after any export attempt (success or refuse).

### 6.2 Fixture definitions (no choice points)

| Fix | Sources (all under `fixtures/viewer-v0/sources/` unless noted) | Expected bundle |
|---|---|---|
| **1** | `fixture-01/` — `synthetic-coherent-v1` per §0.4 / contract §14.1 (sentinels + joinable log/trace/results/manifests) | `bundles/fixture-01/` |
| **3** | `fixture-03/` — `synthetic-coherent-v1` with ≥1 row `fallback_reason` non-null; own sentinels (not smoke IDs) | `bundles/fixture-03/` |
| **4** | `fixture-04/` — replay-only slice of fixture-01 battle+results+manifests (same sha256 as fixture-01 for shared files, recorded in SOURCES.md); no decision_trace | `bundles/fixture-04/` |
| **5** | Trace-only from **smoke** decision_trace + smoke results/manifests (§0.4 hashes); no battle log; no join claimed | `bundles/fixture-05/` |
| **6** | Reader-refuse: copy `bundles/fixture-01/` → `sources/fixture-06/bundle/`, flip one byte in `decisions.jsonl` | validator input only |
| **10** | See §6.3 (structural `|request|` privacy log) | `bundles/fixture-10/` |
| **16** | Trace-only from smoke `decision_trace.jsonl` with `--battle-id 3e6a178b0900195e`; empty-candidate rows export clean | `bundles/fixture-16/` |

### 6.3 Fixture 10 — structural request privacy (binding)

`fixtures/viewer-v0/sources/fixture-10/battle.log` (and A3’s
`tests/python/synthetic/privacy_leak.log`, byte-identical) **must** contain, as distinct protocol
lines:

1. A chat line and a PM line with player display names.
2. `|player|` / join lines with display names and an avatar id.
3. At least one `|request|{...}` line whose JSON payload includes:
   - `side.name` set to a cleartext player display name (e.g. `LeakPlayerOne`);
   - at least one `side.pokemon[].ident` or nickname field carrying a cleartext nickname
     (e.g. `NickLeak`).
4. A `http://` replay URL substring and an absolute path `C:\Users\fixture\leak.log`.

Required tests in `test_a3_privacy.py` / `test_a8_fixtures.py`:

| Test | Asserts |
|---|---|
| `test_fixture10_request_payload_is_json_parsed` | exporter parses `|request|` JSON (not regex-only wipe) |
| `test_fixture10_request_side_name_pseudonymized` | bundle has no `LeakPlayerOne`; seat label `p1`/`p2` appears instead in normalized battle/decision DTOs derived from that request |
| `test_fixture10_request_nickname_stripped_or_pseudonymized` | bundle has no `NickLeak` |
| `test_fixture10_other_literals_absent` | chat/PM/URL/abs-path/avatar literals absent |
| `test_fixture10_source_unchanged` | source sha256 unchanged |

All Studio-authored source digests are **lock-on-commit** into `SOURCES.md` in Task A8 (same commit
as the bytes). Smoke paths use the frozen hashes in §0.4.

---

## 7. Tasks (full RED/GREEN)

Convention: cwd `showdownbot_studio/`. After A0: `python -m pip install -e ".[dev]"` from `python/`.

**RED validity rule:** a RED step counts only when pytest reports the **named expected failure
mode** below (failed assertion mentioning the missing symbol/path, or `ImportError` /
`ModuleNotFoundError` / `FileNotFoundError` / `AttributeError` as specified). A collection error
from a typo in the test file itself, or an unrelated `SyntaxError` in an edited file, is **not** a
valid RED — fix the test harness first, then re-run RED.

### Task A0 — Skeleton

**Files:** `python/pyproject.toml`, `python/src/showdownbot_studio_exporter/__init__.py`,
`tests/python/test_a0_skeleton.py`, `python/README.md`

- [ ] **RED**

```bash
python -m pytest tests/python/test_a0_skeleton.py::test_import_package -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'showdownbot_studio_exporter'`
(or pytest import-path equivalent containing that module name).

- [ ] **GREEN** — create package + pyproject; install editable; re-run → PASS
- [ ] **Commit** `chore(studio): scaffold showdownbot-studio-exporter package`

### Task A1 — JCS pin + vectors

**Files:** `canonicalize.py`, `test_a1_canonicalize.py`, all 18 vector files + `SHA256SUMS`,
`pyproject.toml` dependency `rfc8785==0.1.4`

- [ ] **RED** (tests written; production/vectors absent)

```bash
python -m pytest tests/python/test_a1_canonicalize.py::test_jcs_vectors_sha256sums -v
python -m pytest tests/python/test_a1_canonicalize.py::test_jcs_vector_arrays -v
python -m pytest tests/python/test_a1_canonicalize.py::test_jcs_vector_french -v
python -m pytest tests/python/test_a1_canonicalize.py::test_jcs_vector_structures -v
python -m pytest tests/python/test_a1_canonicalize.py::test_jcs_vector_unicode -v
python -m pytest tests/python/test_a1_canonicalize.py::test_jcs_vector_values -v
python -m pytest tests/python/test_a1_canonicalize.py::test_jcs_vector_weird -v
python -m pytest tests/python/test_a1_canonicalize.py::test_refuse_nan -v
python -m pytest tests/python/test_a1_canonicalize.py::test_refuse_infinity -v
```

Expected: `test_jcs_vectors_sha256sums` FAIL with `FileNotFoundError` for
`tests/python/jcs_vectors/SHA256SUMS` (or AssertionError listing missing vector paths).
Vector tests FAIL with `ImportError`/`AttributeError` for
`showdownbot_studio_exporter.canonicalize.dumps` (or `FileNotFoundError` for the named input JSON).
`test_refuse_nan` / `test_refuse_infinity` FAIL with `ImportError`/`AttributeError` for the refuse
helper.

- [ ] **GREEN** — vectors matching §0.3.1 (no network); wrapper; all nine commands PASS
- [ ] **Commit** `feat(studio): pin rfc8785 0.1.4 and JCS vectors`

### Task A2 — Hash / manifest skeleton

**Files:** `hashutil.py`, `validate_bundle.py` (partial), `export_bundle.py` (staging stub),
`test_a2_manifest_hash.py`

- [ ] **RED**

```bash
python -m pytest tests/python/test_a2_manifest_hash.py -v
```

Expected: FAIL with `ImportError`/`AttributeError` naming
`showdownbot_studio_exporter.hashutil` or `validate_bundle.validate_bundle_dir` (tests must import
those symbols at module level or in each test).

- [ ] **GREEN** — absent optional → `present:false`/`path:null`/`sha256:null`; undeclared file
  refuses; `files.*.sha256` over emitted bytes
- [ ] **Commit** `feat(studio): bundle file hash declarations`

### Task A3 — Privacy

**Files:** `privacy.py`, `test_a3_privacy.py`,
`tests/python/synthetic/privacy_leak.log` (§6.3 shape). A8 copies those **exact** bytes to
`fixtures/viewer-v0/sources/fixture-10/battle.log` (one shared sha256 in SOURCES.md).

- [ ] **RED**

```bash
python -m pytest tests/python/test_a3_privacy.py -v
```

Expected: FAIL with `ImportError`/`AttributeError` for
`showdownbot_studio_exporter.privacy` transform entrypoint, **or** (if import exists but is noop)
AssertionError from `test_fixture10_request_side_name_pseudonymized` mentioning `LeakPlayerOne`.

- [ ] **GREEN** — §6.3 tests all PASS; seat labels; no reversible map; source bytes unchanged
- [ ] **Commit** `feat(studio): portable-pseudonymous-v1 privacy transform`

### Task A4 — Decisions (v3, v2, v1, smoke integrity)

**Files:** `export_decisions.py`, `warnings_emit.py`, A4 test modules, synthetics `trace_v1.jsonl`,
`trace_v2.jsonl`

#### A4a v3

- [ ] **RED**

```bash
python -m pytest tests/python/test_a4_decisions_v3.py -v
```

Expected: FAIL with `ImportError`/`AttributeError` for
`showdownbot_studio_exporter.export_decisions.export_decisions_jsonl` (exact name used by tests).

- [ ] **GREEN** — v3 mapping, opaque `candidate_key`, empty candidates OK, aggregation null+warning,
  navigation fields, integrity refuses
- [ ] **Commit** `feat(studio): export decision-trace-v3 rows`

#### A4b v2

- [ ] **RED**

```bash
python -m pytest tests/python/test_a4_decisions_v2.py -v
```

Expected: FAIL with AssertionError/`ExportRefuse` for `decision-trace-v2` rows (v3-only path
rejects or drops v2) — message must mention `decision-trace-v2` or `unsupported` until v2 branch
exists. Not a bare ImportError from a missing test module.

- [ ] **GREEN** — v2→presentation; chosen integrity; nullability
- [ ] **Commit** `feat(studio): export decision-trace-v2 rows`

#### A4c v1 refuse

- [ ] **RED**

```bash
python -m pytest tests/python/test_a4_decisions_v1_refuse.py -v
```

Expected: FAIL with AssertionError that expected refuse reason `unsupported_trace_v1` was not
raised (v1 incorrectly accepted or wrong reason code).

- [ ] **GREEN** — reason `unsupported_trace_v1`; with log → replay-only still allowed
- [ ] **Commit** `feat(studio): refuse decision-trace-v1 for trace export`

#### A4d smoke-trace integrity (not Fixture 1)

- [ ] **RED**

```bash
python -m pytest tests/python/test_a4_smoke_trace_integrity.py -v
```

Expected: FAIL with AssertionError on chosen-key resolution / empty-candidate export against smoke
rows (exporter path incomplete), **after** successfully opening the smoke file whose sha256 matches
§0.4. FAIL due to wrong smoke path/hash is **not** a valid RED.

- [ ] **GREEN** — gates 10–12 on non-empty chosen rows; gate 36 empty candidates; **no**
  `--battle-log`; smoke file hash unchanged
- [ ] **Commit** `test(studio): smoke decision_trace integrity without synthetic replay join`

### Task A5 — Battle + join + Gate 30

**Files:** `export_battle.py`, `join.py`, `test_a5_battle_join.py`,
`test_a5_request_hash_recipes.py`, synthetics `sparse_protocol.log`, `request_skip.log`

- [ ] **RED**

```bash
python -m pytest tests/python/test_a5_battle_join.py -v
python -m pytest tests/python/test_a5_request_hash_recipes.py -v
```

Expected: `test_a5_battle_join.py` FAIL with `ImportError`/`AttributeError` for
`export_battle` / `join` entrypoints. `test_a5_request_hash_recipes.py` FAIL with AssertionError
that live vs offline digests differ **or** ImportError for the recipe helpers — after verifying
§5.1 fixture hashes match (hash mismatch = stop and fix paths, not RED).

- [ ] **GREEN** — sparse index; skip resend/wait; join/refuse/unjoinable; Gate 30 green
- [ ] **Commit** `feat(studio): battle export, join, and request_hash recipe pin`

### Task A6 — Provenance + modes

**Files:** `provenance.py`, `test_a6_provenance_modes.py`

- [ ] **RED**

```bash
python -m pytest tests/python/test_a6_provenance_modes.py -v
```

Expected: FAIL with `ImportError`/`AttributeError` for
`showdownbot_studio_exporter.provenance.resolve_provenance`.

- [ ] **GREEN** — §11.1.3 precedence/agreement; legal modes; unit refuses 22a/22b/23; dirty null
- [ ] **Commit** `feat(studio): provenance precedence and mode flags`

### Task A7 — CLI, validator, atomicity, pathsafety

**Files:** `cli.py`, `export_bundle.py`, `validate_bundle.py`, `pathsafety.py`,
`test_a7_*.py`, `test_source_immutability.py`

- [ ] **RED**

```bash
python -m pytest tests/python/test_a7_validate_bundle.py -v
python -m pytest tests/python/test_a7_cli.py -v
python -m pytest tests/python/test_a7_atomic_export.py -v
python -m pytest tests/python/test_a7_pathsafety.py -v
python -m pytest tests/python/test_source_immutability.py -v
```

Expected per file:

| Module | Expected RED |
|---|---|
| `test_a7_validate_bundle.py` | `ImportError`/`AttributeError` for `validate_bundle_dir` |
| `test_a7_cli.py` | `SystemExit` code ≠ 2 for refuse cases, or `ImportError` for `cli.main` |
| `test_a7_atomic_export.py` | AssertionError: `--out` exists after refuse **or** staging sibling left behind **or** missing `atomic_publish_unsupported` path |
| `test_a7_pathsafety.py` | AssertionError: protected-tree out was accepted |
| `test_source_immutability.py` | AssertionError: source sha256 changed (or ImportError for export entry) |

- [ ] **GREEN** — §4 CLI; §0.5 atomic directory rename only; §4.1 path counters; immutability
- [ ] **Commit** `feat(studio): CLI, atomic export, path guards`

### Task A8 — Freeze Plan A fixtures

**Files:** all `fixtures/viewer-v0/sources/fixture-{01,03,04,05,06,10,16}/`, matching
`bundles/...`, `SOURCES.md` (incl. `source_kind: synthetic-coherent-v1` + sentinels for 1/3),
`test_a8_fixtures.py`

- [ ] Materialize sources per §6.2–§6.3; fill every Studio sha256 in `SOURCES.md`
- [ ] **RED**

```bash
python -m pytest tests/python/test_a8_fixtures.py -v
```

Expected: FAIL with AssertionError on missing `bundles/fixture-01/` file digests (or
`FileNotFoundError` for that bundle path). Not a collection error.

- [ ] **GREEN** — two exports of fixture 1 → identical digests; fixtures 3–6/10/16 assertions PASS;
  SOURCES.md records `synthetic-coherent-v1` for fixtures 1 and 3; the following named tests PASS:

| Test | Asserts |
|---|---|
| `test_synthetic_fixture_reports_git_and_dirty_unknown` | Fixture-01 (and -03) bundle has `git_sha == "unknown"` and `source_provenance.dirty is null`; never `dirty: false` |
| `test_synthetic_sentinels_match_no_committed_eval_identity` | Sentinel `battle_id`, `run_id`, `config_hash`, `schedule_hash` for fixtures 1 and 3 do not appear as identity values anywhere under repo `data/eval/` (scan `*.jsonl` / `*.json` / `*.manifest.json`); `git_sha` sentinel is exactly `"unknown"` |

- [ ] **Commit** `test(studio): freeze viewer-v0 Plan A fixtures 1,3-6,10,16`

---

## 8. Acceptance

1. `python -m pip install -e ".[dev]"` (from `python/`) and `python -m pytest tests/python -q` green.
2. All **A-fix** and **A-unit** rows in §5 green; Gate 5 and Gate 26 **not** claimed.
3. Fixture 1 is `synthetic-coherent-v1` under contract §14.1 with §0.4 sentinels
   (`git_sha: "unknown"` → bundle `dirty: null`); smoke suite never pairs synthetic logs with smoke
   results; `test_synthetic_fixture_reports_git_and_dirty_unknown` and
   `test_synthetic_sentinels_match_no_committed_eval_identity` green.
4. JCS vectors match §0.3.1; no network in exporter/tests.
5. Atomic export: sibling staging + `os.replace` only; refuse/`atomic_publish_unsupported` leaves
   no `--out` and no staging sibling; no file-by-file publish path.
6. Path safety tests green (symlink tests skip only per §4.1).
7. Fixture 10 structural `|request|` privacy tests green (§6.3).
8. `SOURCES.md` complete; immutability green.
9. No writes under `showdown_bot/`, `data/eval/`, `config/eval/`, `reports/`.
10. Status → APPROVED only by user review.

---

## 9. Commits

| # | Task |
|---|---|
| 1 | A0 |
| 2 | A1 |
| 3 | A2 |
| 4 | A3 |
| 5–8 | A4a–A4d |
| 9 | A5 |
| 10 | A6 |
| 11 | A7 |
| 12 | A8 |

Each: `git diff --check` clean; targeted pytest green.

---

## 10. Handoff

- Plan B loads `fixtures/viewer-v0/bundles/fixture-01/`
- Plan F: fixtures 2, 7–9, 11–15, 17–23; Gate 5 OS matrix; symlink re-run if skipped; promote A-unit
  gates to catalogue fixtures
- Godot: Gates 14, 26 (visual), 27–29
