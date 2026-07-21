class_name FilesTableDTO
extends RefCounted

var _sealed: bool = false
var _battle_log: FileEntryDTO
var _decision_trace: FileEntryDTO
var _warnings: FileEntryDTO
var _config_manifest: FileEntryDTO

var battle_log: FileEntryDTO:
	get:
		return _battle_log
	set(value):
		if _sealed:
			return
		_battle_log = value

var decision_trace: FileEntryDTO:
	get:
		return _decision_trace
	set(value):
		if _sealed:
			return
		_decision_trace = value

var warnings: FileEntryDTO:
	get:
		return _warnings
	set(value):
		if _sealed:
			return
		_warnings = value

var config_manifest: FileEntryDTO:
	get:
		return _config_manifest
	set(value):
		if _sealed:
			return
		_config_manifest = value


func seal() -> void:
	if _sealed:
		return
	if _battle_log != null:
		_battle_log.seal()
	if _decision_trace != null:
		_decision_trace.seal()
	if _warnings != null:
		_warnings.seal()
	if _config_manifest != null:
		_config_manifest.seal()
	_sealed = true
