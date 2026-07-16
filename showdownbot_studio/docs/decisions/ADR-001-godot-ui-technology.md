# ADR-001 — Godot for the Studio desktop UI

**Status:** accepted for Phase 0
**Date:** 2026-07-16
**Decision owners:** ShowdownBot Studio maintainers
**Applies to:** Phase 0 Replay + DecisionTrace Viewer

## Context

ShowdownBot Studio needs a desktop workspace with a custom battle board, synchronized replay and
decision timelines, dockable analysis panels, keyboard-first navigation, and later room for live
spectating. Python remains authoritative for battle normalization, bot-domain calculations, and
bundle export; the desktop layer only renders versioned DTOs.

The technology choice must not force browser DOM compatibility, duplicate bot mechanics, or load
Python into the UI process. It must support Windows first, deterministic local fixtures, headless
tests, and a custom-rendered battle surface without requiring Pokémon artwork.

## Decision

Phase 0 uses **Godot 4.5.2** with typed GDScript.

- Godot renders an abstract battle board and ordinary `Control`-based desktop panels.
- Python exports canonical, read-only viewer bundles; Godot never imports bot Python modules.
- UI tests use gdUnit4 through its CLI in headless CI. The implementation plan pins a gdUnit4
  version after verifying compatibility with Godot 4.5.2.
- Engine upgrades are explicit changes. They require the viewer suite, mixed-DPI check,
  accessibility check, and this ADR to be reviewed again.

## Why this option

- The custom battle surface benefits from Godot's 2D rendering and input model.
- Docked analysis panels, keyboard navigation, themes, and future live presentation can share one
  scene and event model.
- Godot avoids shipping a general browser runtime solely to render a local developer tool.
- Typed GDScript keeps Phase 0 small while preserving a future GDExtension/process boundary if a
  measured bottleneck requires one.

## Alternatives considered

### Tauri or another web UI shell

Advantages: mature HTML accessibility, virtualized-list libraries, and familiar extension tooling.

Rejected for Phase 0 because it reintroduces a browser presentation stack and DOM-oriented design
pressure even though Chrome-extension compatibility is explicitly not a goal. It remains a valid
fallback if Godot cannot satisfy the measured accessibility or large-data gates.

### Qt/PySide

Advantages: mature desktop widgets, accessibility, native tables, and direct Python integration.

Rejected because direct Python/UI coupling conflicts with the stable bundle boundary, and the
custom battle surface would require a second rendering approach. Qt remains a fallback if the
Godot UI gates fail.

### Electron

Advantages: broad ecosystem and straightforward web reuse.

Rejected because its runtime footprint and DOM dependency do not buy capabilities needed by the
offline Phase 0 slice.

## Accepted consequences and mitigations

### Accessibility

Godot 4.5 introduced AccessKit-based screen-reader support but documents it as experimental.
Keyboard operation, visible focus, scaling, contrast, and text/icon alternatives to color are
binding Phase 0 release gates. Screen-reader support is tested and reported as best effort rather
than overstated as complete.

### Long collections

Godot does not provide a general customizable virtual-list control suitable for every Studio view.
Timeline, candidate, warning, and raw-evidence views therefore require bounded rendering,
pagination, or a reviewed recycling implementation. Instantiating one `Control` per unbounded row
is prohibited.

### Loading and parsing

Bundle reading, hashing, JSON parsing, and immutable DTO construction run outside the main UI
thread with progress and cancellation. Worker code never mutates the active scene tree. The
implementation plan must prove this boundary with a representative committed bundle.

### DPI and desktop scaling

Automatic DPI behavior differs by platform. Phase 0 includes a manual Windows check that moves the
window between monitors with different scale factors, plus a user-controlled 75%–200% override.

### Testing

gdUnit4 is the selected Godot test framework because it supports Godot 4, command-line execution,
and JUnit output. The framework version is an implementation pin, not a floating dependency.

## Revisit triggers

Reconsider the UI technology if any of these occurs:

- the representative bundle cannot load without UI stalls despite the approved worker boundary;
- bounded rendering cannot meet the measured timeline/table target;
- required keyboard or scaling behavior cannot be made reliable on the supported desktop target;
- accessibility requirements advance beyond what the pinned Godot line can support;
- a future full-client phase needs capabilities that materially conflict with the Phase 0
  architecture.

Reconsideration requires evidence from the acceptance suite, not preference alone.

## References

- [Godot 4.5 release notes](https://godotengine.org/releases/4.5/)
- [Godot thread-safe APIs](https://docs.godotengine.org/en/4.5/tutorials/performance/thread_safe_apis.html)
- [Godot multiple resolutions](https://docs.godotengine.org/en/4.5/tutorials/rendering/multiple_resolutions.html)
- [Godot virtual-scrolling proposal #9678](https://github.com/godotengine/godot-proposals/issues/9678)
- [Godot Tree performance issue #70869](https://github.com/godotengine/godot/issues/70869)
- [gdUnit4](https://github.com/godot-gdunit-labs/gdUnit4)
