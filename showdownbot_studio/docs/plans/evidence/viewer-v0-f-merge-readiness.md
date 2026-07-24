# Viewer v0 — Plan F Merge Readiness Packet (F5)

Produced per
[`../2026-07-21-viewer-v0-f-e2e-acceptance.md`](../2026-07-21-viewer-v0-f-e2e-acceptance.md) §4 F5.
**Build:** `studio/plan-f-acceptance` @ `ca3f7ba` (F4's commit; this packet is F5, committed
immediately after). **Date:** 2026-07-24.

## Plan F is not complete. This is a readiness packet, not a completion claim.

Read this whole document before deciding whether to merge. Plan F's own §5 acceptance table has
rows that are **not** met today (see "What is still open" at the end). Nothing below should be
read as "Viewer v0 is done" or "Plan F is done" — those are separate, larger claims this packet
does not make.

---

## 1. Specs implemented (A–E scope)

All five prerequisite plans are merged on `main` (verified: each plan document's own `Status:`
header reads APPROVED, and `git log main` shows the merge commits below):

| Plan | Scope | Merge |
|---|---|---|
| A | Python exporter (`showdownbot_studio_exporter`) + the bundle-contract §14 fixture catalogue's Plan-A-owned rows (1, 3, 4, 5, 6, 10, 16) | PR #41 |
| B | Godot project scaffold + sealed, read-only typed DTO loader (`BundleDTO`, `BundleLoader`) | PR #44 |
| C | Abstract replay board + timeline transport | PR #46 @ `1b0be1d` |
| D | Candidate table view + decision detail view | PR #47 + follow-ups PR #48 @ `0256602` |
| E | Diagnostics dock, UI scale/density, keyboard shortcuts, workspace layout shell, offline monospace fonts | E1 as `e757772`, E2–E7 via PR #71 (`4ed406c`) |

Plan F's own scope (fixtures 2/7–9/11–15/17–23, automated gates, visual-capture procedure, honesty
audit, this closeout) is implementation-complete on `studio/plan-f-acceptance` but **that branch is
not merged to `main`** — see "What is still open" below.

## 2. Fixture digests / paths — all 23 catalogue rows, not just Plan F's 17

Authoritative per-file sha256 digests live in
[`../../../fixtures/viewer-v0/SOURCES.md`](../../../fixtures/viewer-v0/SOURCES.md) (474 lines, one
entry per source/bundle directory) — reproduced here as a path/ownership index, not duplicated as a
second hash ledger that could silently drift out of sync with the real one.

| # | Subject (§14) | Owner | `sources/` dir | `bundles/` dir | SOURCES.md § |
|---|---|---|---|---|---|
| 1 | synthetic-coherent baseline | Plan A | `fixture-01` | `fixture-01` | `## fixture-01` / `## bundle/fixture-01` |
| 2 | close decision (margin) | Plan F | `fixture-02` | `fixture-02` | `## fixture-02` / `## bundle/fixture-02` |
| 3 | synthetic-coherent, second config | Plan A | `fixture-03` | `fixture-03` | `## fixture-03` / `## bundle/fixture-03` |
| 4 | replay-only | Plan A | `fixture-04` | `fixture-04` | `## fixture-04` / `## bundle/fixture-04` |
| 5 | smoke trace-only | Plan A | `fixture-05` | `fixture-05` | `## fixture-05` / `## bundle/fixture-05` |
| 6 | invalid hash (deliberate refuse) | Plan A | `fixture-06/bundle` | *(none — refuse fixture)* | `## fixture-06` |
| 7 | unsupported schema major | Plan F | `fixture-07/bundle` | *(none — refuse fixture)* | `## fixture-07` |
| 8 | missing mandatory file | Plan F | `fixture-08/bundle` | *(none — refuse fixture)* | `## fixture-08` |
| 9 | duplicate decision identity | Plan F | `fixture-09/bundle` | *(none — refuse fixture)* | `## fixture-09` |
| 10 | privacy counterexample | Plan A | `fixture-10` | `fixture-10` | `## fixture-10` / `## bundle/fixture-10` |
| 11 | non-finite value | Plan F | `fixture-11` | *(none — export refuses)* | `## fixture-11` |
| 12 | unknown required capability | Plan F | `fixture-12/bundle` | *(none — refuse fixture)* | `## fixture-12` |
| 13 | legacy trace-v1 | Plan F | `fixture-13` | *(none — shape-identical to `bundle/fixture-04`, proved via a throwaway `tmp_path` export instead)* | `## fixture-13` |
| 14 | chosen-candidate desync | Plan F | `fixture-14` | *(none — export refuses)* | `## fixture-14` |
| 15 | `git_sha == "unknown"` → `dirty:null` | Plan F | **no new directory — owner decision point, not settled** (see §4 below) | — | `## fixture-15` |
| 16 | smoke team-preview / empty candidates (also the 104-candidate cross-cutting proof) | Plan A | `fixture-16` | `fixture-16` | `## fixture-16` / `## bundle/fixture-16` |
| 17 | filtered protocol lines / sparse index | Plan F | `fixture-17` | `fixture-17` | `## fixture-17` / `## bundle/fixture-17` |
| 18 | `\|request\|` skip rules | Plan F | `fixture-18` | `fixture-18` | `## fixture-18` / `## bundle/fixture-18` |
| 19 | unjoinable decision | Plan F | `fixture-19` | `fixture-19` | `## fixture-19` / `## bundle/fixture-19` |
| 20 | replay-only nullability (§11.1.3 resolution) | Plan F | **no new directory — shape-identical to `bundle/fixture-04`; proved by extending an existing test** | — | `## fixture-20` |
| 21 | provenance disagreement | Plan F | `fixture-21` | *(none — export refuses)* | `## fixture-21` |
| 22a | mode key `required:false, present:true` | Plan F | `fixture-22a/bundle` | *(none — refuse fixture)* | `## fixture-22a` |
| 22b | mode key `required:true, present:false` | Plan F | `fixture-22b/bundle` | *(none — refuse fixture)* | `## fixture-22b` |
| 23 | optional key `required:true` | Plan F | `fixture-23/bundle` | *(none — refuse fixture)* | `## fixture-23` |

