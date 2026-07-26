extends GdUnitTestSuite


func _event(fields: Dictionary) -> ProtocolEventDTO:
	var e := ProtocolEventDTO.new()
	for key in fields:
		e.set(key, fields[key])
	e.seal()
	return e


func test_repeat_init_discards_poisoned_pre_state_and_rebuilds_from_scratch() -> void:
	var projection := LiveBattleProjection.new()

	# 1. A genuine FIRST battle init reaches the projection -- mirrors Task 29's fixed wiring,
	# which always forwards a confirmed battle init. Without this step, the "second" init below
	# would actually be the projection's first, and the reset this test proves would never need
	# to fire even in a correct implementation.
	projection.apply_event(_event({"event_type": "init", "condition_label": "battle"}))

	# 2. Poison the state: none of this must survive a rebuild.
	projection.apply_event(_event({"event_type": "turn", "turn_number": 99}))
	projection.apply_event(_event({
		"event_type": "switch", "pokemon_side": "p1", "pokemon_slot": "a",
		"pokemon_species": "FakeMon", "hp_current": 1, "hp_maximum": 1, "hp_fainted": false,
	}))
	projection.apply_event(_event({"event_type": "OLD_ONLY_EVENT"}))

	# 3. The resent authoritative history arrives, starting with a genuine SECOND battle init --
	# exactly as a real reconnect resend does.
	var resend_history := [
		_event({"event_type": "init", "condition_label": "battle"}),
		_event({"event_type": "turn", "turn_number": 1}),
		_event({
			"event_type": "switch", "pokemon_side": "p1", "pokemon_slot": "a",
			"pokemon_species": "Pikachu", "hp_current": 100, "hp_maximum": 100, "hp_fainted": false,
		}),
	]
	for e in resend_history:
		projection.apply_event(e)

	# 4. Assert the poison is gone.
	var snapshot := projection.get_current_snapshot()
	assert_int(snapshot.turn).is_equal(1)  # not 99
	assert_str(str(snapshot.get_slot("p1", "a").species)).is_equal("Pikachu")  # not FakeMon

	# 5. The timeline is EXACTLY the resend history (including its own leading init) -- this is
	# the load-bearing proof (see this task's "honesty note" above).
	var timeline := projection.get_timeline()
	assert_int(timeline.size()).is_equal(resend_history.size())
	for e in timeline:
		assert_str(e.event_type).is_not_equal("OLD_ONLY_EVENT")


func test_first_init_never_triggers_a_reset() -> void:
	var projection := LiveBattleProjection.new()
	projection.apply_event(_event({"event_type": "init", "condition_label": "battle"}))
	projection.apply_event(_event({"event_type": "turn", "turn_number": 1}))
	assert_int(projection.get_timeline().size()).is_equal(2)  # not discarded by its own first init
