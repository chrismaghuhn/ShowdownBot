extends GdUnitTestSuite

var _decoder: ProtocolDecoder
var _events: Array[ProtocolEventDTO]


func before_test() -> void:
	_decoder = ProtocolDecoder.new()
	_events = []
	_decoder.event_decoded.connect(func(e: ProtocolEventDTO): _events.append(e))


func test_turn_line_decodes_turn_number() -> void:
	_decoder.decode_frame(">battle-1\n|turn|4")
	assert_int(_events[0].turn_number).is_equal(4)


func test_switch_line_decodes_side_slot_species_and_hp() -> void:
	_decoder.decode_frame(">battle-1\n|switch|p1a: Pikachu|Pikachu, L50, M|100/100")
	var e := _events[0]
	assert_str(str(e.pokemon_side)).is_equal("p1")
	assert_str(str(e.pokemon_slot)).is_equal("a")
	assert_str(str(e.pokemon_species)).is_equal("Pikachu")
	assert_int(e.hp_current).is_equal(100)
	assert_int(e.hp_maximum).is_equal(100)
	assert_bool(e.hp_fainted).is_false()


func test_drag_line_decodes_same_as_switch() -> void:
	_decoder.decode_frame(">battle-1\n|drag|p2b: Ditto|Ditto, shiny|50/50")
	assert_str(_events[0].event_type).is_equal("drag")
	assert_str(str(_events[0].pokemon_species)).is_equal("Ditto")


func test_damage_line_decodes_hp_and_status() -> void:
	_decoder.decode_frame(">battle-1\n|-damage|p1a: Pikachu|50/100 brn")
	var e := _events[0]
	assert_int(e.hp_current).is_equal(50)
	assert_int(e.hp_maximum).is_equal(100)
	assert_str(str(e.hp_status)).is_equal("brn")


func test_heal_line_decodes_hp() -> void:
	_decoder.decode_frame(">battle-1\n|-heal|p1a: Pikachu|75/100")
	assert_int(_events[0].hp_current).is_equal(75)


func test_hidden_max_hp_fainted_with_no_slash_decodes_zero_hp_and_fainted_true() -> void:
	# The real, common "0 fnt" shape (opponent side, hidden max HP, no "/" at all) -- the bug this
	# task fixes.
	_decoder.decode_frame(">battle-1\n|-damage|p2a: Ditto|0 fnt")
	var e := _events[0]
	assert_int(e.hp_current).is_equal(0)
	assert_object(e.hp_maximum).is_null()
	assert_bool(e.hp_fainted).is_true()
	assert_object(e.hp_status).is_null()


func test_exact_zero_over_max_also_sets_fainted_true() -> void:
	_decoder.decode_frame(">battle-1\n|-damage|p1a: Pikachu|0/100")
	assert_bool(_events[0].hp_fainted).is_true()


func test_status_line_decodes_status_label() -> void:
	_decoder.decode_frame(">battle-1\n|-status|p1a: Pikachu|par")
	assert_str(str(_events[0].hp_status)).is_equal("par")


func test_curestatus_line_clears_status() -> void:
	_decoder.decode_frame(">battle-1\n|-curestatus|p1a: Pikachu|par")
	assert_object(_events[0].hp_status).is_null()


func test_faint_line_decodes_side_and_slot() -> void:
	_decoder.decode_frame(">battle-1\n|faint|p2a: Ditto")
	var e := _events[0]
	assert_str(str(e.pokemon_side)).is_equal("p2")
	assert_str(str(e.pokemon_slot)).is_equal("a")
