class_name SocketPeerPort
extends RefCounted

## Thin seam between WebSocketTransport and the actual socket implementation, so
## WebSocketTransport's logic is unit-testable without a live socket (a GDScript file cannot
## subclass the engine's native WebSocketPeer and override its native methods).
## GodotSocketPeerAdapter wraps the real WebSocketPeer for production; gdUnit test doubles
## extend this class directly (a plain script class, fully overridable).

enum ReadyState { CONNECTING, OPEN, CLOSING, CLOSED }


func connect_to_url(_url: String) -> int:
	push_error("SocketPeerPort.connect_to_url is abstract")
	return ERR_UNAVAILABLE


func poll() -> void:
	pass


func get_ready_state() -> ReadyState:
	return ReadyState.CLOSED


func get_available_packet_count() -> int:
	return 0


func get_packet_string() -> String:
	return ""


func send_text(_text: String) -> int:
	push_error("SocketPeerPort.send_text is abstract")
	return ERR_UNAVAILABLE


func close(_code: int, _reason: String) -> void:
	pass


## Configures the engine's periodic WebSocket ping (Godot 4.5's WebSocketPeer.heartbeat_interval).
## Godot's own documentation guarantees only that a ping control frame is sent automatically at
## this interval -- NOT that a missing pong closes the connection within any defined window; this
## plan does not claim more than the engine documents. See this plan's M1a design note for why the
## earlier idle-timeout heuristic was wrong (a quiet battle is not a dead one) and for what this
## plan actually relies on to prove liveness (Tasks 7/36's reconnect tests).
func configure_heartbeat_interval(_seconds: float) -> void:
	pass
