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


# -- Owner finding 2 (M1 hardening, 2026-07-26): CONNECT_TIMEOUT_S was only ever evaluated in
# state CONNECTING. A reconnect peer that never resolves (stays CONNECTING forever) was polled
# every frame indefinitely while RECONNECTING -- no timeout, no next backoff, EXHAUSTED never
# reachable via a hung handshake. --


func test_reconnect_peer_stuck_connecting_past_timeout_schedules_next_backoff() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # initial attempt fails synchronously -> RECONNECTING, backoff[0] scheduled
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)
	_fake.ready_state = SocketPeerPort.ReadyState.CONNECTING  # reconnect peer opens but hangs mid-handshake
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # opens the reconnect peer
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)
	# BUGGY behavior: the peer is polled forever, never times out, RECONNECTING never advances --
	# even after CONNECT_TIMEOUT_S has clearly elapsed for this in-flight attempt.
	_transport._process(WebSocketTransport.CONNECT_TIMEOUT_S + 0.1)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)
	var urls_before := _fake.connect_urls.size()
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[1] + 0.1)
	assert_int(_fake.connect_urls.size()).is_equal(urls_before + 1)  # next backoff's reopen actually fired


func test_reconnect_peer_stuck_connecting_can_reach_exhaustion() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # initial attempt fails -> RECONNECTING
	for i in WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S.size():
		assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)
		_fake.ready_state = SocketPeerPort.ReadyState.CONNECTING
		_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[i] + 0.1)  # opens the peer
		_transport._process(WebSocketTransport.CONNECT_TIMEOUT_S + 0.1)  # it hangs past the timeout
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.EXHAUSTED)
