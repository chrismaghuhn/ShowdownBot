class_name ConfigManifestRawDTO
extends RefCounted

var _sealed: bool = false
var _root: Dictionary = {}

var root: Dictionary:
	get:
		return _root
	set(value):
		if _sealed:
			return
		_root = value.duplicate(true) if value != null else {}


func seal() -> void:
	if _sealed:
		return
	JsonNumbers.freeze_containers(_root)
	_sealed = true
