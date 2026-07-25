# Battle (`godot/src/battle/`)

## Purpose

Pure, deterministic, idempotent `LiveBattleReducer` producing structurally-immutable
`LiveBattleSnapshot` values from `protocol/`'s decoded event stream (spec section 4.7), and
`LiveBattleProjection`, the single owner of "current" derived state and its parallel event
timeline. Never contains UI nodes, never recomputes mechanics/damage/legality, never holds or
imports `HumanBattleCommandGateway`.

## Public interface

New (M1c):

- `battle/dto/LiveBattleSnapshot` / `LiveBattleSlotSnapshot` — structurally immutable (private
  backing fields, read-only-only properties, no setter anywhere).
- `LiveBattleReducer` — `static func apply(previous, event: ProtocolEventDTO) -> LiveBattleSnapshot`.
  Pure function.
- `LiveBattleProjection` — owns the current `LiveBattleSnapshot` and its parallel event timeline;
  `apply_event(event)`, `get_current_snapshot()`, `get_timeline()`. `workspace/`/`ui/panels/`
  never hold or compute derived battle state themselves — they only receive what this class
  publishes.

## Dependencies

Depends on `protocol/dto/ProtocolEventDTO` as a direct dependency. Never depends on `replay/`,
`ui/panels/`, `workspace/`, or `net/`.

## Rule for future producers

`LiveBattleSnapshot` has exactly one producer: `LiveBattleReducer.apply()`, called only from
`LiveBattleProjection.apply_event()`. A direct mutation of derived state from any other code is a
defect (`AGENTS.md` rule 5) — and, since M1c, is also a compile error, not just a review finding.
