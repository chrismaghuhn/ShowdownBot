# Replay (`godot/src/replay/`)

## Purpose

Reconstructs and renders board state from sealed replay evidence (`BundleDTO`/`ReplayDTO`), and
hosts the neutral board-presentation contract that decouples board rendering from any one data
source. This is the module named in `docs/architecture/MODULE_CATALOG.md`'s "Replay" row.

## Public interface

Existing (Phase 0):

- `BoardModel` — mutable, replay-specific board state (species/HP/status per slot, weather,
  terrain, turn, side/field conditions), built by replaying trusted `BattleEventDTO`s.
- `ReplayPresenter.build_board(bundle, replay, selected_entry_index) -> BoardModel` — replays
  events up to a timeline cursor into a fresh `BoardModel`.
- `ReplayWorkspace` — the scene-level controller wiring the timeline and board view together.
- `AbstractBoardView` — the board rendering scene/script.

New (F0, this refactor):

- `BattleBoardSnapshot` / `BattleBoardSlotSnapshot` — the neutral, read-only board-presentation
  contract (spec `2026-07-25-phase3-client-design.md` section 4.7). Typed value objects, not
  `BoardModel`: any producer (replay today, a live-battle adapter from M1d onward) converts its
  own state into this shape.
- `ReplayBoardPresentationAdapter.build_snapshot(board: BoardModel) -> BattleBoardSnapshot` —
  the only place that knows how to turn a `BoardModel` into a `BattleBoardSnapshot`, including the
  replay-specific empty-state text.

Data flow: `BundleDTO`/`ReplayDTO` → `ReplayPresenter.build_board()` → `BoardModel` →
`ReplayBoardPresentationAdapter.build_snapshot()` → `BattleBoardSnapshot` → `AbstractBoardView.bind()`.

Since F0, `AbstractBoardView` renders **only** via `bind(snapshot: BattleBoardSnapshot)`. It has
no knowledge of `BoardModel`, `has_replay`, or any replay-specific wording — those concerns live
entirely in `ReplayBoardPresentationAdapter`.

## Dependencies

Depends on `bundle/` DTOs (`BundleDTO`, `ReplayDTO`, `BattleEventDTO`, `TimelineEntryDTO`) for
sealed replay evidence, and on `timeline/` for the selection cursor driving `ReplayWorkspace`.
Never imports `HumanBattleCommandGateway` or any privileged-command type (AGENTS.md rule 3/the
two-pipelines contract) — this module only ever reads recorded/derived state.

## Rule for future producers

Any future live-battle code (M1d onward) that wants to drive `AbstractBoardView` must build its
own adapter that produces a `BattleBoardSnapshot` — never reuse or reach into `BoardModel`, and
never bind the view to anything but a `BattleBoardSnapshot`. `BoardModel` stays a replay-only
implementation detail behind `ReplayBoardPresentationAdapter`.
