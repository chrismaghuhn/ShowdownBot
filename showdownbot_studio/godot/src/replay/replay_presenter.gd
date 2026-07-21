class_name ReplayPresenter
extends RefCounted

const KNOWN_TERRAINS := [
	"Electric Terrain",
	"Grassy Terrain",
	"Misty Terrain",
	"Psychic Terrain",
]


static func build_board(bundle: BundleDTO, replay: ReplayDTO, selected_entry_index: int) -> BoardModel:
	var board := BoardModel.new()
	board.has_replay = replay.replay_trusted
	if not replay.replay_trusted:
		board.recompute_has_recorded_state()
		return board
	var end_i := mini(selected_entry_index, replay.entries.size() - 1)
	for i in range(0, end_i + 1):
		var entry: TimelineEntryDTO = replay.entries[i]
		if entry.kind != TimelineEntryKind.EVENT:
			continue
		var event: BattleEventDTO = bundle.battle_events[entry.event_index]
		_apply_event(board, event)
	board.recompute_has_recorded_state()
	return board


static func _field_label(event: BattleEventDTO) -> Variant:
	if event.value != null and typeof(event.value) == TYPE_STRING:
		return event.value
	if event.details != null and typeof(event.details) == TYPE_STRING:
		return event.details
	return null


static func _is_terrain_label(label: String) -> bool:
	return label in KNOWN_TERRAINS


static func _is_board_side(side: String) -> bool:
	return side == "p1" or side == "p2"


static func _is_board_slot(slot: String) -> bool:
	return slot == "a" or slot == "b"


## Returns [side, slot] only for p1/p2 × a/b. Unknown sides, numeric slots
## (e.g. 0/1), or missing values → empty Array (fail-soft recorded no-op).
## Never index BoardModel.slots with unvalidated keys.
static func _pokemon_side_slot(event: BattleEventDTO) -> Array:
	if event.pokemon_side == null or event.pokemon_slot == null:
		return []
	var side := str(event.pokemon_side)
	var slot := str(event.pokemon_slot)
	if not _is_board_side(side) or not _is_board_slot(slot):
		return []
	return [side, slot]


static func _apply_event(board: BoardModel, event: BattleEventDTO) -> void:
	match event.type:
		"turn":
			if typeof(event.amount) == TYPE_INT:
				board.turn_number = event.amount
		"switch":
			var id := _pokemon_side_slot(event)
			if id.is_empty():
				return
			board.replace_slot_from_switch(id[0], id[1], event)
		"detailschange":
			var id := _pokemon_side_slot(event)
			if id.is_empty():
				return
			if event.pokemon_species != null:
				board.set_slot_species(id[0], id[1], event.pokemon_species)
			board.apply_slot_hp(id[0], id[1], event)
		"move":
			if typeof(event.details) == TYPE_STRING:
				board.last_move = event.details
		"damage", "heal", "sethp":
			var id := _pokemon_side_slot(event)
			if id.is_empty():
				return
			board.apply_slot_hp(id[0], id[1], event)
		"faint":
			var id := _pokemon_side_slot(event)
			if id.is_empty():
				return
			# Optional recorded max/status first, then force faint + 0 HP.
			board.apply_slot_hp(id[0], id[1], event)
			board.set_slot_fainted(id[0], id[1])
		"status":
			var id := _pokemon_side_slot(event)
			if id.is_empty():
				return
			var st: Variant = event.details if event.details != null else event.value
			board.set_slot_status(id[0], id[1], st)
		"curestatus":
			var id := _pokemon_side_slot(event)
			if id.is_empty():
				return
			board.set_slot_status(id[0], id[1], null)
		"weather":
			board.weather = event.value
		"fieldstart":
			var label = _field_label(event)
			if label == null:
				return
			var s := String(label)
			if _is_terrain_label(s):
				board.terrain = s
			else:
				board.add_field_condition(s)
		"fieldend":
			var label = _field_label(event)
			if label == null:
				return
			var s := String(label)
			if _is_terrain_label(s):
				if board.terrain == s:
					board.terrain = null
			else:
				board.remove_field_condition(s)
		"sidestart":
			if event.side == null:
				return
			var side := String(event.side)
			if not _is_board_side(side):
				return
			var label = _field_label(event)
			if label == null:
				return
			board.add_side_condition(side, String(label))
		"sideend":
			if event.side == null:
				return
			var side := String(event.side)
			if not _is_board_side(side):
				return
			var label = _field_label(event)
			if label == null:
				return
			board.remove_side_condition(side, String(label))
		_:
			pass  # boost/item/enditem/mega — recorded no-op
