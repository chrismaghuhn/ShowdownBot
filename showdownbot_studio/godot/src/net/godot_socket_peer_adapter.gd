class_name GodotSocketPeerAdapter
extends SocketPeerPort

var _peer := WebSocketPeer.new()


func connect_to_url(url: String) -> int:
	return _peer.connect_to_url(url)


func poll() -> void:
	_peer.poll()


func get_ready_state() -> SocketPeerPort.ReadyState:
	match _peer.get_ready_state():
		WebSocketPeer.STATE_CONNECTING:
			return SocketPeerPort.ReadyState.CONNECTING
		WebSocketPeer.STATE_OPEN:
			return SocketPeerPort.ReadyState.OPEN
		WebSocketPeer.STATE_CLOSING:
			return SocketPeerPort.ReadyState.CLOSING
		_:
			return SocketPeerPort.ReadyState.CLOSED


func get_available_packet_count() -> int:
	return _peer.get_available_packet_count()


func get_packet_string() -> String:
	return _peer.get_packet().get_string_from_utf8()


func send_text(text: String) -> int:
	return _peer.send_text(text)


func close(code: int, reason: String) -> void:
	_peer.close(code, reason)


func configure_heartbeat_interval(seconds: float) -> void:
	_peer.heartbeat_interval = seconds
