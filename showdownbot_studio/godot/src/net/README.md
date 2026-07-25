# Net (`godot/src/net/`)

## Purpose

Owns the WebSocket connection to the Showdown server and its connection-lifetime state. Never
parses or encodes protocol text, never holds battle state, never holds `CredentialProvider` state.

## Public interface

New (M1a):

- `ConnectionStateMachine` — pure implementation of the `ConnectionState` transition table
  (`docs/architecture/LIVE_STATE_MACHINES.md`, 12 rows). `signal state_changed(old_state, new_state)`.
- `SocketPeerPort` / `GodotSocketPeerAdapter` — the seam between `WebSocketTransport` and the real
  socket, including heartbeat configuration (`configure_heartbeat_interval`).
- `WebSocketTransport` — connects, disconnects, cancels a pending connect, reconnects with
  backoff, configures the engine's own ping/pong heartbeat. `signal connection_state_changed`;
  `signal raw_text_received(text: String)`.

## Dependencies

Depends on nothing outside this module. `protocol/` depends on `net/` directly (receives raw
text, sends encoded commands); `net/` never depends on `protocol/`.

## Rule for future producers

`net/` never gains knowledge of protocol message shapes, room state, or battle state.
