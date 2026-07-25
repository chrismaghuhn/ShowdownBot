extends GdUnitTestSuite


func test_empty_live_snapshot_is_presentation_available() -> void:
	var snapshot := LiveBoardPresentationAdapter.build_snapshot(LiveBattleSnapshot.new())
	assert_bool(snapshot.presentation_available).is_true()


func test_null_live_snapshot_is_unavailable_with_a_reason() -> void:
	var snapshot := LiveBoardPresentationAdapter.build_snapshot(null)
	assert_bool(snapshot.presentation_available).is_false()
	assert_str(snapshot.empty_state_reason).is_equal("No battle state received yet")


func test_slot_species_and_hp_carry_over() -> void:
	var live := LiveBattleSnapshot.new().with_slot("p1", "a", LiveBattleSlotSnapshot.new("Pikachu", 20, 35))
	var snapshot := LiveBoardPresentationAdapter.build_snapshot(live)
	var out_slot := snapshot.get_slot("p1", "a")
	assert_str(str(out_slot.species)).is_equal("Pikachu")
	assert_int(out_slot.hp_current).is_equal(20)


func test_turn_and_side_conditions_carry_over() -> void:
	var live := LiveBattleSnapshot.new().with_turn(3).with_side_condition_added("p1", "Stealth Rock")
	var snapshot := LiveBoardPresentationAdapter.build_snapshot(live)
	assert_int(snapshot.turn).is_equal(3)
	assert_bool(snapshot.side_conditions["p1"].has("Stealth Rock")).is_true()
