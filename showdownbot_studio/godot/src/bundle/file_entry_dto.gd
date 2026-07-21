class_name FileEntryDTO
extends RefCounted

var _sealed: bool = false
var _path: Variant = null
var _present: bool = false
var _required: bool = false
var _sha256: Variant = null

var path: Variant:
	get:
		return _path
	set(value):
		if _sealed:
			return
		_path = value

var present: bool:
	get:
		return _present
	set(value):
		if _sealed:
			return
		_present = value

var required: bool:
	get:
		return _required
	set(value):
		if _sealed:
			return
		_required = value

var sha256: Variant:
	get:
		return _sha256
	set(value):
		if _sealed:
			return
		_sha256 = value


func seal() -> void:
	if _sealed:
		return
	_sealed = true
