# Protocol (`godot/src/protocol/`)

## Purpose

The only module permitted to decode inbound Showdown protocol text or encode outbound Showdown
protocol commands (spec section 4.1, `PROJECT_BOUNDARIES.md` section 4).

## Public interface

New (M1b):

- `protocol/dto/ProtocolEventDTO` — one decoded, `DECODED_STATE_EVENT`-classified protocol line.
- `RoomStateMachine` — pure-transition implementation of the `RoomState` table
  (`docs/architecture/LIVE_STATE_MACHINES.md`, 11 rows including the local-send-failure edge),
  holding a `net/WebSocketTransport` reference from construction (this module already depends on
  `net/` for sending encoded commands) so M1e can add automatic-reconnect-rejoin behavior without
  changing how any composition root constructs or wires it.
- `ProtocolDecoder` — three-way classification: `signal event_decoded(event: ProtocolEventDTO)`,
  `signal known_ignored_event(raw_line: String, message_type: String)`,
  `signal line_not_understood(raw_line: String)`; `decode_frame(raw_frame: String) -> void`.
- `ProtocolCommandEncoder` — `static func encode_join_room(room_id: String) -> String`,
  `static func encode_leave_room(room_id: String) -> String`.

## Dependencies

Depends on `net/` as a direct dependency (receives raw text via composition-root wiring, sends
encoded commands via a held `WebSocketTransport` reference in `RoomStateMachine`). Never depends
on `battle/`, `replay/`, `workspace/`, or `ui/panels/`.

## Rule for future producers

Every new outbound command family (spec section 4.1.1) is encoded here, in
`ProtocolCommandEncoder` or a narrowly-scoped sibling — never assembled as a raw string anywhere
else. Every human-initiated command additionally reaches this encoder only through a privileged
command gateway living in `ui/panels/` (e.g. `SpectatorRoomGateway`, M1d) — `protocol/` itself
never decides whether a human is allowed to send a given command.
