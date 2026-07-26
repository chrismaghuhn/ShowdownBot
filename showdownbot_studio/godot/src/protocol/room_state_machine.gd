class_name RoomStateMachine
extends RefCounted

## Pure-transition implementation of the RoomState table (docs/architecture/LIVE_STATE_MACHINES.md,
## 11 rows including the two local-send-failure edges, this plan's Task 1). Holds a
## WebSocketTransport reference from construction ONLY to observe its connection_state_changed
## signal -- this class never calls send_raw_text() or references ProtocolCommandEncoder
## (owner re-review, 2026-07-25, second pass, item C). M1e (Task 37) extends
## _on_connection_state_changed to EMIT automatic_rejoin_requested, never to send anything
## itself, so that task stays a pure protocol/ file edit with zero change to how any
## composition root constructs or wires this class.

enum State { NOT_JOINED, JOINING, ACTIVE, LEAVING, CLOSED }

signal state_changed(old_state: State, new_state: State)
## Emitted by M1e's extension of _on_connection_state_changed (Task 37) when a reconnect
## succeeds while this room was mid-rejoin. protocol/ never sends anything itself in reaction
## to this signal; ui/panels/SpectatorRoomGateway (Task 28) is the sole subscriber and the sole
## sender, for both a human-initiated join and this system-initiated one.
signal automatic_rejoin_requested(room_id: String)

var _state: State = State.NOT_JOINED
var _room_id: String = ""
var _last_error_reason: String = ""
var _transport: WebSocketTransport


func _init(transport: WebSocketTransport) -> void:
	_transport = transport
	_transport.connection_state_changed.connect(_on_connection_state_changed)


func get_state() -> State:
	return _state


func get_room_id() -> String:
	return _room_id


func get_last_error_reason() -> String:
	return _last_error_reason


func request_join(room_id: String) -> bool:
	if _state != State.NOT_JOINED:
		return false
	_room_id = room_id
	_transition(State.JOINING)
	return true


func join_confirmed() -> bool:
	if _state != State.JOINING:
		return false
	_transition(State.ACTIVE)
	return true


## Alias of join_confirmed(), same precondition and destination -- named separately so a caller's
## own code distinguishes "first join" from "rejoin after reconnect" even though both are valid
## only from JOINING and land on ACTIVE identically.
func rejoin_confirmed() -> bool:
	return join_confirmed()


func join_rejected(reason: String = "") -> bool:
	if _state != State.JOINING:
		return false
	_last_error_reason = reason
	_transition(State.NOT_JOINED)
	return true


## New edge (Task 1, owner-approved 2026-07-25): the /join command itself could not be sent (e.g.
## the connection dropped between "Watch" being pressed and the command reaching the socket) --
## distinct from the server actively rejecting a join it received.
func join_send_failed() -> bool:
	if _state != State.JOINING:
		return false
	_last_error_reason = "Could not send the join request (not connected)"
	_transition(State.NOT_JOINED)
	return true


func request_leave() -> bool:
	if _state != State.ACTIVE:
		return false
	_transition(State.LEAVING)
	return true


func leave_confirmed() -> bool:
	if _state != State.LEAVING:
		return false
	_transition(State.NOT_JOINED)
	return true


## New edge (Task 1, owner-approved 2026-07-25, second pass): the /leave command itself could
## not be sent. Returns to ACTIVE, not NOT_JOINED -- the room is still joined; the leave simply
## didn't happen. Symmetric with join_send_failed().
func leave_send_failed() -> bool:
	if _state != State.LEAVING:
		return false
	_last_error_reason = "Could not send the leave request (not connected)"
	_transition(State.ACTIVE)
	return true


## Real room closure only -- driven by a decoded `deinit` event, never by win/tie (spec section
## 6.1's fail-closed table; win/tie end the BATTLE, not the room -- see this plan's M1d fixes).
func server_closed_room() -> bool:
	if _state != State.ACTIVE:
		return false
	_transition(State.CLOSED)
	return true


func dismiss_closed_room() -> bool:
	if _state != State.CLOSED:
		return false
	_transition(State.NOT_JOINED)
	return true


func connection_reconnecting() -> bool:
	if _state != State.ACTIVE:
		return false
	_transition(State.JOINING)
	return true


func _transition(new_state: State) -> void:
	var old_state := _state
	_state = new_state
	if new_state == State.NOT_JOINED:
		_room_id = ""
	state_changed.emit(old_state, new_state)


## M1e: emits automatic_rejoin_requested after a successful reconnect (spec section 6.2) --
## system-triggered, distinct from a human-initiated join. This class never sends anything
## itself; ui/panels/SpectatorRoomGateway (subscribed since M1d's Task 28) is the sole sender
## for both this signal and a human-clicked "Watch" (owner re-review, 2026-07-25, second pass,
## item C) -- so this task is a pure protocol/ file edit, never touching ui/panels/ again.
func _on_connection_state_changed(_old_state: ConnectionStateMachine.State, new_state: ConnectionStateMachine.State) -> void:
	if new_state == ConnectionStateMachine.State.RECONNECTING and _state == State.ACTIVE:
		connection_reconnecting()
		return
	if new_state == ConnectionStateMachine.State.CONNECTED and _state == State.JOINING and not _room_id.is_empty():
		automatic_rejoin_requested.emit(_room_id)
