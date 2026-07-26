extends GdUnitTestSuite

var _fake_transport_peer: FakeSocketPeerPort
var _transport: WebSocketTransport


func before_test() -> void:
	_fake_transport_peer = FakeSocketPeerPort.new()
	_transport = WebSocketTransport.new(func(): return _fake_transport_peer)
	add_child(_transport)


func after_test() -> void:
	remove_child(_transport)
	_transport.free()


func test_extracts_room_id_from_bare_id() -> void:
	assert_str(RoomEntryPanel.extract_room_id("battle-1")).is_equal("battle-1")


func test_extracts_room_id_from_full_url() -> void:
	assert_str(RoomEntryPanel.extract_room_id("https://play.pokemonshowdown.com/battle-1")).is_equal("battle-1")


func test_blank_input_extracts_to_empty_string() -> void:
	assert_str(RoomEntryPanel.extract_room_id("   ")).is_equal("")


func test_pressing_watch_calls_the_gateways_join_with_a_room_join_intent() -> void:
	var panel: RoomEntryPanel = preload("res://src/ui/panels/room_entry_panel.tscn").instantiate()
	add_child(panel)
	var fake_gateway := _FakeGatewayPort.new()
	panel.configure(fake_gateway)
	panel.set_input_text_for_test("battle-1")
	panel.press_watch_for_test()
	assert_int(fake_gateway.joined_room_ids.size()).is_equal(1)
	assert_str(fake_gateway.joined_room_ids[0]).is_equal("battle-1")
	panel.free()


func test_on_join_rejected_shows_server_error_text_verbatim_as_plaintext() -> void:
	var panel: RoomEntryPanel = preload("res://src/ui/panels/room_entry_panel.tscn").instantiate()
	add_child(panel)
	panel.on_join_rejected("[Room not found]")
	assert_str(panel.get_error_text()).is_equal("[Room not found]")
	panel.free()


func test_on_join_rejected_sanitizes_control_characters_and_caps_length() -> void:
	# Dirty-input proof (2026-07-26 review): the test above only proves CLEAN server text passes
	# through unchanged -- it would pass even if this call site never sanitized at all. This
	# proves UntrustedTextSanitizer is actually wired at on_join_rejected()'s call site: a server
	# error string with control characters and over-cap length must come out stripped and capped
	# in the rendered label, matching UntrustedTextSanitizer.sanitize() called directly.
	var panel: RoomEntryPanel = preload("res://src/ui/panels/room_entry_panel.tscn").instantiate()
	add_child(panel)
	var dirty := "bad" + char(1) + char(2) + "room".repeat(100)
	panel.on_join_rejected(dirty)
	assert_str(panel.get_error_text()).is_equal(UntrustedTextSanitizer.sanitize(dirty))
	assert_bool(panel.get_error_text().contains(char(1))).is_false()
	assert_int(panel.get_error_text().length()).is_equal(UntrustedTextSanitizer.MAX_LENGTH)
	panel.free()


## --- M1 hardening (owner review of PR #94, P1 item 2, 2026-07-26): the panel gains Leave/Dismiss
## and a RoomStateMachine.state_changed subscription. Uses a REAL RoomStateMachine (with a fake
## transport, the same construction pattern as tests/protocol/test_room_state_machine.gd) so the
## panel is proven against the actual state table -- the gateway stays a port fake throughout
## (test (e): no concrete-gateway dependency).


func test_room_state_machine_starts_not_joined_and_leave_dismiss_are_disabled() -> void:
	var panel: RoomEntryPanel = preload("res://src/ui/panels/room_entry_panel.tscn").instantiate()
	add_child(panel)
	var rsm := RoomStateMachine.new(_transport)
	panel.configure(_FakeGatewayPort.new(), rsm)
	assert_str(panel.get_status_text()).is_equal("Not watching")
	assert_bool(panel.is_join_enabled_for_test()).is_true()
	assert_bool(panel.is_leave_enabled_for_test()).is_false()
	assert_bool(panel.is_dismiss_enabled_for_test()).is_false()
	panel.free()


func test_each_documented_room_state_renders_its_visible_text_and_button_state() -> void:
	# Proves test (c): every user-visible RoomState from
	# docs/architecture/LIVE_STATE_MACHINES.md's RoomState table renders through the panel.
	var panel: RoomEntryPanel = preload("res://src/ui/panels/room_entry_panel.tscn").instantiate()
	add_child(panel)
	var rsm := RoomStateMachine.new(_transport)
	panel.configure(_FakeGatewayPort.new(), rsm)

	rsm.request_join("battle-1")
	assert_str(panel.get_status_text()).is_equal("Joining...")
	assert_bool(panel.is_join_enabled_for_test()).is_false()
	assert_bool(panel.is_leave_enabled_for_test()).is_false()

	rsm.join_confirmed()
	assert_str(panel.get_status_text()).is_equal("Watching battle-1")
	assert_bool(panel.is_leave_enabled_for_test()).is_true()
	assert_bool(panel.is_join_enabled_for_test()).is_false()

	rsm.request_leave()
	assert_str(panel.get_status_text()).is_equal("Leaving...")
	assert_bool(panel.is_leave_enabled_for_test()).is_false()

	rsm.leave_confirmed()
	assert_str(panel.get_status_text()).is_equal("Not watching")
	assert_bool(panel.is_join_enabled_for_test()).is_true()

	rsm.request_join("battle-2")
	rsm.join_confirmed()
	rsm.server_closed_room()
	assert_str(panel.get_status_text()).is_equal("Room closed")
	assert_bool(panel.is_dismiss_enabled_for_test()).is_true()
	assert_bool(panel.is_join_enabled_for_test()).is_false()
	panel.free()


