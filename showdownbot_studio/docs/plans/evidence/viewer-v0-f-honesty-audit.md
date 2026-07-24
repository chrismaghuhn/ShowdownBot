# Viewer v0 — Plan F Honesty / Non-Claim Audit (F3)

Produced per [`2026-07-21-viewer-v0-f-e2e-acceptance.md`](../2026-07-21-viewer-v0-f-e2e-acceptance.md)
§4 F3, against §0.8 (gap analysis), §0.12 (platform decision), and §0.3 rule 10 (open design
inputs stay missing). Consumes, and does not repeat, the fresh captures in
[`viewer-v0-f-manual-checklist.md`](viewer-v0-f-manual-checklist.md) /
[`viewer-v0-f-visual-capture/`](viewer-v0-f-visual-capture/) and the gate audit in
[`viewer-v0-f-gate-coverage-audit.md`](viewer-v0-f-gate-coverage-audit.md).

**Build under audit:** `studio/plan-f-acceptance` @ `451fbd3` (this worktree's `HEAD` at audit
time). **Date:** 2026-07-24.

**Method.** Every `.gd` file under `godot/src/` was read in full (35 files: `bundle/`, `decision/`,
`diagnostics/`, `replay/`, `timeline/`, `workspace/`). Every `.tscn` file under the same tree was
grepped for static `text = ` / `placeholder_text = ` / `tooltip_text = ` literals. Targeted greps
covered assignment sites (`.text =`, `set_text(`, `tooltip_text`, `push_warning(`,
`placeholder_text`) and a strength/safety/correctness word list (`best`, `optimal`, `recommend`,
`correct`, `winning`, `strong`, `accura*`, `confiden*`, `guarant*`, `proven`, `reliab*`, `win rate`,
`elo`, `rating`, `expert`, `superior`). The Python exporter (`python/src/showdownbot_studio_exporter/`)
was spot-checked for warning/refuse-code text that reaches the UI via `warnings.json`. Findings
below cite `file:line`; screenshot claims cite the specific PNG and were visually re-inspected, not
inferred from file existence.

---

## 1. UI copy never implies strength/safety/correctness of the bot

**Verdict: PASS.**

No match anywhere in `godot/src/**/*.gd` or `*.tscn` for any word in the strength/quality list above
(the one incidental hit, `envelope` containing the substring `elo`, is not a claim). All static
labels are one of three kinds:

- Raw field echoes: `"rank: %d"`, `"aggregate_score: %.4f"`, `"candidate_key: %s"`,
  `"request_hash: %s"` (`decision_detail_view.gd:36,42,55-57`) — numbers/hashes straight from the
  DTO, no adjective attached.
- A closed vocabulary of **schema/mode state names**, not decision-quality judgments:
  `BUNDLE_INVALID`, `TRACE_MISSING`, `STATE_DEGRADED`, `WAITING_NO_DECISION`, `FALLBACK_USED`,
  `FORCED_REPLACEMENT`, `TEAM_PREVIEW`, `DECISION_RECORDED`
  (`godot/src/diagnostics/state_banner_presenter.gd:4-11`) — every one of these describes *whether
  data exists / what stage the decision is at*, never *how good* the decision was.
- Static chrome text (`"Open"`, `"Prev"`, `"Next"`, `"Filter candidates..."`, `"Chosen only"`,
  `"Density: Comfortable"`) — pure UI mechanics.

No candidate row, decision header, or state banner anywhere characterizes the bot's play as good,
bad, correct, or safe.

---

## 2. Aggregation degradation visible without opening raw JSON (§15 gate 28)

**Verdict: PASS.**

Two independent, non-Raw-tab surfaces show the degradation, both confirmed in code and in a fresh
capture:

- **Overview tab (decision detail).** `DecisionPresenter.aggregation_headline()`
  (`godot/src/decision/decision_presenter.gd:32-39`) returns the literal string
  `"aggregation mode not recorded"` when all three aggregation fields are null, rendered by
  `decision_detail_view.gd:27` into a plain `Label` on the **Overview** tab — not the Raw tab.
  `risk_lambda` / `must_react_lambda` render `"not recorded"` the same way (`decision_detail_view.gd:28-33`).
  Confirmed on-screen in
  [`fixture-01-1280x720-2026-07-24.png`](viewer-v0-f-visual-capture/fixture-01-1280x720-2026-07-24.png):
  `aggregation: aggregation mode not recorded`, `risk_lambda: not recorded`,
  `must_react_lambda: not recorded` are all directly legible in the Overview panel, Raw tab closed.
