class_name BattleBoardSnapshot
extends RefCounted

## Neutral board-presentation contract (spec docs/specs/2026-07-25-phase3-client-design.md
## section 4.7): the shape AbstractBoardView.bind() consumes, produced either by
## ReplayBoardPresentationAdapter (this F0 slice) or a future live-battle adapter (M1d,
## not built here). `slots` and `side_conditions` use Godot 4.4+ typed-dictionary syntax
## (`Dictionary[K, V]`) specifically so this cross-module value object satisfies AGENTS.md
## rule 9 ("no cross-module public interface exposes an untyped container") -- a typed
## Dictionary is not the "untyped Dictionary" that rule bans.

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
	return slots[slot_key(side, slot)]
