class_name ObservationEventBus
extends RefCounted

## Carries only selected read-only observation events (spec section 4.2.2). Never carries
## battle commands, login/credential data, a mutable session object, or the raw ProtocolEventDTO
## stream. See schemas/observation-event-bus-v1.md for the full contract.

signal connection_state_changed(old_state: ConnectionStateMachine.State, new_state: ConnectionStateMachine.State)
signal battle_state_published(snapshot: LiveBattleSnapshot)
signal battle_completed(room_id: String)


func publish_connection_state_changed(old_state: ConnectionStateMachine.State, new_state: ConnectionStateMachine.State) -> void:
	connection_state_changed.emit(old_state, new_state)


func publish_battle_state_published(snapshot: LiveBattleSnapshot) -> void:
	battle_state_published.emit(snapshot)


func publish_battle_completed(room_id: String) -> void:
	battle_completed.emit(room_id)
