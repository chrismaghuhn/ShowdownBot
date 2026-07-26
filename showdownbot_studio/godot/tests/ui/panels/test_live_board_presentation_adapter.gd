extends GdUnitTestSuite


## Owner-approved cross-slice guard fix (2026-07-26): LiveBattleSnapshot.with_turn() was renamed
## to the battle/-internal _with_turn() (see battle/dto/live_battle_snapshot.gd's own comment).
## This fixture used to call it directly from outside battle/ -- the one external caller the
## guard fix's own grep found. Resolved the derived-state way (AGENTS.md rule 5: state is
## derived, never manually patched) rather than reaching into the internal builder: fold a real
## "turn" ProtocolEventDTO through the SAME public LiveBattleReducer.apply() the real decode path
## uses, exactly like production code would arrive at a turn=3 snapshot.
func _turn_event(turn_number: int) -> ProtocolEventDTO:
	var event := ProtocolEventDTO.new()
	event.event_type = "turn"
	event.turn_number = turn_number
	event.seal()
	return event


func test_empty_live_snapshot_is_presentation_available() -> void:
	var snapshot := LiveBoardPresentationAdapter.build_snapshot(LiveBattleSnapshot.new())
	assert_bool(snapshot.presentation_available).is_true()


func test_null_live_snapshot_is_unavailable_with_a_reason() -> void:
	var snapshot := LiveBoardPresentationAdapter.build_snapshot(null)
	assert_bool(snapshot.presentation_available).is_false()
	assert_str(snapshot.empty_state_reason).is_equal("No battle state received yet")


func test_slot_species_and_hp_carry_over() -> void:
	var live := LiveBattleSnapshot.new().with_slot("p1", "a", LiveBattleSlotSnapshot.new("Pikachu", 20, 35))
	var snapshot := LiveBoardPresentationAdapter.build_snapshot(live)
	var out_slot := snapshot.get_slot("p1", "a")
	assert_str(str(out_slot.species)).is_equal("Pikachu")
	assert_int(out_slot.hp_current).is_equal(20)


func test_turn_and_side_conditions_carry_over() -> void:
	var live := LiveBattleReducer.apply(LiveBattleSnapshot.new(), _turn_event(3)).with_side_condition_added("p1", "Stealth Rock")
	var snapshot := LiveBoardPresentationAdapter.build_snapshot(live)
	assert_int(snapshot.turn).is_equal(3)
	assert_bool(snapshot.side_conditions["p1"].has("Stealth Rock")).is_true()


func _fieldstart_event(condition_label: String) -> ProtocolEventDTO:
	var event := ProtocolEventDTO.new()
	event.event_type = "-fieldstart"
	event.condition_label = condition_label
	event.seal()
	return event


## Owner finding 5 (M1 hardening, 2026-07-26): terrain now reaches LiveBattleSnapshot via
## LiveBattleReducer's terrain routing instead of never being set at all -- this proves the
## adapter's own pre-existing `snapshot.terrain = live.terrain` line (build_snapshot()) actually
## surfaces a real terrain value end to end, not only that the underlying field exists.
func test_terrain_carries_over_from_a_real_fieldstart_event() -> void:
	var live := LiveBattleReducer.apply(LiveBattleSnapshot.new(), _fieldstart_event("Electric Terrain"))
	var snapshot := LiveBoardPresentationAdapter.build_snapshot(live)
	assert_str(str(snapshot.terrain)).is_equal("Electric Terrain")
