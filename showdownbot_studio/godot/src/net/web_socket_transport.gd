class_name WebSocketTransport
extends Node

## Connects to the Showdown server, tracks ConnectionState, and passes inbound frames through
## unmodified for protocol/ (M1b) to decode. This task is deliberately minimal: connect/
## disconnect/passthrough only. Tasks 5-8 add connection_epoch, connect-timeout/cancel, reconnect
## backoff, and heartbeat configuration, each with its own failing test first.

signal connection_state_changed(old_state: ConnectionStateMachine.State, new_state: ConnectionStateMachine.State)
signal raw_text_received(text: String)

const CONNECT_TIMEOUT_S := 15.0
const RECONNECT_BACKOFF_SCHEDULE_S: Array[float] = [1.0, 2.0, 5.0, 10.0, 20.0]
const HEARTBEAT_INTERVAL_S := 20.0

var _peer: SocketPeerPort
var _state_machine := ConnectionStateMachine.new()
var _peer_factory: Callable
var _url: String = ""
var _connection_epoch: int = 0
var _connecting_elapsed_s: float = 0.0
var _reconnect_attempt: int = 0
var _reconnect_timer_s: float = 0.0
## True from the moment a reconnect attempt's _open_socket() call returns until that attempt
## resolves (peer opens or closes) or a new attempt is scheduled. Without this flag, the
## RECONNECTING branch of _process() re-fires every frame once the backoff timer is <= 0.0,
## discarding the in-flight peer and opening a brand-new one forever -- the bug this task fixes.
var _reconnect_attempt_in_flight: bool = false


func _init(peer_factory: Callable = Callable()) -> void:
	_peer_factory = peer_factory if peer_factory.is_valid() else Callable(self, "_make_default_peer")
	_state_machine.state_changed.connect(_on_state_changed)


func _make_default_peer() -> SocketPeerPort:
	return GodotSocketPeerAdapter.new()


func get_state() -> ConnectionStateMachine.State:
	return _state_machine.get_state()


## Incremented on every connect_to_server() and every successful reconnect (Task 7). Spec
## section 6.2/section 7 binds every outbound battle action to this counter; M1 sends no
## /choose, so nothing besides this class's own tests reads it yet, but net/ is the only module
## that can correctly own it.
func get_connection_epoch() -> int:
	return _connection_epoch


func connect_to_server(url: String) -> void:
	if not _state_machine.request_connect():
		return
	_url = url
	_connection_epoch += 1
	_connecting_elapsed_s = 0.0
	_open_socket()


func disconnect_from_server() -> void:
	if not _state_machine.request_disconnect():
		return
	if _peer != null:
		_peer.close(1000, "client disconnect")
	_peer = null


func send_raw_text(text: String) -> int:
	if _peer == null or _state_machine.get_state() != ConnectionStateMachine.State.CONNECTED:
		return ERR_UNCONFIGURED
	return _peer.send_text(text)


## Explicit user-initiated cancel of a pending connection attempt (LIVE_STATE_MACHINES.md's
## CONNECTING -> DISCONNECTED edge, Task 1). A no-op outside CONNECTING.
func cancel_connect_attempt() -> void:
	if not _state_machine.cancel_connect():
		return
	if _peer != null:
		_peer.close(1000, "connect attempt cancelled")
	_peer = null


func _advance_after_failed_attempt() -> void:
	_reconnect_attempt_in_flight = false
	if _state_machine.get_state() == ConnectionStateMachine.State.CONNECTING:
		_state_machine.initial_attempt_failed_retries_remain()
	else:
		_state_machine.reconnect_failed_retries_remain()
	_schedule_next_attempt()


func _schedule_next_attempt() -> void:
	if _reconnect_attempt >= RECONNECT_BACKOFF_SCHEDULE_S.size():
		_state_machine.backoff_exhausted()
		return
	_reconnect_timer_s = RECONNECT_BACKOFF_SCHEDULE_S[_reconnect_attempt]
	_reconnect_attempt += 1


func _open_socket() -> void:
	_peer = _peer_factory.call()
	_peer.configure_heartbeat_interval(HEARTBEAT_INTERVAL_S)
	var err: int = _peer.connect_to_url(_url)
	if err != OK:
		_advance_after_failed_attempt()


func _process(delta: float) -> void:
	if _state_machine.get_state() == ConnectionStateMachine.State.RECONNECTING:
		if not _reconnect_attempt_in_flight:
			_reconnect_timer_s -= delta
			if _reconnect_timer_s <= 0.0:
				_reconnect_attempt_in_flight = true
				_connection_epoch += 1
				_open_socket()
			return
		# An attempt is already in flight for this backoff period: fall through to poll it,
		# exactly like the CONNECTING branch below -- never open a second peer for it.
	elif _state_machine.get_state() == ConnectionStateMachine.State.CONNECTING:
		_connecting_elapsed_s += delta
		if _connecting_elapsed_s >= CONNECT_TIMEOUT_S and _peer.get_ready_state() != SocketPeerPort.ReadyState.OPEN:
			cancel_connect_attempt()
			return
	if _peer == null:
		return
	_peer.poll()
	var ready := _peer.get_ready_state()
	if ready == SocketPeerPort.ReadyState.OPEN:
		_reconnect_attempt_in_flight = false
		_on_peer_open()
	elif ready == SocketPeerPort.ReadyState.CLOSED:
		_reconnect_attempt_in_flight = false
		_on_peer_closed()


func _on_peer_open() -> void:
	if _state_machine.get_state() == ConnectionStateMachine.State.CONNECTING:
		_state_machine.handshake_succeeded()
		_reconnect_attempt = 0
	elif _state_machine.get_state() == ConnectionStateMachine.State.RECONNECTING:
		_state_machine.reconnect_succeeded()
		_reconnect_attempt = 0
	while _peer.get_available_packet_count() > 0:
		raw_text_received.emit(_peer.get_packet_string())


func _on_peer_closed() -> void:
	if _state_machine.get_state() == ConnectionStateMachine.State.CONNECTED:
		_state_machine.connection_lost_retries_remain()
		_schedule_next_attempt()
	elif _state_machine.get_state() == ConnectionStateMachine.State.CONNECTING:
		_advance_after_failed_attempt()
	elif _state_machine.get_state() == ConnectionStateMachine.State.RECONNECTING:
		_advance_after_failed_attempt()


func _on_state_changed(old_state: ConnectionStateMachine.State, new_state: ConnectionStateMachine.State) -> void:
	connection_state_changed.emit(old_state, new_state)