func test_pressing_leave_calls_the_gateways_leave_only_while_active() -> void:
	var panel: RoomEntryPanel = preload("res://src/ui/panels/room_entry_panel.tscn").instantiate()
	add_child(panel)
	var rsm := RoomStateMachine.new(_transport)
	var fake_gateway := _FakeGatewayPort.new()
	panel.configure(fake_gateway, rsm)
	rsm.request_join("battle-1")
	rsm.join_confirmed()
	panel.press_leave_for_test()
	assert_int(fake_gateway.leave_call_count).is_equal(1)
	panel.free()


func test_pressing_dismiss_resets_a_closed_room_so_watch_works_again() -> void:
	# Proves test (b): after CLOSED, dismiss returns the panel to a reusable NOT_JOINED state, and
	# a subsequent Watch on a DIFFERENT room reaches the gateway -- the one-shot dead end the
	# finding named is exactly this path.
	var panel: RoomEntryPanel = preload("res://src/ui/panels/room_entry_panel.tscn").instantiate()
	add_child(panel)
	var rsm := RoomStateMachine.new(_transport)
	var fake_gateway := _FakeGatewayPort.new()
	panel.configure(fake_gateway, rsm)
	rsm.request_join("battle-1")
	rsm.join_confirmed()
	rsm.server_closed_room()
	assert_int(rsm.get_state()).is_equal(RoomStateMachine.State.CLOSED)

	panel.press_dismiss_for_test()

	assert_int(rsm.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)
	assert_bool(panel.is_join_enabled_for_test()).is_true()
	panel.set_input_text_for_test("battle-2")
	panel.press_watch_for_test()
	assert_int(fake_gateway.joined_room_ids.size()).is_equal(1)
	assert_str(fake_gateway.joined_room_ids[0]).is_equal("battle-2")
	panel.free()


func test_join_send_failed_surfaces_a_sanitized_error_and_leaves_join_usable() -> void:
	var panel: RoomEntryPanel = preload("res://src/ui/panels/room_entry_panel.tscn").instantiate()
	add_child(panel)
	var rsm := RoomStateMachine.new(_transport)
	panel.configure(_FakeGatewayPort.new(), rsm)
	rsm.request_join("battle-1")

	rsm.join_send_failed()

	assert_int(rsm.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)
	assert_str(panel.get_error_text()).is_equal(UntrustedTextSanitizer.sanitize(rsm.get_last_error_reason()))
	assert_bool(panel.get_error_text().is_empty()).is_false()
	assert_bool(panel.is_join_enabled_for_test()).is_true()
	panel.free()


func test_leave_send_failed_surfaces_a_sanitized_error_and_returns_to_active_usable() -> void:
	# Proves test (d) at the panel level: a failed leave send must surface visible error text and
	# leave the room ACTIVE (per the table) with Leave usable again -- not a wedged state.
	var panel: RoomEntryPanel = preload("res://src/ui/panels/room_entry_panel.tscn").instantiate()
	add_child(panel)
	var rsm := RoomStateMachine.new(_transport)
	panel.configure(_FakeGatewayPort.new(), rsm)
	rsm.request_join("battle-1")
	rsm.join_confirmed()
	rsm.request_leave()

	rsm.leave_send_failed()

	assert_int(rsm.get_state()).is_equal(RoomStateMachine.State.ACTIVE)
	assert_str(panel.get_error_text()).is_equal(UntrustedTextSanitizer.sanitize(rsm.get_last_error_reason()))
	assert_bool(panel.get_error_text().is_empty()).is_false()
	assert_bool(panel.is_leave_enabled_for_test()).is_true()
	assert_str(panel.get_status_text()).is_equal("Watching battle-1")
	panel.free()


func test_a_successful_transition_clears_any_stale_error_text() -> void:
	var panel: RoomEntryPanel = preload("res://src/ui/panels/room_entry_panel.tscn").instantiate()
	add_child(panel)
	var rsm := RoomStateMachine.new(_transport)
	panel.configure(_FakeGatewayPort.new(), rsm)
	rsm.request_join("battle-1")
	rsm.join_send_failed()
	assert_bool(panel.get_error_text().is_empty()).is_false()

	rsm.request_join("battle-1")

	assert_str(panel.get_error_text()).is_equal("")
	panel.free()


class _FakeGatewayPort:
	extends SpectatorRoomGatewayPort
	var joined_room_ids: Array[String] = []
	var leave_call_count: int = 0

	func join(intent: RoomJoinIntent) -> void:
		joined_room_ids.append(intent.room_id)

	func leave() -> void:
		leave_call_count += 1
