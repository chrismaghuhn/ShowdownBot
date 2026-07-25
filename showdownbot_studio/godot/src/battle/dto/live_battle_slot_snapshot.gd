class_name LiveBattleSlotSnapshot
extends RefCounted

## One board slot's derived state (spec section 4.7's derived-state rule, made STRUCTURALLY
## true, not conventionally true): private backing fields, read-only-only properties (no
## `set:` block anywhere -- external assignment is a language-level error, not a review
## convention). Every field is set exactly once, at construction, by LiveBattleReducer.

var _species: Variant
var _hp_current: Variant
var _hp_maximum: Variant
var _hp_fainted: Variant
var _hp_status: Variant


func _init(
	p_species: Variant = null, p_hp_current: Variant = null, p_hp_maximum: Variant = null,
	p_hp_fainted: Variant = null, p_hp_status: Variant = null,
) -> void:
	_species = p_species
	_hp_current = p_hp_current
	_hp_maximum = p_hp_maximum
	_hp_fainted = p_hp_fainted
	_hp_status = p_hp_status


var species: Variant:
	get: return _species

var hp_current: Variant:
	get: return _hp_current

var hp_maximum: Variant:
	get: return _hp_maximum

var hp_fainted: Variant:
	get: return _hp_fainted

var hp_status: Variant:
	get: return _hp_status
