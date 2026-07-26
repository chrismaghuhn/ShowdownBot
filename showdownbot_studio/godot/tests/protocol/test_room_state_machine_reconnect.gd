extends GdUnitTestSuite

var _fake: FakeSocketPeerPort
var _transport: WebSocketTransport
var _room_state_machine: RoomStateMachine


func before_test() -> void:
	_fake = FakeSocketPeerPort.new()
	_transport = WebSocketTransport.new(func(): return _fake)
	add_child(_transport)
	_room_state_machine = RoomStateMachine.new(_transport)


func after_test() -> void:
	remove_child(_transport)
	_transport.free()


func _connect_join_and_activate(room_id: String) -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	_room_state_machine.request_join(room_id)
	_room_state_machine.join_confirmed()


func test_reconnecting_while_active_moves_room_state_to_joining_automatically() -> void:
	_connect_join_and_activate("battle-1")
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # transport -> RECONNECTING
	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.JOINING)


func test_reconnect_succeeding_emits_automatic_rejoin_requested_for_the_same_room() -> void:
	_connect_join_and_activate("battle-1")
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # -> RECONNECTING, RoomState -> JOINING
	var emitted_room_ids: Array[String] = []
	_room_state_machine.automatic_rejoin_requested.connect(func(room_id: String): emitted_room_ids.append(room_id))
	# Two _process() calls, matching Task 7's attempt-in-flight fix: the first opens the new
	# peer (still RECONNECTING that same frame); the second observes it as OPEN -> CONNECTED.
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	assert_int(emitted_room_ids.size()).is_equal(1)
	assert_str(emitted_room_ids[0]).is_equal("battle-1")


func test_no_automatic_rejoin_is_emitted_when_no_room_was_ever_joined() -> void:
	var emitted_room_ids: Array[String] = []
	_room_state_machine.automatic_rejoin_requested.connect(func(room_id: String): emitted_room_ids.append(room_id))
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)
	assert_int(emitted_room_ids.size()).is_equal(0)


func test_room_state_machine_never_calls_send_raw_text_itself() -> void:
	# Structural proof of item C's fix: even across a full reconnect-and-rejoin cycle, this
	# class's own fake transport never records a sent text -- only SpectatorRoomGateway (Task 28)
	# ever does, and it is not present in this test at all.
	_connect_join_and_activate("battle-1")
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)
	assert_int(_fake.sent_texts.size()).is_equal(0)
