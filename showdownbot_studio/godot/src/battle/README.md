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
- `LiveBattleProjection` reset-on-repeat-`init` (M1e, spec section 6.2): a second `event_type ==
  "init"` whose `condition_label == "battle"` (i.e. a genuine repeat battle init, not this
  projection's own first one) discards the current snapshot and the entire timeline and starts
  folding from scratch — real Showdown's own signal that a reconnect resend of authoritative room
  history is starting over. Gated internally on `condition_label == "battle"`: a non-battle init
  (e.g. a room's own `"chat"` init) is a complete no-op for the reset path and falls through to
  the normal not-applied/ignored handling instead — `apply_event()` never trusts a caller to have
  already filtered this (`AGENTS.md` rule 10), even though `workspace/`'s own event routing
  already does. No content-based protocol-line deduplication exists anywhere; full reset and
  authoritative refolding is the only rebuild model.

## Dependencies

Depends on `protocol/dto/ProtocolEventDTO` as a direct dependency. Never depends on `replay/`,
`ui/panels/`, `workspace/`, or `net/`.

## Rule for future producers

`LiveBattleSnapshot` has exactly one producer: `LiveBattleReducer.apply()`, called only from
`LiveBattleProjection.apply_event()`. A direct mutation of derived state from any other code is a
defect (`AGENTS.md` rule 5) — and, since M1c, is also a compile error, not just a review finding.
