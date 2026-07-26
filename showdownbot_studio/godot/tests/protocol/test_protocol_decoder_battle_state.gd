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


## Owner finding 4 (M1 hardening, 2026-07-26): to_int() on a non-numeric string silently returns
## 0 -- a guess, not a parse failure, the same class of bug already fixed for HP parsing below.
## A malformed turn number must fail closed to null, never guessed 0.
func test_malformed_turn_number_fails_closed_to_null() -> void:
	_decoder.decode_frame(">battle-1\n|turn|abc")
	assert_object(_events[0].turn_number).is_null()


## Owner finding 4: the derived snapshot only ever knows p1a/p1b/p2a/p2b -- an identifier for any
## other side (e.g. a triples/multi-battle "p3a") must fail closed to null side/slot, the same
## shape an unparseable identifier already produces, rather than being decoded as if it named a
## real slot (a later dictionary lookup on an unknown key would blow up).
func test_unknown_side_identity_fails_closed_to_null_side_and_slot() -> void:
	_decoder.decode_frame(">battle-1\n|switch|p3a: Whoever|Whoever, L50|100/100")
	var e := _events[0]
	assert_object(e.pokemon_side).is_null()
	assert_object(e.pokemon_slot).is_null()


func test_unknown_slot_letter_fails_closed_to_null_side_and_slot() -> void:
	_decoder.decode_frame(">battle-1\n|switch|p1c: Whoever|Whoever, L50|100/100")
	var e := _events[0]
	assert_object(e.pokemon_side).is_null()
	assert_object(e.pokemon_slot).is_null()


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


## Fail-closed fix (coordinator code-quality review): the slash branch previously called
## to_int() on both halves with no validation, so a malformed left half silently guessed
## hp_current=0 (to_int() on a non-numeric string returns 0) instead of failing closed like the
## slash-less branch already does. Both halves must now be validated with is_valid_int(); on
## failure this returns the SAME all-null dict as the slash-less invalid-int case, never a guess.
func test_malformed_slash_branch_left_half_fails_closed_to_all_null() -> void:
	_decoder.decode_frame(">battle-1\n|-damage|p1a: Pikachu|abc/100")
	var e := _events[0]
	assert_object(e.hp_current).is_null()
	assert_object(e.hp_maximum).is_null()
	assert_object(e.hp_fainted).is_null()
	assert_object(e.hp_status).is_null()


func test_malformed_slash_branch_right_half_fails_closed_to_all_null() -> void:
	_decoder.decode_frame(">battle-1\n|-damage|p1a: Pikachu|50/xyz")
	var e := _events[0]
	assert_object(e.hp_current).is_null()
	assert_object(e.hp_maximum).is_null()
	assert_object(e.hp_fainted).is_null()
	assert_object(e.hp_status).is_null()


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
