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


func test_heartbeat_interval_is_configured_on_every_new_peer() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	assert_int(_fake.configured_heartbeat_intervals.size()).is_equal(1)
	assert_float(_fake.configured_heartbeat_intervals[0]).is_equal(WebSocketTransport.HEARTBEAT_INTERVAL_S)


func test_heartbeat_interval_is_reconfigured_on_reconnect_reopen() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # -> RECONNECTING
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # reopens
	assert_int(_fake.configured_heartbeat_intervals.size()).is_equal(2)
