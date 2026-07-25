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


func test_cancel_connect_attempt_while_connecting_moves_to_disconnected_and_closes_peer() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_transport.cancel_connect_attempt()
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)
	assert_bool(_fake.close_called).is_true()
	assert_int(_transport.get_connection_epoch()).is_equal(1)  # cancel does not change the epoch


func test_cancel_connect_attempt_while_not_connecting_is_a_no_op() -> void:
	_transport.cancel_connect_attempt()
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


func test_connect_timeout_elapsing_moves_to_disconnected() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.CONNECTING  # handshake never completes
	_transport._process(WebSocketTransport.CONNECT_TIMEOUT_S + 0.1)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)
	assert_int(_transport.get_connection_epoch()).is_equal(1)  # timeout does not change the epoch


func test_handshake_succeeding_just_before_timeout_does_not_cancel() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(WebSocketTransport.CONNECT_TIMEOUT_S - 1.0)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)


func test_handshake_completing_on_the_same_frame_as_timeout_connects_instead_of_cancelling() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.CONNECTING  # not open until this frame's poll()
	_fake.arm_ready_state_on_next_poll(SocketPeerPort.ReadyState.OPEN)
	_transport._process(WebSocketTransport.CONNECT_TIMEOUT_S + 0.1)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)
