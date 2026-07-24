# Viewer v0 — Plan F: End-to-End Acceptance

**Status:** APPROVED — 2026-07-24 (Rev. 4). Owner closed all four §0.11 choice points and marked
this plan APPROVED. **Implementation is still NOT authorized** — approval satisfies index §7 step 1
only; the hard dependency in index §3.2 (Plans A–E green and merged) is **not yet satisfied**, and a
separate implementation go-ahead is still required. See Depends-on below and §0.10.
**Date:** 2026-07-21 · **Rev.:** 4 (2026-07-24 — owner closed all four §0.11 choice points and
approved the plan; implementation remains gated on Plans A–E per §0.10/§3.2; see §9)
**Depends on:** Plans A–E complete and green (implementation index §3.2). As of this expansion,
**A–D are merged on `main`; Plan E is APPROVED with only Task E1 merged** (`e757772`, state banner).
E2–E7 are in progress on an unmerged branch (`studio/plan-e-layout-shell`). **Plan F code cannot
start until all of E1–E7 are green and merged** — this draft may be reviewed and refined now, but
the hard dependency in index §3.2 is not yet satisfied.
**Unblocks:** Viewer v0 merge readiness review (separate user decision)

**Authority:** [`../specs/viewer-v0-bundle-contract-design.md`](../specs/viewer-v0-bundle-contract-design.md)
§14 / §14.1 / §15, [`../specs/viewer-v0-design.md`](../specs/viewer-v0-design.md) §9,
[`2026-07-21-viewer-v0-implementation-index.md`](2026-07-21-viewer-v0-implementation-index.md)
§3.3 (fixture split — binding) / §5 (cross-cutting rules) / §6 (non-goals) / §7 (approval gates),
[`2026-07-21-viewer-v0-e-diagnostics-a11y-layout.md`](2026-07-21-viewer-v0-e-diagnostics-a11y-layout.md)
(structural template for this expansion; also the E-surface Plan F decorates),
mockups README binding corrections.

> **For agentic workers:** APPROVED status alone does **not** authorize code. Plan F code starts
> only after (1) Plans A–E are green and merged (index §3.2 — **not yet true**, see Depends-on
> above), (2) this plan is APPROVED by the project owner — **done, 2026-07-24**, and (3) a separate
> implementation go-ahead. Condition (1) is the open one. Do not invent a second fixture catalogue,
> a second CI runner convention, or a second test-helper module — reuse the patterns cited in §0.1.

## Goal

Close the Phase 0 acceptance matrix: complete the fixture catalogue (bundle contract §14),
automated CI gates (pytest + headless gdUnit4 mapped to §15), a named and reproducible manual
evidence procedure, an honesty audit, and a documentation status bump — without authorizing
Phase 1+.

## Non-goals

- No live network tests
- No strength claims
- No public release license inventory (pre-release gate in license audit §6 — track separately)
- No bot-side producer changes for §16 open inputs
- No fix for the pre-existing gdUnit fail-fast default or the fixture hash drift documented in
  §0.6 — Plan F **gates** against this class of bug; the actual repair of the 5 already-drifted
  unit fixtures is separate, already-scoped work (see §0.6) and is not this plan's commit
- No re-implementation or re-verification of Plan E's own E2–E7 work — Plan F consumes Plan E's
  APPROVED contract as authority (§0.1) and only re-checks, at F4 closeout, that what Plan E's own
  text promised actually landed (§0.9)

---

## 0. Closed decisions / verified surface (binding)

### 0.1 Verified surface (do not invent) — path:line, verified 2026-07-24

Everything below was read from the real files in this worktree (`main` @ `a2ede11`) or produced by
directly running the pinned tooling, not assumed from prose. Cite before writing F-task code; if a
signature drifted, stop and amend this plan.

| Kind | Identifier | Path:lines / evidence |
|---|---|---|
| Fixture dirs (Plan A, present) | `sources/{01,03,04,05,06,10,16}`, `bundles/{01,03,04,05,10,16}` | `fixtures/viewer-v0/{sources,bundles}/` — directory listing, 2026-07-24 |
| Fixture dirs (Plan F, absent) | `2, 7–9, 11–15, 17–23` — none exist yet | same listing; confirms index §3.3 split is still open |
| Fixture provenance ledger | `SOURCES.md` — one entry per source dir + per bundle dir, sha256 per file | `fixtures/viewer-v0/SOURCES.md` |
| 104-candidate real row | `data/eval/champions-panel-v0/smoke-i7a-mega/decision_trace.jsonl` has 20 rows, candidate counts 0–104, **2 rows at exactly 104**, 2 rows at 0; **no companion battle log** in that directory | counted directly, 2026-07-24 (see §0.11 point 3) |
| Exporter surface | `export_bundle(out=, battle_log=, decision_trace=, results=, run_manifest=, config_manifest=)`, `validate_bundle_dir(path)` | `python/src/showdownbot_studio_exporter/export_bundle.py`, `validate_bundle.py`; usage pattern in `tests/python/test_a8_fixtures.py:32–38` |
| Exporter refuse reasons (sample, not exhaustive) | `ExportRefuse(reason, message)`; observed reasons include `unsupported_trace_version`, `unsupported_trace_v1`, `non_finite_value`, `duplicate_decision_identity`, `chosen_integrity`, `config_hash_mismatch`, `missing_mode_inputs`, `missing_provenance`, `our_side_mismatch`, `battle_id_mismatch`, `ambiguous_battle_id` | `errors.py:6–15`; grepped call sites across `export_decisions.py`, `join.py`, `provenance.py`, `validate_bundle.py` |
| pytest baseline | **77** test functions across **17** files | counted `tests/python/test_*.py`, 2026-07-24 |
| gdUnit baseline | **207** test functions across **20** files | counted `godot/tests/**/test_*.gd`, 2026-07-24 |
| Test helper pattern | `_fixture_path`, `_unit_fixture_path`, `_spawn_shell_ready`, `_await_shell_settled`, `_make_candidate` — **duplicated per suite file**, not a shared base class | e.g. `godot/tests/bundle/test_bundle_validator.gd:7–12`; same four/five functions re-defined in 13+ other suite files (grep) — Plan F must follow this repo convention, not invent a shared helper module |
| Bundle hash gate ordering | `BundleValidator.validate_dir()` computes sha256 of **every** `present` file and compares to the manifest's declared `sha256`, returning `hash_mismatch` **before** any decision-row parsing (duplicate-index, chosen-key, warning-shape checks all happen later) | `godot/src/bundle/bundle_validator.gd:216–227` |
| fixture-06 real path | `sources/fixture-06/bundle` (there is **no** `bundles/fixture-06` — it is a refuse fixture, never exported as a bundle) | `godot/tests/bundle/test_bundle_validator.gd:96` (`test_fixture06_hash_mismatch`), `godot/tests/workspace/test_app_shell_smoke.gd` (`test_fixture06_refuse_reason`) |
| Unit-test fixture set (distinct from the §14 catalogue) | 11 dirs under `godot/tests/fixtures/unit/`: `chosen-key-missing-invalid`, `refuse-duplicate-decision-index`, `refuse-duplicate-path`, `refuse-extra-files-key`, `refuse-jsonl-parse-error`, `refuse-malformed-warning`, `refuse-non-integral-decision-index`, `refuse-noncanonical-path`, `unknown-optional-preserved`, `unsupported-trace-downgrade`, `unsupported-trace-no-replay` | directory listing, 2026-07-24 |
| gdUnit CI runner fail-fast default | `GdUnitTestCIRunner` calls `_executor.fail_fast(true)` unconditionally when constructed; `disable_fail_fast()` exists and is wired to the `-c` CLI flag | `godot/addons/gdUnit4/src/core/runners/GdUnitTestCIRunner.gd:109, 194, 200, 348` |
| CI wrapper never disables fail-fast | `run_gdunit_headless.ps1` builds its arg list without `-c` | `godot/tools/run_gdunit_headless.ps1:44–49` |
| Godot 4.5.2 console CLI flags | `--path <dir>`, `--headless`, `--resolution <W>x<H>`, `-s`/`--script <script>` all confirmed present | `Godot_v4.5.2-stable_win64_console.exe --help`, run 2026-07-24 against the pinned binary |
| `DisplayServer` headless stub | `window_set_min_size(Vector2i(1280,720))` then `window_get_min_size()` returns `(0, 0)` under `--headless`; returns `(1280, 720)` in a real (non-headless) run | direct throwaway-script probe against the pinned engine, 2026-07-24 (§0.5) |
| `AppShell` (Task E1, merged) | `parse_cli_args`, `get_deep_link_refuse_reason`, `open_bundle_path`, `get_replay_workspace`, `get_decision_workspace`, `get_loaded_bundle`, `get_trace_trusted`, `get_replay_trusted`, `get_decision_count`, `get_refuse_reason`, `get_downgrade_warning_reasons`, `get_status_text`, `get_selected_decision_index` | `godot/src/workspace/app_shell.gd:31,63,67,72,76,84,100,106,112,118,124,134,138` |
| `StateBanner` / `StateBannerPresenter` (Task E1, merged) | banner mounted in `AppShell`, refreshed on load/refuse/selection change | `godot/src/diagnostics/state_banner.gd`, `state_banner_presenter.gd`; wired at `app_shell.gd:219–226` |
| CI coverage today | `.github/workflows/pytest.yml` runs three jobs, **all** `working-directory: showdown_bot`; **zero** jobs touch `showdownbot_studio/`, pytest or gdUnit | `.github/workflows/pytest.yml` (repo root) |
| Engine pin is Windows-only | `ENGINE_SHA256SUMS` lists exactly one editor `.exe`, one console `.exe`, one `.exe.zip`, all `win64` — no Linux or macOS entry | `godot/tools/ENGINE_SHA256SUMS` |

