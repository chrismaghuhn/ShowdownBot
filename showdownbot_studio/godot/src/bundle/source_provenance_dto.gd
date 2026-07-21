class_name SourceProvenanceDTO
extends RefCounted

var _sealed: bool = false
var _dirty: Variant = null
var _our_side: Variant = null
var _config_id: String = ""
var _schedule_hash: String = ""
var _seed_index: int = 0
var _showdown_commit: Variant = null
var _server_patch_hash: Variant = null
var _unknown_fields: Dictionary = {}

var dirty: Variant:
	get:
		return _dirty
	set(value):
		if _sealed:
			return
		_dirty = value

var our_side: Variant:
	get:
		return _our_side
	set(value):
		if _sealed:
			return
		_our_side = value

var config_id: String:
	get:
		return _config_id
	set(value):
		if _sealed:
			return
		_config_id = value

var schedule_hash: String:
	get:
		return _schedule_hash
	set(value):
		if _sealed:
			return
		_schedule_hash = value

var seed_index: int:
	get:
		return _seed_index
	set(value):
		if _sealed:
			return
		_seed_index = value

var showdown_commit: Variant:
	get:
		return _showdown_commit
	set(value):
		if _sealed:
			return
		_showdown_commit = value

var server_patch_hash: Variant:
	get:
		return _server_patch_hash
	set(value):
		if _sealed:
			return
		_server_patch_hash = value

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
