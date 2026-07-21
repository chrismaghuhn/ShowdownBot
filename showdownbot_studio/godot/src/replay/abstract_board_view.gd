class_name AbstractBoardView
extends VBoxContainer

const EMPTY_REPLAY_TEXT := "No replay evidence in this bundle"

@onready var _loading: Label = $LoadingLabel
@onready var _empty: Label = $EmptyStateLabel
@onready var _turn: Label = $MetaRow/TurnLabel
@onready var _weather: Label = $MetaRow/WeatherLabel
@onready var _terrain: Label = $MetaRow/TerrainLabel
@onready var _field_conditions: Label = $MetaRow/FieldConditionsLabel
@onready var _p1_side: Label = $SideConditionsRow/P1SideLabel
@onready var _p2_side: Label = $SideConditionsRow/P2SideLabel
@onready var _p1a_species: Label = $Slots/P1ASpecies
@onready var _p1a_hp: Label = $Slots/P1AHP
@onready var _p1a_status: Label = $Slots/P1AStatus
@onready var _p1b_species: Label = $Slots/P1BSpecies
@onready var _p1b_hp: Label = $Slots/P1BHP
@onready var _p1b_status: Label = $Slots/P1BStatus
@onready var _p2a_species: Label = $Slots/P2ASpecies
@onready var _p2a_hp: Label = $Slots/P2AHP
@onready var _p2a_status: Label = $Slots/P2AStatus
@onready var _p2b_species: Label = $Slots/P2BSpecies
@onready var _p2b_hp: Label = $Slots/P2BHP
@onready var _p2b_status: Label = $Slots/P2BStatus

var _bound: BoardModel = null


func bind(board: BoardModel) -> void:
	_bound = board
	if board == null or not board.has_replay:
		_empty.visible = true
		_empty.text = EMPTY_REPLAY_TEXT
		_clear_slots_and_meta()
		return
	_empty.visible = false
	_empty.text = ""
	# has_replay and not has_recorded_state: blank slots, NO empty-state banner.
	_render(board)


func set_loading(active: bool) -> void:
	_loading.text = "Loading..." if active else ""


func get_slot_species(side: String, slot: String) -> String:
	return _slot_label(side, slot, "species").text


func get_slot_hp_text(side: String, slot: String) -> String:
	return _slot_label(side, slot, "hp").text


func get_weather_text() -> String:
	return _weather.text


func get_terrain_text() -> String:
	return _terrain.text


func get_field_conditions_text() -> String:
	return _field_conditions.text


func get_side_conditions_text(side: String) -> String:
	return _p1_side.text if side == "p1" else _p2_side.text


func get_empty_state_visible() -> bool:
	return _empty.visible


func _clear_slots_and_meta() -> void:
	_turn.text = ""
	_weather.text = ""
	_terrain.text = ""
	_field_conditions.text = ""
	_p1_side.text = ""
	_p2_side.text = ""
	for lbl in [
		_p1a_species, _p1a_hp, _p1a_status, _p1b_species, _p1b_hp, _p1b_status,
		_p2a_species, _p2a_hp, _p2a_status, _p2b_species, _p2b_hp, _p2b_status,
	]:
		lbl.text = ""


func _render(board: BoardModel) -> void:
	_turn.text = "" if board.turn_number == null else "turn %s" % str(board.turn_number)
	_weather.text = "" if board.weather == null else str(board.weather)
	_terrain.text = "" if board.terrain == null else str(board.terrain)
	_field_conditions.text = ", ".join(board.field_conditions)
	_p1_side.text = ", ".join(board.side_conditions["p1"])
	_p2_side.text = ", ".join(board.side_conditions["p2"])
	_write_slot(_p1a_species, _p1a_hp, _p1a_status, board.get_slot("p1", "a"))
	_write_slot(_p1b_species, _p1b_hp, _p1b_status, board.get_slot("p1", "b"))
	_write_slot(_p2a_species, _p2a_hp, _p2a_status, board.get_slot("p2", "a"))
	_write_slot(_p2b_species, _p2b_hp, _p2b_status, board.get_slot("p2", "b"))


func _write_slot(species_lbl: Label, hp_lbl: Label, status_lbl: Label, cell: Dictionary) -> void:
	species_lbl.text = "" if cell["species"] == null else str(cell["species"])
	if cell["hp_current"] == null and cell["hp_maximum"] == null:
		hp_lbl.text = ""
	else:
		hp_lbl.text = "%s/%s" % [
			"?" if cell["hp_current"] == null else str(cell["hp_current"]),
			"?" if cell["hp_maximum"] == null else str(cell["hp_maximum"]),
		]
	status_lbl.text = "" if cell["hp_status"] == null else str(cell["hp_status"])


func _slot_label(side: String, slot: String, kind: String) -> Label:
	# kind: species|hp|status — explicit map only (no dynamic get_node inventing)
	match "%s-%s-%s" % [side, slot, kind]:
		"p1-a-species":
			return _p1a_species
		"p1-a-hp":
			return _p1a_hp
		"p1-a-status":
			return _p1a_status
		"p1-b-species":
			return _p1b_species
		"p1-b-hp":
			return _p1b_hp
		"p1-b-status":
			return _p1b_status
		"p2-a-species":
			return _p2a_species
		"p2-a-hp":
			return _p2a_hp
		"p2-a-status":
			return _p2a_status
		"p2-b-species":
			return _p2b_species
		"p2-b-hp":
			return _p2b_hp
		"p2-b-status":
			return _p2b_status
		_:
			push_error("invalid slot seam %s-%s-%s" % [side, slot, kind])
			return _p1a_species
