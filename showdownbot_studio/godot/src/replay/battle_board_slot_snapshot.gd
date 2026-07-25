class_name BattleBoardSlotSnapshot
extends RefCounted

## One board slot's presentation fields, all nullable (Variant) -- mirrors the five fields
## BoardModel already tracks per slot (species, hp_current, hp_maximum, hp_fainted, hp_status),
## just promoted to named typed fields on a dedicated value object instead of raw Dictionary
## keys, so BattleBoardSnapshot.slots below can be a TYPED Dictionary (Godot 4.4+
## `Dictionary[String, T]` syntax) rather than an untyped one.

var species: Variant = null
var hp_current: Variant = null
var hp_maximum: Variant = null
var hp_fainted: Variant = null
var hp_status: Variant = null
