extends GdUnitTestSuite

var _fake: FakeSocketPeerPort
var _workspace: LiveClientWorkspace


func before_test() -> void:
	_fake = FakeSocketPeerPort.new()
	_workspace = preload("res://src/workspace/live_client_workspace.tscn").instantiate()
	add_child(_workspace)
	_workspace.configure_transport_for_test(func(): return _fake)


func after_test() -> void:
	remove_child(_workspace)
	_workspace.free()


func _connect_and_open() -> void:
	_workspace.get_transport().connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_workspace.get_transport()._process(0.016)


func test_watch_sends_the_join_command_through_the_gateway_not_directly() -> void:
	_connect_and_open()
	_workspace.get_room_entry_panel().set_input_text_for_test("battle-1")
	_workspace.get_room_entry_panel().press_watch_for_test()
	assert_int(_fake.sent_texts.size()).is_equal(1)
	assert_str(_fake.sent_texts[0]).is_equal("|/join battle-1")


func test_init_battle_confirms_join_and_battle_frames_render() -> void:
	_connect_and_open()
	_workspace.get_room_entry_panel().set_input_text_for_test("battle-1")
	_workspace.get_room_entry_panel().press_watch_for_test()
	_fake.queued_packets = [
		">battle-1\n|init|battle",
		">battle-1\n|switch|p1a: Pikachu|Pikachu, L50, M|100/100",
	]
	_workspace.get_transport()._process(0.016)
	assert_int(_workspace.get_room_state_machine().get_state()).is_equal(RoomStateMachine.State.ACTIVE)
	assert_str(_workspace.get_battle_board_panel().get_board_view().get_slot_species("p1", "a")).is_equal("Pikachu")


func test_init_chat_does_not_confirm_a_battle_join() -> void:
	_connect_and_open()
	_workspace.get_room_entry_panel().set_input_text_for_test("some-room")
	_workspace.get_room_entry_panel().press_watch_for_test()
	_fake.queued_packets = [">some-room\n|init|chat"]
	_workspace.get_transport()._process(0.016)
	assert_int(_workspace.get_room_state_machine().get_state()).is_not_equal(RoomStateMachine.State.ACTIVE)


func test_events_for_a_different_room_are_ignored() -> void:
	_connect_and_open()
	_workspace.get_room_entry_panel().set_input_text_for_test("battle-1")
	_workspace.get_room_entry_panel().press_watch_for_test()
	_fake.queued_packets = [">battle-1\n|init|battle"]
	_workspace.get_transport()._process(0.016)
	_fake.queued_packets = [">some-other-room\n|switch|p1a: Ditto|Ditto|50/50"]
	_workspace.get_transport()._process(0.016)
	# NOTE: the plan's own sample used assert_object(...) here, but get_slot_species() returns a
	# String, not an Object -- gdUnit4's ObjectAssert rejects non-Object values outright ("inital
	# error, unexpected type <String>"). assert_str is the correct assertion for this return type.
	assert_str(_workspace.get_battle_board_panel().get_board_view().get_slot_species("p1", "a")).is_not_equal("Ditto")


func test_win_publishes_completion_but_does_not_close_the_room() -> void:
	_connect_and_open()
	_workspace.get_room_entry_panel().set_input_text_for_test("battle-1")
	_workspace.get_room_entry_panel().press_watch_for_test()
	_fake.queued_packets = [">battle-1\n|init|battle"]
	_workspace.get_transport()._process(0.016)
	_fake.queued_packets = [">battle-1\n|win|Alice"]
	_workspace.get_transport()._process(0.016)
	assert_int(_workspace.get_room_state_machine().get_state()).is_equal(RoomStateMachine.State.ACTIVE)


func test_deinit_while_active_closes_the_room() -> void:
	_connect_and_open()
	_workspace.get_room_entry_panel().set_input_text_for_test("battle-1")
	_workspace.get_room_entry_panel().press_watch_for_test()
	_fake.queued_packets = [">battle-1\n|init|battle"]
	_workspace.get_transport()._process(0.016)
	_fake.queued_packets = [">battle-1\n|deinit"]
	_workspace.get_transport()._process(0.016)
	assert_int(_workspace.get_room_state_machine().get_state()).is_equal(RoomStateMachine.State.CLOSED)


func test_deinit_while_leaving_confirms_the_leave_instead_of_closing() -> void:
	# A deinit racing an already-in-flight human leave() must not try server_closed_room()
	# (invalid from LEAVING, silently a no-op) and leave RoomState stuck in LEAVING forever.
	_connect_and_open()
	_workspace.get_room_entry_panel().set_input_text_for_test("battle-1")
	_workspace.get_room_entry_panel().press_watch_for_test()
	_fake.queued_packets = [">battle-1\n|init|battle"]
	_workspace.get_transport()._process(0.016)
	_workspace.get_room_state_machine().request_leave()  # simulate a leave already in flight
	assert_int(_workspace.get_room_state_machine().get_state()).is_equal(RoomStateMachine.State.LEAVING)
	_fake.queued_packets = [">battle-1\n|deinit"]
	_workspace.get_transport()._process(0.016)
	assert_int(_workspace.get_room_state_machine().get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)


func test_confirmed_battle_init_is_forwarded_to_the_projection() -> void:
	# Proves item B's fix directly: the confirmed `init` event itself must reach
	# LiveBattleProjection.apply_event() (checked via the projection's own timeline), not just
	# the events that follow it -- otherwise Task 38's (M1e) reset-on-repeat-init logic could
	# never fire through this real wiring, no matter how correct it is in isolation.
	_connect_and_open()
	_workspace.get_room_entry_panel().set_input_text_for_test("battle-1")
	_workspace.get_room_entry_panel().press_watch_for_test()
	_fake.queued_packets = [">battle-1\n|init|battle"]
	_workspace.get_transport()._process(0.016)
	assert_int(_workspace.get_projection_for_test().get_timeline().size()).is_equal(1)
	assert_str(_workspace.get_projection_for_test().get_timeline()[0].event_type).is_equal("init")


func test_unknown_room_error_rejects_join_and_shows_error_text() -> void:
	_connect_and_open()
	_workspace.get_room_entry_panel().set_input_text_for_test("battle-missing")
	_workspace.get_room_entry_panel().press_watch_for_test()
	_fake.queued_packets = [">battle-missing\n|error|[Room not found]"]
	_workspace.get_transport()._process(0.016)
	assert_int(_workspace.get_room_state_machine().get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)
	assert_str(_workspace.get_room_entry_panel().get_error_text()).is_equal("[Room not found]")


func test_connection_state_changes_reach_the_status_panel_via_the_bus() -> void:
	_workspace.get_transport().connect_to_server("ws://localhost:8000/showdown/websocket")
	assert_str(_workspace.get_connection_status_panel().get_status_text()).is_equal("Connecting...")
