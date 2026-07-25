class_name BattleBoardSnapshot
extends RefCounted

## Neutral board-presentation contract (spec docs/specs/2026-07-25-phase3-client-design.md
## section 4.7): the shape AbstractBoardView.bind() consumes, produced either by
## ReplayBoardPresentationAdapter (this F0 slice) or a future live-battle adapter (M1d,
## not built here). `slots` and `side_conditions` use Godot 4.4+ typed-dictionary syntax
## (`Dictionary[K, V]`) specifically so this cross-module value object satisfies AGENTS.md
## rule 9 ("no cross-module public interface exposes an untyped container") -- a typed
## Dictionary is not the "untyped Dictionary" that rule bans.
##
## `turn`, `weather`, and `terrain` stay `Variant`, not typed, under the amended AGENTS.md
## rule 9 (2026-07-25 PR-88 review): `Variant` is permitted for documented nullable scalar
## FIELDS in a named typed value object such as this one -- never for containers, and never
## as a parameter or return type on a cross-module public interface. These three fields are
## exactly that: a nullable display value (absent vs present) on a named DTO, mirroring the
## existing Phase-0 `BoardModel` convention (see `board_model.gd`'s own
## `turn_number`/`weather`/`terrain`). A typed sentinel scheme for "no value recorded yet" is
## deliberately deferred until the live chain (M1c) gives these fields a producing contract
## to design the sentinel against.

const SLOT_KEYS := ["p1a", "p1b", "p2a", "p2b"]

var presentation_available: bool = false
var empty_state_reason: String = ""
var turn: Variant = null
var weather: Variant = null
var terrain: Variant = null
var slots: Dictionary[String, BattleBoardSlotSnapshot] = {}
var side_conditions: Dictionary[String, PackedStringArray] = {}
var field_conditions: PackedStringArray = PackedStringArray()


func _init() -> void:
	for key in SLOT_KEYS:
		slots[key] = BattleBoardSlotSnapshot.new()
	side_conditions["p1"] = PackedStringArray()
	side_conditions["p2"] = PackedStringArray()


static func slot_key(side: String, slot: String) -> String:
	return "%s%s" % [side, slot]


func get_slot(side: String, slot: String) -> BattleBoardSlotSnapshot:
	var key := slot_key(side, slot)
	if not slots.has(key):
		push_error("BattleBoardSnapshot.get_slot: unknown side/slot %s/%s" % [side, slot])
		return null
	return slots[key]
