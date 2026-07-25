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
		_:
			line_not_understood.emit(line)


func _arg(parts: PackedStringArray, index: int) -> String:
	return parts[index] if index < parts.size() else ""


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
