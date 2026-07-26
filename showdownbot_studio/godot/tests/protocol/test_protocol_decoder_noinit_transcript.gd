extends GdUnitTestSuite

## Owner finding 3 (M1 hardening, 2026-07-26): the real captured rejection frame from the pinned
## local server (fixtures/live-protocol-v0/local-noinit-nonexistent-01/, see this fixture set's
## SOURCES.md for full provenance) decodes exactly as the hand-derived golden expects -- proves
## the fix against the actual wire content the server sends, not only a hand-written literal in
## a unit test.

const _TRANSCRIPT_PATH := "res://../fixtures/live-protocol-v0/local-noinit-nonexistent-01/transcript.jsonl"
const _GOLDEN_PATH := "res://../fixtures/live-protocol-v0/local-noinit-nonexistent-01/golden_events.jsonl"


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


func test_real_noinit_rejection_frame_decodes_to_the_golden_event() -> void:
	var events := _decode_transcript()
	var golden := _load_golden()
	assert_int(events.size()).is_equal(golden.size())
	if events.size() != golden.size():
		return
	for i in range(golden.size()):
		var expected: Dictionary = golden[i]
		var actual := events[i]
		for key in expected:
			assert_that(actual.get(key)).is_equal(expected[key])
