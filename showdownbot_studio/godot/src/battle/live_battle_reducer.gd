class_name LiveBattleReducer
extends RefCounted

## Pure, deterministic fold: apply(previous, event) -> next. Never mutates `previous`
## (LiveBattleSnapshot has no setter anywhere). An unmodeled event type returns `previous`
## unchanged (spec section 6.1).


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
