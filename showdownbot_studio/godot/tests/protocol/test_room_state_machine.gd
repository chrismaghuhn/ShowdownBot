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


func test_initial_state_is_not_joined() -> void:
	var m := RoomStateMachine.new(_transport)
	assert_int(m.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)


func test_request_join_moves_to_joining_and_records_room_id() -> void:
	var m := RoomStateMachine.new(_transport)
	assert_bool(m.request_join("battle-1")).is_true()
	assert_int(m.get_state()).is_equal(RoomStateMachine.State.JOINING)
	assert_str(m.get_room_id()).is_equal("battle-1")


func test_join_confirmed_moves_to_active() -> void:
	var m := RoomStateMachine.new(_transport)
	m.request_join("battle-1")
	assert_bool(m.join_confirmed()).is_true()
	assert_int(m.get_state()).is_equal(RoomStateMachine.State.ACTIVE)


func test_join_rejected_moves_back_to_not_joined_and_records_reason() -> void:
	var m := RoomStateMachine.new(_transport)
	m.request_join("battle-1")
	assert_bool(m.join_rejected("[Room not found]")).is_true()
	assert_int(m.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)
	assert_str(m.get_last_error_reason()).is_equal("[Room not found]")
	assert_str(m.get_room_id()).is_equal("")


func test_join_send_failed_moves_back_to_not_joined_with_a_surfaced_reason() -> void:
	var m := RoomStateMachine.new(_transport)
	m.request_join("battle-1")
	assert_bool(m.join_send_failed()).is_true()
	assert_int(m.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)
	assert_bool(m.get_last_error_reason().length() > 0).is_true()


func test_request_leave_from_active_moves_to_leaving() -> void:
	var m := RoomStateMachine.new(_transport)
	m.request_join("battle-1")
	m.join_confirmed()
	assert_bool(m.request_leave()).is_true()
	assert_int(m.get_state()).is_equal(RoomStateMachine.State.LEAVING)


func test_leave_send_failed_returns_to_active_with_a_surfaced_reason_and_keeps_room_id() -> void:
	var m := RoomStateMachine.new(_transport)
	m.request_join("battle-1")
	m.join_confirmed()
	m.request_leave()
	assert_bool(m.leave_send_failed()).is_true()
	assert_int(m.get_state()).is_equal(RoomStateMachine.State.ACTIVE)
	assert_bool(m.get_last_error_reason().length() > 0).is_true()
	assert_str(m.get_room_id()).is_equal("battle-1")  # the room is still joined -- leave didn't happen


func test_leave_send_failed_outside_leaving_is_rejected() -> void:
	var m := RoomStateMachine.new(_transport)
	m.request_join("battle-1")
	m.join_confirmed()
	assert_bool(m.leave_send_failed()).is_false()
	assert_int(m.get_state()).is_equal(RoomStateMachine.State.ACTIVE)


func test_leave_confirmed_moves_to_not_joined() -> void:
	var m := RoomStateMachine.new(_transport)
	m.request_join("battle-1")
	m.join_confirmed()
	m.request_leave()
	assert_bool(m.leave_confirmed()).is_true()
	assert_int(m.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)


func test_server_closed_room_from_active_moves_to_closed() -> void:
	var m := RoomStateMachine.new(_transport)
	m.request_join("battle-1")
	m.join_confirmed()
	assert_bool(m.server_closed_room()).is_true()
	assert_int(m.get_state()).is_equal(RoomStateMachine.State.CLOSED)


func test_dismiss_closed_room_moves_to_not_joined() -> void:
	var m := RoomStateMachine.new(_transport)
	m.request_join("battle-1")
	m.join_confirmed()
	m.server_closed_room()
	assert_bool(m.dismiss_closed_room()).is_true()
	assert_int(m.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)


func test_connection_reconnecting_while_active_moves_to_joining() -> void:
	var m := RoomStateMachine.new(_transport)
	m.request_join("battle-1")
	m.join_confirmed()
	assert_bool(m.connection_reconnecting()).is_true()
	assert_int(m.get_state()).is_equal(RoomStateMachine.State.JOINING)


func test_not_joined_to_active_directly_is_rejected() -> void:
	var m := RoomStateMachine.new(_transport)
	assert_bool(m.join_confirmed()).is_false()
	assert_int(m.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)


func test_closed_to_active_directly_is_rejected() -> void:
	var m := RoomStateMachine.new(_transport)
	m.request_join("battle-1")
	m.join_confirmed()
	m.server_closed_room()
	assert_bool(m.join_confirmed()).is_false()
	assert_int(m.get_state()).is_equal(RoomStateMachine.State.CLOSED)