- **Warnings tab.** The exporter emits a per-decision `aggregation_mode_not_recorded` code
  (`python/src/showdownbot_studio_exporter/warnings_emit.py:7,21-22`) into `warnings.json`; Godot
  surfaces every such entry as a `Warnings`-tab row with icon `"!"` and the owning decision index
  (`godot/src/diagnostics/diagnostics_presenter.gd:13-19,26-32`,
  `godot/src/diagnostics/diagnostics_dock.gd:88-91`) — again a dedicated tab, not Raw JSON.

**Precision note (do not overclaim):** the top-level `StateBanner`'s `STATE_DEGRADED` state is
**not** triggered by an aggregation-null decision. `StateBannerPresenter.compute()`
(`state_banner_presenter.gd:29`) only flips to `STATE_DEGRADED` on `bundle.downgrade_warnings`
(schema/mode downgrades) or an absent optional *display* file — `bundle.warnings` (the
per-decision exporter warnings, including `aggregation_mode_not_recorded`) is a separate array
that never feeds the banner. Gate 28 is still satisfied — the Overview text and the Warnings tab
are both non-Raw, always-visible UI — but the banner itself does not announce this particular
degradation, and this audit does not claim it does.

---

## 3. `suspected` not rendered at schema 1.0 (§15 gate 29)

**Verdict: PASS.**

`grep -i "suspected" godot/src -r` returns zero matches in any `.gd` or `.tscn` file. The string
appears only in `docs/design/viewer-v0-mockups/*.html` (the frozen external mockup artifact,
explicitly not shipped, per that folder's own README) and in prose documentation (bundle contract
§16.3, plan text). `DecisionPresenter.NOT_RECORDED` (`"not recorded"`) is the only information-state
vocabulary present anywhere in shipped code (`decision_presenter.gd:5`, used throughout
`decision_detail_view.gd`, `decision_workspace.gd`, `provenance_presenter.gd`). No belief/suspicion
field exists on any DTO (`candidate_dto.gd`, `decision_row_dto.gd` read in full — no `suspected` or
`belief` property). Matches bundle contract §16.3 / §10.5 exactly: the belief snapshot input is
missing, and the viewer renders nothing that claims to fill the gap.

---

## 4. Completeness of candidate set neither claimed nor denied (bundle contract §16.1)

**Verdict: PASS.**

No label, tab title, header, or tooltip anywhere states or implies a count relationship for the
candidate list. `candidate_table_view.tscn` has no header/count node at all (`placeholder_text =
"Filter candidates..."`, `text = "Chosen only"` are the only static strings —
`godot/src/decision/candidate_table_view.tscn:15,19`). Grepped `godot/src` for
`Top `/`top_k`/`TOP_K`/`showing`/`out of`/`total candidates`/`all candidates`/`complete`/`exhausti`/`truncat`:
the only hit is `diagnostics_dock.gd:13` (`TRUNCATION_MARKER := "… truncated"`), which bounds the
**Raw JSON blob** at `MAX_RAW_CHARS` (`diagnostics_dock.gd:36-40`) — an explicit, honestly-labeled
truncation of the raw-text dump, unrelated to the candidate list and not a claim about candidate
completeness either way. This matches §16.1's own binding text verbatim ("the viewer must not claim
the candidate list is complete, and must not claim it is truncated either") — neither claim exists
in the shipped surface.

---

## 5. §0.8 separation — "data is honest" vs "control/affordance doesn't exist yet"

Both named findings from §0.8 were re-checked directly against the merged code and fresh captures,
not carried forward from the stale gap-analysis note. **Both are capability gaps, not data-honesty
defects** — see the (a)/(b) list below for the full reasoning; this section records that the
separation was performed, not just asserted.

