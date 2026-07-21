class_name TimelineEntryDTO
extends RefCounted

var _sealed: bool = false
var _kind: String = ""
var _event_index: int = -1
var _decision_row_index: int = -1
var _protocol_anchor: Variant = null

var kind: String:
	get:
		return _kind
	set(value):
		if _sealed:
			return
		_kind = value

var event_index: int:
	get:
		return _event_index
	set(value):
		if _sealed:
			return
		_event_index = value

var decision_row_index: int:
	get:
		return _decision_row_index
	set(value):
		if _sealed:
			return
		_decision_row_index = value

var protocol_anchor: Variant:
	get:
		return _protocol_anchor
	set(value):
		if _sealed:
			return
		_protocol_anchor = value


func seal() -> void:
	if _sealed:
		return
	_sealed = true
