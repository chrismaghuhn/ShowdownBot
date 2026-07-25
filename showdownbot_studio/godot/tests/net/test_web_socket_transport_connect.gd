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


func test_initial_state_is_disconnected() -> void:
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


func test_connect_to_server_moves_to_connecting_and_calls_peer() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTING)
	assert_int(_fake.connect_urls.size()).is_equal(1)
	assert_str(_fake.connect_urls[0]).is_equal("ws://localhost:8000/showdown/websocket")


func test_poll_detects_open_and_moves_to_connected() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)


func test_inbound_packets_are_emitted_in_order() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_fake.queued_packets = ["|turn|1", "|turn|2"]
	var received: Array[String] = []
	_transport.raw_text_received.connect(func(text: String): received.append(text))
	_transport._process(0.016)
	assert_int(received.size()).is_equal(2)
	assert_str(received[0]).is_equal("|turn|1")
	assert_str(received[1]).is_equal("|turn|2")


func test_disconnect_from_connected_calls_peer_close() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	_transport.disconnect_from_server()
	assert_bool(_fake.close_called).is_true()
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


func test_send_raw_text_while_connected_forwards_to_peer() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	assert_int(_transport.send_raw_text("|/join lobby")).is_equal(OK)
	assert_int(_fake.sent_texts.size()).is_equal(1)
	assert_str(_fake.sent_texts[0]).is_equal("|/join lobby")


func test_send_raw_text_while_disconnected_is_rejected() -> void:
	assert_int(_transport.send_raw_text("|/join lobby")).is_not_equal(OK)
	assert_int(_fake.sent_texts.size()).is_equal(0)
