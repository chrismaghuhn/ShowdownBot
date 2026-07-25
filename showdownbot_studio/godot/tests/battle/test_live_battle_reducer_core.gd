extends GdUnitTestSuite


func _event(fields: Dictionary) -> ProtocolEventDTO:
	var e := ProtocolEventDTO.new()
	for key in fields:
		e.set(key, fields[key])
	e.seal()
	return e


func test_turn_event_updates_turn_number() -> void:
	var s := LiveBattleReducer.apply(LiveBattleSnapshot.new(), _event({"event_type": "turn", "turn_number": 3}))
	assert_int(s.turn).is_equal(3)


func test_switch_event_sets_slot_species_and_hp() -> void:
	var e := _event({
		"event_type": "switch", "pokemon_side": "p1", "pokemon_slot": "a",
		"pokemon_species": "Pikachu", "hp_current": 100, "hp_maximum": 100, "hp_fainted": false,
	})
	var s := LiveBattleReducer.apply(LiveBattleSnapshot.new(), e)
	var slot := s.get_slot("p1", "a")
	assert_str(str(slot.species)).is_equal("Pikachu")
	assert_int(slot.hp_current).is_equal(100)


func test_damage_event_updates_hp_without_clearing_species() -> void:
	var initial := LiveBattleReducer.apply(LiveBattleSnapshot.new(), _event({
		"event_type": "switch", "pokemon_side": "p1", "pokemon_slot": "a",
		"pokemon_species": "Pikachu", "hp_current": 100, "hp_maximum": 100, "hp_fainted": false,
	}))
	var damaged := LiveBattleReducer.apply(initial, _event({
		"event_type": "-damage", "pokemon_side": "p1", "pokemon_slot": "a",
		"hp_current": 50, "hp_maximum": 100, "hp_fainted": false, "hp_status": "brn",
	}))
	var slot := damaged.get_slot("p1", "a")
	assert_str(str(slot.species)).is_equal("Pikachu")
	assert_int(slot.hp_current).is_equal(50)


func test_faint_event_forces_zero_hp_and_fainted_true() -> void:
	var initial := LiveBattleReducer.apply(LiveBattleSnapshot.new(), _event({
		"event_type": "switch", "pokemon_side": "p2", "pokemon_slot": "a",
		"pokemon_species": "Ditto", "hp_current": 10, "hp_maximum": 100, "hp_fainted": false,
	}))
	var fainted := LiveBattleReducer.apply(initial, _event({
		"event_type": "faint", "pokemon_side": "p2", "pokemon_slot": "a",
		"hp_current": 0, "hp_fainted": true,
	}))
	var slot := fainted.get_slot("p2", "a")
	assert_int(slot.hp_current).is_equal(0)
	assert_bool(slot.hp_fainted).is_true()


func test_unhandled_event_type_returns_snapshot_unchanged() -> void:
	var s := LiveBattleSnapshot.new()
	var next := LiveBattleReducer.apply(s, _event({"event_type": "init"}))
	assert_object(next.turn).is_equal(s.turn)


func test_determinism_replaying_same_event_list_twice_yields_equal_by_value_snapshots() -> void:
	var events := [
		_event({"event_type": "turn", "turn_number": 1}),
		_event({
			"event_type": "switch", "pokemon_side": "p1", "pokemon_slot": "a",
			"pokemon_species": "Pikachu", "hp_current": 100, "hp_maximum": 100, "hp_fainted": false,
		}),
	]
	var first := LiveBattleSnapshot.new()
	for e in events:
		first = LiveBattleReducer.apply(first, e)
	var second := LiveBattleSnapshot.new()
	for e in events:
		second = LiveBattleReducer.apply(second, e)
	# Byte-meaningful: full-snapshot equals(), not just turn + one slot's hp_current, so a
	# non-determinism bug hiding in any OTHER field (weather/terrain/other slots/conditions)
	# would actually be caught.
	assert_bool(first.equals(second)).is_true()
