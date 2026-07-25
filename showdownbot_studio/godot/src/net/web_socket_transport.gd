class_name WebSocketTransport
extends Node

## Connects to the Showdown server, tracks ConnectionState, and passes inbound frames through
## unmodified for protocol/ (M1b) to decode. This task is deliberately minimal: connect/
## disconnect/passthrough only. Tasks 5-8 add connection_epoch, connect-timeout/cancel, reconnect
## backoff, and heartbeat configuration, each with its own failing test first.

signal connection_state_changed(old_state: ConnectionStateMachine.State, new_state: ConnectionStateMachine.State)
signal raw_text_received(text: String)

var _peer: SocketPeerPort
var _state_machine := ConnectionStateMachine.new()
var _peer_factory: Callable
var _url: String = ""


func _init(peer_factory: Callable = Callable()) -> void:
	_peer_factory = peer_factory if peer_factory.is_valid() else Callable(self, "_make_default_peer")
	_state_machine.state_changed.connect(_on_state_changed)


func _make_default_peer() -> SocketPeerPort:
	return GodotSocketPeerAdapter.new()


func get_state() -> ConnectionStateMachine.State:
	return _state_machine.get_state()


func connect_to_server(url: String) -> void:
	if not _state_machine.request_connect():
		return
	_url = url
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


func _open_socket() -> void:
	_peer = _peer_factory.call()
	_peer.connect_to_url(_url)


func _process(_delta: float) -> void:
	if _peer == null:
		return
	_peer.poll()
	var ready := _peer.get_ready_state()
	if ready == SocketPeerPort.ReadyState.OPEN:
		_on_peer_open()


func _on_peer_open() -> void:
	if _state_machine.get_state() == ConnectionStateMachine.State.CONNECTING:
		_state_machine.handshake_succeeded()
	while _peer.get_available_packet_count() > 0:
		raw_text_received.emit(_peer.get_packet_string())


func _on_state_changed(old_state: ConnectionStateMachine.State, new_state: ConnectionStateMachine.State) -> void:
	connection_state_changed.emit(old_state, new_state)