- Scale/density controls are **not** inert at F3 time (§0.8's "not yet wireable" framing is stale —
  already corrected in the F2 checklist, confirmed again here): `AppShell` wires a real
  `Scale:` `OptionButton` and `Density:` toggle to `WorkspaceLayout.set_ui_scale()` /
  `set_density()` (`app_shell.gd:42-48,281-291,305-311`), and both presets produce a real, measured
  visual effect (§0.8's overlap finding **confirms** the scale control is wired — a no-op control
  could not overlap anything).
- The overlap itself, and the un-truncated hash values, are both **rendering/layout defects that
  reproduce with 100%-honest data** — nothing about them causes the UI to assert something false
  about the underlying bundle. See the (a)/(b) split below.

---

## 6. UI copy, docs, and CI job naming never imply Linux support (§0.12)

**Verdict: PASS in shipped code and CI. FINDING in two documentation files (not fixed — see below).**

- **Shipped code:** `ShortcutLabels.mod_key()` (`godot/src/workspace/shortcut_labels.gd:7-8`) is a
  binary `OS.get_name() == "macOS"` check returning `"Cmd"` or `"Ctrl"`. It never names Linux, and
  its `"Ctrl"` branch is simply "not macOS" — not a Linux-support claim. No other `.gd`/`.tscn` file
  under `godot/src/` mentions Linux (grepped case-insensitively, zero hits).
- **CI:** `.github/workflows/` contains one file (`pytest.yml`); grepped case-insensitively for
  `studio`, zero hits. No Studio CI job exists yet at all (Choice Point 1/K1 authorized a future
  Windows-only lane; F1's CI task is still unchecked in the plan's own task list, §4). There is
  nothing to name yet, so this half of the checklist item is vacuously satisfied — revisit when F1
  lands the CI job.
