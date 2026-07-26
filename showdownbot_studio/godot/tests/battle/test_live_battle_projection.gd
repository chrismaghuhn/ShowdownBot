extends GdUnitTestSuite


func _event(fields: Dictionary) -> ProtocolEventDTO:
	var e := ProtocolEventDTO.new()
	for key in fields:
		e.set(key, fields[key])
	e.seal()
	return e


func test_initial_snapshot_is_empty_and_timeline_is_empty() -> void:
	var p := LiveBattleProjection.new()
	assert_int(p.get_timeline().size()).is_equal(0)
	assert_object(p.get_current_snapshot().turn).is_null()


func test_apply_event_updates_current_snapshot_and_appends_to_timeline() -> void:
	var p := LiveBattleProjection.new()
	p.apply_event(_event({"event_type": "turn", "turn_number": 1}))
	assert_int(p.get_current_snapshot().turn).is_equal(1)
	assert_int(p.get_timeline().size()).is_equal(1)


func test_apply_event_emits_snapshot_published() -> void:
	var p := LiveBattleProjection.new()
	var received: Array[LiveBattleSnapshot] = []
	p.snapshot_published.connect(func(s: LiveBattleSnapshot): received.append(s))
	p.apply_event(_event({"event_type": "turn", "turn_number": 1}))
	assert_int(received.size()).is_equal(1)
	assert_int(received[0].turn).is_equal(1)


func test_battle_completed_signal_fires_on_win() -> void:
	var p := LiveBattleProjection.new()
	var completed_rooms: Array[String] = []
	p.battle_completed.connect(func(room_id: String): completed_rooms.append(room_id))
	p.set_room_id("battle-1")
	p.apply_event(_event({"event_type": "win"}))
	assert_int(completed_rooms.size()).is_equal(1)
	assert_str(completed_rooms[0]).is_equal("battle-1")


## Owner finding 6 (M1 hardening, 2026-07-26): battle_completed was level-triggered (fires again
## on every subsequently applied event once _current.battle_completed is true), not edge-triggered
## on the false->true transition. A trailing event after win/tie (e.g. a late -heal/upkeep-shaped
## event some real transcripts still carry) must not re-publish completion.
func test_battle_completed_signal_fires_only_once_even_after_further_events() -> void:
	var p := LiveBattleProjection.new()
	var completed_rooms: Array[String] = []
	p.battle_completed.connect(func(room_id: String): completed_rooms.append(room_id))
	p.set_room_id("battle-1")
	p.apply_event(_event({"event_type": "win"}))
	p.apply_event(_event({
		"event_type": "-heal", "pokemon_side": "p1", "pokemon_slot": "a", "hp_current": 50,
	}))
	p.apply_event(_event({"event_type": "turn", "turn_number": 99}))
	assert_int(completed_rooms.size()).is_equal(1)
	assert_str(completed_rooms[0]).is_equal("battle-1")


func test_get_timeline_returns_an_independent_copy() -> void:
	var p := LiveBattleProjection.new()
	p.apply_event(_event({"event_type": "turn", "turn_number": 1}))
	var timeline := p.get_timeline()
	timeline.append(_event({"event_type": "turn", "turn_number": 2}))
	assert_int(p.get_timeline().size()).is_equal(1)
