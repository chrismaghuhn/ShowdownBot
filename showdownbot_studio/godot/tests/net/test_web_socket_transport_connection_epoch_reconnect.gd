extends GdUnitTestSuite

var _fake: FakeSocketPeerPort
var _transport: WebSocketTransport


func before_test() -> void:
	_fake = FakeSocketPeerPort.new()
	_transport = WebSocketTransport.new(func(): return _fake)
	add_child(_transport)


func after_test() -> void:
	remove_child(_transport)
	_transport.free()


func test_epoch_does_not_change_while_staying_connected_and_receiving_traffic() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	var epoch_before := _transport.get_connection_epoch()
	_fake.queued_packets = ["|turn|1"]
	_transport._process(0.016)
	assert_int(_transport.get_connection_epoch()).is_equal(epoch_before)


func test_epoch_increments_exactly_once_per_full_reconnect_cycle() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	var epoch_after_initial := _transport.get_connection_epoch()
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # -> RECONNECTING
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # reopens
	assert_int(_transport.get_connection_epoch()).is_equal(epoch_after_initial + 1)
