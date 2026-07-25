class_name ProtocolDecoder
extends RefCounted

## The only place raw Showdown protocol text is parsed (spec section 4.1). Three-way
## classification (this plan's M1b section header): DECODED_STATE_EVENT (event_decoded),
## KNOWN_IGNORED_EVENT (known_ignored_event -- a deliberately out-of-scope but recognized line,
## never a fail-closed warning), UNKNOWN_EVENT (line_not_understood -- the real spec section 6.1
## "not understood" signal).

signal event_decoded(event: ProtocolEventDTO)
signal known_ignored_event(raw_line: String, message_type: String)
signal line_not_understood(raw_line: String)

## Real, valid Showdown protocol lines M1's bounded vocabulary deliberately does not model yet.
## Each is a candidate for later, deliberate promotion to DECODED_STATE_EVENT -- never silently
## dropped, never mistaken for a genuinely unrecognized line.
##
## Widened beyond the M1b plan's illustrative Task 13 list (real-capture finding, Task 12's
## local-spectate-01 transcript, `fixtures/live-protocol-v0/SOURCES.md`): a real VGC doubles
## battle, captured from the pinned local server and decided entirely by the server's own
## `/choose default` autoChoose (no showdown_bot decision logic in the loop), naturally produced
## these additional real, valid message types plus the empty-body separator line ("|") Showdown
## emits between event batches within a frame.
const _KNOWN_IGNORED_TYPES: PackedStringArray = [
	"player", "teamsize", "gametype", "gen", "tier", "rule", "clearpoke", "poke", "teampreview",
	"start", "rated", "j", "join", "l", "leave", "c", "c:", "chat", "t:",
	# Real-capture additions (Task 12/13, local-spectate-01):
	"", "-ability", "-unboost", "-boost", "-resisted", "-crit", "-supereffective",
	"-singleturn", "-fail", "-activate", "-enditem", "upkeep",
]

var _next_protocol_index: int = 0


func decode_frame(raw_frame: String) -> void:
	var room_id := ""
	var body := raw_frame
	if raw_frame.begins_with(">"):
		var newline_index := raw_frame.find("\n")
		if newline_index == -1:
			room_id = raw_frame.substr(1)
			body = ""
		else:
			room_id = raw_frame.substr(1, newline_index - 1)
			body = raw_frame.substr(newline_index + 1)
	for line in body.split("\n"):
		if line.is_empty():
			continue
		_decode_line(room_id, line)


func _decode_line(room_id: String, line: String) -> void:
	var parts := line.split("|")
	if parts.size() < 2:
		line_not_understood.emit(line)
		return
	var msg_type := parts[1]
	if msg_type in _KNOWN_IGNORED_TYPES:
		known_ignored_event.emit(line, msg_type)
		return
	match msg_type:
		"init":
			_emit(room_id, "init", {"condition_label": _arg(parts, 2)})
		"title":
			_emit(room_id, "title", {})
		"error":
			_emit(room_id, "error", {"error_reason": _arg(parts, 2)})
		"deinit":
			_emit(room_id, "deinit", {})
		"turn":
			_emit(room_id, "turn", {"turn_number": _arg(parts, 2).to_int()})
		"switch", "drag":
			_emit_switch(room_id, msg_type, parts)
		"-damage", "-heal":
			_emit_hp_change(room_id, msg_type, parts)
		"-status":
			_emit_side_slot(room_id, "-status", parts, {"hp_status": _arg(parts, 3)})
		"-curestatus":
			_emit_side_slot(room_id, "-curestatus", parts, {"hp_status": null})
		"faint":
			_emit_faint(room_id, parts)
		"-weather":
			_emit(room_id, "-weather", {"condition_label": _clean_condition(_arg(parts, 2))})
		"-fieldstart", "-fieldend":
			_emit(room_id, msg_type, {"condition_label": _clean_condition(_arg(parts, 2))})
		"-sidestart", "-sideend":
			_emit(room_id, msg_type, {
				"side": _arg(parts, 2).split(":")[0],
				"condition_label": _clean_condition(_arg(parts, 3)),
			})
		"move":
			_emit_side_slot(room_id, "move", parts, {})
		"win", "tie":
			_emit(room_id, msg_type, {})
		_:
			line_not_understood.emit(line)


