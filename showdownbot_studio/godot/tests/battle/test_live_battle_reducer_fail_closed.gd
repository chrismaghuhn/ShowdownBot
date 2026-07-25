extends GdUnitTestSuite


func _event(fields: Dictionary) -> ProtocolEventDTO:
	var e := ProtocolEventDTO.new()
	for key in fields:
		e.set(key, fields[key])
	e.seal()
	return e


func test_damage_event_for_a_slot_never_switched_in_does_not_crash_and_only_sets_given_fields() -> void:
	var s := LiveBattleReducer.apply(LiveBattleSnapshot.new(), _event({
		"event_type": "-damage", "pokemon_side": "p2", "pokemon_slot": "b",
		"hp_current": 40, "hp_maximum": 100,
	}))
	var slot := s.get_slot("p2", "b")
	assert_int(slot.hp_current).is_equal(40)
	assert_object(slot.species).is_null()


func test_event_missing_side_or_slot_returns_snapshot_unchanged() -> void:
	var s := LiveBattleSnapshot.new()
	var next := LiveBattleReducer.apply(s, _event({"event_type": "-damage", "hp_current": 10}))
	assert_object(next.get_slot("p1", "a").hp_current).is_equal(s.get_slot("p1", "a").hp_current)


func test_error_event_never_mutates_battle_state() -> void:
	var s := LiveBattleSnapshot.new()
	var next := LiveBattleReducer.apply(s, _event({"event_type": "error", "error_reason": "[Room not found]"}))
	assert_bool(next.battle_completed).is_equal(s.battle_completed)
