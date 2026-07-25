# ObservationEventBus events — schema v1

**Status:** binding (spec section 4.2.2). **Introduced:** M1d.
`schema_version: {major: 1, minor: 0}`.

| Event | Payload | Publisher | Subscribers (M1) |
|---|---|---|---|
| `connection_state_changed` | `old_state`, `new_state: ConnectionStateMachine.State` | `workspace/`'s composition root, republishing `net/WebSocketTransport.connection_state_changed` | `ui/panels/ConnectionStatusPanel` |
| `battle_state_published` | `snapshot: LiveBattleSnapshot` | `workspace/`'s composition root, republishing `battle/LiveBattleProjection.snapshot_published` | `ui/panels/BattleBoardPanel`, `ui/panels/LiveBattleLogPanel` |
| `battle_completed` | `room_id: String` | same composition root, republishing `battle/LiveBattleProjection.battle_completed` | reserved for a future replay-save prompt (M3, not built here) |
| `chat_received` | not populated in M1 (no chat UI until M2f) | — | — |

Never carries: battle commands, login/credential data, a mutable session object, or the raw
`ProtocolEventDTO` stream.
