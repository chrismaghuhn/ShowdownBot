# Viewer v0 — Plan F Gate Coverage Audit

> **The status column below is STALE — do not pick work from it.** Added 2026-07-25.
>
> This audit was correct when written, at `main @ 5feaa7c`. `git merge-base` confirms that base is
> an **ancestor** of commit `1980174` — *"close gate-coverage gaps the Plan F audit verified"* —
> the commit whose entire purpose was to consume the MISSING list below. Reading it as current
> cost duplicate work twice on 2026-07-25 (PR #82 and PR #83).
>
> Current state, and the reason a refreshed table was deliberately **not** produced:
> [`viewer-v0-gate-coverage-recheck.md`](viewer-v0-gate-coverage-recheck.md).
>
> The **method** here was right and is reused by the recheck. Nothing below is rewritten: an
> evidence file that edits its own past measurements is worth less than one that shows where it
> stood.

**Task:** Plan F §4, task F1, first checkbox — "Verify the 'existing' cells in §3's gate table
against the actual 77 pytest tests (do not assume from names)."

**Method:** every test body under `tests/python/test_*.py` was read in full (not grepped for
names) and checked against bundle contract
[`viewer-v0-bundle-contract-design.md`](../../specs/viewer-v0-bundle-contract-design.md) §15's own
wording for each of the 37 numbered gates. Plan F §3's coverage table
([`2026-07-21-viewer-v0-f-e2e-acceptance.md`](../2026-07-21-viewer-v0-f-e2e-acceptance.md)) was
treated as a hypothesis to test, not a source of truth. Run against `main @ 5feaa7c` (this
worktree's actual base — see "Baseline count" below for why this differs from the plan's own
`a2ede11` citation).

## 0. Confirmed baseline (do not assume from the plan's §0.1 table)

The plan's §0.1 table claims "**77** test functions across **17** files," counted on `main @
a2ede11`, 2026-07-24. On this worktree's actual base, `main @ 5feaa7c`, the real count is:

- **18 files**, **80** `def test_*` function definitions, **82** pytest-collected test IDs (one
  parametrized function, `test_a5_request_hash_recipes.py::test_fixture_bytes_pinned`, expands 3
  parameter sets into 3 collected cases — `pytest --collect-only` confirms `82 tests collected`).

The gap is explained by two commits that landed on `main` **after** the plan's `a2ede11` baseline
was written, neither of which is Plan F's own work:

- `fix/studio-fixture-hash-integrity` (merged PR #70) added `tests/python/test_fixture_manifest_hash_guard.py`
  (3 test functions) — see §2 below, this is directly relevant to F1's own task list.
- The Plan E merge (PR #71) and the Plan F draft-approval merge (PR #72) also landed between
  `a2ede11` and `5feaa7c`.

**F1 must use 18 files / 80–82 tests as its working baseline, not the plan's stale 77/17.**

## 1. Gate-by-gate verified status

Status legend: **COVERED** = a specific test genuinely asserts the gate's exact requirement.
**PARTIAL** = a test touches the area but does not assert the full requirement (detailed per row).
**MISSING** = nothing asserts it (production code may still implement it correctly).

| # | §15 requirement (short) | Plan's claim | Verified status | Evidence |
|---|---|---|---|---|
| 1 | Two exports: same file list, identical SHA-256/file | existing | **COVERED** | `test_a8_fixtures.py::test_two_exports_fixture01_identical` — exports fixture-01 twice to independent tmp dirs, compares `{name: sha256}` dicts |
| 2 | Comparison uses file list/digest only, never dir/archive metadata | existing (folded into 1–5) | **PARTIAL** | Same test only ever computes `{name: sha256}` — never touches mtime/permissions, so it can't be fooled by metadata, but nothing stress-tests that claim (no test varies metadata and confirms irrelevance) |
| 3 | One-byte source mutation changes bundle digest | existing (folded into 1–5) | **MISSING** | No test mutates a source file and re-exports to confirm the resulting digest changes |
| 4 | No bundle file has absolute path/URL/username/hostname/wall-clock | existing (folded into 1–5) | **PARTIAL** | `test_a3_privacy.py::test_fixture10_other_literals_absent` checks one exported file (fixture-10's `battle.jsonl`) against one hardcoded absolute path and one URL literal — not comprehensive across bundle files/fixtures, no hostname or wall-clock check anywhere |
| 5 | Cross-directory/user/OS export byte-identical | existing (folded into 1–5) | **PARTIAL** | "Different directory" component covered by test #1 above (`tmp_path/"a"` vs `tmp_path/"b"`); different-user/different-OS is untestable in one CI run and not otherwise asserted |
| 6 | RFC 8785 JCS conformance vector suite | existing | **COVERED** | `test_a1_canonicalize.py` — 6 vector tests (`arrays`/`french`/`structures`/`unicode`/`values`/`weird`) plus `test_jcs_vectors_sha256sums` pinning the vector files themselves |
| 7 | Every JSONL file: exactly one trailing `\n`, no `\r` | existing (folded into "6–7 existing") | **MISSING** | No test inspects any emitted JSONL bytes for newline shape |
| 8 | Non-finite input fails export (fixture 11) | **new** (plan is honest here) | **PARTIAL** | `canonicalize.dumps()`'s own NaN/Infinity refusal is tested (`test_a1_canonicalize.py::test_refuse_nan` / `test_refuse_infinity`); `export_decisions_jsonl`'s `non_finite_value` checks on `decision_latency_ms`/`aggregate_score` (the actual export path fixture 11 targets) are implemented but untested. Not a discrepancy — the plan already marked this "new" |
| 9 | `candidate_key` round-trips byte-identically; exporter never re-serializes it | existing (folded into "…, 9 existing", citing `test_a1_canonicalize.py`) | **MISSING** | `test_a1_canonicalize.py` has no relation to `candidate_key` at all (it only tests the generic `dumps()` serializer against JCS vectors). No test anywhere compares a source row's `candidate_key` bytes to the output row's, or asserts non-reserialization |
| 10 | Non-null `chosen_candidate_key` on a non-empty candidate set resolves to exactly one candidate | existing (`test_a4_decisions_v3.py`) | **PARTIAL** | Only exercised *implicitly*: `_resolve_chosen()` in `export_decisions.py` would raise `chosen_integrity`/`ambiguous_chosen_candidate` on failure, and several tests successfully export real fixture-01/smoke data without it raising — but no test positively asserts a resolved value, and no test exercises the refuse path |
| 11 | `chosen_rank` equals the resolved candidate's `rank` | existing (folded with 10) | **PARTIAL** | Same implicit-only coverage; `chosen_rank_mismatch` (the refuse reason for this exact gate) is never referenced by any test |
| 12 | Resolved candidate agrees with `normalized_action` | existing (folded with 10) | **PARTIAL** | Enforced in `showdown_bot`'s `validate_trace_row` (called from `load_trace_rows`) and implicitly exercised whenever real fixture data loads without raising; no Studio-side test asserts the agreement directly or exercises a disagreement |
| 13 | Duplicate identity and duplicate candidate keys refuse (fixtures 9, 14) | **new** (fixtures 9/14 correctly flagged) | **MISSING** | `duplicate_decision_identity` and `duplicate_candidate_key` refuse reasons are implemented (`export_decisions.py`) but referenced by zero tests. Matches the plan's own "new" framing — not a discrepancy. **Note:** the contract's own gate 13 cites fixture 14 for "duplicate candidate keys," but §14's catalogue defines fixture 14 as *chosen-candidate desync* (`chosen_*` vs `normalized_action`, i.e. gate 12's subject) — an inconsistency in the contract itself, not resolved here (see §3) |
| 14 | Sorting the candidate table by any column never changes chosen row or `rank` | existing (folded into "10–14… existing") | **MISSING from pytest scope** | No Python code sorts the candidate table (it's a fixed JSONL emission); this is a Godot/UI concern. `godot/tests/decision/test_candidate_table_view.gd` and `test_decision_presenter.gd` exist and look topically relevant by name — but reading gdUnit test bodies is outside this pytest-scoped task, so this is not credited here (see §3, "could not resolve") |
| 15 | Unknown major refuses; unknown required capability refuses naming it | **new** (fixtures 7/12 correctly flagged) | **MISSING** | Consistent with the plan |
| 16 | Higher minor + known capabilities opens, preserves unknown optional fields | "likely existing in `test_a6_provenance_modes.py` — verify" | **MISSING — guess is wrong** | `test_a6_provenance_modes.py` was read in full (5 tests): none touch minor-version bumps or unknown-field preservation. No other file does either |
| 17 | Minor bump adding a required field is rejected by a schema test | "likely existing in `test_a6_provenance_modes.py` — verify" (same citation) | **MISSING — guess is wrong** | Same file, same finding as gate 16 |
| 18 | Privacy counterexample: bundle contains none of fixture-10's literal values, input unchanged | existing | **COVERED** | `test_a3_privacy.py` (6 tests) + `test_a8_fixtures.py::test_fixture10_bundle_has_no_leaks` + `test_synthetic_sentinels_match_no_committed_eval_identity` |
| 19 | Every exported file uses the same seat pseudonyms; no reversible map present | existing (folded into 18–21) | **PARTIAL** | Pseudonym correctness is checked for one field of one payload (`test_fixture10_request_side_name_pseudonymized`: `side.name` → `"p1"`); cross-file consistency and "no reversible map present" are asserted nowhere |
| 20 | No bundle field matches a credential-shaped key | existing (folded into 18–21) | **MISSING** | No test does credential-shaped-key pattern checking anywhere |
| 21 | No nickname, no `LogEvent.raw` in any bundle file | existing (folded into 18–21) | **PARTIAL** | Nickname absence checked for one literal in one file (`"NickLeak" not in battle_bytes`); the `LogEvent.raw` component has zero coverage anywhere |
| 22 | `git_sha == "unknown"` → `dirty: null` (fixture 15) | existing (`test_a8_fixtures.py::test_synthetic_fixture_reports_git_and_dirty_unknown`) | **COVERED — citation confirmed accurate** | That exact test (checks fixture-01 and fixture-03) plus an independent unit-level test, `test_a6_provenance_modes.py::test_unknown_git_sha_dirty_null` |
| 23 | `source_hashes` equal real source digests, never compared to `files.*.sha256` | "likely existing in `test_a6_provenance_modes.py`/`test_a2_manifest_hash.py` — verify" | **MISSING — guess is wrong** | Neither file asserts `source_hashes` against a recomputed real source digest, nor asserts non-comparison to `files.*.sha256`. `test_a6_provenance_modes.py`'s only `source_hashes` reference checks it's `None` in replay-only mode (gate 32's subject, not gate 23's) |
| 24 | `config-manifest.json`'s `config_hash` equals row `config_hash`; mismatch refuses | "likely existing… verify" (same citation) | **PARTIAL** | The refuse mechanism is implemented (`export_bundle.py:138–139`, reason `config_hash_mismatch`) and its positive path is exercised implicitly whenever fixture-01's real `results.config-manifest.json` is used in passing tests (`test_a8_fixtures.py`, `test_a7_cli.py`) — but zero tests exercise the mismatch/refuse path, and none positively assert the equality |
| 25 | Nothing derived from `config_hash`; a test asserts no reverse-lookup exists | "likely existing… verify" (same citation) | **MISSING — guess is wrong** | The string `"reverse"` appears nowhere under `tests/python/` |
| 26 | All 3 modes reachable and visually distinct | existing | **PARTIAL** | Reachability of all three modes is genuinely tested (`test_a6_provenance_modes.py::test_export_modes_replay_trace_replay_only_trace_only`, plus frozen fixture-04/05 checks); "visually distinct" is a Godot/UI rendering claim outside pytest's reach and untested here |
| 27 | Absent optional data renders "not recorded", never `0`/`false`/`[]` | existing (folded into "26 existing") | **MISSING from pytest scope** | UI-rendering text; Godot-side, not found anywhere under `tests/python/` |
| 28 | `aggregation.mode: null` visibly degraded without opening raw JSON | existing (folded into "26 existing") | **PARTIAL** | The data half is tested — `aggregation.mode is None` plus an attached warning (`test_a4_decisions_v3.py::test_v3_aggregation_null_with_warning`); the "visibly degraded… without raw JSON" UI half is untested in pytest |
| 29 | `suspected` not rendered at schema 1.0 | correctly flagged "Godot-side, folds into F3" | **MISSING from pytest scope** | Consistent with the plan — not a discrepancy |
| 30 | `request_hash` byte-identical live/offline recipes | existing | **COVERED** | `test_a5_request_hash_recipes.py::test_request_hash_live_offline_recipes_byte_identical` — asserts `live == offline == studio` on all 3 pinned real request fixtures |
| 31 | All 3 legal `required`/`present` combos exercised; both malformed directions (22a/22b) and optional-required (23) refuse | not explicitly classified in the plan's coverage cell (see §2) | **SPLIT — legal-combo half COVERED, malformed-refuse half MISSING** | Legal combos: `test_export_modes_replay_trace_replay_only_trace_only` + frozen fixture-04/05 tests. Malformed refuses: `validate_bundle.py:51` (`"required != present on mode keys"`) and `:116` (`"{key} must not be required"`) are implemented; zero tests exercise either path |
| 32 | Replay-only nullability matches §11.1.2 exactly (fixture 20) | **new** ("20 new") | **COVERED — discrepancy, plan is wrong** | `test_a6_provenance_modes.py::test_frozen_fixture04_replay_only_nullability` asserts all 3 of §11.1.2's replay-only-nullable fields (`trace_schema_version`, `source_hashes.decision_trace`, `source_provenance.our_side`) against the real, already-committed fixture-04 bundle — a complete match of the gate, just proved via fixture-04 rather than the not-yet-built fixture-20 |
| 33 | Provenance disagreement between two sources refuses (fixture 21) | **new** ("21 new") | **COVERED — discrepancy, plan is wrong** | `test_a6_provenance_modes.py::test_provenance_disagreement_refuses` + `::test_trace_rows_disagreeing_config_hash_refuses` + `test_a7_cli.py::test_cli_refuse_provenance_disagreement` — three tests directly assert `reason == "provenance_disagreement"` on mismatched `config_hash` |
| 34 | `protocol_index` sparse, strictly increasing, gaps land exactly on filtered lines (fixture 17) | **new** ("17 new") | **PARTIAL** | `test_a5_battle_join.py::test_sparse_protocol_index_gaps` proves indices are sorted and a strict subset of the raw log, but only against fixture-01's real log (not a purpose-built log mixing `\|player\|`/`\|j\|`/`\|t:\|`/chat); `sorted(x) == x` also doesn't rule out duplicates (not strictly monotonic by construction), and nothing asserts gaps land exactly on filtered-line types |
| 35 | `rqid` resends and `wait` requests produce no decision (fixture 18) | **new** ("18 new") | **PARTIAL, materially stronger than "new" implies — discrepancy** | `test_a5_battle_join.py::test_request_skip_rules` directly proves both skip rules at the `index_requests_from_log` level with 4 inline synthetic request lines (resend + wait both skipped, 2 of 4 survive) — the core assertion gate 35 requires is already proven, just not yet through the full export pipeline against a numbered fixture-18 bundle |
| 36 | Empty candidate set exports cleanly, `chosen_*: null`, not flagged degraded (fixture 16) | existing ("36 existing (fixture-16)") | **PARTIAL — citation is wrong, substance is covered elsewhere** | `test_a4_decisions_v3.py::test_v3_empty_candidates_team_preview_ok` (fixture-01 row 0) and `test_a4_smoke_trace_integrity.py::test_smoke_empty_candidate_rows_export_clean` (smoke corpus) both prove `candidates == []` and `chosen_candidate_key is None` — but **fixture-16 itself is never referenced by name in any pytest test** (confirmed by grep). `chosen_rank is None` and "not reported as degraded" are not explicitly asserted either |
| 37 | trace-v1 rejected with a precise reason; still yields a replay-only bundle when a room log exists (fixture 13) | **new** ("13 new") | **COVERED — discrepancy, plan is wrong** | `test_a4_decisions_v1_refuse.py::test_refuse_v1_trace_export` (asserts exact reason `"unsupported_trace_v1"`) + `::test_v1_with_log_replay_only` (proves a replay-only bundle is still produced from `battle_log` + `results` alone) |

**Tally: 8 COVERED / 15 PARTIAL / 14 MISSING** (out of 37).

## 2. Discrepancies against the plan's §3 table, most consequential first

1. **Gates 16 and 17 (versioning) — the plan's own flagged "verify" guess is confirmed wrong.**
   Both cite `test_a6_provenance_modes.py` as "likely existing." That file was read in full (5
   tests, all about `git_sha`/`dirty` and provenance-disagreement refuses) — it contains **no**
   minor-version-bump or unknown-required-field-rejection logic at all. Both gates are **MISSING**,
   not "likely existing." F1 must build real schema tests here from scratch.
2. **Gates 23 and 25 (source_hashes / no reverse-lookup) — same flagged "verify" guess, also
   wrong.** Neither `test_a6_provenance_modes.py` nor `test_a2_manifest_hash.py` asserts
   `source_hashes` against a recomputed real source digest, or asserts the absence of a
   `config_hash` reverse-lookup. Gate 25 in particular has zero trace anywhere in the test suite.
3. **Gate 32 (fixture 20, replay-only nullability) marked "new" — actually COVERED.**
   `test_a6_provenance_modes.py::test_frozen_fixture04_replay_only_nullability` already asserts
   all three §11.1.2 nullable fields against the real, committed fixture-04 bundle. This is exactly
   the "pytest extension over the existing fixture-04 export" the plan's own §1 fixture-20 row
   speculated might be enough — it already exists. **F1 should not build fixture 20's assertions
   from scratch; only the naming/redundancy question (same as fixture 15 vs. 1/3) needs resolving.**
4. **Gate 33 (fixture 21, provenance disagreement) marked "new" — actually COVERED**, by three
   separate tests with exact `reason == "provenance_disagreement"` assertions
   (`test_a6_provenance_modes.py` x2, `test_a7_cli.py` x1).
5. **Gate 37 (fixture 13, trace-v1 refuse + replay-only fallback) marked "new" — actually
   COVERED.** `test_a4_decisions_v1_refuse.py` already proves both halves of the gate: a precise
   refuse reason and a working replay-only fallback. The plan's own §1 fixture-13 row already
   half-acknowledged this ("pair with `test_a4_decisions_v1_refuse.py` — already exists") but §3's
   coverage cell still lists it flatly as "new."
6. **Gate 35 (fixture 18, rqid/wait skip rules) marked "new" — substantially already proven.**
   `test_a5_battle_join.py::test_request_skip_rules` directly exercises both skip conditions with
   an exact count assertion. Only the full-pipeline/fixture-catalogue wrapper is actually new work.
7. **Gate 9 (candidate_key round-trip) miscited.** The plan's "6–7, 9 existing" cell points at
   `test_a1_canonicalize.py`, which has no relation to `candidate_key` at all — it is pure JCS
   `dumps()` conformance testing. Gate 9 is genuinely **MISSING**.
8. **Gates 10–12 (chosen-key resolution, `chosen_rank`, `normalized_action` agreement)
   over-claimed as "existing."** The cited file, `test_a4_decisions_v3.py`, never asserts any of
   these three things directly — coverage is only implicit (the underlying validation would raise
   on real data if broken, and several tests happen to load real data without it raising). No test
   anywhere exercises the `chosen_rank_mismatch`, `chosen_integrity`, or
   `ambiguous_chosen_candidate` refuse paths.
9. **Gates 3 and 7, folded into blanket "1–5 existing" / "6–7 existing" claims, are MISSING.**
   Gate 3 (one-byte mutation changes the digest) and gate 7 (JSONL newline shape) have no
   dedicated assertion anywhere.
10. **Gate 36's citation is wrong** — "fixture-16" is never referenced by name in any pytest test —
    though the gate's substance is genuinely covered via fixture-01's row 0 and the smoke corpus.
11. **Gate 31 is not classified at all in the plan's own coverage cell** (its "what it proves"
    column mentions fixtures 22a/22b/23, but the coverage column never says existing or new for
    it). Verified split: the three legal-combination cases are covered, the two malformed-refuse
    invariants are not.
12. **Side-finding, outside the 37-gate table but directly relevant to F1's own task list:**
    F1's second task-list bullet ("Write `test_f1_fixture_integrity.py` per §3.1... Prove the
    fixture-integrity gate detects drift") describes building a gate that **already exists**,
    functionally identical, as `tests/python/test_fixture_manifest_hash_guard.py` — landed via the
    already-merged `fix/studio-fixture-hash-integrity` branch (PR #70, commit `fbdc69f`, now on
    `main`). It has the exact P1-1 fix (recursive glob, not a fixed-depth one), the exact
    minimum-manifest-count assertion (18: 11 unit + 6 bundles + 1 sources/fixture-06), and the
    exact P1-2 fix (a positive assertion that fixture-06 stays deliberately mismatched). **It is
    unconditionally blocking** (`assert not mismatches`), not advisory — which is a live
    contradiction of §0.11 Choice Point 2's recorded decision (G1/advisory). The plan's own
    Choice-Point-2 amendment already anticipated this exact scenario and imposed a binding
    re-check obligation on F1 ("re-check… whether `fix/studio-fixture-hash-integrity` has landed
    and blocking has become free before building the advisory shape") — confirmed: it has landed.
    F1 should point at this file rather than duplicate it, and the owner needs to decide whether
    the now-blocking gate is accepted as-is or needs to be relaxed to match G1.

## 3. What could not be resolved either way

- **Gate 13's own citation, in the contract itself, looks inconsistent.** §15 gate 13 cites
  "fixtures 9, 14" for "duplicate identity and duplicate candidate keys refuse," but §14's
  catalogue defines fixture 14 as *chosen-candidate desync* (`chosen_*` vs. `normalized_action`
  disagreement — the actual subject of gate 12, not gate 13). No fixture in the 23-row §14
  catalogue is described as "duplicate candidate keys within one row." This reads as an authoring
  inconsistency in the bundle-contract design doc itself, not something this audit can resolve
  without asking its author — flagged, not fixed.
- **Gate 14 (candidate-table sort stability)** has no Python surface to test (sorting is a Godot/UI
  concern). `godot/tests/decision/test_candidate_table_view.gd` and `test_decision_presenter.gd`
  exist and are topically named for this gate, but this task's scope was explicitly the pytest
  suite ("against the actual 77 pytest tests") — reading gdUnit test bodies to confirm or refute
  their coverage was not attempted, and crediting them from names alone would repeat exactly the
  mistake this audit exists to catch. Left as **MISSING from pytest scope**, status in gdUnit
  unverified.
- Gates 26–29's "visible/rendered" halves are, by nature, UI claims outside what any Python test
  can assert. The data-correctness halves were verified where present; the rendering halves are
  left unresolved here (consistent with the plan's own treatment of gate 29 as Godot-side/F3).

## 4. Pytest run result

```
cd showdownbot_studio
python -m pytest tests/python -q
```

Result: **5 failed, 75 passed, 2 skipped** (82 collected). The 2 skips are the Windows
symlink-privilege tests in `test_a7_pathsafety.py` (skip cleanly when the process lacks symlink
privilege). The 5 failures were inspected individually and confirmed to be exactly the four
pre-existing, out-of-scope categories named in the task brief — **nothing new**:

1. `test_a1_canonicalize.py::test_jcs_vectors_sha256sums` — CRLF drift in
   `tests/python/jcs_vectors/**` (not covered by `.gitattributes`).
2. `test_a3_privacy.py::test_privacy_leak_matches_fixture10_source` — CRLF drift in
   `tests/python/synthetic/privacy_leak.log` (`\r\n` vs. fixture-10's `\n`).
3. `test_a4_smoke_trace_integrity.py::test_smoke_trace_hash_pinned` — pinned hash for
   `data/eval/champions-panel-v0/smoke-i7a-mega/decision_trace.jsonl`, a file **outside**
   `showdownbot_studio/`.
4. `test_source_immutability.py::test_sources_md_hashes_match_committed_files` — SOURCES.md hash
   drift. **Broader than the task brief's "fixture-03/decision_trace.jsonl" framing**: the actual
   mismatch spans **12 files across 4 fixture directories** (`fixture-03`, `fixture-05`,
   `fixture-10`, `fixture-16` — `decision_trace.jsonl`, `results.jsonl`, `results.manifest.json`,
   `results.config-manifest.json`, `battle.log` as applicable per fixture). Same single root cause
   (`SOURCES.md` not resealed after a prior fixture regeneration), same "separately scoped, not
   Plan F's fix" status — just wider than the one-file description implied.
5. `test_source_immutability.py::test_all_plan_a_sources_unchanged_after_export` — same root cause
   as #4, a second test function tripped by the identical drift.

No other failures appeared. The failing-test-function count (5) matches the task brief exactly;
the underlying-drift scope (12 files, not 1) does not — noted so F1 doesn't under-scope the
eventual repair.

## 5. What this audit does NOT establish

- **COVERED means the assertion exists and is genuine — it does not mean the underlying production
  behaviour is bug-free.** No production code was modified or newly exercised beyond what running
  the existing suite does; this is a coverage audit, not a correctness re-verification of
  `showdownbot_studio_exporter` or `showdown_bot.eval.decision_capture`.
- It does not establish anything about the ~207 gdUnit4 tests under `godot/tests/` — that suite was
  not read here (out of this task's explicit scope) and no claim above should be read as covering
  it, including gate 14 and the "visually distinct"/"renders" halves of gates 26–29.
- A **PARTIAL** rating means real, passing coverage exists for part of a gate's wording — it is not
  a promise that the missing part is trivial to add; several PARTIALs above (gates 10–12, 19, 21)
  are missing their entire refuse/negative-path half, which is usually the harder test to write.
- This audit did not re-run gdUnit4, did not touch any fixture, and did not modify any production
  or test code — per the task's constraints, it is read-only plus this one new doc file.
