# Viewer v0 — Plan C: Replay and Timeline (Sketch)

**Status:** DRAFT — sketch only; **implementation not authorized**
**Date:** 2026-07-21
**Depends on:** Plan B loader + fixtures 1, 4, 5
**Unblocks:** Plan D (decision placement on timeline), Plan E (state banner coupling)

**Authority:** [`../specs/viewer-v0-design.md`](../specs/viewer-v0-design.md) §5.3–5.4 / §6.1,
bundle contract §10.3 / §11.3

## Goal

Render an abstract, sprite-independent doubles board and a synchronized timeline ordered by
`protocol_index`, placing decisions by `request_protocol_index` without simulating mechanics.

## Non-goals

- No candidate table (Plan D)
- No Pokémon artwork
- No what-if / takeover / simulator resume
- No inventing field state in trace-only mode

## Architecture

```text
BattleEvent DTOs + Decision DTOs
  → BattleTimeline (ordered entries)
  → ReplayPresenter (abstract board from recorded events only)
  → play/pause / step controls
```

Join rule (binding): order by `protocol_index`; place a decision immediately after the last event
with `protocol_index < request_protocol_index`. Null `request_protocol_index` → distinct timeline
entry with no replay event. Never join by row adjacency alone.

## Proposed files

| Path | Responsibility |
|---|---|
| `godot/src/timeline/battle_timeline.gd` | Build ordered entries; modes |
| `godot/src/timeline/timeline_view.tscn` | Scrollable bounded list |
| `godot/src/replay/abstract_board.tscn` | Text/HP/status/field chips |
| `godot/src/replay/replay_presenter.gd` | Apply recorded events to board model |
| `godot/src/replay/board_model.gd` | Presentation state only |

## Task sketch

### C1 — Timeline model

- [ ] Merge events + decisions per §11.3.3
- [ ] Distinct entry types: event, decision, decision-without-replay-event
- [ ] Phases visually distinct later via banner (Plan E); model carries `decision_phase`
- [ ] Trace-only: decisions only; no board claims
- [ ] Replay-only: events only; no candidate claims

### C2 — Bounded timeline view

- [ ] Pagination or recycling — no Control per unbounded row
- [ ] Keyboard prev/next entry (bindings finalized in Plan E)
- [ ] Selection sync signal for board + later decision panel

### C3 — Abstract board

- [ ] Sides, slots, species labels, HP bars, status chips, weather/terrain/side conditions
- [ ] Project-owned semantic type icons only
- [ ] Fully understandable with artwork disabled (acceptance)
- [ ] Trace-only: board hidden or empty with explicit “no replay” state — no simulated state

### C4 — Playback

- [ ] Step / play / pause driven by timeline selection
- [ ] No animation may hide degraded or missing data
- [ ] Malformed recoverable events follow exporter classification only

## Acceptance (Plan C done)

- Fixture 1: navigate turn/decision entries; board updates from recorded events only
- Fixture 4: replay-only — no decision panel claims
- Fixture 5: trace-only — no board simulation
- Fixture 17/19 behaviors visible when those fixtures exist (gaps + unjoined decisions)
- Timeline remains usable with long battles via bounded rendering

## Visual input

Follow [`../design/viewer-v0-mockups/README.md`](../design/viewer-v0-mockups/README.md) direction and
binding corrections (offline fonts deferred to Plan E; platform shortcut labels deferred to Plan E).
