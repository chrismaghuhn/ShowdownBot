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


## Owner finding 3 (M1 hardening, 2026-07-26): the pinned local server rejects an unknown/private
## room join with `|noinit|<subtype>|<reason>`, never `|error|` (verified against the real server,
## fixtures/live-protocol-v0/local-noinit-nonexistent-01/). Before this fix, `noinit` fell through
## to the decoder's default case and was reported line_not_understood -- RoomState never learned
## the join was rejected and silently hung in JOINING forever.
func test_noinit_nonexistent_line_decodes_with_subtype_and_reason() -> void:
	_decoder.decode_frame(
		">battle-studio-nonexistent-room-capture\n" +
		"|noinit|nonexistent|The room \"battle-studio-nonexistent-room-capture\" does not exist."
	)
	assert_int(_unrecognized.size()).is_equal(0)
	assert_int(_events.size()).is_equal(1)
	if _events.size() != 1:
		return  # guard: avoid an out-of-bounds crash on the pre-fix red run below
	assert_str(_events[0].event_type).is_equal("noinit")
	assert_str(str(_events[0].noinit_subtype)).is_equal("nonexistent")
	assert_str(str(_events[0].error_reason)).is_equal(
		"The room \"battle-studio-nonexistent-room-capture\" does not exist."
	)


## Real, valid subtype (server/users.ts ~1310-1335: invite-only room, tour-join failure, room ban,
## groupchat ban all use joinfailed) -- not captured live (requires a trusted/authenticated setup
## beyond this finding's scope), but the wire shape is identical and documented in server source.
func test_noinit_joinfailed_line_decodes_with_subtype_and_reason() -> void:
	_decoder.decode_frame(">groupchat-x\n|noinit|joinfailed|You are banned from the room \"groupchat-x\".")
	assert_int(_events.size()).is_equal(1)
	if _events.size() != 1:
		return
	assert_str(_events[0].event_type).is_equal("noinit")
	assert_str(str(_events[0].noinit_subtype)).is_equal("joinfailed")
	assert_str(str(_events[0].error_reason)).is_equal("You are banned from the room \"groupchat-x\".")


## Fail-closed per finding 3(b): a noinit subtype outside the known {nonexistent, joinfailed} set
## (e.g. server/rooms.ts:973's own "rename" noinit, unrelated to a join rejection) must never be
## guessed as one of the known subtypes -- it is still surfaced as a DECODED_STATE_EVENT (so a
## pending join is never left hanging), but tagged UNKNOWN rather than misclassified.
func test_noinit_unrecognized_subtype_stays_fail_closed_as_unknown() -> void:
	_decoder.decode_frame(">some-room\n|noinit|rename|newroomid|New Title")
	assert_int(_unrecognized.size()).is_equal(0)
	assert_int(_events.size()).is_equal(1)
	if _events.size() != 1:
		return
	assert_str(_events[0].event_type).is_equal("noinit")
	assert_str(str(_events[0].noinit_subtype)).is_equal("UNKNOWN")


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


## Two-room no-leakage test (coordinator code-quality review, M1b watchlist item): decode_frame()
## is called for two DIFFERENT rooms in sequential calls -- every event must carry only its OWN
## frame's room id, and nothing persists across calls (each decode_frame() call resets room_id
## from that frame's own ">roomid" header, never carrying forward the previous frame's).
func test_room_id_does_not_leak_across_sequential_frames_from_different_rooms() -> void:
	_decoder.decode_frame(">room-a\n|init|battle\n|title|A vs B")
	_decoder.decode_frame(">room-b\n|init|chat")
	assert_int(_events.size()).is_equal(3)
	assert_str(_events[0].room_id).is_equal("room-a")
	assert_str(_events[1].room_id).is_equal("room-a")
	assert_str(_events[2].room_id).is_equal("room-b")
	assert_str(str(_events[2].condition_label)).is_equal("chat")
	assert_str(_events[0].room_id).is_not_equal("room-b")
	assert_str(_events[2].room_id).is_not_equal("room-a")
