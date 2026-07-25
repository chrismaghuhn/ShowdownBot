class_name LiveBattleSnapshot
extends RefCounted

## battle/'s own structurally-immutable authoritative snapshot. Every `with_*` method returns a
## NEW LiveBattleSnapshot built via the constructor; there is no setter anywhere on this class,
## and no accessor ever hands out a container a caller could mutate to affect a FUTURE read of
## this same snapshot (get_side_conditions/get_field_conditions always return a duplicate).

const SLOT_KEYS := ["p1a", "p1b", "p2a", "p2b"]

var _turn: Variant
var _weather: Variant
var _terrain: Variant
var _battle_completed: bool
var _slots: Dictionary[String, LiveBattleSlotSnapshot] = {}
var _side_conditions: Dictionary[String, PackedStringArray] = {}
var _field_conditions: PackedStringArray = PackedStringArray()


func _init(
	p_turn: Variant = null, p_weather: Variant = null, p_terrain: Variant = null,
	p_slots: Dictionary[String, LiveBattleSlotSnapshot] = {},
	p_side_conditions: Dictionary[String, PackedStringArray] = {},
	p_field_conditions: PackedStringArray = PackedStringArray(),
	p_battle_completed: bool = false,
) -> void:
	_turn = p_turn
	_weather = p_weather
	_terrain = p_terrain
	_battle_completed = p_battle_completed
	for key in SLOT_KEYS:
		_slots[key] = p_slots.get(key, LiveBattleSlotSnapshot.new())
	for side in ["p1", "p2"]:
		_side_conditions[side] = p_side_conditions.get(side, PackedStringArray()).duplicate()
	_field_conditions = p_field_conditions.duplicate()


var turn: Variant:
	get: return _turn

var weather: Variant:
	get: return _weather

var terrain: Variant:
	get: return _terrain

var battle_completed: bool:
	get: return _battle_completed


static func slot_key(side: String, slot: String) -> String:
	return "%s%s" % [side, slot]


func get_slot(side: String, slot: String) -> LiveBattleSlotSnapshot:
	return _slots[slot_key(side, slot)]


func get_side_conditions(side: String) -> PackedStringArray:
	return _side_conditions[side].duplicate()


func get_field_conditions() -> PackedStringArray:
	return _field_conditions.duplicate()


## Full, byte-meaningful, field-by-field value comparison (watchlist M1c's determinism proof
## needs more than "same final turn number" -- two independent folds of the same event list must
## agree on every field: turn/weather/terrain/battle_completed, all four slots' own five fields,
## both sides' conditions, and the field conditions). A public typed method here, not a
## Dictionary-returning to_dict() surface (AGENTS.md rule 9).
func equals(other: LiveBattleSnapshot) -> bool:
	if other == null:
		return false
	if _turn != other.turn or _weather != other.weather or _terrain != other.terrain:
		return false
	if _battle_completed != other.battle_completed:
		return false
	for key in SLOT_KEYS:
		var mine: LiveBattleSlotSnapshot = _slots[key]
		var theirs: LiveBattleSlotSnapshot = other._slots[key]
		if (
			mine.species != theirs.species
			or mine.hp_current != theirs.hp_current
			or mine.hp_maximum != theirs.hp_maximum
			or mine.hp_fainted != theirs.hp_fainted
			or mine.hp_status != theirs.hp_status
		):
			return false
	for side in ["p1", "p2"]:
		if _side_conditions[side] != other._side_conditions[side]:
			return false
	return _field_conditions == other._field_conditions


func with_slot(side: String, slot: String, next_slot: LiveBattleSlotSnapshot) -> LiveBattleSnapshot:
	var next_slots := _duplicate_slots()
	next_slots[slot_key(side, slot)] = next_slot
	return LiveBattleSnapshot.new(_turn, _weather, _terrain, next_slots, _duplicate_side_conditions(), _field_conditions, _battle_completed)


func with_turn(next_turn: Variant) -> LiveBattleSnapshot:
	return LiveBattleSnapshot.new(next_turn, _weather, _terrain, _duplicate_slots(), _duplicate_side_conditions(), _field_conditions, _battle_completed)


func with_weather(next_weather: Variant) -> LiveBattleSnapshot:
	return LiveBattleSnapshot.new(_turn, next_weather, _terrain, _duplicate_slots(), _duplicate_side_conditions(), _field_conditions, _battle_completed)


func with_terrain(next_terrain: Variant) -> LiveBattleSnapshot:
	return LiveBattleSnapshot.new(_turn, _weather, next_terrain, _duplicate_slots(), _duplicate_side_conditions(), _field_conditions, _battle_completed)


func with_field_condition_added(label: String) -> LiveBattleSnapshot:
	var next_fields := _field_conditions.duplicate()
	if not label in next_fields:
		next_fields.append(label)
	return LiveBattleSnapshot.new(_turn, _weather, _terrain, _duplicate_slots(), _duplicate_side_conditions(), next_fields, _battle_completed)


func with_field_condition_removed(label: String) -> LiveBattleSnapshot:
	var next_fields := PackedStringArray()
	for item in _field_conditions:
		if item != label:
			next_fields.append(item)
	return LiveBattleSnapshot.new(_turn, _weather, _terrain, _duplicate_slots(), _duplicate_side_conditions(), next_fields, _battle_completed)


func with_side_condition_added(side: String, label: String) -> LiveBattleSnapshot:
	var next_conditions := _duplicate_side_conditions()
	var arr: PackedStringArray = next_conditions[side]
	if not label in arr:
		arr.append(label)
	next_conditions[side] = arr
	return LiveBattleSnapshot.new(_turn, _weather, _terrain, _duplicate_slots(), next_conditions, _field_conditions, _battle_completed)


func with_side_condition_removed(side: String, label: String) -> LiveBattleSnapshot:
	var next_conditions := _duplicate_side_conditions()
	var next_arr := PackedStringArray()
	for item in next_conditions[side]:
		if item != label:
			next_arr.append(item)
	next_conditions[side] = next_arr
	return LiveBattleSnapshot.new(_turn, _weather, _terrain, _duplicate_slots(), next_conditions, _field_conditions, _battle_completed)


func with_battle_completed() -> LiveBattleSnapshot:
	return LiveBattleSnapshot.new(_turn, _weather, _terrain, _duplicate_slots(), _duplicate_side_conditions(), _field_conditions, true)


func _duplicate_slots() -> Dictionary[String, LiveBattleSlotSnapshot]:
	var copy: Dictionary[String, LiveBattleSlotSnapshot] = {}
	for key in _slots:
		copy[key] = _slots[key]  # slot values are themselves immutable; sharing the reference is safe
	return copy


func _duplicate_side_conditions() -> Dictionary[String, PackedStringArray]:
	var copy: Dictionary[String, PackedStringArray] = {}
	for side in _side_conditions:
		copy[side] = _side_conditions[side].duplicate()
	return copy
