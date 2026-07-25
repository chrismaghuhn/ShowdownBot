class_name ConnectionStateMachine
extends RefCounted

## Pure, dependency-free implementation of the ConnectionState transition table
## (docs/architecture/LIVE_STATE_MACHINES.md, 12 rows including the CONNECTING -> DISCONNECTED
## cancel/timeout edge added by this plan's Task 1, owner-approved 2026-07-25). One public
## method per named trigger; a call from a disallowed source state returns false and emits
## nothing.

enum State { DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING, EXHAUSTED }

signal state_changed(old_state: State, new_state: State)

var _state: State = State.DISCONNECTED


func get_state() -> State:
	return _state


## DISCONNECTED --user/app connect--> CONNECTING; EXHAUSTED --user manually retries--> CONNECTING.
func request_connect() -> bool:
	if _state != State.DISCONNECTED and _state != State.EXHAUSTED:
		return false
	_transition(State.CONNECTING)
	return true


## CONNECTING --WebSocket handshake succeeds--> CONNECTED.
func handshake_succeeded() -> bool:
	if _state != State.CONNECTING:
		return false
	_transition(State.CONNECTED)
	return true


## CONNECTING --initial connection attempt fails, retries remain--> RECONNECTING.
func initial_attempt_failed_retries_remain() -> bool:
	if _state != State.CONNECTING:
		return false
	_transition(State.RECONNECTING)
	return true


## CONNECTING --user cancels, or a connect timeout elapses--> DISCONNECTED (Task 1's added edge).
func cancel_connect() -> bool:
	if _state != State.CONNECTING:
		return false
	_transition(State.DISCONNECTED)
	return true


## CONNECTED --socket closes unexpectedly--> RECONNECTING (the engine's own ping/pong, Task 5,
## is what surfaces "unexpectedly" as a closed ready-state; this class has no timer of its own).
func connection_lost_retries_remain() -> bool:
	if _state != State.CONNECTED:
		return false
	_transition(State.RECONNECTING)
	return true


## CONNECTED / RECONNECTING / EXHAUSTED --user explicit disconnect--> DISCONNECTED.
func request_disconnect() -> bool:
	if _state != State.CONNECTED and _state != State.RECONNECTING and _state != State.EXHAUSTED:
		return false
	_transition(State.DISCONNECTED)
	return true


## RECONNECTING --a reconnect attempt succeeds--> CONNECTED.
func reconnect_succeeded() -> bool:
	if _state != State.RECONNECTING:
		return false
	_transition(State.CONNECTED)
	return true


## RECONNECTING --a reconnect attempt fails, retries remain--> RECONNECTING (self-transition;
## still emits so a listening UI can refresh its backoff countdown).
func reconnect_failed_retries_remain() -> bool:
	if _state != State.RECONNECTING:
		return false
	_transition(State.RECONNECTING)
	return true


## RECONNECTING --backoff attempts exhausted--> EXHAUSTED.
func backoff_exhausted() -> bool:
	if _state != State.RECONNECTING:
		return false
	_transition(State.EXHAUSTED)
	return true


func _transition(new_state: State) -> void:
	var old_state := _state
	_state = new_state
	state_changed.emit(old_state, new_state)


static func describe(state: State) -> String:
	match state:
		State.DISCONNECTED:
			return "Disconnected"
		State.CONNECTING:
			return "Connecting..."
		State.CONNECTED:
			return "Connected"
		State.RECONNECTING:
			return "Reconnecting..."
		State.EXHAUSTED:
			return "Disconnected"
		_:
			return "Unknown"
