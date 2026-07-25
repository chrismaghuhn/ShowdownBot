class_name LiveBattleReducer
extends RefCounted

## Pure, deterministic fold: apply(previous, event) -> next. Never mutates `previous`
## (LiveBattleSnapshot has no setter anywhere). An unmodeled event type returns `previous`
## unchanged (spec section 6.1).
##
## Watchlist M1c ("Unknown or inconsistent state events fail closed and remain diagnostically
## visible"): apply() itself stays a pure, signal-free function -- LiveBattleProjection is the
## one that surfaces WHY an event did not change state, using the two pure predicates below to
## classify an event BEFORE calling apply(), never by inspecting apply()'s return value (a
## no-op result is otherwise indistinguishable from "this event legitimately does nothing").

## Every event_type this reducer's match statement below actually has an arm for.
const _HANDLED_EVENT_TYPES: PackedStringArray = [
	"turn", "switch", "drag", "-damage", "-heal", "-status", "-curestatus", "faint",
	"-weather", "-fieldstart", "-fieldend", "-sidestart", "-sideend", "win", "tie",
]

## The subset of _HANDLED_EVENT_TYPES whose arms require pokemon_side/pokemon_slot
## (_apply_switch/_apply_hp_change/_apply_status/_apply_faint's own early-return guard).
const _POKEMON_IDENTITY_EVENT_TYPES: PackedStringArray = [
	"switch", "drag", "-damage", "-heal", "-status", "-curestatus", "faint",
]


## True iff apply() has a match arm for this event_type at all (spec section 6.1's "not
## understood"/unmodeled-type case is the false side of this).
static func is_handled_event_type(event_type: String) -> bool:
	return event_type in _HANDLED_EVENT_TYPES


## True iff a handled event_type additionally requires pokemon_side/pokemon_slot to identify
## which slot it applies to -- the exact condition _apply_switch/_apply_hp_change/_apply_status/
## _apply_faint already early-return on when missing.
static func requires_pokemon_identity(event_type: String) -> bool:
	return event_type in _POKEMON_IDENTITY_EVENT_TYPES


static func apply(previous: LiveBattleSnapshot, event: ProtocolEventDTO) -> LiveBattleSnapshot:
	match event.event_type:
		"turn":
			return previous.with_turn(event.turn_number)
		"switch", "drag":
			return _apply_switch(previous, event)
		"-damage", "-heal":
			return _apply_hp_change(previous, event)
		"-status", "-curestatus":
			return _apply_status(previous, event)
		"faint":
			return _apply_faint(previous, event)
		"-weather":
			return previous.with_weather(event.condition_label)
		"-fieldstart":
			return previous.with_field_condition_added(str(event.condition_label))
		"-fieldend":
			return previous.with_field_condition_removed(str(event.condition_label))
		"-sidestart":
			return previous.with_side_condition_added(str(event.side), str(event.condition_label))
		"-sideend":
			return previous.with_side_condition_removed(str(event.side), str(event.condition_label))
		"win", "tie":
			return previous.with_battle_completed()
		_:
			return previous


static func _apply_switch(previous: LiveBattleSnapshot, event: ProtocolEventDTO) -> LiveBattleSnapshot:
	if event.pokemon_side == null or event.pokemon_slot == null:
		return previous
	var slot := LiveBattleSlotSnapshot.new(event.pokemon_species, event.hp_current, event.hp_maximum, event.hp_fainted, event.hp_status)
	return previous.with_slot(str(event.pokemon_side), str(event.pokemon_slot), slot)


static func _apply_hp_change(previous: LiveBattleSnapshot, event: ProtocolEventDTO) -> LiveBattleSnapshot:
	if event.pokemon_side == null or event.pokemon_slot == null:
		return previous
	var existing := previous.get_slot(str(event.pokemon_side), str(event.pokemon_slot))
	var slot := LiveBattleSlotSnapshot.new(
		existing.species,
		event.hp_current if event.hp_current != null else existing.hp_current,
		event.hp_maximum if event.hp_maximum != null else existing.hp_maximum,
		event.hp_fainted if event.hp_fainted != null else existing.hp_fainted,
		event.hp_status if event.hp_status != null else existing.hp_status,
	)
	return previous.with_slot(str(event.pokemon_side), str(event.pokemon_slot), slot)


static func _apply_status(previous: LiveBattleSnapshot, event: ProtocolEventDTO) -> LiveBattleSnapshot:
	if event.pokemon_side == null or event.pokemon_slot == null:
		return previous
	var existing := previous.get_slot(str(event.pokemon_side), str(event.pokemon_slot))
	var slot := LiveBattleSlotSnapshot.new(existing.species, existing.hp_current, existing.hp_maximum, existing.hp_fainted, event.hp_status)
	return previous.with_slot(str(event.pokemon_side), str(event.pokemon_slot), slot)


static func _apply_faint(previous: LiveBattleSnapshot, event: ProtocolEventDTO) -> LiveBattleSnapshot:
	if event.pokemon_side == null or event.pokemon_slot == null:
		return previous
	var existing := previous.get_slot(str(event.pokemon_side), str(event.pokemon_slot))
	var slot := LiveBattleSlotSnapshot.new(existing.species, 0, existing.hp_maximum, true, existing.hp_status)
	return previous.with_slot(str(event.pokemon_side), str(event.pokemon_slot), slot)
