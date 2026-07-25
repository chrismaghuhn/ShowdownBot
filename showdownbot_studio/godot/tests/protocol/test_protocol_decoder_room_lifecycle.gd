extends GdUnitTestSuite

var _decoder: ProtocolDecoder
var _events: Array[ProtocolEventDTO]
var _known_ignored: Array[String]
var _unrecognized: Array[String]


func before_test() -> void:
	_decoder = ProtocolDecoder.new()
	_events = []
	_known_ignored = []
	_unrecognized = []
	_decoder.event_decoded.connect(func(e: ProtocolEventDTO): _events.append(e))
	_decoder.known_ignored_event.connect(func(_line: String, message_type: String): _known_ignored.append(message_type))
	_decoder.line_not_understood.connect(func(line: String): _unrecognized.append(line))


func test_room_prefix_is_attached_to_every_event_in_the_frame() -> void:
	_decoder.decode_frame(">battle-1\n|init|battle\n|title|A vs B")
	assert_int(_events.size()).is_equal(2)
	assert_str(_events[0].room_id).is_equal("battle-1")
	assert_str(_events[1].room_id).is_equal("battle-1")


func test_init_battle_line_decodes_room_type() -> void:
	_decoder.decode_frame(">battle-1\n|init|battle")
	assert_str(_events[0].event_type).is_equal("init")
	assert_str(str(_events[0].condition_label)).is_equal("battle")


func test_init_chat_line_decodes_a_different_room_type() -> void:
	_decoder.decode_frame(">some-room\n|init|chat")
	assert_str(str(_events[0].condition_label)).is_equal("chat")


func test_error_line_decodes_with_reason() -> void:
	_decoder.decode_frame(">battle-1\n|error|[Room not found]")
	assert_str(_events[0].event_type).is_equal("error")
	assert_str(str(_events[0].error_reason)).is_equal("[Room not found]")


func test_deinit_line_decodes_as_its_own_event_type() -> void:
	_decoder.decode_frame(">battle-1\n|deinit")
	assert_str(_events[0].event_type).is_equal("deinit")


func test_protocol_index_increments_monotonically_across_frames() -> void:
	_decoder.decode_frame(">battle-1\n|init|battle")
	_decoder.decode_frame(">battle-1\n|title|A vs B")
	assert_int(_events[0].protocol_index).is_equal(0)
	assert_int(_events[1].protocol_index).is_equal(1)


func test_known_ignored_line_is_reported_but_never_as_not_understood() -> void:
	_decoder.decode_frame(">battle-1\n|player|p1|Alice|1")
	assert_int(_events.size()).is_equal(0)
	assert_int(_unrecognized.size()).is_equal(0)
	assert_int(_known_ignored.size()).is_equal(1)
	assert_str(_known_ignored[0]).is_equal("player")


func test_chat_and_timestamp_lines_are_known_ignored() -> void:
	_decoder.decode_frame(">battle-1\n|c|Alice|hi\n|t:|1234567890")
	assert_int(_known_ignored.size()).is_equal(2)


func test_genuinely_unrecognized_line_is_reported_not_understood() -> void:
	_decoder.decode_frame(">battle-1\n|totallyunknowntype|foo|bar")
	assert_int(_events.size()).is_equal(0)
	assert_int(_known_ignored.size()).is_equal(0)
	assert_int(_unrecognized.size()).is_equal(1)
	assert_str(_unrecognized[0]).is_equal("|totallyunknowntype|foo|bar")


func test_frame_without_room_prefix_decodes_with_empty_room_id() -> void:
	_decoder.decode_frame("|init|battle")
	assert_str(_events[0].room_id).is_equal("")


## Real-capture finding (Task 12's local-spectate-01 transcript): Showdown emits a bare "|"
## separator line between event batches within a frame -- a genuine, valid, recognized-but-
## deliberately-out-of-scope construct, never a genuinely unrecognized line.
func test_blank_separator_line_is_known_ignored() -> void:
	# "|turn|1" is deliberately NOT used here -- turn is decoded starting Task 14, and this test
	# must isolate the blank-separator classification without depending on later vocabulary.
	_decoder.decode_frame(">battle-1\n|\n|init|battle")
	assert_int(_unrecognized.size()).is_equal(0)
	assert_int(_known_ignored.size()).is_equal(1)
	assert_int(_events.size()).is_equal(1)


## Real-capture finding: several genuine, valid VGC battle message types the real transcript
## produced (abilities/boosts/crits/protect activation/upkeep) that Tasks 13-15's decoded
## vocabulary deliberately does not model yet -- each must be KNOWN_IGNORED, never UNKNOWN.
func test_additional_real_battle_message_types_are_known_ignored() -> void:
	_decoder.decode_frame(
		">battle-1" +
		"\n|-ability|p1a: Granbull|Intimidate|boost" +
		"\n|-unboost|p2a: Cetitan|atk|1" +
		"\n|-boost|p1b: Primarina|spa|1" +
		"\n|-resisted|p1b: Primarina" +
		"\n|-crit|p2a: Orthworm" +
		"\n|-supereffective|p1a: Granbull" +
		"\n|-singleturn|p1b: Lunala|Protect" +
		"\n|-fail|p1b: Lunala" +
		"\n|-activate|p1b: Lunala|move: Protect" +
		"\n|-enditem|p1b: Primarina|Throat Spray" +
		"\n|upkeep"
	)
	assert_int(_unrecognized.size()).is_equal(0)
	assert_int(_known_ignored.size()).is_equal(11)
