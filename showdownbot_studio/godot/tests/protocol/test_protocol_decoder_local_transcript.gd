extends GdUnitTestSuite

const _TRANSCRIPT_PATH := "res://../fixtures/live-protocol-v0/local-spectate-01/transcript.jsonl"
const _GOLDEN_PATH := "res://../fixtures/live-protocol-v0/local-spectate-01/golden_events.jsonl"


func _decode_transcript() -> Array[ProtocolEventDTO]:
	var file := FileAccess.open(_TRANSCRIPT_PATH, FileAccess.READ)
	var decoder := ProtocolDecoder.new()
	var events: Array[ProtocolEventDTO] = []
	var unrecognized: Array[String] = []
	decoder.event_decoded.connect(func(e: ProtocolEventDTO): events.append(e))
	decoder.line_not_understood.connect(func(line: String): unrecognized.append(line))
	while not file.eof_reached():
		var raw_line := file.get_line()
		if raw_line.is_empty():
			continue
		var frame_obj: Dictionary = JSON.parse_string(raw_line)
		decoder.decode_frame(str(frame_obj["raw_frame"]))
	file.close()
	# Every line in this bounded-vocabulary fixture is expected to be either decoded or a
	# documented KNOWN_IGNORED type -- a real transcript tripping line_not_understood is a real
	# gap in this plan's bounded vocabulary (Tasks 13-15), never silently ignored.
	assert_int(unrecognized.size()).is_equal(0)
	return events


func _load_golden() -> Array[Dictionary]:
	var file := FileAccess.open(_GOLDEN_PATH, FileAccess.READ)
	var golden: Array[Dictionary] = []
	while not file.eof_reached():
		var raw_line := file.get_line()
		if not raw_line.is_empty():
			golden.append(JSON.parse_string(raw_line))
	file.close()
	return golden


func test_decoded_events_match_the_golden_sequence_exactly() -> void:
	var events := _decode_transcript()
	var golden := _load_golden()
	assert_int(events.size()).is_equal(golden.size())
	for i in range(golden.size()):
		var expected: Dictionary = golden[i]
		var actual := events[i]
		for key in expected:
			var actual_value: Variant = actual.get(key)
			var expected_value: Variant = expected[key]
			# JSON.parse_string() always returns FLOAT for a JSON number (a Godot JSON parsing
			# quirk, not a real difference), while the DTO's own hp/turn fields are native ints
			# (assert_object() also does not accept String/int actual values at all in this
			# pinned gdUnit4 version -- both are real implementation-reality findings against
			# the plan's illustrative comparison code, fixed here rather than in protocol/
			# itself, which is otherwise unaffected).
			if typeof(actual_value) == TYPE_INT and typeof(expected_value) == TYPE_FLOAT:
				expected_value = int(expected_value)
			assert_that(actual_value).is_equal(expected_value)
