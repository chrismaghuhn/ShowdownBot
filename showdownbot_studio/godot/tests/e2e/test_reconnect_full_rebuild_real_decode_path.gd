extends GdUnitTestSuite

var _fake: FakeSocketPeerPort
var _transport: WebSocketTransport
var _decoder: ProtocolDecoder
var _room_state_machine: RoomStateMachine
var _projection: LiveBattleProjection


func before_test() -> void:
	_fake = FakeSocketPeerPort.new()
	_transport = WebSocketTransport.new(func(): return _fake)
	add_child(_transport)
	_decoder = ProtocolDecoder.new()
	_room_state_machine = RoomStateMachine.new(_transport)
	_projection = LiveBattleProjection.new()
	_transport.raw_text_received.connect(_decoder.decode_frame)
	_decoder.event_decoded.connect(func(e: ProtocolEventDTO):
		if e.event_type == "init":
			_room_state_machine.rejoin_confirmed()
			_projection.set_room_id(e.room_id)
		# Fixed (item B): every event, including init, reaches the projection -- mirrors Task
		# 29's corrected LiveClientWorkspace wiring exactly.
		_projection.apply_event(e)
	)


func after_test() -> void:
	remove_child(_transport)
	_transport.free()


func test_full_reconnect_rebuild_through_the_real_decode_path_no_dedup_needed() -> void:
	# 1. Connect, join, and receive the pre-disconnect history through the real decode path.
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	_room_state_machine.request_join("battle-1")
	_fake.queued_packets = [">battle-1\n|init|battle\n|turn|1\n|switch|p1a: Pikachu|Pikachu, L50, M|100/100"]
	_transport._process(0.016)
	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.ACTIVE)
	assert_int(_projection.get_current_snapshot().turn).is_equal(1)
	assert_int(_projection.get_timeline().size()).is_equal(3)  # init, turn, switch

	# 2. Connection drops; automatic reconnect begins; RoomState reacts to ACTIVE -> RECONNECTING.
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)
	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.JOINING)

	# 3. Reconnect succeeds; RoomStateMachine emits automatic_rejoin_requested; there is no
	# gateway in this test, so nothing actually sends /join here -- this test proves the
	# rebuild, not the send (that is SpectatorRoomGateway's own tested behavior, Task 28). Two
	# _process() calls are required here, matching Task 7's attempt-in-flight fix: the first
	# opens the new peer (still RECONNECTING that same frame); the second observes it as OPEN.
	var rejoin_requested_room_ids: Array[String] = []
	_room_state_machine.automatic_rejoin_requested.connect(func(room_id: String): rejoin_requested_room_ids.append(room_id))
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # opens the new peer
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)  # observes OPEN -> CONNECTED
	assert_int(rejoin_requested_room_ids.size()).is_equal(1)
	assert_str(rejoin_requested_room_ids[0]).is_equal("battle-1")

	# 4. Server resends the ENTIRE authoritative history from scratch (a second `init`), through
	# the same real decode path, containing neither the pre-disconnect turn number nor species.
	_fake.queued_packets = [">battle-1\n|init|battle\n|turn|1\n|switch|p1a: Ditto|Ditto|50/50"]
	_transport._process(0.016)

	# 5. Only now do new live events continue -- verified separately below.
	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.ACTIVE)
	var snapshot := _projection.get_current_snapshot()
	assert_int(snapshot.turn).is_equal(1)
	assert_str(str(snapshot.get_slot("p1", "a").species)).is_equal("Ditto")  # not "Pikachu"
	# Timeline count equals exactly the rebuilt (resent) history's three lines (init, turn,
	# switch) -- no leftover from before the reconnect, and no dedup-driven under- or over-count.
	assert_int(_projection.get_timeline().size()).is_equal(3)

	_fake.queued_packets = [">battle-1\n|turn|2"]
	_transport._process(0.016)
	assert_int(_projection.get_current_snapshot().turn).is_equal(2)
	assert_int(_projection.get_timeline().size()).is_equal(4)
