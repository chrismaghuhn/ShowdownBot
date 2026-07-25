extends GdUnitTestSuite


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


class _FakeGatewayPort:
	extends SpectatorRoomGatewayPort
	var joined_room_ids: Array[String] = []

	func join(intent: RoomJoinIntent) -> void:
		joined_room_ids.append(intent.room_id)