- **Engine pin:** `godot/tools/ENGINE_SHA256SUMS` lists exactly three Windows (`win64`) artifacts,
  no Linux/macOS entry — consistent with §0.12 (already cited in the plan's own §0.1).
- **FINDING (documentation, not shipped UI copy):**
  - `docs/design/viewer-v0-mockups/README.md:57` — *"Shortcut presentation must therefore come from
    a platform-aware label layer: `Ctrl` on Windows/Linux and `Cmd` on macOS."* This groups Linux
    with Windows as a keybinding target. Written 2026-07-16, predating the §0.12 platform decision
    (2026-07-24), and not revisited when that decision closed.
  - `docs/plans/2026-07-21-viewer-v0-e-diagnostics-a11y-layout.md:161` — the default-keybindings
    table header reads `| Action | Windows/Linux | macOS label |`, same pattern, same pre-§0.12
    vintage. This is Plan E's own already-approved plan text.

  **Not fixed, deliberately:** (1) neither instance is "shipped UI copy" — the shipped code
  (`shortcut_labels.gd`) itself makes no Linux claim, so there is no honesty defect in what a user
  of the running app sees; (2) the Plan E table is another plan's own approved text, out of Plan
  F's scope fence (§0.4: *"Out: implementing any of Plan E's E2–E7 ... that is Plan E's own plan
  and branch"*) and CLAUDE.md's rule against broadening a slice or rewriting another approved
  artifact without explicit approval; (3) the mockups README is a design-corrections doc for a
  frozen external artifact, not runtime UI. Recorded here for the owner to decide whether to amend
  either document; not treated as a defect this task is authorized to fix.
  - A third Linux mention, `docs/research/2026-07-showdown-client-user-research.md:216`
    ("Controller and Linux/Android-handheld support requested"), was checked and is **not** a
    finding: it is user-research synthesis about the third-party, official Pokémon Showdown client
    (a different product), not a claim about this Studio viewer.

---

## The Plan E §7 scale-claim contradiction

Plan E's own acceptance table
([`2026-07-21-viewer-v0-e-diagnostics-a11y-layout.md`](../2026-07-21-viewer-v0-e-diagnostics-a11y-layout.md)
§7) states, verbatim:

> | Scale 75/100/150/200 | §5.4 + primary controls reachable at **1280×720** |

This bundles two citations into one "met" row, covering all four scale presets at the spec-minimum
window. Neither citation actually proves that at all four presets:

- **§5.4's own test**, `test_scale_presets` (`viewer-v0-e-diagnostics-a11y-layout.md:550`), asserts
  only that "0.75/1.0/1.5/2.0 stick" — a setter/getter round-trip run under headless gdUnit, which
  per this plan's own §0.5 **cannot observe real window or control geometry at all**
  (`DisplayServer.window_get_min_size()` reads back `(0,0)` under `--headless` regardless of what
  production code sets — verified by direct probe, §0.1/§0.5). It is not a layout-reachability
  check at any scale.
- **"Primary controls reachable at 1280×720"** was verified this session (F2,
  [`viewer-v0-f-manual-checklist.md`](viewer-v0-f-manual-checklist.md), PASS) only at **100%**
  scale — the only scale a real, non-headless capture was taken at for that specific row.

A fresh, this-session capture at the fourth named preset —
[`fixture-01-1280x720-scale200-2026-07-24.png`](viewer-v0-f-visual-capture/fixture-01-1280x720-scale200-2026-07-24.png),
1280×720, `set_ui_scale(2.0)` — shows the claim is **false at 200%**: the enlarged `"decision #0"`
header text draws directly on top of the `Scale:`/`Density:` row, the `stage:`/status line is
overdrawn, and the timeline transport row (`Prev`/`Next`/`Start`/`End`/`Play`) plus the entire
decision-list column are pushed off-frame with no scrollbar or reflow to recover them.

**Root cause** (named in the F2 checklist, re-confirmed by direct read here):
`WorkspaceLayout extends Control` (`godot/src/workspace/workspace_layout.gd:2`), not `Container` —
so `WorkspaceLayout` never propagates its children's minimum size when the runtime theme's
`default_font_size` grows with scale (`workspace_layout.gd:20-29`); the parent `VBoxContainer` never
learns the rows got taller and does not reflow around them.

**Verdict:** Plan E §7's "Scale 75/100/150/200" row is **not true** at 1280×720/200% — the exact
minimum window the same row's own evidence column names. This is a claims-vs-reality defect in a
merged, previously-accepted plan document, not a defect this audit introduces. Per the task's
binding instruction and Plan F's own scope fence (§0.4), this is named and evidenced here, **not**
fixed — `WorkspaceLayout`'s container type is a layout rewrite, out of scope for Plan F.

---

## (a) Data-honesty findings vs (b) capability-gap findings

Per §0.8's binding instruction, these two categories are kept strictly separate. A data-honesty
defect is the UI asserting something about the recorded data that the data does not support
(inventing a value, hiding a degradation, mislabeling a null as a real value). A capability gap is
a control, layout, or affordance that is missing, broken, or absent — while the data shown, when it
is shown, remains accurate.

### (a) Data-honesty findings: **none found.**

Every rendered field checked in §§1–4 above either (i) echoes a DTO field verbatim, (ii) renders
`DecisionPresenter.NOT_RECORDED` / `"aggregation mode not recorded"` / `"dirty state not recorded"`
for a genuinely-null optional field (never a false `0`/`false`/`[]` standing in for absence — e.g.
`decision_workspace.gd:118`'s `"fallback: false (not recorded)"` correctly separates the real
boolean `fallback_used` from the null-optional `fallback_reason`), or (iii) uses one of the eight
closed state-banner names, all of which describe schema/data state rather than decision quality.
No instance was found of the UI claiming completeness, correctness, safety, or a stronger
information state than the data warrants.

### (b) Capability-gap findings: **two, both already in Plan E's own tracked scope.**

1. **200%-scale / 1280×720 layout overlap.** `WorkspaceLayout extends Control`
   (`workspace_layout.gd:2`) instead of `Container` — does not propagate child minimum-size growth,
   so the shell overlaps itself at high scale in the minimum window. Reproduced in
   `fixture-01-1280x720-scale200-2026-07-24.png` (see the dedicated section above). This is the
   mechanism behind the Plan E §7 contradiction.
2. **Hash-value overflow with no truncation/tooltip/copy affordance in the Provenance panel.**
   `ProvenancePresenter.present()` emits full, un-truncated hash strings
   (`provenance_presenter.gd:25-34`) as plain `Label.text` via `diagnostics_dock.gd:82` — no
   wrapping, ellipsis, or tooltip logic is applied to these `Value` labels (contrast with the
   deliberate `MAX_RAW_CHARS` truncation that **is** applied to the Raw tab's `TextEdit`,
   `diagnostics_dock.gd:13,36-40`). Visually confirmed in
   [`fixture-01-1400x900-2026-07-24.png`](viewer-v0-f-visual-capture/fixture-01-1400x900-2026-07-24.png):
   `source_hashes_decision_trace` and the row above it are clipped hard at the window's right edge
   mid-character, no ellipsis, no visible affordance to read or copy the full value.

**Neither is a data-honesty defect and neither is silently absorbed as fine.** In both cases the
underlying value the UI is trying to show (the scale-inflated labels; the full hash string) is the
real, accurate value — nothing is invented, hidden, or mislabeled. What's missing is a rendering
affordance (container reflow; truncation/tooltip/copy) to present that accurate value usably at an
extreme setting. Both are already named as open items in Plan E's own scope (§0.8, design spec
§9.2's release-gate claims) and are recorded again here per this task's binding instruction, not
newly discovered and not Plan F's to fix (§0.4).

---

## Shipped-string changes made this session

**None.** No genuine honesty defect was found in any shipped UI string under `godot/src/`. Every
checklist item passes on direct inspection of the real code and this session's fresh, non-headless
captures. The two open findings are (b) capability gaps already tracked in Plan E's own scope and
named again here per the binding instruction in §0.8, not new discoveries requiring a fix; the
Linux mentions found are in documentation/plan text outside both "shipped UI copy" and Plan F's own
edit scope (§0.4). Consequently no production file was touched — `git status` shows only this
document — and the Godot test suite was not re-run (the task's re-run condition, "if you changed
any shipped string," does not apply).

---

## What this audit does not establish

- **Gate coverage for gates 1–27 and 30–37.** That is the separate, already-committed
  [gate-coverage audit](viewer-v0-f-gate-coverage-audit.md) (8 COVERED / 15 PARTIAL / 14 MISSING of
  37) and [fail-check pass](viewer-v0-f-gate-test-failcheck.md) (PARTIAL — only gates 10–12
  fail-checked). This document only speaks to the six F3 checklist items and the §7 contradiction.
- **Fixtures 2, 7–9, 11–15, 17–23.** ~~None exist yet — F1's own task, still unchecked in the plan.
  Nothing in this audit exercises them because there is nothing to exercise.~~
  **Corrected 2026-07-24 — the struck sentence was false when written.** All of those fixtures were
  already authored and committed on this branch (`8027fc2`, `3b57d09`, `4f72227`, `da431e6`) before
  this audit was written, and `fixtures/viewer-v0/sources/` holds every one of them. What is true is
  the narrower claim: **this audit did not exercise them.** Its six checklist items are about shipped
  UI copy and rendered surfaces, and it worked from the fixture-01 captures only. Their existence and
  correctness are established elsewhere — `SOURCES.md` for provenance, the §14 catalogue tests for
  behaviour. The error is left visible rather than silently rewritten, because an evidence file that
  quietly edits its own past claims is worth less than one that shows where it was wrong.
- **Exhaustiveness of the string sweep.** The sweep covered every `.gd` file under `godot/src/` read
  in full, every `.tscn` static-text literal, and a targeted assignment-site/word-list grep. A
  string built through some other, unswept mechanism (e.g., composed at runtime from data not
  covered by the greps above) could exist unseen. No such mechanism was found, but the sweep is not
  a formal proof of completeness.
- **Screen-reader announcement text or localization.** Not filed this session (an honest, explicitly
  marked gap in the F2 manual checklist, not this audit's subject); no i18n exists — only literal
  English strings were checked.
- **Anything under `showdown_bot/`, `data/eval/`, `config/eval/`, `reports/`.** Out of Plan F's
  scope fence (§0.4); not touched or inspected.
- **Whether the Linux-implying documentation should be corrected.** Flagged for the owner in §6
  above; this audit does not decide it and did not edit either document.
- **Whether the 200%-scale overlap or the hash-truncation gap should be fixed, or how.** Both are
  named, evidenced, and left exactly as found, per §0.4's explicit prohibition on Plan F implementing
  UI fixes.
