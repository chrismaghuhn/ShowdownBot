class_name FakeSocketPeerPort
extends SocketPeerPort

var connect_result: int = OK
var ready_state: SocketPeerPort.ReadyState = SocketPeerPort.ReadyState.CONNECTING
var queued_packets: Array[String] = []
var sent_texts: Array[String] = []
var connect_urls: Array[String] = []
var close_called: bool = false
var configured_heartbeat_intervals: Array[float] = []


func connect_to_url(url: String) -> int:
	connect_urls.append(url)
	return connect_result


func poll() -> void:
	pass


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
