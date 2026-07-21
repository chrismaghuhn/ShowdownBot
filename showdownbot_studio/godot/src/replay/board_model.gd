class_name BoardModel
extends RefCounted

## True iff the sealed replay carries trusted battle events (replay.replay_trusted).
## Independent of whether any EVENT has been applied yet.
var has_replay: bool = false

## True iff at least one recorded presentation field is non-empty after apply.
var has_recorded_state: bool = false

var turn_number: Variant = null
var weather: Variant = null
var terrain: Variant = null
var last_move: Variant = null
var field_conditions: PackedStringArray = PackedStringArray()

## slots[side][slot] -> Dictionary with keys:
## species, hp_current, hp_maximum, hp_fainted, hp_status  (all Variant; null = unset)
var slots: Dictionary = {}

## side_conditions[side] -> PackedStringArray
var side_conditions: Dictionary = {}


func _init() -> void:
	slots = {
		"p1": {"a": _empty_slot(), "b": _empty_slot()},
		"p2": {"a": _empty_slot(), "b": _empty_slot()},
	}
	side_conditions = {
		"p1": PackedStringArray(),
		"p2": PackedStringArray(),
	}


static func _empty_slot() -> Dictionary:
	return {
		"species": null,
		"hp_current": null,
		"hp_maximum": null,
		"hp_fainted": null,
		"hp_status": null,
	}


func get_slot(side: String, slot: String) -> Dictionary:
	return slots[side][slot]


func set_slot_species(side: String, slot: String, species: Variant) -> void:
	slots[side][slot]["species"] = species


## Partial HP update for damage/heal/sethp/detailschange — never used for switch.
func apply_slot_hp(side: String, slot: String, event: BattleEventDTO) -> void:
	var cell: Dictionary = slots[side][slot]
	if event.hp_current != null:
		cell["hp_current"] = event.hp_current
	if event.hp_maximum != null:
		cell["hp_maximum"] = event.hp_maximum
	if event.hp_fainted != null:
		cell["hp_fainted"] = event.hp_fainted
	if event.hp_status != null:
		cell["hp_status"] = event.hp_status


## Full slot replace for `switch`: overwrites species and all five HP fields,
## including explicit nulls (clears prior burn/status/HP from the previous occupant).
func replace_slot_from_switch(side: String, slot: String, event: BattleEventDTO) -> void:
	slots[side][slot] = {
		"species": event.pokemon_species,
		"hp_current": event.hp_current,
		"hp_maximum": event.hp_maximum,
		"hp_fainted": event.hp_fainted,
		"hp_status": event.hp_status,
	}


func set_slot_status(side: String, slot: String, status: Variant) -> void:
	slots[side][slot]["hp_status"] = status


## Recorded faint proves 0 HP. Always force hp_current=0 and hp_fainted=true,
## even when a prior positive hp_current was recorded.
func set_slot_fainted(side: String, slot: String) -> void:
	slots[side][slot]["hp_fainted"] = true
	slots[side][slot]["hp_current"] = 0



func add_side_condition(side: String, label: String) -> void:
	var arr: PackedStringArray = side_conditions[side]
	if not label in arr:
		arr.append(label)
		side_conditions[side] = arr


func remove_side_condition(side: String, label: String) -> void:
	var arr: PackedStringArray = side_conditions[side]
	var next := PackedStringArray()
	for item in arr:
		if item != label:
			next.append(item)
	side_conditions[side] = next


func add_field_condition(label: String) -> void:
	if not label in field_conditions:
		field_conditions.append(label)


func remove_field_condition(label: String) -> void:
	var next := PackedStringArray()
	for item in field_conditions:
		if item != label:
			next.append(item)
	field_conditions = next


func recompute_has_recorded_state() -> void:
	if turn_number != null or weather != null or terrain != null or last_move != null:
		has_recorded_state = true
		return
	if field_conditions.size() > 0:
		has_recorded_state = true
		return
	for side in ["p1", "p2"]:
		if side_conditions[side].size() > 0:
			has_recorded_state = true
			return
		for slot in ["a", "b"]:
			var cell: Dictionary = slots[side][slot]
			# Any of the five slot fields being non-null counts, including
			# recorded hp_fainted=false and a lone hp_maximum.
			if (
				cell["species"] != null
				or cell["hp_current"] != null
				or cell["hp_maximum"] != null
				or cell["hp_fainted"] != null
				or cell["hp_status"] != null
			):
				has_recorded_state = true
				return
	has_recorded_state = false
