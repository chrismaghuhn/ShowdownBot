extends GdUnitTestSuite

var _decoder: ProtocolDecoder
var _events: Array[ProtocolEventDTO]


func before_test() -> void:
	_decoder = ProtocolDecoder.new()
	_events = []
	_decoder.event_decoded.connect(func(e: ProtocolEventDTO): _events.append(e))


func test_weather_line_decodes_condition_label() -> void:
	_decoder.decode_frame(">battle-1\n|-weather|RainDance")
	assert_str(str(_events[0].condition_label)).is_equal("RainDance")


func test_weather_none_clears_weather() -> void:
	_decoder.decode_frame(">battle-1\n|-weather|none")
	assert_object(_events[0].condition_label).is_null()


func test_fieldstart_strips_move_prefix() -> void:
	_decoder.decode_frame(">battle-1\n|-fieldstart|move: Trick Room")
	assert_str(str(_events[0].condition_label)).is_equal("Trick Room")


func test_sidestart_decodes_side_and_condition() -> void:
	_decoder.decode_frame(">battle-1\n|-sidestart|p1: Player1|move: Stealth Rock")
	var e := _events[0]
	assert_str(str(e.side)).is_equal("p1")
	assert_str(str(e.condition_label)).is_equal("Stealth Rock")


func test_move_line_decodes_species_side_slot() -> void:
	_decoder.decode_frame(">battle-1\n|move|p1a: Pikachu|Thunderbolt|p2a: Ditto")
	assert_str(str(_events[0].pokemon_side)).is_equal("p1")


func test_win_line_decodes_battle_completion() -> void:
	_decoder.decode_frame(">battle-1\n|win|Player1")
	assert_str(_events[0].event_type).is_equal("win")


func test_tie_line_decodes_battle_completion() -> void:
	_decoder.decode_frame(">battle-1\n|tie")
	assert_str(_events[0].event_type).is_equal("tie")