All 23 rows are accounted for: 21 have a committed catalogue directory (some source-only, by
design — a refuse fixture never produces a bundle); 2 (15, 20) are deliberately **not** authored as
separate directories, each with a written justification in `SOURCES.md` for why a fresh directory
would only duplicate an existing one — fixture 15 explicitly flagged there as an **open owner
decision point**, not resolved by this packet (§4 below preserves it, does not close it).

**Verified present on disk, this session** (`ls fixtures/viewer-v0/{sources,bundles}`): every
directory named in the table above exists in this worktree. This corrects a stale claim in
[`viewer-v0-f-honesty-audit.md`](viewer-v0-f-honesty-audit.md) — see "Evidence that disagreed with
itself" below.

## 3. CI command + last green counts, including the truncation-guard result

**There is no CI for `showdownbot_studio/` today.** `.github/workflows/pytest.yml` has zero jobs
touching this directory (`grep -in studio .github/workflows/pytest.yml` → no match, re-confirmed
this session). Every count below is a **local measurement**, run fresh in this session, not a CI
result.

**Python** (from `showdownbot_studio/`):

```
$env:PYTHONPATH = "python/src"   # REQUIRED — without this the global editable install resolves
                                  # to the main checkout, not this worktree (silently wrong data)
python -m pytest tests/python -q
```

