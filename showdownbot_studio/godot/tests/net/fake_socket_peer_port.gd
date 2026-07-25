class_name FakeSocketPeerPort
extends SocketPeerPort

var connect_result: int = OK
var ready_state: SocketPeerPort.ReadyState = SocketPeerPort.ReadyState.CONNECTING
var queued_packets: Array[String] = []
var sent_texts: Array[String] = []
var connect_urls: Array[String] = []
var close_called: bool = false
var configured_heartbeat_intervals: Array[float] = []
var poll_count: int = 0
var _armed_ready_state: SocketPeerPort.ReadyState = SocketPeerPort.ReadyState.CONNECTING
var _has_armed_ready_state: bool = false


func connect_to_url(url: String) -> int:
	connect_urls.append(url)
	return connect_result


## Arms a one-shot ready_state transition that poll() applies on its NEXT call, simulating a
## real WebSocketPeer whose handshake completes only once actually polled (poll() is what
## pumps the underlying connection). Without this, the fake could never distinguish "the
## production code read a stale pre-poll ready state" from "it read the post-poll one".
func arm_ready_state_on_next_poll(state: SocketPeerPort.ReadyState) -> void:
	_armed_ready_state = state
	_has_armed_ready_state = true


func poll() -> void:
	poll_count += 1
	if _has_armed_ready_state:
		ready_state = _armed_ready_state
		_has_armed_ready_state = false


func get_ready_state() -> SocketPeerPort.ReadyState:
	return ready_state


func get_available_packet_count() -> int:
	return queued_packets.size()


func get_packet_string() -> String:
	return queued_packets.pop_front()


func send_text(text: String) -> int:
	sent_texts.append(text)
	return OK


func close(_code: int, _reason: String) -> void:
	close_called = true
	ready_state = SocketPeerPort.ReadyState.CLOSED


func configure_heartbeat_interval(seconds: float) -> void:
	configured_heartbeat_intervals.append(seconds)
