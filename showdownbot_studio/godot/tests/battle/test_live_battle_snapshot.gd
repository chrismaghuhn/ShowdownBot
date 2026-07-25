extends GdUnitTestSuite


func test_default_snapshot_has_four_empty_slots() -> void:
	var s := LiveBattleSnapshot.new()
	assert_object(s.get_slot("p1", "a")).is_not_null()
	assert_object(s.get_slot("p2", "b")).is_not_null()
	assert_bool(s.battle_completed).is_false()


func test_slot_snapshot_fields_default_to_null() -> void:
	var slot := LiveBattleSlotSnapshot.new()
	assert_object(slot.species).is_null()
	assert_object(slot.hp_current).is_null()


func test_slot_snapshot_fields_are_set_only_through_the_constructor() -> void:
	var slot := LiveBattleSlotSnapshot.new("Pikachu", 100, 100, false, null)
	assert_str(str(slot.species)).is_equal("Pikachu")
	assert_int(slot.hp_current).is_equal(100)


func test_with_slot_returns_a_new_snapshot_leaving_the_original_untouched() -> void:
	var original := LiveBattleSnapshot.new()
	var updated := original.with_slot("p1", "a", LiveBattleSlotSnapshot.new("Pikachu"))
	assert_object(original.get_slot("p1", "a").species).is_null()
	assert_str(str(updated.get_slot("p1", "a").species)).is_equal("Pikachu")


func test_get_side_conditions_returns_an_independent_copy() -> void:
	var s := LiveBattleSnapshot.new().with_side_condition_added("p1", "Stealth Rock")
	var copy := s.get_side_conditions("p1")
	copy.append("Spikes")  # mutate the RETURNED array only
	assert_bool(s.get_side_conditions("p1").has("Spikes")).is_false()
