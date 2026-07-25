extends GdUnitTestSuite


func _event(fields: Dictionary) -> ProtocolEventDTO:
	var e := ProtocolEventDTO.new()
	for key in fields:
		e.set(key, fields[key])
	e.seal()
	return e


func test_rebuild_from_timeline_shows_one_line_per_event_without_per_row_nodes() -> void:
	var panel: LiveBattleLogPanel = preload("res://src/ui/panels/live_battle_log_panel.tscn").instantiate()
	add_child(panel)
	var timeline: Array[ProtocolEventDTO] = [_event({"event_type": "turn", "turn_number": 4})]
	panel.rebuild_from_timeline(timeline)
	assert_str(panel.get_log_text()).contains("turn 4")
	assert_int(panel.get_child_count()).is_equal(1)  # the RichTextLabel itself, never one node/row
	panel.free()


func test_rebuild_from_timeline_replaces_prior_content_entirely() -> void:
	var panel: LiveBattleLogPanel = preload("res://src/ui/panels/live_battle_log_panel.tscn").instantiate()
	add_child(panel)
	panel.rebuild_from_timeline([_event({"event_type": "turn", "turn_number": 99})])
	panel.rebuild_from_timeline([_event({"event_type": "turn", "turn_number": 1})])
	assert_bool(panel.get_log_text().contains("turn 99")).is_false()
	assert_bool(panel.get_log_text().contains("turn 1")).is_true()
	panel.free()


func test_switch_summary_sanitizes_control_characters_and_caps_species_length() -> void:
	# Dirty-input proof (2026-07-26 review), mirroring test_room_entry_panel.gd's own: this call
	# site (the "switch"/"drag" summary's species field) was only ever exercised with clean
	# species names like "Pikachu" before -- never dirty input, so UntrustedTextSanitizer's
	# actual wiring here was unproven. A control-character-laden, over-cap species string must
	# come out stripped and capped in the rendered log line.
	var panel: LiveBattleLogPanel = preload("res://src/ui/panels/live_battle_log_panel.tscn").instantiate()
	add_child(panel)
	var dirty_species := "Bad" + char(1) + char(2) + "Mon".repeat(100)
	var timeline: Array[ProtocolEventDTO] = [_event({
		"event_type": "switch", "pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": dirty_species,
	})]
	panel.rebuild_from_timeline(timeline)
	var log_text := panel.get_log_text()
	assert_bool(log_text.contains(char(1))).is_false()
	assert_str(log_text).contains(UntrustedTextSanitizer.sanitize(dirty_species))
	panel.free()
