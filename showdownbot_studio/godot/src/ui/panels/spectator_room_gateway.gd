class_name SpectatorRoomGateway
extends SpectatorRoomGatewayPort

## Privileged command gateway for room join/leave (spec section 4.2.3's "narrowly scoped
## sibling" gateways -- the human-battle-command gateway's own architecture guard names only
## its own class, not this one; this file is a sibling gateway, not that gateway). Holds both
## net/'s transport and protocol/'s RoomStateMachine -- the only object in the application that
## does. Injected only into RoomEntryPanel (ui/panels/). Four bans, matching that sibling
## gateway's own (spec section 4.2.3): never registered on or discoverable through the
## ObservationEventBus; never part of any mod attachment surface; never imported by replay/,
## battle/, or any future analysis module; injected only into the intended UI component.
##
## Handles BOTH a human-clicked "Watch"/"Leave" and a system-triggered automatic reconnect
## rejoin (RoomStateMachine.automatic_rejoin_requested, emitted by M1e's Task 37) through the
## SAME send-and-check-failure code path -- this is the only object anywhere that ever calls
## send_raw_text() for a room command, regardless of what triggered it (owner re-review,
## 2026-07-25, second pass, item C). GDScript cannot enforce this at the language level --
## upheld by injection discipline and review, the same honesty note spec section 4.2.3 states
## for that sibling gateway.

var _transport: WebSocketTransport
var _room_state_machine: RoomStateMachine


func _init(transport: WebSocketTransport, room_state_machine: RoomStateMachine) -> void:
	_transport = transport
	_room_state_machine = room_state_machine
	_room_state_machine.automatic_rejoin_requested.connect(_on_automatic_rejoin_requested)


func join(intent: RoomJoinIntent) -> void:
	if not _room_state_machine.request_join(intent.room_id):
		return
	_send_join_command(intent.room_id)


func leave() -> void:
	var room_id := _room_state_machine.get_room_id()
	if not _room_state_machine.request_leave():
		return
	var err := _transport.send_raw_text(ProtocolCommandEncoder.encode_leave_room(room_id))
	if err != OK:
		_room_state_machine.leave_send_failed()


## System-triggered rejoin: RoomStateMachine has already transitioned ACTIVE -> JOINING itself
## (connection_reconnecting()), so no request_join() call is needed or valid here -- only the
## send, through the identical path a human join uses.
func _on_automatic_rejoin_requested(room_id: String) -> void:
	_send_join_command(room_id)


func _send_join_command(room_id: String) -> void:
	var err := _transport.send_raw_text(ProtocolCommandEncoder.encode_join_room(room_id))
	if err != OK:
		_room_state_machine.join_send_failed()
