extends GdUnitTestSuite


func test_default_snapshot_has_four_empty_slots_and_two_side_condition_lists() -> void:
	var snapshot := BattleBoardSnapshot.new()
	assert_bool(snapshot.presentation_available).is_false()
	assert_str(snapshot.empty_state_reason).is_equal("")
	assert_object(snapshot.get_slot("p1", "a")).is_not_null()
	assert_object(snapshot.get_slot("p1", "b")).is_not_null()
	assert_object(snapshot.get_slot("p2", "a")).is_not_null()
	assert_object(snapshot.get_slot("p2", "b")).is_not_null()
	assert_bool(snapshot.side_conditions.has("p1")).is_true()
	assert_bool(snapshot.side_conditions.has("p2")).is_true()


func test_slot_key_matches_get_slot_addressing() -> void:
	var snapshot := BattleBoardSnapshot.new()
	var direct: BattleBoardSlotSnapshot = snapshot.slots[BattleBoardSnapshot.slot_key("p2", "b")]
	assert_object(direct).is_equal(snapshot.get_slot("p2", "b"))


func test_slot_snapshot_fields_default_to_null() -> void:
	var slot := BattleBoardSlotSnapshot.new()
	assert_object(slot.species).is_null()
	assert_object(slot.hp_current).is_null()
	assert_object(slot.hp_maximum).is_null()
	assert_object(slot.hp_fainted).is_null()
	assert_object(slot.hp_status).is_null()


func test_get_slot_unknown_key_pushes_error_and_returns_null() -> void:
	var snapshot := BattleBoardSnapshot.new()
	var captured: Array = [true]
	await assert_error(func() -> void: captured[0] = snapshot.get_slot("p3", "z")).is_push_error(
		"BattleBoardSnapshot.get_slot: unknown side/slot p3/z"
	)
	assert_object(captured[0]).is_null()
