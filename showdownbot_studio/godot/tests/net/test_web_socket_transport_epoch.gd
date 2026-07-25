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


func test_epoch_starts_at_zero() -> void:
	assert_int(_transport.get_connection_epoch()).is_equal(0)


func test_epoch_increments_to_one_on_first_connect() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	assert_int(_transport.get_connection_epoch()).is_equal(1)


func test_epoch_does_not_change_while_staying_connected() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	var epoch_before := _transport.get_connection_epoch()
	_fake.queued_packets = ["|turn|1"]
	_transport._process(0.016)
	assert_int(_transport.get_connection_epoch()).is_equal(epoch_before)
