class_name BattleEventDTO
extends RefCounted

var _sealed: bool = false
var _protocol_index: int = 0
var _type: String = ""
var _pokemon_side: Variant = null
var _pokemon_slot: Variant = null
var _pokemon_species: Variant = null
var _target_side: Variant = null
var _target_slot: Variant = null
var _details: Variant = null
var _value: Variant = null
var _side: Variant = null
var _amount: Variant = null
var _hp_current: Variant = null
var _hp_maximum: Variant = null
var _hp_fainted: Variant = null
var _hp_status: Variant = null
var _tags: PackedStringArray = PackedStringArray()
var _unknown_fields: Dictionary = {}

var protocol_index: int:
	get:
		return _protocol_index
	set(value):
		if _sealed:
			return
		_protocol_index = value

var type: String:
	get:
		return _type
	set(value):
		if _sealed:
			return
		_type = value

var pokemon_side: Variant:
	get:
		return _pokemon_side
	set(value):
		if _sealed:
			return
		_pokemon_side = JsonNumbers.deep_copy_value(value)

var pokemon_slot: Variant:
	get:
		return _pokemon_slot
	set(value):
		if _sealed:
			return
		_pokemon_slot = JsonNumbers.deep_copy_value(value)

var pokemon_species: Variant:
	get:
		return _pokemon_species
	set(value):
		if _sealed:
			return
		_pokemon_species = JsonNumbers.deep_copy_value(value)

var target_side: Variant:
	get:
		return _target_side
	set(value):
		if _sealed:
			return
		_target_side = JsonNumbers.deep_copy_value(value)

var target_slot: Variant:
	get:
		return _target_slot
	set(value):
		if _sealed:
			return
		_target_slot = JsonNumbers.deep_copy_value(value)

var details: Variant:
	get:
		return _details
	set(value):
		if _sealed:
			return
		_details = JsonNumbers.deep_copy_value(value)

var value: Variant:
	get:
		return _value
	set(value):
		if _sealed:
			return
		_value = JsonNumbers.deep_copy_value(value)

var side: Variant:
	get:
		return _side
	set(value):
		if _sealed:
			return
		_side = JsonNumbers.deep_copy_value(value)

var amount: Variant:
	get:
		return _amount
	set(value):
		if _sealed:
			return
		_amount = JsonNumbers.deep_copy_value(value)

var hp_current: Variant:
	get:
		return _hp_current
	set(value):
		if _sealed:
			return
		_hp_current = JsonNumbers.deep_copy_value(value)

var hp_maximum: Variant:
	get:
		return _hp_maximum
	set(value):
		if _sealed:
			return
		_hp_maximum = JsonNumbers.deep_copy_value(value)

var hp_fainted: Variant:
	get:
		return _hp_fainted
	set(value):
		if _sealed:
			return
		_hp_fainted = JsonNumbers.deep_copy_value(value)

var hp_status: Variant:
	get:
		return _hp_status
	set(value):
		if _sealed:
			return
		_hp_status = JsonNumbers.deep_copy_value(value)

var tags: PackedStringArray:
	get:
		return _tags
	set(value):
		if _sealed:
			return
		_tags = value

var unknown_fields: Dictionary:
	get:
		return _unknown_fields
	set(value):
		if _sealed:
			return
		_unknown_fields = value.duplicate(true) if value != null else {}


func seal() -> void:
	if _sealed:
		return
	JsonNumbers.freeze_containers(_pokemon_side)
	JsonNumbers.freeze_containers(_pokemon_species)
	JsonNumbers.freeze_containers(_target_side)
	JsonNumbers.freeze_containers(_details)
	JsonNumbers.freeze_containers(_value)
	JsonNumbers.freeze_containers(_side)
	JsonNumbers.freeze_containers(_hp_status)
	JsonNumbers.freeze_containers(_unknown_fields)
	_sealed = true