**E2–E7 surfaces are cited from Plan E, not independently re-verified here.** `WorkspaceLayout`,
`WorkspaceShortcuts`, `DiagnosticsDock`, `StudioMonoFont`, `ShortcutLabels` (Plan E §3/§4) do not
exist in this worktree (`main` @ `a2ede11`) — only Task E1 is merged. Plan F treats Plan E's own
§0.1/§3/§4 contract as authority per the delivery order in the implementation index, exactly as
Plan E treated Plan D's contract as authority without re-deriving it. **F4 must re-verify these
against the actually-merged code once E lands** (§0.9) — Plan E's own plan text is not evidence of
what shipped, only of what was promised.

### 0.2 Fixture ownership (binding, implementation index §3.3)

| Owner | Fixtures | Status here |
|---|---|---|
| Plan A (shipped) | 1, 3, 4, 5, 6, 10, 16 | present, provenance-logged in `SOURCES.md` |
| **Plan F (this plan)** | **2, 7–9, 11–15, 17–23** | none exist; §1 below is the completion matrix |

Plan F does not touch Plan A's fixtures except to read them as precedent for the synthetic-coherent
recipe (§14.1) and the `SOURCES.md` ledger format.

### 0.3 Cross-cutting rules inherited (index §5 — not restated, cited)

All ten rules in index §5 bind Plan F like every other plan. The ones most load-bearing for F's own
work: **fail closed** on unknown major / unknown required capability / hash mismatch / identity
conflict (rule 1) is what every refuse fixture in §1 must prove; **bounded rendering** (rule 7) is
what the 104-candidate fixture must prove, not merely assert; **offline only** (rule 8) bounds the
CI-platform choice point in §0.11; **TDD** (rule 9) governs every F1 task; **open design inputs stay
missing** (rule 10) governs F3's honesty audit.

### 0.4 Scope fence

**In:** authoring and proving fixtures 2, 7–9, 11–15, 17–23 against bundle-contract §14/§15; an F1
automated-gate suite (pytest + gdUnit) mapped to §15's 37 gates; a named, reproducible F2 visual
capture procedure plus the manual SR/DPI evidence templates; an F3 honesty audit; F4 docs closeout;
F5 merge-readiness packet.

**Out:** implementing any of Plan E's E2–E7 (that is Plan E's own plan and branch); fixing the
gdUnit fail-fast default (§0.6) or the `run_gdunit_headless.ps1` wrapper — Plan F documents and
gates against the failure class, a source-code fix is separate, already-scoped work (§0.6); fixing
the 5 already-drifted unit-test fixture hashes (§0.6) — same reasoning, already scoped elsewhere;
fixing the scale/density/App-Bar/hash-truncation gaps a parallel gap-analysis found in the Plan E
branch (§0.8) — Plan F **records** these as named, checkable acceptance rows, it does not implement
UI fixes; Live Spectator, Team Analyzer, full client, add-ons, external bots (explicit stop line,
§8); anything under `showdown_bot/`, `data/eval/`, `config/eval/`, `reports/`.

### 0.5 Headless testing has a structural blind spot (binding limitation)

**Verified by direct probe, 2026-07-24.** A throwaway `SceneTree` script that calls
`DisplayServer.window_set_min_size(Vector2i(1280, 720))` then reads
`DisplayServer.window_get_min_size()` back returns:

| Invocation | `window_get_min_size()` |
|---|---|
| `Godot_v4.5.2-stable_win64_console.exe --path <project> --headless -s res://<script>.gd` | `(0, 0)` |
| `Godot_v4.5.2-stable_win64_console.exe --path <project> -s res://<script>.gd` (no `--headless`) | `(1280, 720)` |

Under `--headless`, Godot's `DisplayServer` window geometry is stubbed — production code's own
`window_set_min_size` call has no observable effect through the headless API. This is **why**
`run_gdunit_headless.ps1` (which always passes `--headless`) structurally **cannot** verify Plan
E's own `test_min_window_set` claim (`Vector2i(1280, 720)`) end-to-end, no matter how the test is
written: it can only assert that `WorkspaceLayout` *called* the setter, never that the window
geometry actually took effect. **F2's manual/visual checks are load-bearing for exactly this
reason and cannot be replaced by writing more gdUnit tests** — document this as a named limitation
in the F2 evidence template (§4 F2 task), not as a gap to be closed by more automation.

### 0.6 Fixture-integrity gate — corrected finding, not the finding as briefed

**The premise "only one test fails visibly; why do the other four pass" does not hold.** It was
checked directly against the real code and two live gdUnit runs, and the true picture is worse
and more specific than that framing suggests.

**Step 1 — the hash drift itself, confirmed at the byte level.** A script comparing each
`godot/tests/fixtures/unit/*/manifest.json`'s declared `files.decision_trace.sha256` against the
actual sha256 of `decisions.jsonl` in the same directory found **5 of 11 mismatches**:
`chosen-key-missing-invalid`, `refuse-duplicate-decision-index`, `refuse-jsonl-parse-error`,
`refuse-non-integral-decision-index`, `unknown-optional-preserved`. Each mismatched value was then
compared against `git show HEAD:<path>` for the same file — **the working-tree bytes are
byte-identical to the committed git blob** (`.gitattributes` `eol=lf` is doing its job; this is
not a local checkout / CRLF artifact). The drift is real and committed.

**Step 2 — what actually happens when the suite runs, verified by running it twice.**
`BundleValidator.validate_dir()` checks the sha256 of **every** present file, `decision_trace`
included, **before** any decision-row-specific logic (§0.1) — so all five mismatched fixtures
necessarily hit `hash_mismatch` before reaching the code path their test names claim to exercise.
Running `godot/tests/bundle/test_bundle_validator.gd` (which references all five) with the
project's actual `run_gdunit_headless.ps1` invocation (no `-c`) produced:

```
Statistics: 14 test cases | 0 errors | 1 failures | 0 flaky | 2 skipped | 0 orphans | PASSED
Executed test cases : (12/14), 2 skipped
```

— against a file that declares **33** `func test_*`. The run silently stopped after the first
failure (`test_refuse_duplicate_decision_index`), never reaching 19 further tests, including the
other four fixture-hash-mismatch tests. Nothing in the console summary or the exit code flags this
as a truncated run; only the outer `<testsuites tests="33">` XML attribute disagreeing with the
number of `<testcase>` elements written reveals it.

Re-running with `-c` (disables fail-fast, §0.1) surfaced the real, previously-hidden picture:

| Test | Fixture | Real outcome (with `-c`) |
|---|---|---|
| `test_refuse_duplicate_decision_index` | `refuse-duplicate-decision-index` | **FAILS** — expects `duplicate_decision_index`, gets `hash_mismatch` |
| `test_refuse_jsonl_parse_error` | `refuse-jsonl-parse-error` | **FAILS** — expects `jsonl_parse_error`, gets `hash_mismatch` |
| `test_refuse_non_integral_decision_index` | `refuse-non-integral-decision-index` | **FAILS** — expects `malformed_integer`, gets `hash_mismatch` |
| `test_chosen_key_missing_marks_invalid` | `chosen-key-missing-invalid` | **CRASHES the whole process** — `SCRIPT ERROR: Invalid access to property or key 'decisions' on a base object of type 'Nil'`; the test asserts `result.ok` is true and then unconditionally reads `result.bundle.decisions` with no guard, so a (correct, hash-gate) `result.ok == false` makes `result.bundle` null and the test itself crashes rather than fails |
| `test_unknown_optional_preserved` | `unknown-optional-preserved` | **not reached** — the run aborted on the crash above before this test started; same unguarded `result.bundle.decisions[0]` pattern makes an identical crash likely, unconfirmed here |

None of the five "pass." Under the project's actual default invocation, four of the five are never
even attempted, which is the failure mode that made them look green. This is a second, independent
defect layered on top of the hash drift: **the CI harness's fail-fast default silently truncates a
suite after its first failure**, so a small number of visible failures gives no evidence about
what else in the same (or a later-queued) suite might be broken. `fail_fast(true)` is set once per
run at the executor (`GdUnitTestCIRunner.gd:109`), not per-suite, so this risk is not confined to
`test_bundle_validator.gd` — it was only *demonstrated* there, not scoped there.

**A related, separate note for the record.** An informal working file exists at
`C:/Users/chris/AppData/Local/Temp/claude/C--Users-chris-Documents-SHowdown-BOt/7f6cafed-1235-4764-8e1c-e4263547ea7b/scratchpad/bugfix-analysis-fixture-hash-drift.md`
covering the same hash-drift root cause (independently, before this expansion), scoped as a
separate later PR ("do the fix after E5/E6/E7 + PRs"), not an approved plan artifact and not
binding on Plan F — but its sequencing intent (fix after E lands, own PR) directly shapes the
choice point below.

