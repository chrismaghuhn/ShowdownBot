class_name RefuseDiagnostic
extends RefCounted

var _sealed: bool = false
var _reason: String = ""
var _message: String = ""
var _offender: String = ""

var reason: String:
	get:
		return _reason
	set(value):
		if _sealed:
			return
		_reason = value

var message: String:
	get:
		return _message
	set(value):
		if _sealed:
			return
		_message = value

var offender: String:
	get:
		return _offender
	set(value):
		if _sealed:
			return
		_offender = value


func seal() -> void:
	if _sealed:
		return
	_sealed = true
