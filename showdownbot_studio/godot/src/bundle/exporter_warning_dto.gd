class_name ExporterWarningDTO
extends RefCounted

var _sealed: bool = false
var _code: String = ""
var _decision_index: Variant = null
var _message: Variant = null
var _unknown_fields: Dictionary = {}

var code: String:
	get:
		return _code
	set(value):
		if _sealed:
			return
		_code = value

var decision_index: Variant:
	get:
		return _decision_index
	set(value):
		if _sealed:
			return
		_decision_index = value

var message: Variant:
	get:
		return _message
	set(value):
		if _sealed:
			return
		_message = value

var unknown_fields: Dictionary:
	get:
		return _unknown_fields
	set(value):
		if _sealed:
			return
		_unknown_fields = value if value != null else {}


func seal() -> void:
	if _sealed:
		return
	_unknown_fields.make_read_only()
	_sealed = true
