extends GdUnitTestSuite


func test_initial_state_is_disconnected() -> void:
	var m := ConnectionStateMachine.new()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


func test_request_connect_from_disconnected_moves_to_connecting() -> void:
	var m := ConnectionStateMachine.new()
	assert_bool(m.request_connect()).is_true()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.CONNECTING)


func test_handshake_succeeded_from_connecting_moves_to_connected() -> void:
	var m := ConnectionStateMachine.new()
	m.request_connect()
	assert_bool(m.handshake_succeeded()).is_true()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)


func test_initial_attempt_failed_retries_remain_from_connecting_moves_to_reconnecting() -> void:
	var m := ConnectionStateMachine.new()
	m.request_connect()
	assert_bool(m.initial_attempt_failed_retries_remain()).is_true()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)


func test_cancel_connect_from_connecting_moves_to_disconnected() -> void:
	var m := ConnectionStateMachine.new()
	m.request_connect()
	assert_bool(m.cancel_connect()).is_true()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


func test_connection_lost_retries_remain_from_connected_moves_to_reconnecting() -> void:
	var m := ConnectionStateMachine.new()
	m.request_connect()
	m.handshake_succeeded()
	assert_bool(m.connection_lost_retries_remain()).is_true()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)


func test_request_disconnect_from_connected_moves_to_disconnected() -> void:
	var m := ConnectionStateMachine.new()
	m.request_connect()
	m.handshake_succeeded()
	assert_bool(m.request_disconnect()).is_true()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


func test_reconnect_succeeded_from_reconnecting_moves_to_connected() -> void:
	var m := ConnectionStateMachine.new()
	m.request_connect()
	m.initial_attempt_failed_retries_remain()  # CONNECTING -> RECONNECTING (only valid path here)
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)
	assert_bool(m.reconnect_succeeded()).is_true()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)


func test_reconnect_failed_retries_remain_is_a_self_transition_and_still_emits() -> void:
	var m := ConnectionStateMachine.new()
	m.request_connect()
	m.initial_attempt_failed_retries_remain()
	var emitted := []
	m.state_changed.connect(func(old_state, new_state): emitted.append([old_state, new_state]))
	assert_bool(m.reconnect_failed_retries_remain()).is_true()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)
	assert_int(emitted.size()).is_equal(1)
	assert_int(emitted[0][1]).is_equal(ConnectionStateMachine.State.RECONNECTING)


func test_backoff_exhausted_from_reconnecting_moves_to_exhausted() -> void:
	var m := ConnectionStateMachine.new()
	m.request_connect()
	m.initial_attempt_failed_retries_remain()
	assert_bool(m.backoff_exhausted()).is_true()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.EXHAUSTED)


func test_request_disconnect_from_reconnecting_moves_to_disconnected() -> void:
	var m := ConnectionStateMachine.new()
	m.request_connect()
	m.initial_attempt_failed_retries_remain()
	assert_bool(m.request_disconnect()).is_true()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


func test_request_connect_from_exhausted_moves_to_connecting() -> void:
	var m := ConnectionStateMachine.new()
	m.request_connect()
	m.initial_attempt_failed_retries_remain()
	m.backoff_exhausted()
	assert_bool(m.request_connect()).is_true()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.CONNECTING)


func test_request_disconnect_from_exhausted_moves_to_disconnected() -> void:
	var m := ConnectionStateMachine.new()
	m.request_connect()
	m.initial_attempt_failed_retries_remain()
	m.backoff_exhausted()
	assert_bool(m.request_disconnect()).is_true()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


# -- Invalid transitions --


func test_handshake_succeeded_from_disconnected_is_rejected() -> void:
	var m := ConnectionStateMachine.new()
	assert_bool(m.handshake_succeeded()).is_false()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


func test_reconnect_succeeded_from_disconnected_is_rejected() -> void:
	var m := ConnectionStateMachine.new()
	assert_bool(m.reconnect_succeeded()).is_false()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


func test_request_connect_from_connecting_is_rejected_not_queued() -> void:
	var m := ConnectionStateMachine.new()
	m.request_connect()
	assert_bool(m.request_connect()).is_false()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.CONNECTING)


func test_request_disconnect_from_connecting_is_rejected() -> void:
	# request_disconnect() is valid only from CONNECTED/RECONNECTING/EXHAUSTED; CONNECTING's own
	# exit is cancel_connect(), a distinct method (see test above).
	var m := ConnectionStateMachine.new()
	m.request_connect()
	assert_bool(m.request_disconnect()).is_false()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.CONNECTING)


func test_cancel_connect_from_connected_is_rejected() -> void:
	var m := ConnectionStateMachine.new()
	m.request_connect()
	m.handshake_succeeded()
	assert_bool(m.cancel_connect()).is_false()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)


func test_backoff_exhausted_from_connected_is_rejected() -> void:
	var m := ConnectionStateMachine.new()
	m.request_connect()
	m.handshake_succeeded()
	assert_bool(m.backoff_exhausted()).is_false()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)


# Doc-mandated invalid transition: DISCONNECTED -> RECONNECTING directly (no prior connection
# attempt to reconnect from) is invalid regardless of which RECONNECTING-reaching trigger fires.


func test_connection_lost_retries_remain_from_disconnected_is_rejected() -> void:
	var m := ConnectionStateMachine.new()
	assert_bool(m.connection_lost_retries_remain()).is_false()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


func test_initial_attempt_failed_retries_remain_from_disconnected_is_rejected() -> void:
	var m := ConnectionStateMachine.new()
	assert_bool(m.initial_attempt_failed_retries_remain()).is_false()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


# Doc-mandated invalid transition: EXHAUSTED -> CONNECTED directly (must pass through CONNECTING)
# is invalid regardless of which CONNECTED-reaching trigger fires.


func test_handshake_succeeded_from_exhausted_is_rejected() -> void:
	var m := ConnectionStateMachine.new()
	m.request_connect()
	m.initial_attempt_failed_retries_remain()
	m.backoff_exhausted()
	assert_bool(m.handshake_succeeded()).is_false()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.EXHAUSTED)


func test_reconnect_succeeded_from_exhausted_is_rejected() -> void:
	var m := ConnectionStateMachine.new()
	m.request_connect()
	m.initial_attempt_failed_retries_remain()
	m.backoff_exhausted()
	assert_bool(m.reconnect_succeeded()).is_false()
	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.EXHAUSTED)
