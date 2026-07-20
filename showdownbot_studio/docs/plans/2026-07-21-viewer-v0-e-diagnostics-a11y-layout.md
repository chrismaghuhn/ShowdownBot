# Viewer v0 — Plan E: Diagnostics, Accessibility, and Layout (Sketch)

**Status:** DRAFT — sketch only; **implementation not authorized**
**Date:** 2026-07-21
**Depends on:** Plans B–D surfaces to decorate
**Unblocks:** Plan F closeout checklist

**Authority:** [`../specs/viewer-v0-design.md`](../specs/viewer-v0-design.md) §6 / §8,
[`../MASTER_SPEC.md`](../MASTER_SPEC.md) §2.4 / §5,
[`../decisions/ADR-001-godot-ui-technology.md`](../decisions/ADR-001-godot-ui-technology.md),
mockups README binding corrections

## Goal

Ship the persistent state banner, diagnostics/provenance panels, Compact/Comfortable density,
75%–200% scale, keyboard-first workflows, and layout resilience gates — without network font loads.

## Non-goals

- Screen-reader completeness as a hard release gate (best effort + honest report only)
- Shortcut remapping unless cheap (spec: not required)
- Localization
- Dark/light theme polish beyond workable defaults from mockup direction

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

Minimum actions:

- prev/next timeline entry
- prev/next decision
- play/pause
- jump to selected candidate
- focus candidate filter
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

- Keyboard-only inspection of fixture 1 possible
- Scale presets 75/100/150/200 reachability check recorded
- Mixed-DPI checklist filled (manual evidence note in Plan F)
- Screen-reader: smoke notes written as best effort — no overclaim
- Banner always visible and correct for fixtures 1, 3, 4, 5, 6
