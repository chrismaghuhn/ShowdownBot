# Viewer v0 — Plan F: End-to-End Acceptance

**Status:** DRAFT — expanded to an executable draft; **implementation not authorized**
**Date:** 2026-07-21 · **Rev.:** 1 (2026-07-24 — sketch → executable, per Plan E structural template)
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

> **For agentic workers:** do **not** implement from this DRAFT. Plan F code starts only after (1)
> Plans A–E are green and merged (index §3.2 — **not yet true**, see Depends-on above), (2) this
> plan's status is moved to **APPROVED** by the project owner in a **docs-only** commit, and (3) a
> separate implementation go-ahead. Do not invent a second fixture catalogue, a second CI runner
> convention, or a second test-helper module — reuse the patterns cited in §0.1.

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
landing is Open Choice Point 2 (§0.11)** — the 5 already-drifted unit fixtures are not part of
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

### 0.11 Open choice points for the OWNER

None of these are closed by this expansion. Each carries options, trade-offs, and a
recommendation — the recommendation is not a decision.

#### Choice Point 1 — CI platform/runner scope

**Grounding:** `.github/workflows/pytest.yml` runs three jobs today, all on `showdown_bot/`, all
(or matrixed) on `ubuntu-latest`/`windows-latest` per job; **none** touch `showdownbot_studio/`.
The pinned Godot engine (`ENGINE_SHA256SUMS`) has **Windows-only** artifacts — no Linux or macOS
binary is pinned or verified anywhere in the repo.

| Option | Shape | Consequence |
|---|---|---|
| K1 | Add a `windows-latest` GH Actions job that downloads the pinned zip, verifies it against `ENGINE_SHA256SUMS`, then runs pytest + gdUnit as one job (mirroring the existing per-track job convention, e.g. `champions-mega`) | Real CI coverage of the Godot side; adds a new binary-download step to a repo whose stated Phase-0 posture is offline-first at *runtime* (tooling acquisition is a separate concern, but still worth the owner's sign-off) |
| K2 | Ship only a `showdownbot_studio` **pytest** job now (platform-agnostic, pure Python, same shape as the existing `showdown_bot` jobs); keep gdUnit as a documented local pre-merge command a developer runs on Windows before requesting review | Ships real CI today with zero new infrastructure; gdUnit stays un-gated in CI until someone stands up K1 or K3 later |
| K3 | Pin a Linux headless Godot export template in addition to the Windows console exe, run both in CI | Matches contributor OS diversity if it ever exists; doubles the engine-pin maintenance burden for a single-developer project (per memory: solo dev) |

**Recommendation:** K2 now, K1 as the natural next step once someone wants gdUnit in CI. Standing
up a new Windows GH Actions lane and a licensed binary-download step is infrastructure work Plan F
was not scoped to include, and pytest alone is cheap, real, and immediately actionable. **Status:
OPEN.**

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
making Plan F's closeout depend on a fix explicitly scheduled for later by someone else. **Status:
OPEN.**

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
synthetic exception was never meant to normalize. **Status: OPEN.**

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
needing to be baked into this plan. **Status: OPEN.**

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
| — | 104-candidate bounded-render | cross-cutting rule 7 (index §5), not a numbered §14 fixture | absent | Choice Point 3 (§0.11) — recommend deriving `TRACE_ONLY` from the real committed row |

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

```python
# tests/python/test_f1_fixture_integrity.py (shape, not final code)
import hashlib, json
from pathlib import Path
from conftest import STUDIO_ROOT

ROOTS = [
    STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources",
    STUDIO_ROOT / "fixtures" / "viewer-v0" / "bundles",
    STUDIO_ROOT / "godot" / "tests" / "fixtures" / "unit",
]

def test_every_declared_sha256_matches_actual_bytes():
    mismatches = []
    for root in ROOTS:
        for manifest_path in root.glob("*/manifest.json"):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for key, entry in manifest.get("files", {}).items():
                if not entry.get("present"):
                    continue
                target = manifest_path.parent / entry["path"]
                actual = hashlib.sha256(target.read_bytes()).hexdigest()
                if actual != entry.get("sha256"):
                    mismatches.append((str(target), entry.get("sha256"), actual))
    # Choice Point 2 (§0.11) decides whether this line asserts or only reports.
    assert not mismatches, mismatches
```

Whether the final `assert` is unconditional (G2/blocking), absent entirely in favor of a warning
log (G1/advisory), or scoped to only the `fixtures/viewer-v0/` roots while `godot/tests/fixtures/unit/`
is collected-and-reported-only (G3, recommended) is Choice Point 2 — not decided here.

### 3.2 CI truncation guard (§0.6, binding, not a choice point)

The CI script (location depends on Choice Point 1) must invoke gdUnit with fail-fast disabled
(`-c`, verified §0.1) and assert, per suite file, that
`executed + skipped == (count of top-level "func test_" in that .gd file)`. This can be a small
wrapper script comparing the JUnit XML's outer `tests` attribute against the number of `<testcase>`
children, or an equivalent pytest-side check over the XML gdUnit already emits
(`run_gdunit_headless.ps1` already writes `reports/report_N/results.xml`, §0.1).

---

## 4. Task breakdown (F1–F5)

### F1 — Automated gate suite

- [ ] Verify the "existing" cells in §3's gate table against the actual 77 pytest tests (do not
      assume from names)
- [ ] Author fixtures 2, 7–9, 11–15, 17–23 per §1, extending `SOURCES.md` in the existing format
- [ ] Author the 104-candidate bounded-render fixture per Choice Point 3's resolution
- [ ] Write the new-gate pytest rows from §3 (11, 7, 12, 9, 14, 20, 21, 17, 18, 13)
- [ ] Write `test_f1_fixture_integrity.py` per §3.1, scoped per Choice Point 2's resolution
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
4. Manual checklist results, with Choice Point 4's required-vs-filed distinction stated explicitly
5. Known §16 gaps still open
6. Residual privacy linkability reminder (bundle contract §12.6)
7. The §0.8 scale/density/hash-truncation gaps, named as open items against Plan E's own §9.2
   release-gate claims — not silently dropped because they are Plan E's scope, not Plan F's fix

- [ ] **Commit:** `docs(studio): Plan F merge readiness packet`

---

## 5. Acceptance (Viewer v0 program done)

| Criterion | Evidence |
|---|---|
| All 23 fixtures green in automated or documented manual form | §1 matrix; §3 gate table |
| Fixture-integrity gate runs and its scope matches Choice Point 2's resolution | §3.1 |
| CI does not silently truncate on first failure | §3.2, demonstrated defect in §0.6 |
| Primary controls reachable at 1280×720 | fresh §0.7 capture, not the §0.8 note carried forward |
| No Studio writes into frozen eval sources | unchanged from sketch |
| No network in runtime paths | unchanged from sketch; §0.7's capture script is dev tooling, not runtime |
| Screen-reader / mixed-DPI evidence filed | Choice Point 4's resolution decides "filed" vs "filed + signed off" |
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

1. Owner reviews this DRAFT against Plan E's actual merged state (currently E1 only) and the four
   open choice points in §0.11.
2. Owner closes Choice Points 1–4, or leaves them for a later revision.
3. Status → **APPROVED** in a **docs-only** commit (owner) — only after Plans A–E are actually
   green and merged (index §3.2); approving this draft's text does not waive that dependency.
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
