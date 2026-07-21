# Viewer v0 — Plan E: Diagnostics, Accessibility, and Layout (Sketch)

**Status:** DRAFT — sketch only; **implementation not authorized**
**Date:** 2026-07-21
**Depends on:** Plans B–D surfaces to decorate
**Unblocks:** Plan F closeout checklist

**Authority:** [`../specs/viewer-v0-design.md`](../specs/viewer-v0-design.md) §6 / §8,
[`../MASTER_SPEC.md`](../MASTER_SPEC.md) §2.4 / §5,
[`../decisions/ADR-001-godot-ui-technology.md`](../decisions/ADR-001-godot-ui-technology.md),
mockups README binding corrections,
[`2026-07-21-viewer-v0-d-decision-inspection.md`](2026-07-21-viewer-v0-d-decision-inspection.md)
§0.11 / §0.13 (filter ownership — amended with Plan D Rev. 4)

## Goal

Ship the persistent state banner, diagnostics/provenance panels, Compact/Comfortable density,
75%–200% scale, keyboard-first workflows, and layout resilience gates — without network font loads.

## Non-goals

- Screen-reader completeness as a hard release gate (best effort + honest report only)
- Shortcut remapping unless cheap (spec: not required)
- Localization
- Dark/light theme polish beyond workable defaults from mockup direction
- **Candidate filter semantics, FilterLineEdit/ChosenOnly UI, or filter tests** — those are
  **Plan D** (Rev. 4 §0.11). Plan E must not leave the Viewer-v0 filter requirement orphaned by
  treating “focus candidate filter” as the only filter work.

## Proposed files

| Path | Responsibility |
|---|---|
| `godot/src/diagnostics/state_banner.tscn` | Exactly one prominent banner |
| `godot/src/diagnostics/diagnostics_presenter.gd` | Warnings / degradation |
| `godot/src/diagnostics/provenance_presenter.gd` | hashes, versions, dirty tri-state |
| `godot/src/diagnostics/raw_evidence_tab.tscn` | Normalized raw only; bounded |
| `godot/src/workspace/workspace_layout.gd` | docks, density, scale, reset |
| `godot/src/workspace/shortcut_labels.gd` | Ctrl vs Cmd presentation |
| `godot/assets/fonts/` or system stack | Offline fonts only (decision on approval) |

## Ownership split vs Plan D (binding amendment)

| Concern | Owner |
|---|---|
| Filter text + chosen-only checkbox UI | Plan D |
| Filter semantics + gdUnit coverage | Plan D |
| `CandidateTableView.get_filter_line_edit()` | Plan D |
| `CandidateTableView.focus_selected()` API | Plan D |
| Keyboard shortcut to **focus** existing filter LineEdit | Plan E |
| Keyboard shortcut to call `focus_selected()` (“jump to selected candidate”) | Plan E |
| Global state banner / density / scale / a11y polish | Plan E |

If Plan D is APPROVED without filter, Plan E **cannot** absorb filter implementation under the
label “focus candidate filter.” Filter must ship in D before E keyboard wiring is meaningful.

## Task sketch

### E1 — State banner

Exactly one banner; states include at least:

- `TEAM PREVIEW`
- `DECISION RECORDED`
- `FORCED REPLACEMENT`
- `WAITING / NO DECISION ROW`
- `TRACE MISSING`
- `STATE DEGRADED`
- `FALLBACK USED`
- `BUNDLE INVALID`

Warnings: text + icon, not color alone.

### E2 — Provenance + diagnostics

- [ ] Bundle schema, trace schema, format, git_sha, config_hash, source hashes, exporter version
- [ ] `dirty`: true / false / null → null shown as `dirty state not recorded` (never as clean)
- [ ] Optional absent files → persistent degraded warning
- [ ] Raw evidence tab: bundle-normalized content only; bounded rendering

### E3 — Scale and density

- [ ] UI scale 75%–200% with user override
- [ ] Compact + Comfortable preserve same information and selection
- [ ] Long labels: visual truncate + full-value tooltip/detail; copy never truncates IDs
- [ ] Primary controls reachable at min supported window (pin size numbers on approval)

### E4 — Keyboard-first

Minimum actions (bind to **existing** Plan D/C APIs; do not reimplement filter/selection):

- prev/next timeline entry
- prev/next decision
- play/pause
- jump to selected candidate → `CandidateTableView.focus_selected()`
- focus candidate filter → `CandidateTableView.get_filter_line_edit().grab_focus()`
- open diagnostics
- reset layout/scale
- honor deep link from Plan D

Platform-aware shortcut labels (`Ctrl` on Windows/Linux, `Cmd` on macOS).

### E5 — Layout shell

- [ ] Resizable / collapsible docks
- [ ] Reset-to-safe-layout action
- [ ] Small window may stack/tab; never lose timeline or close controls
- [ ] Mixed-DPI manual Windows check: move window across monitors; keep selection + readability

### E6 — Offline fonts

- [ ] Remove any Google Fonts / network font dependency from the app
- [ ] Bundle license-reviewed font **or** approved system stack (choose at approval)
- [ ] Mockup HTML may keep network fonts; app must not

## Acceptance (Plan E done)

- Keyboard-only inspection of fixture 1 possible (filter already present from Plan D)
- Scale presets 75/100/150/200 reachability check recorded
- Mixed-DPI checklist filled (manual evidence note in Plan F)
- Screen-reader: smoke notes written as best effort — no overclaim
- Banner always visible and correct for fixtures 1, 3, 4, 5, 6
- “Focus candidate filter” focuses Plan D’s LineEdit; does not invent a second filter control
