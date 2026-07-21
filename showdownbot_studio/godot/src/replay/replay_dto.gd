class_name ReplayDTO
extends RefCounted

var _sealed: bool = false
var _entries: Array = []
var _declared_mode: String = ""
var _effective_mode: String = ""
var _replay_trusted: bool = false
var _trace_trusted: bool = false

var entries: Array:
	get:
		return _entries
	set(value):
		if _sealed:
			return
		_entries = value if value != null else []

var declared_mode: String:
	get:
		return _declared_mode
	set(value):
		if _sealed:
			return
		_declared_mode = value

var effective_mode: String:
	get:
		return _effective_mode
	set(value):
		if _sealed:
			return
		_effective_mode = value

var replay_trusted: bool:
	get:
		return _replay_trusted
	set(value):
		if _sealed:
			return
		_replay_trusted = value

var trace_trusted: bool:
	get:
		return _trace_trusted
	set(value):
		if _sealed:
			return
		_trace_trusted = value


func seal() -> void:
	if _sealed:
		return
	for entry in _entries:
		if entry is TimelineEntryDTO:
			entry.seal()
	_entries.make_read_only()
	_sealed = true
