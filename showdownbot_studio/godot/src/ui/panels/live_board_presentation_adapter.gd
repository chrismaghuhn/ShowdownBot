class_name LiveBoardPresentationAdapter
extends RefCounted

## Converts battle/'s LiveBattleSnapshot into replay/'s neutral BattleBoardSnapshot contract
## (spec section 4.7), mirroring ReplayBoardPresentationAdapter's pattern (F0). Lives in
## ui/panels/ (not replay/, which spec section 4.4's table does not list for M1d).

const NO_BATTLE_STATE_TEXT := "No battle state received yet"


static func build_snapshot(live: LiveBattleSnapshot) -> BattleBoardSnapshot:
	var snapshot := BattleBoardSnapshot.new()
	if live == null:
		snapshot.presentation_available = false
		snapshot.empty_state_reason = NO_BATTLE_STATE_TEXT
		return snapshot
	snapshot.presentation_available = true
	snapshot.empty_state_reason = ""
	snapshot.turn = live.turn
	snapshot.weather = live.weather
	snapshot.terrain = live.terrain
	snapshot.field_conditions = live.get_field_conditions()
	for side in ["p1", "p2"]:
		snapshot.side_conditions[side] = live.get_side_conditions(side)
		for slot in ["a", "b"]:
			var live_slot := live.get_slot(side, slot)
			var out_slot := snapshot.get_slot(side, slot)
			out_slot.species = live_slot.species
			out_slot.hp_current = live_slot.hp_current
			out_slot.hp_maximum = live_slot.hp_maximum
			out_slot.hp_fainted = live_slot.hp_fainted
			out_slot.hp_status = live_slot.hp_status
	return snapshot
