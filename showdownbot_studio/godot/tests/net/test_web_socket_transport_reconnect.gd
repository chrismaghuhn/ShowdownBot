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


func test_unexpected_close_while_connected_moves_to_reconnecting() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)


func test_reconnect_reopens_socket_after_backoff_elapses() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # CONNECTING -> RECONNECTING (initial attempt failed)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)
	var urls_before := _fake.connect_urls.size()
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)
	assert_int(_fake.connect_urls.size()).is_equal(urls_before + 1)


func test_repeated_failures_exhaust_backoff_schedule() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.connect_result = ERR_CANT_CONNECT
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # attempt 1 fails -> RECONNECTING
	for backoff_s in WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S:
		assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)
		_transport._process(backoff_s + 0.1)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.EXHAUSTED)
	# 1 initial connect + 5 reopen attempts (one per RECONNECT_BACKOFF_SCHEDULE_S entry) = 6;
	# reaching EXHAUSTED itself adds no further increment beyond the last reopen's own.
	assert_int(_transport.get_connection_epoch()).is_equal(6)


func test_process_after_exhausted_does_not_poll_the_old_peer() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.connect_result = ERR_CANT_CONNECT
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # attempt 1 fails -> RECONNECTING
	for backoff_s in WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S:
		_transport._process(backoff_s + 0.1)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.EXHAUSTED)
	var poll_count_at_exhaustion := _fake.poll_count
	_transport._process(0.016)
	assert_int(_fake.poll_count).is_equal(poll_count_at_exhaustion)


func test_manual_retry_from_exhausted_moves_to_connecting() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.connect_result = ERR_CANT_CONNECT
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)
	for backoff_s in WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S:
		_transport._process(backoff_s + 0.1)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.EXHAUSTED)
	_fake.connect_result = OK
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTING)


func test_epoch_increments_exactly_once_per_reconnect_reopen() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	var epoch_after_initial := _transport.get_connection_epoch()
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # -> RECONNECTING
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # reopens
	assert_int(_transport.get_connection_epoch()).is_equal(epoch_after_initial + 1)


# -- Reconnect attempt-in-flight coverage (owner re-review, 2026-07-25, second pass) --


func test_backoff_elapsed_opens_exactly_one_new_peer() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # -> RECONNECTING
	var urls_before := _fake.connect_urls.size()
	_fake.ready_state = SocketPeerPort.ReadyState.CONNECTING  # the new peer hasn't opened yet
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)
	assert_int(_fake.connect_urls.size()).is_equal(urls_before + 1)


func test_peer_still_connecting_on_subsequent_frames_opens_no_second_peer() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # -> RECONNECTING
	_fake.ready_state = SocketPeerPort.ReadyState.CONNECTING
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # attempt opens
	var urls_after_first_attempt := _fake.connect_urls.size()
	# Several more frames pass with the SAME attempt still connecting -- without the
	# attempt-in-flight guard, each of these would discard the peer and open a new one.
	_transport._process(0.016)
	_transport._process(0.016)
	_transport._process(0.016)
	assert_int(_fake.connect_urls.size()).is_equal(urls_after_first_attempt)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)


func test_peer_opening_after_backoff_reaches_connected() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # -> RECONNECTING
	_fake.ready_state = SocketPeerPort.ReadyState.CONNECTING
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # attempt opens
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)
	# The attempt's peer now finishes opening, observed on a later frame.
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)
	# Epoch was already incremented to 2 by the reopen attempt above; reconnect_succeeded()
	# itself must not increment it again.
	assert_int(_transport.get_connection_epoch()).is_equal(2)


func test_immediate_connect_failure_schedules_the_next_backoff_without_a_busy_loop() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # attempt 1 fails synchronously -> RECONNECTING, backoff[0] scheduled
	_fake.connect_result = ERR_CANT_CONNECT  # attempt 2's connect_to_url will fail synchronously too
	var urls_before := _fake.connect_urls.size()
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # attempt 2 fires and fails
	assert_int(_fake.connect_urls.size()).is_equal(urls_before + 1)  # exactly one new attempt, not a loop
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)
	# Processing less than backoff[1] must NOT trigger another attempt (no busy loop): the failed
	# synchronous attempt must have scheduled backoff[1], not left the timer at <= 0.
	var urls_after_attempt_2 := _fake.connect_urls.size()
	_transport._process(0.1)
	assert_int(_fake.connect_urls.size()).is_equal(urls_after_attempt_2)
