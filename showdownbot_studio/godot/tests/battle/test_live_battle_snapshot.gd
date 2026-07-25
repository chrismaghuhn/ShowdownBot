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
	# Watchlist M1c: "Reducer operations return new values and never modify their input
	# snapshot." A prior version of this test only re-checked the touched slot's species --
	# widened here to re-check the ORIGINAL's FULL content (every field, not just the one
	# touched by with_slot) so a purity bug anywhere else in with_slot's construction would
	# actually be caught.
	var original := (
		LiveBattleSnapshot.new()
		.with_turn(5)
		.with_weather("RainDance")
		.with_terrain("Electric Terrain")
		.with_slot("p2", "b", LiveBattleSlotSnapshot.new("Ditto", 42, 100, false, "brn"))
		.with_side_condition_added("p2", "Stealth Rock")
		.with_field_condition_added("Trick Room")
		.with_battle_completed()
	)
	var updated := original.with_slot("p1", "a", LiveBattleSlotSnapshot.new("Pikachu"))

	# The touched slot, read back on the ORIGINAL, must still be untouched.
	assert_object(original.get_slot("p1", "a").species).is_null()
	# Every OTHER field on the ORIGINAL must be exactly what it was before with_slot() ran.
	assert_int(original.turn).is_equal(5)
	assert_str(str(original.weather)).is_equal("RainDance")
	assert_str(str(original.terrain)).is_equal("Electric Terrain")
	assert_bool(original.battle_completed).is_true()
	assert_str(str(original.get_slot("p2", "b").species)).is_equal("Ditto")
	assert_int(original.get_slot("p2", "b").hp_current).is_equal(42)
	assert_bool(original.get_side_conditions("p2").has("Stealth Rock")).is_true()
	assert_bool(original.get_field_conditions().has("Trick Room")).is_true()

	assert_str(str(updated.get_slot("p1", "a").species)).is_equal("Pikachu")


func test_get_side_conditions_returns_an_independent_copy() -> void:
	var s := LiveBattleSnapshot.new().with_side_condition_added("p1", "Stealth Rock")
	var copy := s.get_side_conditions("p1")
	copy.append("Spikes")  # mutate the RETURNED array only
	assert_bool(s.get_side_conditions("p1").has("Spikes")).is_false()


func test_get_field_conditions_returns_an_independent_copy() -> void:
	var s := LiveBattleSnapshot.new().with_field_condition_added("Trick Room")
	var copy := s.get_field_conditions()
	copy.append("Gravity")  # mutate the RETURNED array only
	assert_bool(s.get_field_conditions().has("Gravity")).is_false()


func test_equals_is_true_for_snapshots_with_identical_content() -> void:
	var a := LiveBattleSnapshot.new().with_turn(3).with_slot("p1", "a", LiveBattleSlotSnapshot.new("Pikachu", 50, 100, false, null))
	var b := LiveBattleSnapshot.new().with_turn(3).with_slot("p1", "a", LiveBattleSlotSnapshot.new("Pikachu", 50, 100, false, null))
	assert_bool(a.equals(b)).is_true()


func test_equals_is_false_when_any_field_differs() -> void:
	var a := LiveBattleSnapshot.new().with_turn(3)
	var b := LiveBattleSnapshot.new().with_turn(4)
	assert_bool(a.equals(b)).is_false()
