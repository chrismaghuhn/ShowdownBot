extends GdUnitTestSuite


func test_defaults_are_null_or_empty() -> void:
	var e := ProtocolEventDTO.new()
	assert_int(e.protocol_index).is_equal(0)
	assert_str(e.room_id).is_equal("")
	assert_str(e.event_type).is_equal("")
	assert_object(e.pokemon_species).is_null()
	assert_object(e.hp_current).is_null()


func test_fields_are_settable_before_seal() -> void:
	var e := ProtocolEventDTO.new()
	e.protocol_index = 3
	e.event_type = "switch"
	e.pokemon_side = "p1"
	e.pokemon_slot = "a"
	e.pokemon_species = "Pikachu"
	e.hp_current = 100
	e.hp_maximum = 100
	e.hp_fainted = false
	assert_int(e.protocol_index).is_equal(3)
	assert_str(str(e.pokemon_species)).is_equal("Pikachu")
	assert_int(e.hp_current).is_equal(100)


func test_condition_label_carries_init_room_type() -> void:
	var e := ProtocolEventDTO.new()
	e.event_type = "init"
	e.condition_label = "battle"
	assert_str(str(e.condition_label)).is_equal("battle")


func test_seal_freezes_further_writes() -> void:
	var e := ProtocolEventDTO.new()
	e.event_type = "turn"
	e.turn_number = 1
	e.seal()
	e.turn_number = 99
	assert_int(e.turn_number).is_equal(1)