func _arg(parts: PackedStringArray, index: int) -> String:
	return parts[index] if index < parts.size() else ""


static func _parse_pokemon_identifier(identifier: String) -> Dictionary:
	var colon_index := identifier.find(":")
	if colon_index < 3:
		return {"side": null, "slot": null}
	var side_slot := identifier.substr(0, colon_index)
	return {"side": side_slot.substr(0, 2), "slot": side_slot.substr(2, 1)}


## "100/100" | "50/100 brn" | "0 fnt" (NO slash -- hidden max HP) -> hp_current/hp_maximum/
## hp_fainted/hp_status. Fixed bug: the slash-less case must not fall through to all-null.
static func _parse_hp_status(hp_status_text: String) -> Dictionary:
	var space_index := hp_status_text.find(" ")
	var hp_part := hp_status_text if space_index == -1 else hp_status_text.substr(0, space_index)
	var status_part := "" if space_index == -1 else hp_status_text.substr(space_index + 1)
	var slash_index := hp_part.find("/")
	var hp_current: int
	var hp_maximum: Variant = null
	if slash_index == -1:
		if not hp_part.is_valid_int():
			return {"hp_current": null, "hp_maximum": null, "hp_fainted": null, "hp_status": null}
		hp_current = hp_part.to_int()
	else:
		hp_current = hp_part.substr(0, slash_index).to_int()
		hp_maximum = hp_part.substr(slash_index + 1).to_int()
	var fainted := status_part == "fnt" or hp_current == 0
	var status: Variant = null if status_part.is_empty() or status_part == "fnt" else status_part
	return {"hp_current": hp_current, "hp_maximum": hp_maximum, "hp_fainted": fainted, "hp_status": status}


func _emit_switch(room_id: String, event_type: String, parts: PackedStringArray) -> void:
	var identifier := _parse_pokemon_identifier(_arg(parts, 2))
	var details := _arg(parts, 3)
	var species: Variant = details.split(",")[0] if not details.is_empty() else null
	var hp := _parse_hp_status(_arg(parts, 4))
	var fields := {
		"pokemon_side": identifier["side"], "pokemon_slot": identifier["slot"], "pokemon_species": species,
	}
	fields.merge(hp)
	_emit(room_id, event_type, fields)


func _emit_hp_change(room_id: String, event_type: String, parts: PackedStringArray) -> void:
	var identifier := _parse_pokemon_identifier(_arg(parts, 2))
	var hp := _parse_hp_status(_arg(parts, 3))
	var fields := {"pokemon_side": identifier["side"], "pokemon_slot": identifier["slot"]}
	fields.merge(hp)
	_emit(room_id, event_type, fields)


func _emit_side_slot(room_id: String, event_type: String, parts: PackedStringArray, extra: Dictionary) -> void:
	var identifier := _parse_pokemon_identifier(_arg(parts, 2))
	var fields := {"pokemon_side": identifier["side"], "pokemon_slot": identifier["slot"]}
	fields.merge(extra)
	_emit(room_id, event_type, fields)


func _emit_faint(room_id: String, parts: PackedStringArray) -> void:
	var identifier := _parse_pokemon_identifier(_arg(parts, 2))
	_emit(room_id, "faint", {
		"pokemon_side": identifier["side"], "pokemon_slot": identifier["slot"],
		"hp_current": 0, "hp_fainted": true,
	})


static func _clean_condition(raw: String) -> Variant:
	if raw == "none":
		return null
	var colon_index := raw.find(": ")
	return raw.substr(colon_index + 2) if colon_index != -1 else raw


func _emit(room_id: String, event_type: String, fields: Dictionary) -> void:
	var e := ProtocolEventDTO.new()
	e.protocol_index = _next_protocol_index
	_next_protocol_index += 1
	e.room_id = room_id
	e.event_type = event_type
	for key in fields:
		e.set(key, fields[key])
	e.seal()
	event_decoded.emit(e)
