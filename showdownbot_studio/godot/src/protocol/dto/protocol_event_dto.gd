class_name ProtocolEventDTO
extends RefCounted

## One decoded, DECODED_STATE_EVENT-classified Showdown protocol line (this plan's M1b section
## header). Flat and generic like bundle/battle_event_dto.gd's proven shape, but a distinct
## class under protocol/dto/, never a live/bundle DTO reuse (spec section 4.1.2). Sealed after
## construction by the decoder.

var _sealed: bool = false
var _protocol_index: int = 0
var _room_id: String = ""
var _event_type: String = ""
var _pokemon_side: Variant = null
var _pokemon_slot: Variant = null
var _pokemon_species: Variant = null
var _hp_current: Variant = null
var _hp_maximum: Variant = null
var _hp_fainted: Variant = null
var _hp_status: Variant = null
## Weather/terrain/field-condition/side-condition name, OR |init|'s room-type argument
## ("battle"/"chat"/...) -- one shared field across several event families.
var _condition_label: Variant = null
var _side: Variant = null
var _turn_number: Variant = null
var _error_reason: Variant = null
## `|noinit|<subtype>|<reason>` only (owner finding 3, M1 hardening): "nonexistent" or
## "joinfailed" (server/users.ts's own two real join-rejection subtypes) verbatim, or the literal
## string "UNKNOWN" for any other noinit subtype (fail-closed per AGENTS.md rule 10 -- never
## guessed as one of the known two). Null for every other event type.
var _noinit_subtype: Variant = null

var protocol_index: int:
	get: return _protocol_index
	set(value):
		if _sealed: return
		_protocol_index = value

var room_id: String:
	get: return _room_id
	set(value):
		if _sealed: return
		_room_id = value

var event_type: String:
	get: return _event_type
	set(value):
		if _sealed: return
		_event_type = value

var pokemon_side: Variant:
	get: return _pokemon_side
	set(value):
		if _sealed: return
		_pokemon_side = value

var pokemon_slot: Variant:
	get: return _pokemon_slot
	set(value):
		if _sealed: return
		_pokemon_slot = value

var pokemon_species: Variant:
	get: return _pokemon_species
	set(value):
		if _sealed: return
		_pokemon_species = value

var hp_current: Variant:
	get: return _hp_current
	set(value):
		if _sealed: return
		_hp_current = value

var hp_maximum: Variant:
	get: return _hp_maximum
	set(value):
		if _sealed: return
		_hp_maximum = value

var hp_fainted: Variant:
	get: return _hp_fainted
	set(value):
		if _sealed: return
		_hp_fainted = value

var hp_status: Variant:
	get: return _hp_status
	set(value):
		if _sealed: return
		_hp_status = value

var condition_label: Variant:
	get: return _condition_label
	set(value):
		if _sealed: return
		_condition_label = value

var side: Variant:
	get: return _side
	set(value):
		if _sealed: return
		_side = value

var turn_number: Variant:
	get: return _turn_number
	set(value):
		if _sealed: return
		_turn_number = value

var error_reason: Variant:
	get: return _error_reason
	set(value):
		if _sealed: return
		_error_reason = value

var noinit_subtype: Variant:
	get: return _noinit_subtype
	set(value):
		if _sealed: return
		_noinit_subtype = value


func seal() -> void:
	_sealed = true