**What F1 must gate (binding requirement, shape only — implementation is F1's job, not this
plan's).** A single check that walks **every** fixture manifest under both
`fixtures/viewer-v0/{sources,bundles}/**/manifest.json` (the §14 catalogue Plan F owns) and
`godot/tests/fixtures/unit/*/manifest.json` (the pre-existing gdUnit-only fixture set), and for
every entry with `present: true`, asserts declared `sha256` equals the actual sha256 of the file
at `path`. One guard covering all fixtures, not per-fixture whack-a-mole (same shape as the
informal note above independently proposed). **Whether this gate is blocking or advisory on Plan F
landing is Choice Point 2 (§0.11, CLOSED: G1/advisory — with a binding F1 re-check obligation, see
the amendment there)** — the 5 already-drifted unit fixtures are not part of
Plan F's own fixture ownership (§0.2) and their repair is explicitly out of scope here (§0.4), so a
naively blocking gate would fail on day one against fixtures Plan F does not own.

**Also binding for F1 regardless of the choice point above:** the CI script must not silently
truncate. At minimum it must run with fail-fast disabled (the `-c` flag demonstrated above) or
otherwise assert, per suite, that executed-plus-skipped test count equals the suite's declared
test count — so a truncated run fails closed instead of reporting a misleadingly small green
summary. This is not a trade-off with a legitimate other side; it is not a choice point.

### 0.7 Visual-capture procedure (binding recipe)

**Verified against the pinned engine, 2026-07-24** (`--help` output confirms `--resolution`,
`-s`/`--script`, `--headless`, `--path` are real flags on
`Godot_v4.5.2-stable_win64_console.exe`). F2 replaces "manual desktop checklist" prose with this
named, reproducible procedure:

1. Write a throwaway `SceneTree`/scene-boot script under a scratch path (never committed) that
   loads `res://src/workspace/app_shell.tscn`, drives `AppShell.open_bundle_path(<fixture>)`,
   waits for settle (Plan E §5 "settled ≠ loaded" rule — assert a positive load signal, not just
   `is_loading() == false`), then calls
   `get_root().get_texture().get_image().save_png(<out_path>)`.
2. Invoke it **without** `--headless` (headless stubs window geometry — §0.5 — so a headless
   capture would not be evidence of anything reachability-related):
   ```
   Godot_v4.5.2-stable_win64_console.exe --path <project> -s res://<script>.gd \
     --resolution 1280x720 -- --out=<png>
   ```
   `--` separates engine flags from user args, read via `OS.get_cmdline_user_args()` — the same
   convention `AppShell.parse_cli_args` already uses (`app_shell.gd:31–34`).
3. Save the PNG under `docs/plans/evidence/` alongside the manual checklist (§4 F2 task), named
   `<fixture>-<WxH>-<date>.png`.
4. Record window size, fixture id, and git commit of the build under test in the same evidence
   file — comparable run-to-run, not a one-off screenshot.

**Honesty boundary (binding):** a captured frame is evidence of **layout only** — control
placement, text overflow, visible chrome. It is **not** evidence of screen-reader behavior,
keyboard focus order, or mixed-DPI conformance (Plan E §0.10's "best effort, not automated" framing
applies identically here). F2's acceptance rows must not conflate "I have a screenshot" with "this
passes."

### 0.8 1280×720 primary-control reachability — named, unresolved acceptance row

A parallel structural gap analysis (`.../scratchpad/gap-analysis-render-vs-dossier.md`, comparing
two real captures — 1400×900 and the spec-mandated minimum 1280×720 — of the `AppShell` UI on the
in-flight `studio/plan-e-layout-shell` branch, tip `0cd93f2`) found the timeline transport row
(Prev/Next/Start/End/Play) and the lower provenance rows **unreachable at 1280×720** — the exact
control set Plan E §0.7 requires to "remain reachable." This worktree does not have that branch
checked out, so it is cited, not independently re-run, here. A fix is reported in flight on that
branch. **Plan F must not describe this as fixed.** F2's task list (§4) and the program acceptance
table (§5) both carry it as an explicit, checkable row: *"primary controls reachable at 1280×720,
evidenced by a captured frame per §0.7"* — pass/fail decided by a fresh capture against whatever
Plan E ships, not assumed from this note.

The same gap-analysis file also found, on that branch: UI scale (75–200%) and density
(Compact/Comfortable) setters exist but nothing reads them (no visible effect, no reachable
control, no keyboard shortcut) and long hash values in the provenance panel overflow with no
truncation/tooltip/copy affordance (violating Plan E §0.8's own binding truncation rule). These are
Plan E's own release-gate claims (§9.2 of the design spec), not Plan F's to fix — but F2/F3 must
not paper over them. **F2's scale/density checklist rows should read "not yet wireable" rather than
infer a pass from the app looking identical at every setting**, and **F3's honesty audit should
explicitly separate "the underlying data is honest" from "the control to reach this state doesn't
exist yet"** so the latter is not mistaken for a data-honesty defect during audit — both gaps are
functional-completeness gaps in Plan E's own scope, tracked there, not silently absorbed into F3's
verdict.

### 0.9 Plan E deferred-work verification for F4 (binding closeout step)

Plan E's own task breakdown deferred work across task boundaries, discovered mid-run rather than
planned:

| Deferred from | Deferred to | What | Evidence |
|---|---|---|---|
| E2 (diagnostics dock) | E6 (offline fonts) | `StudioMonoFont.apply_to()` on provenance hash/value controls and the raw `TextEdit` (Plan E §4.6, §5.3 `test_hash_surfaces_use_monospace`) | code comment cited by the gap analysis at `diagnostics_dock.gd:9–11`: *"value/text controls below intentionally do NOT call `StudioMonoFont.apply_to()` yet — that helper and its RED/GREEN cycle are Task E6..., not this task"* |
| E3 (scale/density) / E4 (shortcuts) | E5 (layout shell) | `WorkspaceLayout.reset_to_safe()`, `WorkspaceLayout.focus_diagnostics()` — both are in Plan E §4.3's `WorkspaceLayout` contract and both are bound by name in Plan E §0.6's keyboard-action table (E4), but Plan E's own §6 task list places their **implementation** under Task E5, not E3/E4 | Plan E §4.3 (API on `WorkspaceLayout`) cross-referenced against §6 Task E3/E4/E5 scope lines |

**F4 must not assume these landed because Plan E's plan text says they will.** Before flipping
Plan E's status note or writing the F5 merge-readiness packet, F4 re-reads the actually-merged
source (once E is fully on `main`) and confirms: `StudioMonoFont` exists and
`diagnostics_dock.gd`'s hash/value controls call it (the deferral comment is gone); `reset_to_safe`
and `focus_diagnostics` exist on `WorkspaceLayout` and are invoked from `WorkspaceShortcuts`. This
is a read, not a re-implementation — if either is still missing, that is Plan E's own regression
task (E7) failing to close its own deferral, not something F4 fixes.

### 0.10 Implementation gate

This Rev. 1 is **DRAFT**. Code still starts only after: (1) Plans A–E are green and merged (index
§3.2 — currently **not** satisfied, only E1 of E1–E7 is on `main`), (2) this plan's status →
**APPROVED** in a docs-only commit by the project owner, (3) a separate implementation go-ahead.
Approve-commit precedes code, same sequencing Plan E bound on itself (Plan E header).

### 0.11 Choice points — CLOSED (owner, 2026-07-24)

All four choice points below are now closed by owner decision, 2026-07-24. Option tables and
trade-offs are retained as protocol — closing a choice point is not deleting the record of what
was weighed, and it is **not** the same act as approving this plan (§0.10/§7 — this document's
`Status:` line stays **DRAFT**, unchanged by this section). Each point now carries a **Decision** /
**Rationale** / **Status** block after its option table, following the pattern
[Plan E §0.13](2026-07-21-viewer-v0-e-diagnostics-a11y-layout.md#0-13) established for closed
choice points.

#### Choice Point 1 — CI platform/runner scope

**Grounding (revised, item 8 review):** the repo owner has decided Studio's target platforms
(§0.12): **Windows is the target, Linux is out, macOS is possible later.** This choice point is
about CI *runner* scope, not about which platform the product supports — that question is no
longer open (§0.12) and does not by itself resolve this one. The previous grounding here reasoned
from the shape of today's CI — `.github/workflows/pytest.yml` runs three jobs, two `ubuntu-latest`
-only and one matrixed `[ubuntu-latest, windows-latest]`, **none** touching `showdownbot_studio/` —
that is a fact about the pre-existing `showdown_bot` lanes, predating the platform decision, and is
not itself an argument for or against a Studio-side Windows lane. The pinned Godot engine
(`ENGINE_SHA256SUMS`) has **Windows-only** artifacts, consistent with the platform decision.

| Option | Shape | Consequence |
|---|---|---|
| K1 | Add a `windows-latest` GH Actions job that downloads the pinned zip, verifies it against `ENGINE_SHA256SUMS`, then runs pytest + gdUnit as one job (mirroring the existing per-track job convention, e.g. `champions-mega`) | Real CI coverage of the Godot side, on the platform that is now the actual target (§0.12) — but see the two costs below; neither is free |
| K2 | Ship only a `showdownbot_studio` **pytest** job now (platform-agnostic, pure Python, same shape as the existing `showdown_bot` jobs); keep gdUnit as a documented local pre-merge command a developer runs on Windows before requesting review | Ships real CI today with zero new infrastructure and zero new runner cost; gdUnit — the half of the suite that actually exercises the target platform — stays un-gated in CI until someone stands up K1 |
| K3 | Pin a Linux headless Godot export template in addition to the Windows console exe, run both in CI | **Deprioritized by §0.12** — Linux is not a target platform, so K3 would add and maintain a second engine pin for a platform the product does not ship on; kept here for completeness, not a live contender |

**Two honest costs of K1, for the owner to weigh (these do not change the platform decision; they
bear on whether standing up a Windows CI lane is worth it now):**

- The pinned engine is **not committed** — `showdownbot_studio/godot/.gitignore` excludes
  `/Godot_*.exe`, `/Godot_*.exe.zip`, `/tools/engine/`, `/tools/engine_cache/`; it is installed via
  `install_engine.ps1` against `ENGINE_SHA256SUMS` (§0.1, verified present). A CI job must download
  and verify it every run unless a cache step is added — cacheable, but not free on a first run or
  a cache miss.
- GitHub Actions bills **Windows runner minutes at roughly double** the Linux rate. On a free-tier
  budget (per memory: solo dev) this is a real recurring cost that scales with how often the job
  runs (every push vs. every PR vs. nightly), not a one-time setup tax.

**Recommendation:** K2 now, K1 as the natural next step once someone wants gdUnit gated in CI. This
recommendation is **unchanged** by the platform decision itself: Windows being the real target
makes K1 more *valuable* once it lands, it does not make it cheaper to stand up today — the two
costs above are the owner's to weigh against that value, not new information that flips the
recommendation on its own. This revision corrects the reasoning behind the K2 recommendation, not
the choice itself; the owner has deferred the choice to Plan F review.

| | |
|---|---|
| **Decision** | **K1 — Windows CI lane.** Add a `windows-latest` GH Actions job that downloads the pinned engine zip, verifies it against `ENGINE_SHA256SUMS`, then runs pytest + gdUnit as one job (mirroring the existing per-track job convention). |
| **Rationale** | Grounded in the §0.12 platform decision — Windows is the actual target (Linux out, macOS possible later) — not in the shape of today's ubuntu-only `showdown_bot` workflow, which predates that decision and is not itself an argument either way. This closes the choice **against** this plan's own K2 recommendation: the owner weighed the two named costs (engine not committed → download+verify every run; Windows runner minutes billed at roughly double) against the value of real CI coverage on the actual target platform and chose K1 anyway. Both costs stand, accepted, not waived. |
| **Scope note (binding)** | Wiring `showdownbot_studio/` into `.github/workflows/` is itself an F1 implementation step — it is still gated by this plan's `Status:` line staying **DRAFT** (§0.10) and by Plans A–E being green and merged (index §3.2). Closing this choice point authorizes what F1 will build, not building it now. |
| **Status** | **CLOSED (owner, 2026-07-24).** |

#### Choice Point 2 — Fixture-integrity gate: blocking or advisory

**Grounding:** §0.6. The gate Plan F proposes would, if blocking from day one, fail against 5
already-drifted `godot/tests/fixtures/unit/` fixtures that predate Plan F and are outside Plan F's
own fixture ownership (§0.2) — their repair is explicitly out of scope here (§0.4) and separately
noted as deferred work ("fix after E5/E6/E7 + PRs" per the informal note in §0.6).

| Option | Shape | Consequence |
|---|---|---|
| G1 | Advisory only (reports mismatches, does not fail CI) until the separate fix PR lands, then flip to blocking in a follow-up commit | Never blocks Plan F's own closeout on someone else's deferred fix; risks the gate being ignored as noise in the interim |
| G2 | Blocking immediately | Forces the unit-fixture hash fix to become a prerequisite of Plan F landing, contradicting the already-stated sequencing ("fix after E ... + PRs") |
| G3 | Blocking for the **new** catalogue fixtures Plan F authors (2, 7–9, 11–15, 17–23) from day one; advisory for the pre-existing `godot/tests/fixtures/unit/` set until the separate fix lands, then flip that half to blocking too | New fixtures never rot silently even before the old ones are cleaned up; two-speed gate is slightly more code than a single flag |

**Recommendation:** G3 — it protects everything Plan F actually authors immediately, without
making Plan F's closeout depend on a fix explicitly scheduled for later by someone else.

| | |
|---|---|
| **Decision** | **G1 — advisory only** (reports mismatches, does not fail CI), against this plan's own G3 recommendation. |
| **Rationale** | The owner chose the simpler G1 shape over the recommended two-speed G3. |
| **Amendment — premise change (binding, must be re-checked at F1)** | Choice Point 2's grounding was that a *blocking* gate would fail immediately and permanently against the 5 pre-existing drifted `godot/tests/fixtures/unit/` fixtures (§0.6). **That premise is being removed concurrently with this decision:** a separate, independent branch `fix/studio-fixture-hash-integrity` (off `main`, **not merged**, **not part of Plan F**) reseals those 5 manifests, null-guards the two crashing tests identified in §0.6, and stops `run_gdunit_headless.ps1` truncating on first failure. The decision recorded here is advisory, exactly as the owner chose — but **the reason for choosing advisory may no longer hold by the time F1 is implemented**. F1 (§3.1, §4) must therefore re-check, at implementation time, whether `fix/studio-fixture-hash-integrity` has landed and blocking has become free before building the advisory shape sketched in §3.1. This is **not** a silent upgrade to blocking — that stays the owner's call — it is a re-check obligation on F1, not a new decision made here. |
| **Status** | **CLOSED (owner, 2026-07-24).** |

#### Choice Point 3 — 104-candidate bounded-render fixture: derive or author fresh

**Grounding:** bundle contract §14's own default rule prefers derivation from committed producer
evidence. `data/eval/champions-panel-v0/smoke-i7a-mega/decision_trace.jsonl` was counted directly
(§0.1): 20 rows, candidate counts 0–104, **2 rows already at exactly 104**, 2 at 0 — but that
directory has **no** companion battle log, so a derived fixture from it can only be `TRACE_ONLY`
(fixture-05/16's precedent in `SOURCES.md`), not a replay+trace pairing.

| Option | Shape | Consequence |
|---|---|---|
| L1 | Derive `TRACE_ONLY` from the real 104-candidate row already in the committed corpus, following the `fixture-05`/`fixture-16` `SOURCES.md` pattern exactly | No synthetic-coherent labeling needed (§14.1 exception not invoked); proves bounded rendering against a real producer row, which is the stronger claim; loses the ability to exercise replay+trace-mode bounded rendering together |
| L2 | Author a synthetic-coherent fixture (§14.1 Amendment A) with a fabricated 104-candidate replay+trace pair | Full control over the exact row shape; requires all five §14.1 conditions (labeling, internal coherence, no false producer claim, `git_sha:"unknown"`, privacy) that fixture-01/03 already had to satisfy — more work for a proof that a real row already provides more cheaply |

**Recommendation:** L1 — the real row already exists and is committed; inventing a synthetic one
when a real one covers the claim is exactly the kind of unrequested extra work the fixture-01/03
synthetic exception was never meant to normalize.

| | |
|---|---|
| **Decision** | **L1 — derive.** `TRACE_ONLY` from the real committed 104-candidate row in `smoke-i7a-mega/decision_trace.jsonl` (§0.1), following the `fixture-05`/`fixture-16` `SOURCES.md` pattern exactly. |
| **Rationale** | Derived-from-committed-evidence beats fabricated, and this repo has direct same-session evidence for it: every one of the 5 fixtures that drifted (§0.6) was **hand-authored** (`godot/tests/fixtures/unit/`), while every exporter-produced catalogue fixture under `fixtures/viewer-v0/bundles/` was correct. Hand-made fixtures rot; derived ones don't. L2 would also invoke the §14.1 synthetic-coherent exception permanently for a claim a real row already proves more cheaply — a burden every future maintainer then has to understand. |
| **Known gap (accepted by owner, not silently absorbed)** | The `smoke-i7a-mega` corpus directory has **no companion battle log** (§0.1), so a fixture derived from it can only be `TRACE_ONLY` — never a replay+trace pairing. **Bounded rendering is therefore never exercised together with active replay mode by this fixture.** A defect that only manifests with board + timeline + a live 104-row candidate table simultaneously would not be caught here. Also recorded in §1's fixture matrix and §5's acceptance table so it stays visible at implementation and closeout time, not buried in this choice point alone. |
| **Status** | **CLOSED (owner, 2026-07-24).** |

#### Choice Point 4 — How much manual evidence is required before "green"

**Grounding:** Plan E §0.10 frames screen-reader as "best effort," never a hard gate; Plan E's own
§1 non-goals list "screen-reader completeness as a hard release gate" explicitly. Mixed-DPI is a
"manual Windows checklist," also not an automated gate.

| Option | Shape | Consequence |
|---|---|---|
| J1 | F5's merge-readiness packet requires the SR smoke-note and DPI checklist to be **filed** (attempted, non-empty, honest about failures) but not required to fully pass | Matches Plan E's own non-goal; a real attempt is recorded even if imperfect |
| J2 | J1, plus an explicit owner sign-off checkbox in the F5 packet before merge | Adds an explicit human gate on top of "filed"; more process for a solo-developer project (per memory: solo dev) |

**Recommendation:** J1 — Plan F cannot retroactively turn Plan E's own stated non-goal into a hard
gate; J2's sign-off is a low-cost addition the owner can add unilaterally at review time without
needing to be baked into this plan.

| | |
|---|---|
| **Decision** | **J2 — filed, plus explicit owner sign-off.** Every manual check (screen-reader smoke note, mixed-DPI checklist) must be **filed**: attempted, non-empty, and honest about failures — plus an explicit owner sign-off checkbox in F5's merge-readiness packet (§4 F5) before merge, against the plan's own J1 recommendation. |
| **Rationale** | The owner added the sign-off gate J1 called optional; the cost (one checkbox, solo-developer project) is low against the value of an explicit human checkpoint before merge. |
| **Binding constraint (must be unambiguous — state with this closure)** | **J2 means everything is *filed and signed off*, NOT that everything must *pass*.** Plan E §1 lists "screen-reader completeness as a hard release gate" as an explicit non-goal, and Plan E §0.10 frames screen-reader evidence as best-effort, never claiming completeness. A partially-failing screen-reader result is therefore an **honest recorded outcome**, not a release blocker. The F5 sign-off attests that the evidence was **produced and reviewed** — it never attests that it all **passed**. No later reader of this plan, F5's packet, or the sign-off checkbox itself may treat J2 as "SR must pass"; F5's task list (§4) and the acceptance table (§5) must phrase the sign-off requirement accordingly. |
| **Status** | **CLOSED (owner, 2026-07-24).** |

### 0.12 Target platform (binding, owner decision — 2026-07-24, item 8 review)

The repo owner has decided Studio's target platforms: **Windows is the target platform. Linux is
out. macOS is possible later.** This supersedes any reasoning in this plan that argued from the
shape of today's CI rather than from the product's actual target — in particular Choice Point 1
(§0.11), which is about CI *runner* scope, not about which platform is in scope; that reasoning has
been rewritten above to reflect this decision. Choice Point 1 itself was **OPEN** at the time this
section was first written and is now **CLOSED (owner, 2026-07-24) — K1, see §0.11**.

Two things this decision does **not** do:

- It does not retroactively delete work already aimed at "macOS possible later." Plan E's own
  `ShortcutLabels.mod_key()` (Plan E §4, cited per §0.1 — not yet merged code, only Plan E's own
  plan text at this point) returns `"Cmd"` on macOS and `"Ctrl"` elsewhere. That branch **retains
  its purpose** under this decision and is not dead code to be pruned by F3 or anyone else.
- It does not resolve Choice Point 1 on its own — K1/K2/K3 (§0.11) stayed open until the owner
  closed the choice separately (§0.11, K1, 2026-07-24); this section only fixes what the choice
  point's reasoning is grounded in, not the choice.

**Binding on F3 (§4):** the honesty audit must not let UI copy, docs, or CI job naming imply Linux
support that does not exist anywhere in this repo.

---

## 1. Fixture completion matrix

Each row is a fixture Plan F owns (§0.2). "Must prove" is bundle contract §14's own text, not
paraphrased. "Status" and "recipe" are Plan F's job to execute once approved.

| # | Fixture | Must prove (§14) | Status | Recipe |
|---|---|---|---|---|
| 2 | close decision (margin) | `top1_top2_margin` small and correct; no threshold implied; margin `null` when fewer than two candidates | absent | derive from a real multi-candidate decision row with a small measured margin, or construct if none exists with a small-enough gap |
| 7 | unsupported major | `viewer_bundle_schema.major` above the supported set; refuse; supported majors listed | absent | mutate a copy of an existing bundle's `manifest.json` `viewer_bundle_schema.major`; same recipe shape as fixture-06's byte mutation |
| 8 | missing mandatory file | `required: true` file declared `present: true` but absent on disk; refuse | absent | copy a bundle, delete one required file, leave its manifest entry unchanged (`present: true`) |
| 9 | duplicate decision identity | two rows with the same `(battle_id, decision_index, our_side)`; refuse | absent | same shape as `godot/tests/fixtures/unit/refuse-duplicate-decision-index` **but with a correct, recomputed manifest hash** — do not repeat the §0.6 drift in a fresh fixture |
| 11 | non-finite value | a source row with `NaN`/`Infinity`; export refuses | absent | exporter-side pytest fixture; export must raise `ExportRefuse("non_finite_value", ...)` (§0.1) |
| 12 | unknown required capability | `required_capabilities: ["belief_v2"]`; refuse; name it | absent | mutate a manifest's `required_capabilities` list |
| 13 | legacy trace-v1 → refuse trace / replay-only | no validated `candidate_key`; trace export rejected with a precise reason; replay-only bundle still produced when a room log exists; Godot holds no migration logic | absent | pair with `test_a4_decisions_v1_refuse.py` (already exists, exporter-side) — extend to the fixture catalogue, not a new mechanism |
| 14 | chosen-candidate desync | `chosen_*` disagreeing with `normalized_action`; export refuses | absent | mutate a source row's `chosen_candidate_key` away from what `normalized_action` implies |
| 15 | `git_sha == "unknown"` | `dirty` is `null`, never `false`; viewer shows `dirty state not recorded` | absent | fixture-01/03 already exercise the exporter half of this (`test_synthetic_fixture_reports_git_and_dirty_unknown`, §0.1) — fixture 15 needs its own catalogue-numbered dir per §14's list, or an explicit note that 1/3 already satisfy it and 15 is redundant (flag for owner at F1, don't silently skip) |
| 17 | filtered protocol lines / sparse index | log with `\|player\|`, `\|j\|`, `\|t:\|`, chat; `protocol_index` sparse and strictly increasing; gaps land exactly on filtered lines | absent | construct a battle log with those line types interleaved with real request/event lines |
| 18 | `\|request\|` skip rules | `rqid` resend + a `req.wait` request; neither produces a decision; surviving joins still resolve | absent | construct a log exercising both skip conditions |
| 19 | unjoinable decision | trace row's `request_hash` matches no raw request; `request_protocol_index: null`; decision remains a distinct timeline entry, never dropped | absent | mutate a trace row's `request_hash` to a value with no request-line match |
| 20 | replay-only nullability | `trace_schema_version`, `our_side`, `source_hashes.decision_trace` all `null`; provenance resolves from the result row | absent | fixture-04 (replay-only, present) is close precedent — 20 needs the explicit nullability assertions named, likely a pytest extension over the existing fixture-04 export rather than a new bundle |
| 21 | provenance disagreement | trace row and result row disagree on `config_hash`; export refuses | absent | mutate a source pairing's `config_hash` in one of the two files |
| 22a | mode key `required:false, present:true` | refuse as malformed (invariant 1) | absent | mutate a manifest's `battle_log` entry |
| 22b | mode key `required:true, present:false` | refuse as malformed (invariant 1); distinct from fixture 8 (8 = declared present, missing on disk; 22b = declared not-present while required) | absent | mutate a manifest's `battle_log` entry, opposite direction from 22a |
| 23 | optional key `required:true` | `warnings` declared `required: true`; refuse (invariant 2) | absent | mutate a manifest's `warnings` entry |
| — | 104-candidate bounded-render | cross-cutting rule 7 (index §5), not a numbered §14 fixture | absent | Choice Point 3 (§0.11, **CLOSED: L1**) — derive `TRACE_ONLY` from the real committed row (`smoke-i7a-mega`, §0.1). **Known gap (accepted by owner):** no companion battle log in that corpus ⇒ this fixture can only be `TRACE_ONLY`; bounded rendering is never exercised together with active replay mode. A defect only reproducible with board + timeline + a live 104-row candidate table simultaneously would not be caught by this fixture |

Fixtures **9, 22a, 22b, 23** already have structural precedent in `godot/tests/fixtures/unit/`
(`refuse-duplicate-decision-index`, `refuse-extra-files-key`, others) — Plan F's catalogue copies
must **not** reuse those files directly (different ownership, §0.2) and must get their own
correctly-hashed manifests, learning from §0.6 rather than repeating it.

---

## 2. Architecture (fixture + gate layout)

```text
fixtures/viewer-v0/
  SOURCES.md                     ← extend: one entry per new source + bundle dir (existing pattern)
  sources/fixture-{02,07-09,11-15,17-23}/
  bundles/fixture-{02,07-09,...}/  (only for fixtures whose end state is a valid, opened bundle)

tests/python/
  test_f1_fixture_catalogue.py   ← gate mapping for exporter-side §15 rows (11 total; §3)
  test_f1_fixture_integrity.py   ← §0.6 sha256-drift gate, walks both fixture roots

godot/tests/bundle|decision|workspace/
  (extend existing suites where a §15 row is Godot-side; do not invent a new top-level dir)

docs/plans/evidence/
  viewer-v0-f-visual-capture/    ← §0.7 procedure output: PNGs + run notes
  viewer-v0-f-manual-checklist.md ← F2 SR/DPI/scale/density checklist (consumes Plan E's E6 template)

tools/
  (CI script location — depends on Choice Point 1, §0.11; not pinned here)
```

---

## 3. Named tests (F1 gate mapping)

Bundle contract §15 lists 37 numbered gates. The table below maps each to where it is proved.
Gates already covered by Plan A's existing 77 pytest tests are marked **existing**; F1's job is the
**new** rows, plus the two integrity/truncation gates from §0.6.

| §15 gate(s) | What it proves | Coverage |
|---|---|---|
| 1–5 (determinism) | byte-identical re-export; file-list/digest comparison; one-byte mutation changes digest; no absolute paths; cross-machine determinism | **existing** — `test_a7_atomic_export.py`, `test_a8_fixtures.py::test_two_exports_fixture01_identical` |
| 6–9 (canonical form) | RFC 8785 JCS; JSONL `\n`-only; non-finite fails (fixture 11); `candidate_key` round-trips | 6–7, 9 **existing** (`test_a1_canonicalize.py`); **8 new** — pair with fixture 11 |
| 10–14 (identity/integrity) | chosen-key resolution; `chosen_rank`; chosen/`normalized_action` agreement; duplicate refuse (fixtures 9, 14); sort stability | **existing** on the real v3 fixture (`test_a4_decisions_v3.py`); **fixtures 9/14 new** |
| 15–17 (versioning) | unknown major/capability refuse (fixtures 7, 12); minor bump preserves unknowns; required-field minor bump rejected by schema test | **fixtures 7/12 new**; 16–17 likely **existing** in `test_a6_provenance_modes.py` — verify at F1 start, do not assume |
| 18–21 (privacy) | fixture-10 counterexample; seat pseudonym consistency; no credential-shaped keys; no nickname/`LogEvent.raw` | **existing** — `test_a3_privacy.py`, `test_a8_fixtures.py::test_fixture10_bundle_has_no_leaks` |
| 22–25 (provenance) | `git_sha=="unknown"` → `dirty:null` (fixture 15); `source_hashes` real; `config-manifest.json` hash agreement; no `config_hash` reverse-lookup | 22 **existing** (`test_a8_fixtures.py::test_synthetic_fixture_reports_git_and_dirty_unknown`) — fixture 15's own catalogue slot per §1 is a naming question, not new coverage; 23–25 likely **existing** in `test_a6_provenance_modes.py`/`test_a2_manifest_hash.py` — verify |
| 26–29 (degradation) | all 3 modes reachable (fixtures 1, 4, 5); `not recorded` never `0`/`false`/`[]`; `aggregation.mode:null` visible; `suspected` never rendered at 1.0 | 26 **existing**; 29 is Godot-side, folds into F3 (§4 honesty rules) |
| 30–37 (modes/join/identity) | `request_hash` byte-identical live/offline; §11.1.1 truth table incl. fixtures 4/5/20/22a/22b/23; §11.1.2 nullability (fixture 20); provenance disagreement refuses (fixture 21); `protocol_index` sparse (fixture 17); `rqid`/`wait` skip (fixture 18); empty candidate set (fixture 16, existing); trace-v1 rejected + replay-only fallback (fixture 13) | **30 existing** (`test_a5_request_hash_recipes.py`); **20, 21, 17, 18, 13 new**; 36 **existing** (fixture-16) |

**F1 must verify the "existing" cells above before relying on them** — this table was built by
reading test *names* and fixture *usage*, not by re-running every one of the 77 pytest tests
line-by-line against every gate's exact wording. Treat "existing" as a strong prior, not a closed
box.

### 3.1 Fixture-integrity gate (§0.6, binding shape)

**Two defects in the sketched gate itself, corrected here (P1-1, P1-2 — verified against the real
fixture layout, 2026-07-24):**

**P1-1 — glob depth silently skips the `sources/` root.** Under `fixtures/viewer-v0/sources/`,
manifests do not sit at `<fixture>/manifest.json`: the only fixture dir currently there is
`fixture-06`, and its manifest is at `sources/fixture-06/bundle/manifest.json` — one level deeper.
Verified directly: `sources/*/manifest.json` matches **0** files; `bundles/*/manifest.json`
matches **6**. A one-level glob against the `sources` root therefore scans zero manifests and
reports "no mismatches" — not because nothing was wrong, but because the gate never looked at that
root at all. That is the exact silent-no-coverage failure mode §0.6 exists to close off,
reintroduced in the gate meant to guard against it. Fixed below with a recursive glob.

A depth-correct glob alone is not sufficient, though: `**/manifest.json` matching zero files (a
renamed root, a moved directory, a typo'd path after a future refactor) still reports "no
mismatches" for the identical silent reason. **The recursive glob fixes today's specific miss; a
minimum-manifest-count assertion is the general guard against the same failure mode recurring in a
different shape tomorrow** — that is why the count assertion is binding alongside the glob fix, not
redundant with it.

**P1-2 — fixture-06's mismatch is deliberate, not drift.** §0.1 and §0.6 already establish
`sources/fixture-06/bundle` as the refuse fixture proving `hash_mismatch`
(`godot/tests/bundle/test_bundle_validator.gd:96` — `test_fixture06_hash_mismatch`;
`godot/tests/workspace/test_app_shell_smoke.gd` — `test_fixture06_refuse_reason`). Once the fixed
glob above actually reaches it, this gate will (correctly) find its `decision_trace` hash disagrees
with its manifest — and either fail on legitimate data, or tempt a future editor to "repair"
fixture-06's hash and silently break the two tests that depend on it staying wrong. A bare exclusion
list (skip fixture-06, don't look) would hide that risk rather than remove it: someone could still
"fix" the file and the exclusion would keep the gate quiet either way. Asserting the mismatch
**positively** — check it is still exactly the expected mismatch, fail if it is ever anything else,
including "no longer mismatched" — makes fixture-06 self-defending instead of merely invisible to
the gate. That is the concrete difference: an exclusion is a silent hole, a positive assertion is a
guard.

```python
# tests/python/test_f1_fixture_integrity.py (shape, not final code)
import hashlib, json
from pathlib import Path
from conftest import STUDIO_ROOT

# Minimum manifest count per root (P1-1): today's verified counts. F1 raises these as fixtures
# 2/7-9/11-15/17-23 land (§1). A floor that isn't bumped is merely loose, not wrong — but a root
# that silently returns fewer manifests than its floor must fail loudly either way.
ROOTS = {
    STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources": 1,   # fixture-06 only, today
    STUDIO_ROOT / "fixtures" / "viewer-v0" / "bundles": 6,   # fixtures 1/3/4/5/10/16, today
    STUDIO_ROOT / "godot" / "tests" / "fixtures" / "unit": 11,
}

# P1-2: fixture-06's decision_trace hash is a deliberate mismatch (§0.1, §0.6), asserted
# positively rather than excluded — see prose above for why an exclusion list is the weaker guard.
EXPECTED_MISMATCHES = {
    (STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-06" / "bundle", "decision_trace"),
}

def test_every_declared_sha256_matches_actual_bytes():
    unexpected_mismatches = []
    seen_expected = set()
    for root, min_manifests in ROOTS.items():
        manifests = list(root.glob("**/manifest.json"))
        assert len(manifests) >= min_manifests, (
            f"{root} matched {len(manifests)} manifest(s), expected >= {min_manifests} — a glob "
            "that silently under-matches its root is the P1-1 failure mode this gate exists to "
            "close, not a passing result"
        )
        for manifest_path in manifests:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for key, entry in manifest.get("files", {}).items():
                if not entry.get("present"):
                    continue
                target = manifest_path.parent / entry["path"]
                actual = hashlib.sha256(target.read_bytes()).hexdigest()
                if actual == entry.get("sha256"):
                    continue
                identity = (manifest_path.parent, key)
                if identity in EXPECTED_MISMATCHES:
                    seen_expected.add(identity)
                else:
                    unexpected_mismatches.append((str(target), entry.get("sha256"), actual))
    # Choice Point 2 (§0.11) is CLOSED: G1/advisory (all roots, not the two-speed G3 this sketch
    # originally assumed) — the line below is advisory-only shape: report unexpected_mismatches
    # (log / warning), do not fail CI on it. Re-check at F1 implementation time whether
    # fix/studio-fixture-hash-integrity has landed and blocking has become free before keeping this
    # advisory (§0.11 amendment). This does not touch fixture-06's assertion below, which stays
    # unconditional regardless of Choice Point 2's outcome (P1-2).
    if unexpected_mismatches:
        print(f"[advisory] fixture hash mismatches: {unexpected_mismatches}")  # does not fail CI
    # Fixture-06 must still mismatch. If this fails, someone "repaired" the deliberate refuse
    # fixture and silently broke the two tests cited above that depend on it staying wrong (P1-2).
    assert seen_expected == EXPECTED_MISMATCHES, EXPECTED_MISMATCHES - seen_expected
```

Whether `unexpected_mismatches` is asserted unconditionally (G2/blocking), replaced with a warning
log (G1/advisory), or scoped so only `fixtures/viewer-v0/` roots are blocking while
`godot/tests/fixtures/unit/` is collected-and-reported-only (G3, this plan's own recommendation)
was Choice Point 2 — now **CLOSED (owner, 2026-07-24): G1**, plain advisory across all roots, not
the two-speed G3 shape this section originally sketched around. See §0.11's closure block for the
binding amendment: the premise for choosing advisory (5 pre-existing drifted unit fixtures would
make a blocking gate red on day one) is itself being removed by a separate, unmerged branch
(`fix/studio-fixture-hash-integrity`), so F1 must re-check at implementation time whether blocking
has become free before building the advisory shape below unchanged. The minimum-count assertions
and fixture-06's positive assertion above are **not** part of that choice point: they are binding
regardless of Choice Point 2's outcome — an empty scan and a silently "repaired" refuse fixture are
bugs in the gate itself, not a blocking-vs-advisory policy question.

### 3.2 CI truncation guard (§0.6, binding, not a choice point)

The CI script (location depends on Choice Point 1) must invoke gdUnit with fail-fast disabled
(`-c`, verified §0.1) and assert, per suite file, that
`executed + skipped == (count of top-level "func test_" in that .gd file)`. This can be a small
wrapper script comparing the JUnit XML's outer `tests` attribute against the number of `<testcase>`
children, or an equivalent pytest-side check over the XML gdUnit already emits
(`run_gdunit_headless.ps1` already writes `reports/report_N/results.xml`, §0.1).

**Assumption this formula rests on (P2-3):** `executed + skipped == (count of top-level "func
test_")` holds only while no gdUnit **parameterized** test exists in the suite — a single
`func test_x` under `@warning_ignore("unused_parameter")`/parameter-source annotation can expand
into many executed cases at run time, breaking the 1:1 count this guard assumes. Verified absent
today (`grep -rn "test_parameters" godot/tests` returns nothing, 2026-07-24). If parameterized
tests are ever introduced, this equality must be redefined per declared parameter set (or read the
JUnit case count directly rather than counting `func test_` occurrences) — it will not fail loudly
on its own; whoever adds the first parameterized test must update this guard by hand.

---

## 4. Task breakdown (F1–F5)

### F1 — Automated gate suite

- [ ] Verify the "existing" cells in §3's gate table against the actual 77 pytest tests (do not
      assume from names)
- [ ] Author fixtures 2, 7–9, 11–15, 17–23 per §1, extending `SOURCES.md` in the existing format
- [ ] Author the 104-candidate bounded-render fixture per Choice Point 3's resolution
- [ ] Write the new-gate pytest rows from §3 (11, 7, 12, 9, 14, 20, 21, 17, 18, 13)
- [ ] Write `test_f1_fixture_integrity.py` per §3.1, scoped per Choice Point 2's resolution
- [ ] Prove the fixture-integrity gate detects drift (P1-3): mutate one byte of a fixture file in a
      **temporary copy** (never a committed fixture), run the gate against the copy, assert it
      fails; delete the copy after. "The gate runs" is not evidence it detects anything
- [ ] Write the CI truncation guard per §3.2
- [ ] Map viewer-side §15 rows (bounded rendering, gate 14 sorting) to gdUnit where automatable —
      extend existing suites (`test_bundle_validator.gd`, `test_decision_presenter.gd`), do not
      create a new top-level test directory
- [ ] CI script per Choice Point 1's resolution: Python tests + Godot headless gdUnit4 with JUnit
      output, fail-fast disabled, truncation-guarded
- [ ] **Commit:** `test(studio): add Plan F fixture catalogue and automated gate suite`

### F2 — Named visual-capture procedure + manual checklist

- [ ] Implement the throwaway capture script per §0.7 (never committed as production code; lives
      under a scratch/tools path with a comment marking it non-shipping)
- [ ] Capture fixture-01 at 1280×720 and one larger size (e.g. 1400×900) once Plan E's E1–E5 are
      merged; file both PNGs under `docs/plans/evidence/viewer-v0-f-visual-capture/`
- [ ] Record the §0.8 reachability row as pass/fail against the fresh capture — do not carry
      forward the "fix in flight" note as evidence of a fix
- [ ] Record scale/density rows as "not yet wireable" if §0.8's gap analysis still holds at F2
      time, rather than inferring a pass
- [ ] Fill the SR smoke-note and mixed-DPI checklist (Plan E §0.10 templates), Choice Point 4's
      resolution decides how much is required before "green"
- [ ] Document the headless blind spot (§0.5) directly in the checklist file, not just in this plan
- [ ] **Commit:** `docs(studio): add Plan F visual-capture procedure and manual evidence`

### F3 — Honesty / non-claim audit

- [ ] UI copy never implies strength/safety/correctness of the bot
- [ ] Aggregation degradation visible without opening raw JSON (§15 gate 28)
- [ ] `suspected` not rendered at schema 1.0 (§15 gate 29)
- [ ] Completeness of candidate set neither claimed nor denied (bundle contract §16.1)
- [ ] Explicitly separate "data is honest" from "control/affordance doesn't exist yet" per §0.8 —
      the scale/density inertness and hash-overflow-no-truncation findings are **not** data-honesty
      defects and must not be reported as such, nor silently absorbed as if they were fine
- [ ] UI copy, docs, and CI job naming never imply Linux support (§0.12) — Windows is the target,
      macOS is possible later, Linux is not shipped anywhere in this repo
- [ ] **Commit:** `docs(studio): Plan F honesty and non-claim audit`

### F4 — Docs closeout

- [ ] Re-verify Plan E's deferred work landed per §0.9 (`StudioMonoFont` wired, `reset_to_safe` /
      `focus_diagnostics` wired) by reading the merged source, not Plan E's own plan text
- [ ] Flip plan statuses A–F from DRAFT→APPROVED only for plans already approved earlier; else
      leave history untouched
- [ ] Update [`../README.md`](../README.md) Studio status lines
- [ ] Update [`README.md`](README.md) plans index
- [ ] Explicitly state Phase 1+ still unauthorized
- [ ] **Commit:** `docs(studio): Plan F documentation closeout`

### F5 — Merge readiness packet

Produce a short review note listing:

1. Specs implemented (A–E scope)
2. Fixture digests / paths (all 23, not just F's 17)
3. CI command + last green counts, including the truncation-guard result
4. Manual checklist results, filed and reviewed per Choice Point 4 (§0.11, CLOSED: J2), plus an
   explicit owner sign-off checkbox — stated as "filed and signed off," never as "passed" (§0.11's
   binding constraint)
5. Known §16 gaps still open
6. Residual privacy linkability reminder (bundle contract §12.6)
7. The §0.8 scale/density/hash-truncation gaps, named as open items against Plan E's own §9.2
   release-gate claims — not silently dropped because they are Plan E's scope, not Plan F's fix

- [ ] **Commit:** `docs(studio): Plan F merge readiness packet`

---

## 5. Acceptance (Viewer v0 program done)

| Criterion | Evidence |
|---|---|
| All 23 fixtures have **automated** coverage that is genuinely green (pytest/gdUnit pass); any fixture without automated coverage instead has manual evidence **filed** — the two are never conflated as both being "green" in the closeout packet (P2-1; §0.5/§0.10 lineage, Plan E §0.10) | §1 matrix; §3 gate table; F5 packet states, per fixture, which of the two applies |
| §3's "existing" gate-coverage cells verified against the actual pytest tests, not left as an assumption from test/fixture names (P2-2) | §3 caveat paragraph; F1 task list |
| Fixture-integrity gate runs, its scope matches Choice Point 2's resolution, **and it demonstrably detects drift** — mutated one byte of a fixture in a temporary copy, ran the gate against the copy, confirmed it fails (P1-3; "runs" alone is not evidence of detection — the same defect class that let Plan E's `test_scale_presets` pass against a no-op implementation) | §3.1; F1 task list |
| CI does not silently truncate on first failure | §3.2, demonstrated defect in §0.6 |
| Primary controls reachable at 1280×720 | fresh §0.7 capture, not the §0.8 note carried forward |
| No Studio writes into frozen eval sources | unchanged from sketch |
| No network in runtime paths | unchanged from sketch; §0.7's capture script is dev tooling, not runtime |
| Screen-reader / mixed-DPI evidence filed **and reviewed**, with an explicit owner sign-off checkbox (Choice Point 4, §0.11, CLOSED: J2) — filed-and-signed-off is not the same claim as "passed" (binding constraint, §0.11) | F5 packet, sign-off checkbox |
| 104-candidate bounded-render fixture proves bounded rendering against a real committed producer row (Choice Point 3, §0.11, CLOSED: L1) — **known gap:** `TRACE_ONLY` only (no companion battle log), so bounded rendering is never exercised together with active replay mode by this fixture | §1 matrix (104-candidate row); §0.11 Choice Point 3 |
| Plan E's E2→E6, E3/E4→E5 deferrals verified landed | §0.9 |
| User review before merge; user review before any Phase 1 design kickoff | unchanged from sketch |

---

## 6. Self-review checklist (author)

- [x] Every new identifier cited in §0.1 was read from the real file or produced by directly
      running the pinned tooling, not assumed
- [x] E2–E7 surfaces are explicitly marked as cited-not-verified (only E1 is merged here)
- [x] §0.6's corrected finding replaces the briefed premise with what two live gdUnit runs actually
      showed, with exact commands and output
- [x] Choice points left genuinely open: CI platform scope, fixture-gate blocking/advisory,
      104-candidate derive-vs-author, manual-evidence requirement — none pre-closed by this draft
- [x] Explicit stop line preserved verbatim in substance (§8)
- [x] No fixture, test, or API cited that was not confirmed to exist (or confirmed absent, e.g. the
      17 unowned catalogue fixtures)
- [x] Status remains DRAFT; no source file touched by this expansion

---

## 7. Handoff

1. ~~Owner reviews this DRAFT against Plan E's actual merged state (currently E1 only) and the
   four open choice points in §0.11~~ — the four choice points are now closed (§0.11, Rev. 3,
   2026-07-24); Plan E's actual merged state is still only E1 as of this revision and still needs
   owner review against whatever lands.
2. ~~Owner closes Choice Points 1–4, or leaves them for a later revision~~ — **done**, 2026-07-24
   (§0.11; Rev. 3 changelog entry, §9).
3. Status → **APPROVED** in a **docs-only** commit (owner) — **a separate, later act from closing
   the choice points above** (§0.11's own intro states this explicitly) — only after Plans A–E are
   actually green and merged (index §3.2); approving this draft's text does not waive that
   dependency.
4. Separate go-ahead → isolated branch/worktree → F1…F5, same task-level TDD discipline as every
   other plan in this set.

**Do not** start F code from this DRAFT alone, and do not start it while any of E2–E7 remains
unmerged.

---

## 8. Explicit stop line

After Plan F, **stop**. Live Spectator, Team Analyzer, full client, add-ons, and external bots each
require their own approved design + plan. This document must not grow those tasks.

---

## 9. Changelog

### Rev. 4 — owner marked the plan APPROVED (2026-07-24)

- **Status DRAFT → APPROVED**, on the project owner's explicit instruction, satisfying implementation
  index §7 step 1 ("User reviews and marks the plan APPROVED").
- **Deliberately unchanged:** the §3.2 hard dependency. Approval is *not* an implementation
  go-ahead. Plans A–E must be green and merged first, and Plan E is **not** complete — Task E7 is
  outstanding and no Plan E branch is merged to `main` at the time of this revision. The
  "For agentic workers" note now states that condition (1) is the open one, so an implementer
  cannot read APPROVED as permission to start.
- The §8 explicit stop line is unchanged.
- Rev. 3's four choice-point closures, the CP2 premise-change note, the CP3 known gap, and the CP4
  "filed ≠ passed" constraint all carry forward unmodified.

### Rev. 3 — owner closed all four §0.11 choice points; status stays DRAFT (2026-07-24)

All four Rev. 1/Rev. 2 choice points are now **CLOSED (owner, 2026-07-24)**. Full option tables are
retained as protocol; each choice point gained a **Decision** / **Rationale** / **Status** block,
following the pattern Plan E §0.13 uses for its own closed choice points. **Closing these choice
points is not approving this plan** — the `Status:` line above is deliberately left unchanged
(**DRAFT — implementation not authorized**); marking APPROVED is a separate, later act by the owner
per §0.10/§7, gated independently on Plans A–E being green and merged (index §3.2, still not true —
only Task E1 is on `main`).

- **Choice Point 1** (§0.11) → **K1**: a `windows-latest` CI job (pytest + gdUnit, download+verify
  the pinned engine), against this plan's own K2 recommendation. Grounded in the §0.12 platform
  decision (Windows target, Linux out), not in today's ubuntu-only workflow shape. The two named
  costs (engine not committed → download+verify every run; Windows runner minutes billed at
  roughly double) are accepted, not waived. Wiring `showdownbot_studio/` into
  `.github/workflows/` remains an F1 implementation step, still gated by `Status: DRAFT`.
- **Choice Point 2** (§0.11) → **G1**: advisory only (reports mismatches, does not fail CI), against
  this plan's own G3 recommendation. **Binding amendment:** the grounding for advisory — that a
  blocking gate would fail immediately and permanently against the 5 pre-existing drifted
  `godot/tests/fixtures/unit/` fixtures (§0.6) — is being removed concurrently by a separate,
  unmerged branch `fix/studio-fixture-hash-integrity` (off `main`, not part of Plan F) that
  reseals those 5 manifests, null-guards the two crashing tests, and stops the gdUnit wrapper
  truncating on first failure. The decision is advisory as the owner chose, but the reason for it
  may no longer hold by the time F1 is implemented — F1 must re-check whether blocking has become
  free before building the advisory shape in §3.1. Not a silent upgrade to blocking; that stays the
  owner's call. §3.1's code-shape comment and surrounding prose updated to match (advisory-report
  shape, not an unconditional assert, for `unexpected_mismatches`).
- **Choice Point 3** (§0.11) → **L1**: derive `TRACE_ONLY` from the real committed 104-candidate row
  in `smoke-i7a-mega/decision_trace.jsonl`, following the `fixture-05`/`fixture-16` `SOURCES.md`
  pattern — matching this plan's own recommendation. Rationale: every one of the 5 hand-authored
  fixtures that drifted (§0.6) came from `godot/tests/fixtures/unit/`, while every
  exporter-produced fixture under `fixtures/viewer-v0/bundles/` was correct — derived beats
  hand-authored on this repo's own evidence, and L2 would also invoke the §14.1 synthetic-coherent
  exception permanently for a claim a real row already proves. **Known gap, accepted by the owner,
  not silently absorbed:** that corpus directory has no companion battle log, so the derived
  fixture can only be `TRACE_ONLY` — bounded rendering is never exercised together with active
  replay mode by this fixture. Recorded in §1's fixture matrix (104-candidate row) and as its own
  row in §5's acceptance table, not buried in the choice point alone.
- **Choice Point 4** (§0.11) → **J2**: every manual check (SR smoke note, mixed-DPI checklist) must
  be filed (attempted, non-empty, honest about failures) plus an explicit owner sign-off checkbox
  in F5's merge-readiness packet, against this plan's own J1 recommendation. **Binding constraint,
  stated unambiguously:** J2 means *filed and signed off*, **not** that everything must *pass* —
  Plan E §1 lists screen-reader completeness as a hard release gate among its explicit non-goals,
  and Plan E §0.10 frames SR evidence as best-effort only. A partially-failing SR result is an
  honest recorded outcome, not a release blocker; F5's sign-off attests the evidence was produced
  and reviewed, never that it all passed. F5's own task list (§4) and §5's acceptance table were
  reworded to state "filed and signed off," never "passed."
- §7 Handoff's steps 1–2 (owner reviews/closes the choice points) marked done via strikethrough,
  matching Plan E §7's own style for closed items; step 3 (Status → APPROVED) reworded to state
  explicitly that it remains a separate, later act, not a consequence of this revision.

### Rev. 2 — review amendments: P1/P2 gate-defect findings + platform-decision reasoning (2026-07-24)

Amendments from a review against the real code (repo owner's reviewer). Status stays **DRAFT**; all
four Rev. 1 choice points remain **OPEN** — this revision corrects reasoning and closes gaps in the
gate design, it does not close any decision.

- **P1-1** (§3.1): the sketched fixture-integrity gate's `root.glob("*/manifest.json")` silently
  scanned **zero** manifests under `fixtures/viewer-v0/sources/` — verified directly
  (`sources/*/manifest.json` matches 0 files; the only manifest there is one level deeper, at
  `sources/fixture-06/bundle/manifest.json`) — the exact silent-no-coverage failure mode §0.6
  exists to close, reintroduced in the gate meant to guard against it. Fixed with a recursive glob
  plus a binding minimum-manifest-count assertion per root, so an empty or under-matching scan
  fails loudly instead of reporting a spuriously clean "no mismatches."
- **P1-2** (§3.1): once the glob above actually reaches `fixture-06` — the refuse fixture whose
  hash mismatch is deliberate (§0.1, §0.6) — a naive gate would either fail on correct data or
  invite someone to "repair" it and silently break the two tests that depend on it staying wrong.
  Replaced a bare-exclusion approach with a positive assertion: fixture-06's mismatch must still be
  exactly the expected one, and the check fails if it is ever anything else, including "no longer
  mismatched."
- **P1-3** (§5, §4 F1): the acceptance row "fixture-integrity gate runs..." was satisfiable by a
  gate that runs but detects nothing — the same defect class that let Plan E's `test_scale_presets`
  pass against a no-op implementation. Amended to require a demonstrated failure against injected
  drift (one byte mutated in a temporary fixture copy), with the corresponding F1 task step added.
- **P2-1** (§5): the acceptance row "All 23 fixtures green in automated or documented manual form"
  blurred the plan's own automated-vs-manual-evidence discipline (§0.5/§0.10 lineage). Split into
  an explicit statement that automated coverage is "green" and manual coverage is "evidence filed,"
  never conflated in the closeout packet.
- **P2-2** (§5): §3's honest "F1 must verify the existing cells" caveat had no acceptance-table hook
  forcing that verification to actually happen before program-done is claimed. Added an acceptance
  row; the corresponding F1 task step already existed in Rev. 1 (§4 F1's first bullet) and was left
  as-is rather than duplicated (see report — this half of the review finding did not hold up).
- **P2-3** (§3.2): named the CI truncation guard's unstated assumption that no gdUnit parameterized
  test exists (`executed + skipped == count of top-level "func test_"` breaks if one ever does),
  verified still absent today (`grep -rn "test_parameters" godot/tests` — empty), with a note on
  what breaks and what to do if that changes.
- **Item 8** (§0.11 Choice Point 1, new §0.12): Choice Point 1's grounding argued from the shape of
  today's CI (mixed `ubuntu-latest`/`windows-latest` job matrix), which is a fact about pre-existing
  `showdown_bot` lanes, not about the product. Recorded the owner's actual target-platform decision
  as binding (§0.12: Windows target, Linux out, macOS possible later) and rewrote Choice Point 1's
  reasoning to argue from it instead, adding two costs of a Windows CI lane the owner should weigh
  (the pinned engine is gitignored and not committed, so CI must download-and-verify it per run;
  GitHub bills Windows runner minutes at roughly double Linux). The choice (K1/K2/K3) itself stays
  **OPEN**, deferred to Plan F review by the owner. §0.12 also records that Plan E's
  `ShortcutLabels.mod_key()` macOS branch (Plan E §4, cited — not yet merged code) retains its
  purpose under "macOS possible later" and is not dead code, and binds F3's honesty audit to never
  let the codebase imply Linux support.

### Rev. 1 — sketch → executable draft (2026-07-24)

- Expanded to Plan E's structural density: §0 verified surface with `path:line` citations, fixture
  ownership binding, cross-cutting-rules pointer, scope fence, four genuinely open choice points
  with options/trade-offs/recommendations, named-test gate mapping, TDD task breakdown, acceptance
  table, self-review checklist, handoff.
- §0.5: documented the headless `DisplayServer` window-geometry stub as a binding, verified
  limitation (direct probe: `(0,0)` headless vs the real value non-headless) — this is why F2's
  manual/visual checks cannot be replaced by more gdUnit tests.
- §0.6: **corrected** the briefed premise about the fixture-hash-drift finding. Independently
  confirmed the 5/11 sha256 mismatch (byte-verified against the committed git blob, ruling out a
  CRLF/checkout artifact), then ran the actual gdUnit suite twice (default invocation and with
  `-c`) and found the true picture is not "one visible failure, four silent passes" — it is one
  visible failure, three more confirmed failures once fail-fast is disabled, one confirmed process
  crash from a missing `result.ok` guard in the test itself, and one test never reached. Also
  discovered and documented, as a second and separately-actionable defect, that gdUnit4's CI runner
  defaults to fail-fast and the project's own `run_gdunit_headless.ps1` never disables it — a
  single early failure can silently truncate an entire suite (demonstrated: 14 of 33 tests executed)
  with no signal in the console summary or exit code.
- §0.7: turned the vague "manual desktop checklist" into a named, reproducible capture procedure,
  verified against the pinned engine's real `--help` output.
- §0.8: recorded the 1280×720 reachability gap and the scale/density/hash-truncation gaps from a
  parallel gap analysis as named, checkable F2/F3 rows — explicitly not claimed fixed.
- §0.9: recorded Plan E's own E2→E6 and E3/E4→E5 deferrals as a binding F4 re-verification step
  against merged source, not against Plan E's plan text.
- §1: rebuilt the fixture completion matrix against bundle contract §14's exact "must prove"
  wording and confirmed, by direct count, that fixtures 2/7–9/11–15/17–23 are all still absent, and
  that a real 104-candidate row (needed for the bounded-render proof) already exists in the
  committed `smoke-i7a-mega` corpus (2 rows at exactly 104 candidates, out of 20), informing Choice
  Point 3's recommendation.
- Preserved the sketch's explicit stop line verbatim in substance.
