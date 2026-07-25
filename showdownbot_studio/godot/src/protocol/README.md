# Protocol (`godot/src/protocol/`)

## Purpose

The only module permitted to decode inbound Showdown protocol text or encode outbound Showdown
protocol commands (spec section 4.1, `PROJECT_BOUNDARIES.md` section 4).

## Public interface

New (M1b):

- `protocol/dto/ProtocolEventDTO` — one decoded, `DECODED_STATE_EVENT`-classified protocol line.
- `RoomStateMachine` — pure-transition implementation of the `RoomState` table
  (`docs/architecture/LIVE_STATE_MACHINES.md`, 11 rows including the two local-send-failure
  edges), holding a `net/WebSocketTransport` reference from construction **only to observe** its
  `connection_state_changed` signal — this class never calls `send_raw_text()` and never
  references `ProtocolCommandEncoder`. M1e extends its (currently empty)
  `_on_connection_state_changed` handler to *emit* `automatic_rejoin_requested`, still without
  sending anything itself, so no composition root construction/wiring changes when that lands.
  `ui/panels/SpectatorRoomGateway` (M1d) is the sole sender for both a human-initiated join/leave
  and this system-initiated rejoin — it is the one that actually depends on `ProtocolCommandEncoder`
  and `net/WebSocketTransport.send_raw_text()`.
- `ProtocolDecoder` — three-way classification: `signal event_decoded(event: ProtocolEventDTO)`,
  `signal known_ignored_event(raw_line: String, message_type: String)`,
  `signal line_not_understood(raw_line: String)`; `decode_frame(raw_frame: String) -> void`.
- `ProtocolCommandEncoder` — `static func encode_join_room(room_id: String) -> String`,
  `static func encode_leave_room(room_id: String) -> String`.

## Dependencies

Depends on `net/` as a direct dependency: `ProtocolDecoder` receives raw text via composition-root
wiring, and `RoomStateMachine` holds a `net/WebSocketTransport` reference **only to observe**
`connection_state_changed` — it never sends anything. Nothing in `protocol/` calls
`send_raw_text()`; that call site lives in `ui/panels/SpectatorRoomGateway` (`ui/panels/`, M1d),
which depends on both `protocol/ProtocolCommandEncoder` and `net/WebSocketTransport` to actually
send an encoded command. `protocol/` never depends on `battle/`, `replay/`, `workspace/`, or
`ui/panels/`.

## Rule for future producers

Every new outbound command family (spec section 4.1.1) is encoded here, in
`ProtocolCommandEncoder` or a narrowly-scoped sibling — never assembled as a raw string anywhere
else. Every human-initiated command additionally reaches this encoder only through a privileged
command gateway living in `ui/panels/` (e.g. `SpectatorRoomGateway`, M1d) — `protocol/` itself
never decides whether a human is allowed to send a given command.
