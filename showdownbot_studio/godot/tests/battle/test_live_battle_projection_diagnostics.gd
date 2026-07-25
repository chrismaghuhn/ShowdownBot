extends GdUnitTestSuite

## Watchlist M1c: "Unknown or inconsistent state events fail closed and remain diagnostically
## visible" (2026-07-25-phase3-m1-implementation-watchlist.md). The reducer/projection previously
## no-op'd silently on an unmatched event type (live_battle_reducer.gd's default `_:` branch) and
## on an inconsistent one (the early `return previous` guards in _apply_switch/_apply_hp_change/
## _apply_status/_apply_faint when pokemon_side/pokemon_slot is missing). Fail-closed alone is not
## enough per the watchlist; this proves the diagnostic-visibility half too.
##
## Precedence: the watchlist's own precedence rule (this document, "Rule of precedence") --
## "the later revision note and its corresponding acceptance test win over earlier code samples"
## -- applies here the same way it already applied to M1a's literal peer-null guard: the M1c plan
## task text did not show this signal, but the watchlist is the binding companion document and
## wins over the earlier, less complete code sample. No owner block needed for this application.


func _event(fields: Dictionary) -> ProtocolEventDTO:
	var e := ProtocolEventDTO.new()
	for key in fields:
		e.set(key, fields[key])
	e.seal()
	return e


func test_inconsistent_event_fires_signal_with_reason_and_leaves_state_unchanged() -> void:
	var p := LiveBattleProjection.new()
	var reasons: Array[String] = []
	var events: Array[ProtocolEventDTO] = []
	p.event_not_applied.connect(func(evt: ProtocolEventDTO, reason: String):
		events.append(evt)
		reasons.append(reason)
	)
	var before := p.get_current_snapshot()
	# Missing pokemon_side/pokemon_slot on a -damage event -- the reducer's own early-return
	# guard (this is a modeled event type, but a genuinely inconsistent instance of it).
	p.apply_event(_event({"event_type": "-damage", "hp_current": 10}))
	assert_int(reasons.size()).is_equal(1)
	assert_str(reasons[0]).is_equal("inconsistent_state")
	assert_object(p.get_current_snapshot().get_slot("p1", "a").hp_current).is_equal(before.get_slot("p1", "a").hp_current)
	assert_object(p.get_current_snapshot().turn).is_equal(before.turn)


func test_unhandled_decoded_type_fires_signal_with_unhandled_type_reason() -> void:
	var p := LiveBattleProjection.new()
	var reasons: Array[String] = []
	p.event_not_applied.connect(func(_evt: ProtocolEventDTO, reason: String): reasons.append(reason))
	# "move" is a genuinely DECODED_STATE_EVENT type (protocol/protocol_decoder.gd emits it), but
	# the reducer has no match arm for it -- the default `_:` branch.
	p.apply_event(_event({"event_type": "move", "pokemon_side": "p1", "pokemon_slot": "a"}))
	assert_int(reasons.size()).is_equal(1)
	assert_str(reasons[0]).is_equal("unhandled_type")


func test_consistent_event_never_fires_the_diagnostic_signal() -> void:
	var p := LiveBattleProjection.new()
	var reasons: Array[String] = []
	p.event_not_applied.connect(func(_evt: ProtocolEventDTO, reason: String): reasons.append(reason))
	p.apply_event(_event({"event_type": "turn", "turn_number": 1}))
	assert_int(reasons.size()).is_equal(0)
	assert_int(p.get_current_snapshot().turn).is_equal(1)