Fresh result, this session: **102 passed, 5 failed, 2 skipped** (109 collected). The 2 skips are
the Windows symlink-privilege tests in `test_a7_pathsafety.py` (clean skip, not a failure). All 5
failures are pre-existing and out of Plan F's scope (§0.4 excludes fixing them) — 3 trace to a
CRLF-vs-LF working-copy difference between checkouts of the same committed blob (documented in
`SOURCES.md`'s own out-of-scope note, end of the 104-candidate entry), the other 2 to a `SOURCES.md`
hash-ledger drift across 4 pre-existing fixture directories, same root cause class. This exact
102/5/2 split matches what commit `1980174` (`test(studio): close gate-coverage gaps the Plan F
audit verified`) reported when it landed — re-run and reconfirmed here, not copied forward.

**Godot / gdUnit4** (from `showdownbot_studio/godot/`):

```
.\tools\run_gdunit_headless.ps1 -a "res://tests/"
```

Fresh result, this session: **268 test cases | 0 errors | 0 failures | 0 flaky | 2 skipped | 0
orphans**, all 26 suites executed (`Executed test suites: (26/26)`), exit code 0. Matches commit
`1980174`'s reported 268, re-run and reconfirmed here. (The many `ERROR: Dictionary is in read-only
state` lines in the raw console output are the *expected* runtime errors that
`test_bundle_dto.gd`'s sealed-DTO tests deliberately trigger and assert on via
`GdUnitGodotErrorAssertImpl` — not failures; the `PASSED` statistics line per suite confirms this.)

**Truncation-guard result (§3.2):** `run_gdunit_headless.ps1` passes `-c` (disable fail-fast)
**unconditionally**, not as an opt-in flag —
[`godot/tools/run_gdunit_headless.ps1:45–54`](../../../godot/tools/run_gdunit_headless.ps1) — closing
the specific silent-truncation risk §0.6 demonstrated (a suite that stops at its first failure with
no summary-line or exit-code signal that later tests never ran). This was verified structurally
(the flag is unconditional in the script) and behaviourally (this session's fresh run above
executed all 26/26 suites, not a truncated subset). **What is *not* built:** §3.2 also asked for a
standalone assertion that `executed + skipped == (declared per-suite test count)`, read from the
JUnit XML, as a second, independent check. No such script exists in this repo. F1's own checklist
item for the CI truncation guard is still unchecked in the plan text. The `-c` flag closes the
practical risk in the meantime; the independent cross-check §3.2 also specified is genuinely not
built.

## 4. Manual checklist — filed and reviewed, per Choice Point 4 (CLOSED: J2)

**Filed:** yes. [`viewer-v0-f-manual-checklist.md`](viewer-v0-f-manual-checklist.md) records three
fresh, non-headless captures (1280×720, 1400×900, 1280×720@200% scale) against this build, with
primary-control reachability, monospace-hash-surface, scale, and density rows all checked directly
against the captures — not inferred.

**Owner sign-off:** ☐ **NOT YET CHECKED.** The checklist's own sign-off line
(`viewer-v0-f-manual-checklist.md`, "Owner sign-off" section) reads `- [ ] Owner has reviewed this
checklist and its three captures.` — still unchecked as of this packet. Per J2's binding constraint
(§0.11), this attests the evidence was **produced and reviewed**, never that it **passed**; nothing
below should be read as "SR/DPI checks passed."

- **Screen-reader smoke note:** **not performed** — requires a human at an interactive desktop
  session with a screen reader attached; this session drove the engine headlessly/via subprocess
  capture only. Filed as an explicit, honest gap (template reproduced, unfilled), not invented.
- **Mixed-DPI checklist:** **not performed** — requires real second-monitor hardware and a human
  moving a live window between displays with different Windows scaling settings. Same honest-gap
  treatment.
- Both are consistent with Plan E's own §0.10/§1 framing: screen-reader completeness is an explicit
  **non-goal**, never a hard release gate. An unfilled SR/DPI check is not a release blocker under
  J2 — it is a recorded, honest gap awaiting the owner's sign-off.

**Action needed before merge:** the owner reviews the three captures and the checklist rows, then
checks the sign-off box in `viewer-v0-f-manual-checklist.md` (or explicitly declines to). This
packet does not check it on the owner's behalf.

## 5. Known §16 gaps still open (bundle contract, unrelated to Plan F, not fixed by it)

All eight are explicitly "DESIGN INPUT MISSING" in
[`../../specs/viewer-v0-bundle-contract-design.md`](../../specs/viewer-v0-bundle-contract-design.md)
§16 — none blocks schema 1.0, none is Plan F's to close:

| § | Gap |
|---|---|
| 16.1 | Candidate-set completeness — no producer flag for `TOP_K_TRACE_CANDIDATES` truncation; the viewer must neither claim completeness nor truncation (verified honest in practice, F3 §4) |
| 16.2 | Aggregation mode / `risk_lambda` / `must_react_lambda` — not persisted in any trace version; schema 1.0 emits `null` + a degradation warning |
| 16.3 | Belief snapshot / `suspected` — no belief field on any DTO or row; reserved capability `belief_v2` |
| 16.4 | Per-decision warning severity vocabulary — no bot-side producer; `warnings.json` carries exporter warnings only |
| 16.5 | Score components — `OutcomeBreakdown`'s nine component fields never reach the trace row; candidate detail can show only `aggregate_score` |
| 16.6 | `selection_stage` / `fallback_reason` vocabularies — persisted but unvalidated, no closed enum; viewer must render unknown values verbatim |
| 16.7 | State-summary fields beyond the recorded payload — any mockup field outside `observable_state_payload`/`_pokemon_payload` has no producer |
| 16.8 | `seed`, `seed_base`, `run_id`, `start_ts` — explicitly excluded from schema 1.0 |

## 6. Residual privacy linkability reminder (bundle contract §12.6)

`portable-pseudonymous-v1` is **pseudonymous, not anonymous**, and does not make a bundle
unlinkable. Per §12.6, five vectors survive by design: `source_hashes.*` (known-plaintext linkage
to the original artifact), stable run/config identifiers (`battle_id`, `config_hash`,
`schedule_hash`, `seed_index`, `git_sha`), deterministic state digests
(`observable_state_hash`/`request_hash`), stable seat pseudonyms (re-identifiable by anyone with
side knowledge of who occupied a seat), and the battle content itself (team/move-sequence
fingerprint). **The consequence is a sharing rule, not a defect:** a bundle is safe to share only
under the same trust assumptions as the source it was built from. No manifest field asserts
anonymity, and Plan F has not added one. Public distribution and a cleartext-name mode remain
outside v0, pending separate legal review (§12.6 cites the license/data audit directly).

## 7. §0.8 scale/density/hash-truncation gaps — status against Plan E's own §9.2 release-gate claims

**Named here per the task brief, not silently dropped — these are Plan E's scope, not Plan F's
fix.** The picture is more nuanced than §0.8's original note, and F2/F3 (this branch, same session)
already corrected part of it with fresh evidence — recorded precisely, not glossed:

- **Primary-control reachability at 1280×720 — REVERSED to PASS.** §0.8 cited a stale note against
  an unmerged branch (`studio/plan-e-layout-shell` @ `0cd93f2`, "fix reported in flight"). A fresh
  capture against the now-merged `main @ 5feaa7c` (F2,
  [`viewer-v0-f-manual-checklist.md`](viewer-v0-f-manual-checklist.md)) shows the transport row,
  PathRow, and DiagnosticsDock all reachable and unclipped at 1280×720. Not carried forward as "fix
  in flight" — decided by the fresh capture.
- **Scale/density controls — REVERSED from "not yet wireable" to wired and reachable, but with a
  real, newly-confirmed defect.** Both the `Scale:` `OptionButton` and `Density:` toggle are live
  and produce a measured visual effect. **New finding, not in §0.8's original note:** at
  1280×720/200% scale, `WorkspaceLayout` — which `extends Control`, not `Container`
  (`godot/src/workspace/workspace_layout.gd:2`) — does not propagate its children's minimum-size
  growth, so the enlarged text overlaps itself and the timeline/decision-list columns are pushed
  off-frame with no reflow or scrollbar recovery. Reproduced and captured
  (`fixture-01-1280x720-scale200-2026-07-24.png`). **This directly contradicts Plan E's own §7
  acceptance table**, which marks its "Scale 75/100/150/200" row met by citing a headless-only
  setter/getter test (`test_scale_presets`, which §0.5 already establishes cannot observe real
  window/control geometry) plus the 100%-only reachability check. That Plan E acceptance row is
  **not true at 200%/1280×720**. Filed as a claims-vs-reality defect in a merged, previously-accepted
  plan document (F3, `viewer-v0-f-honesty-audit.md` §"The Plan E §7 scale-claim contradiction") —
  **not fixed here**; the container-type fix is a layout rewrite, out of Plan F's scope (§0.4).
- **Hash-value overflow with no truncation/tooltip/copy affordance — CONFIRMED, unchanged from
  §0.8.** `ProvenancePresenter.present()`'s full, un-truncated hash strings render as plain
  `Label.text` (`diagnostics_dock.gd:82`) with no wrapping/ellipsis/tooltip — contrast the
  deliberate `MAX_RAW_CHARS` truncation applied to the Raw tab. Visually confirmed clipped hard at
  the window edge in `fixture-01-1400x900-2026-07-24.png`.
- **Neither is a data-honesty defect.** Both are capability/rendering gaps against accurate,
  honestly-labeled data (F3 §5 "(a)/(b) split" — no invented, hidden, or mislabeled value in either
  case). Both remain Plan E's own tracked scope (design spec §9.2's release-gate claims), recorded
  again here per this task's binding instruction, not newly discovered and not Plan F's to fix.

---

## What is still open (Plan F is not complete)

This packet is explicit that **Plan F itself is not done** and Viewer v0 acceptance is **not**
claimed. Specifically, still open against Plan F's own §5 acceptance table:

1. **No CI wiring exists at all** (§4 F1, Choice Point 1 closed as K1 — a Windows GH Actions lane —
   but never built). `.github/workflows/pytest.yml` has zero jobs touching
   `showdownbot_studio/`. Neither the Studio pytest suite nor the Godot gdUnit suite runs in CI.
   **Every green count in this packet, and every green count in every Plan F evidence file, is a
   local measurement**, not CI-verified.
2. **The fail-check pass is partial**, not complete. Only gates 10/11/12 were fail-checked (broken,
   confirmed red, restored, confirmed green again) —
   [`viewer-v0-f-gate-test-failcheck.md`](viewer-v0-f-gate-test-failcheck.md). That check found the
   exporter's own `_resolve_chosen` refuse branches never run on the real
   `load_trace_rows → export_bundle` path (an upstream validator refuses first, under a different
   message) — the tests pass, but do not exercise the code path their names claim to. The remaining
   ~99 tests added by commit `1980174` are **green but unproven** — "asserted", not "covered", is
   the honest word until each is fail-checked the same way.
3. **Gate-coverage tally is stale, not re-audited.** The committed
   [gate-coverage audit](viewer-v0-f-gate-coverage-audit.md) measured **8 COVERED / 15 PARTIAL / 14
   MISSING of 37** — but that measurement predates commit `1980174`, which added tests against many
   of the gaps it found. The tally has **not** been re-run against the current suite. This packet
   does not state a new tally it has not verified, and neither should any reader of it.
4. **Screen-reader and mixed-DPI checks are filed as templates, not performed** (§4 above) — both
   need a human at the machine with real assistive-technology / multi-monitor hardware. Consistent
   with Plan E's own non-goal (SR completeness is never a hard release gate), but genuinely
   unattempted, not merely unfinished.

Also recorded here as open items for the owner, found during Plan F's execution, all out of Plan
F's own scope fence (§0.4) to fix:

- `export_decisions.py`'s `_resolve_chosen` and `non_finite_value` refuse branches appear
  unreachable on the real production path (item 2 above) — defence-in-depth or dead code,
  undecided; needs an owner call, not a Plan F fix.
- Two docs still imply Linux support, predating the §0.12 platform decision:
  `docs/design/viewer-v0-mockups/README.md:57` and
  `docs/plans/2026-07-21-viewer-v0-e-diagnostics-a11y-layout.md:161`'s keybinding table header. The
  first is a frozen external-mockup corrections doc; the second is Plan E's own already-approved
  plan text. Neither is shipped UI copy (F3 confirmed `shortcut_labels.gd` itself makes no Linux
  claim), so this is a documentation-accuracy item, not a shipped-honesty defect. Not fixed here —
  out of Plan F's edit scope (§0.4 / CLAUDE.md's rule against rewriting another approved artifact
  without explicit approval).
- Five pre-existing Python test failures (§3 above), three tracing to a CRLF-vs-LF working-copy
  difference between checkouts of the same committed blob — documented in `SOURCES.md`'s own
  out-of-scope note. Separately scoped repair, not Plan F's.
- Fixture 15 is a documented, deliberately unsettled **owner decision point**
  (`SOURCES.md`, `## fixture-15`): redundant with fixture-01's existing proof, or authored anyway
  for catalogue browsability. Recommendation given (redundant, don't author), not decided.

## Evidence that disagreed with itself (found while writing this packet)

[`viewer-v0-f-honesty-audit.md`](viewer-v0-f-honesty-audit.md) (commit `9270bd2`) states, in its
"What this audit does not establish" section: *"Fixtures 2, 7–9, 11–15, 17–23. None exist yet —
F1's own task, still unchecked in the plan. Nothing in this audit exercises them because there is
nothing to exercise."* This is **incorrect** at the time it was written. All of Plan F's own
fixture-authoring commits (`8027fc2`, `3b57d09`, `4f72227`, `da431e6` — fixtures 2, 7, 8, 9, 11, 12,
13, 14, 17, 18, 19, 21, 22a, 22b, 23, plus the 104-candidate proof) landed between 10:45 and 12:02
on 2026-07-24, all **before** the honesty-audit commit at 13:00 the same day. `ls
fixtures/viewer-v0/{sources,bundles}` in this worktree confirms every one of those directories is
present right now. The honesty audit's F3 checklist items (UI-copy/aggregation/`suspected`/Linux
checks) do not depend on the fixtures existing and are unaffected by this — but the one sentence
above is stale/wrong and should not be relied on for fixture-existence claims. Flagged here rather
than silently corrected in place; `viewer-v0-f-honesty-audit.md` itself is untouched by this
packet (F3's own deliverable, out of F5's scope to edit).
