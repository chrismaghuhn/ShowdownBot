class_name ReplayBoardPresentationAdapter
extends RefCounted

## Converts the existing Phase-0 BoardModel into the neutral BattleBoardSnapshot contract
## (spec docs/specs/2026-07-25-phase3-client-design.md section 4.7). Owns the replay-specific
## empty-state wording that used to live directly in AbstractBoardView
## (godot/src/replay/abstract_board_view.gd's old EMPTY_REPLAY_TEXT constant, removed there
## in the same F0 slice, Task 15) -- AbstractBoardView itself no longer knows this string, or
## anything about BoardModel or "has_replay" at all.

const EMPTY_REPLAY_TEXT := "No replay evidence in this bundle"


static func build_snapshot(board: BoardModel) -> BattleBoardSnapshot:
	var snapshot := BattleBoardSnapshot.new()
	if board == null or not board.has_replay:
		snapshot.presentation_available = false
		snapshot.empty_state_reason = EMPTY_REPLAY_TEXT
		return snapshot
	snapshot.presentation_available = true
	snapshot.empty_state_reason = ""
	snapshot.turn = board.turn_number
	snapshot.weather = board.weather
	snapshot.terrain = board.terrain
	snapshot.field_conditions = board.field_conditions
	for side in ["p1", "p2"]:
		snapshot.side_conditions[side] = board.side_conditions[side]
		for slot in ["a", "b"]:
			var cell: Dictionary = board.get_slot(side, slot)
			var slot_snapshot := snapshot.get_slot(side, slot)
			slot_snapshot.species = cell["species"]
			slot_snapshot.hp_current = cell["hp_current"]
			slot_snapshot.hp_maximum = cell["hp_maximum"]
			slot_snapshot.hp_fainted = cell["hp_fainted"]
			slot_snapshot.hp_status = cell["hp_status"]
	return snapshot
