# UI panels (`godot/src/ui/panels/`)

## Purpose

Board, log, move choice, battle chat, and connection status panels. Renders via
`BoardPresentationAdapter`-style conversions; never produces protocol text directly, never
decides legality.

## Public interface

New (M1d):

- `LiveBoardPresentationAdapter`, `UntrustedTextSanitizer`.
- `BattleBoardPanel` — wraps `replay/AbstractBoardView` unchanged; `bind(live)`.
- `ConnectionStatusPanel` — `on_connection_state_changed(old_state, new_state)`.
- `LiveBattleLogPanel` — `rebuild_from_timeline(timeline: Array[ProtocolEventDTO])`; re-renders
  fully from the projection's timeline every time, never accumulates its own separate copy.
- `RoomEntryPanel` (Task 27) — direct room-ID/URL entry, no room browser; sends nothing itself —
  it holds a `SpectatorRoomGateway` (Task 28), injected, and calls it.
- `SpectatorRoomGateway` (Task 28) — the privileged command gateway for room join/leave (spec
  section 4.2.3).

## Dependencies

Depends on `battle/dto/LiveBattleSnapshot`, `protocol/dto/ProtocolEventDTO`,
`net/ConnectionStateMachine`, `protocol/ProtocolCommandEncoder`, `net/WebSocketTransport`, and
`replay/`'s `BattleBoardSnapshot`/`AbstractBoardView` (F0 contract, reused unchanged) as direct
dependencies; subscribes to `workspace/ObservationEventBus` for render-only notifications.

## Rule for future producers

A panel never assembles protocol text itself. `SpectatorRoomGateway` is the only object that
holds both an encoder call site and a transport reference for room commands, and it is injected
only into `RoomEntryPanel` — the same four bans spec section 4.2.3 states for
`HumanBattleCommandGateway` (never on the bus, never in a mod surface, never imported by
`replay/`/`battle/`/an analysis module, injected only into its one intended UI component).
