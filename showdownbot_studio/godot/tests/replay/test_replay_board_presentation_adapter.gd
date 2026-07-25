extends GdUnitTestSuite


func _make_event(side: String, slot: String, species: String, hp_current: int, hp_maximum: int, status: Variant = null) -> BattleEventDTO:
	var e := BattleEventDTO.new()
	e.protocol_index = 1
	e.type = "switch"
	e.pokemon_side = side
	e.pokemon_slot = slot
	e.pokemon_species = species
	e.hp_current = hp_current
	e.hp_maximum = hp_maximum
	e.hp_fainted = false
	e.hp_status = status
	return e


func test_not_has_replay_yields_unavailable_with_reason() -> void:
	var board := BoardModel.new()
	board.has_replay = false
	var snapshot := ReplayBoardPresentationAdapter.build_snapshot(board)
	assert_bool(snapshot.presentation_available).is_false()
	assert_str(snapshot.empty_state_reason).is_equal("No replay evidence in this bundle")


func test_null_board_yields_unavailable_with_reason() -> void:
	var snapshot := ReplayBoardPresentationAdapter.build_snapshot(null)
	assert_bool(snapshot.presentation_available).is_false()
	assert_str(snapshot.empty_state_reason).is_equal("No replay evidence in this bundle")


func test_has_replay_true_yields_available_regardless_of_recorded_state() -> void:
	var board := BoardModel.new()
	board.has_replay = true
	board.has_recorded_state = false
	var snapshot := ReplayBoardPresentationAdapter.build_snapshot(board)
	assert_bool(snapshot.presentation_available).is_true()
	assert_str(snapshot.empty_state_reason).is_equal("")


func test_slot_species_hp_and_status_carry_over() -> void:
	var board := BoardModel.new()
	board.has_replay = true
	board.replace_slot_from_switch("p1", "a", _make_event("p1", "a", "Pikachu", 20, 35, "brn"))
	var snapshot := ReplayBoardPresentationAdapter.build_snapshot(board)
	var slot := snapshot.get_slot("p1", "a")
	assert_str(str(slot.species)).is_equal("Pikachu")
	assert_int(slot.hp_current).is_equal(20)
	assert_int(slot.hp_maximum).is_equal(35)
	assert_str(str(slot.hp_status)).is_equal("brn")


func test_turn_weather_terrain_and_field_conditions_carry_over() -> void:
	var board := BoardModel.new()
	board.has_replay = true
	board.turn_number = 3
	board.weather = "RainDance"
	board.terrain = "Electric Terrain"
	board.add_field_condition("Trick Room")
	var snapshot := ReplayBoardPresentationAdapter.build_snapshot(board)
	assert_int(snapshot.turn).is_equal(3)
	assert_str(str(snapshot.weather)).is_equal("RainDance")
	assert_str(str(snapshot.terrain)).is_equal("Electric Terrain")
	assert_bool(snapshot.field_conditions.has("Trick Room")).is_true()


func test_side_conditions_carry_over_per_side() -> void:
	var board := BoardModel.new()
	board.has_replay = true
	board.add_side_condition("p1", "Stealth Rock")
	board.add_side_condition("p2", "Spikes")
	var snapshot := ReplayBoardPresentationAdapter.build_snapshot(board)
	assert_bool(snapshot.side_conditions["p1"].has("Stealth Rock")).is_true()
	assert_bool(snapshot.side_conditions["p2"].has("Spikes")).is_true()
