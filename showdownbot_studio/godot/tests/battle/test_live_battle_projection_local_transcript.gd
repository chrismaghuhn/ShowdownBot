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


func test_folding_the_real_transcript_twice_yields_equal_by_value_snapshots() -> void:
	var first := _fold_transcript()
	var second := _fold_transcript()
	# Byte-meaningful: full-snapshot equals() (turn/weather/terrain/battle_completed, all four
	# slots' full fields, both sides' conditions, field conditions) -- not just the final turn
	# number, which would miss a non-determinism bug hiding in any other field.
	assert_bool(first.get_current_snapshot().equals(second.get_current_snapshot())).is_true()


## Hand-derived end state, cross-checked directly against
## fixtures/live-protocol-v0/local-spectate-01/golden_events.jsonl (the M1b hand-reviewed golden
## DTO sequence, not the fold's own output): applying LiveBattleReducer's documented rules
## (switch/drag fully replaces a slot; -damage/-heal merges only the fields the event carries,
## keeping the existing species; faint and a "0 fnt"-style -damage both force hp_current=0,
## hp_fainted=true; win completes the battle) line by line to every p1a/p1b/p2a/p2b-tagged event
## in the golden file gives:
##   - final turn: 16 (golden_events.jsonl line 144, the last "turn" event; no further turn event
##     precedes the "win" on line 153)
##   - battle_completed: true (the "win" on line 153)
##   - p1a: last switch is Brambleghast (line 109); last HP event is the "0 fnt"-style -damage on
##     line 151, immediately followed by the faint on line 152 -- both sides of p1 end fainted,
##     which is exactly why p2 wins.
##   - p1b: last switch is Emboar (line 125); faints on line 147/148.
##   - p2a: last switch is Scream Tail (line 149), switched in with full HP and never damaged
##     again before the battle ends.
##   - p2b: last switch is Poliwrath (line 48); the only damage after that switch is line 142
##     (100 -> 74), never fainted.
## This was cross-checked with an independent, from-scratch Python re-implementation of the same
## reducer rules run directly against golden_events.jsonl (not against this test's own
## expectations) before being pinned here -- it agrees with the values below exactly.
## Owner finding 5 (M1 hardening, 2026-07-26): golden_events.jsonl lines 11/63 record a real
## Electric Terrain -fieldstart/-fieldend pair (see local-spectate-01/SOURCES.md provenance).
## The end-state pin below cannot see this on its own -- the matching -fieldend has already
## cleared it by the time the transcript finishes folding -- so this test observes every
## PUBLISHED snapshot along the way via snapshot_published, proving terrain was actually SET to
## "Electric Terrain" at some point mid-battle, not only that it ends null (which a decoder that
## never sets terrain at all would also satisfy).
func test_folding_the_real_transcript_sets_and_clears_terrain_from_the_real_electric_terrain_pair() -> void:
	var terrain_values: Array = []
	var decoder := ProtocolDecoder.new()
	var projection := LiveBattleProjection.new()
	projection.snapshot_published.connect(func(s: LiveBattleSnapshot): terrain_values.append(s.terrain))
	decoder.event_decoded.connect(projection.apply_event)
	var file := FileAccess.open(_TRANSCRIPT_PATH, FileAccess.READ)
	while not file.eof_reached():
		var raw_line := file.get_line()
		if raw_line.is_empty():
			continue
		var frame_obj: Dictionary = JSON.parse_string(raw_line)
		decoder.decode_frame(str(frame_obj["raw_frame"]))
	file.close()
	assert_bool(terrain_values.has("Electric Terrain")).is_true()
	var final_snapshot := projection.get_current_snapshot()
	assert_object(final_snapshot.terrain).is_null()  # cleared by the real -fieldend
	# Electric Terrain must never leak into field_conditions -- routed to `terrain` exclusively.
	assert_bool(Array(final_snapshot.get_field_conditions()).has("Electric Terrain")).is_false()


func test_folding_the_real_transcript_pins_the_golden_end_state() -> void:
	var snapshot := _fold_transcript().get_current_snapshot()

	assert_int(snapshot.turn).is_equal(16)
	assert_bool(snapshot.battle_completed).is_true()

	var p1a := snapshot.get_slot("p1", "a")
	assert_str(str(p1a.species)).is_equal("Brambleghast")
	assert_int(p1a.hp_current).is_equal(0)
	assert_bool(p1a.hp_fainted).is_true()

	var p1b := snapshot.get_slot("p1", "b")
	assert_str(str(p1b.species)).is_equal("Emboar")
	assert_int(p1b.hp_current).is_equal(0)
	assert_bool(p1b.hp_fainted).is_true()

	var p2a := snapshot.get_slot("p2", "a")
	assert_str(str(p2a.species)).is_equal("Scream Tail")
	assert_int(p2a.hp_current).is_equal(100)
	assert_bool(p2a.hp_fainted).is_false()

	var p2b := snapshot.get_slot("p2", "b")
	assert_str(str(p2b.species)).is_equal("Poliwrath")
	assert_int(p2b.hp_current).is_equal(74)
	assert_bool(p2b.hp_fainted).is_false()
