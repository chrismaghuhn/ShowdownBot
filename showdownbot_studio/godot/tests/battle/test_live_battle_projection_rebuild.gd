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


## Quality-review fix (2026-07-26): the reset path must not fail-open by trusting a caller to
## have already filtered non-battle inits before calling apply_event() -- workspace/'s own
## _on_event_decoded() already does this filtering (it never forwards a "chat" init to the
## projection at all), but AGENTS.md rule 10 (fail closed by default) means this class must be
## safe on its own even if some future or test caller forwards one anyway. A repeat init whose
## condition_label is NOT "battle" (e.g. a room's own "chat" init) must be a complete no-op for
## the RESET path specifically: it neither wipes the current snapshot/timeline nor disturbs
## whether a genuine battle init has already been seen. It still flows through the normal
## not-applied/ignored handling like any other event LiveBattleReducer has no arm for (event_type
## "init" is never in LiveBattleReducer's own handled-type list, regardless of condition_label),
## so it is still appended to the timeline and still fires event_not_applied("unhandled_type") --
## it is only the RESET that is gated on "battle", never the event's own presence in the record.
func test_repeat_init_with_a_non_battle_condition_label_is_a_no_op_for_the_reset_path() -> void:
	var projection := LiveBattleProjection.new()
	projection.apply_event(_event({"event_type": "init", "condition_label": "battle"}))
	projection.apply_event(_event({"event_type": "turn", "turn_number": 5}))
	var timeline_size_before := projection.get_timeline().size()
	var turn_before: Variant = projection.get_current_snapshot().turn

	var not_applied_reasons: Array[String] = []
	projection.event_not_applied.connect(func(_e: ProtocolEventDTO, reason: String): not_applied_reasons.append(reason))

	# A second init that is NOT a battle init (e.g. a chat room's own |init|chat) must never
	# reset -- the poison-equivalent here is simply "the prior snapshot/timeline", which must
	# survive completely untouched.
	projection.apply_event(_event({"event_type": "init", "condition_label": "chat"}))
	assert_int(projection.get_current_snapshot().turn).is_equal(turn_before)  # no reset happened
	assert_int(projection.get_timeline().size()).is_equal(timeline_size_before + 1)  # still appended, not reset away
	assert_int(not_applied_reasons.size()).is_equal(1)
	assert_str(not_applied_reasons[0]).is_equal("unhandled_type")  # normal ignored/not-applied handling

	# Prove _has_seen_init was never disturbed by the chat init above (neither re-armed nor
	# cleared): a genuine SECOND battle init still triggers a real reset here.
	projection.apply_event(_event({"event_type": "init", "condition_label": "battle"}))
	assert_int(projection.get_timeline().size()).is_equal(1)  # reset to just this one battle init
