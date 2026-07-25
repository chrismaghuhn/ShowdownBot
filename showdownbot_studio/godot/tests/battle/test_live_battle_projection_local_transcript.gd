extends GdUnitTestSuite

const _TRANSCRIPT_PATH := "res://../fixtures/live-protocol-v0/local-spectate-01/transcript.jsonl"


func _fold_transcript() -> LiveBattleProjection:
	var file := FileAccess.open(_TRANSCRIPT_PATH, FileAccess.READ)
	var decoder := ProtocolDecoder.new()
	var projection := LiveBattleProjection.new()
	decoder.event_decoded.connect(projection.apply_event)
	while not file.eof_reached():
		var raw_line := file.get_line()
		if raw_line.is_empty():
			continue
		var frame_obj: Dictionary = JSON.parse_string(raw_line)
		decoder.decode_frame(str(frame_obj["raw_frame"]))
	file.close()
	return projection


func test_folding_the_real_transcript_ends_with_a_completed_battle() -> void:
	assert_bool(_fold_transcript().get_current_snapshot().battle_completed).is_true()


func test_folding_the_real_transcript_twice_yields_equal_by_value_final_turn_numbers() -> void:
	var first := _fold_transcript()
	var second := _fold_transcript()
	# assert_object() only accepts Object/null (confirmed red: "GdUnitObjectAssert inital error,
	# unexpected type <int>") -- turn is a non-null int by the end of a real transcript fold, so
	# assert_int() is the correct comparison for this Variant-typed nullable scalar (same pattern
	# Task 19's test_turn_event_updates_turn_number already uses successfully).
	assert_int(first.get_current_snapshot().turn).is_equal(second.get_current_snapshot().turn)
