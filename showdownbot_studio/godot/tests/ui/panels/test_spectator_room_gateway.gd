extends GdUnitTestSuite

var _fake: FakeSocketPeerPort
var _transport: WebSocketTransport
var _room_state_machine: RoomStateMachine
var _gateway: SpectatorRoomGateway


func before_test() -> void:
	_fake = FakeSocketPeerPort.new()
	_transport = WebSocketTransport.new(func(): return _fake)
	add_child(_transport)
	_room_state_machine = RoomStateMachine.new(_transport)
	_gateway = SpectatorRoomGateway.new(_transport, _room_state_machine)


func after_test() -> void:
	remove_child(_transport)
	_transport.free()


func test_join_while_connected_sends_the_encoded_command_and_moves_to_joining() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	_gateway.join(RoomJoinIntent.new("battle-1"))
	assert_int(_fake.sent_texts.size()).is_equal(1)
	assert_str(_fake.sent_texts[0]).is_equal("|/join battle-1")
	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.JOINING)


func test_join_while_disconnected_fails_the_send_and_returns_to_not_joined_with_an_error() -> void:
	_gateway.join(RoomJoinIntent.new("battle-1"))
	assert_int(_fake.sent_texts.size()).is_equal(0)
	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)
	assert_bool(_room_state_machine.get_last_error_reason().length() > 0).is_true()


func test_leave_while_active_sends_the_encoded_command() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	_gateway.join(RoomJoinIntent.new("battle-1"))
	_room_state_machine.join_confirmed()
	_gateway.leave()
	assert_str(_fake.sent_texts[1]).is_equal("|/leave battle-1")


func test_leave_send_failure_calls_leave_send_failed_on_the_room_state_machine() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	_gateway.join(RoomJoinIntent.new("battle-1"))
	_room_state_machine.join_confirmed()
	_transport.disconnect_from_server()  # send_raw_text now fails (not CONNECTED)
	_gateway.leave()
	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.ACTIVE)
	assert_bool(_room_state_machine.get_last_error_reason().length() > 0).is_true()


func test_automatic_rejoin_requested_sends_the_same_join_command_as_a_human_join() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	# Exercised directly, decoupled from RoomStateMachine actually emitting it on a real
	# reconnect (that emission is Task 37's, M1e) -- this test only proves the gateway's own
	# reaction, through the exact same send path join() uses.
	_room_state_machine.automatic_rejoin_requested.emit("battle-1")
	assert_int(_fake.sent_texts.size()).is_equal(1)
	assert_str(_fake.sent_texts[0]).is_equal("|/join battle-1")


func test_automatic_rejoin_send_failure_calls_join_send_failed() -> void:
	# Not connected -- send_raw_text fails.
	_room_state_machine.request_join("battle-1")  # pure transition only, mirrors a resend already in JOINING
	_room_state_machine.automatic_rejoin_requested.emit("battle-1")
	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)
