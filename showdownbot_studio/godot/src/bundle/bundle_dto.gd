class_name BundleDTO
extends RefCounted

var _sealed: bool = false
var _declared_mode: String = ""
var _effective_mode: String = ""
var _trace_trusted: bool = false
var _replay_trusted: bool = false
var _manifest: BundleManifestDTO
var _decisions: Array = []
var _battle_events: Array = []
var _warnings: Array = []
var _config_manifest: Variant = null
var _downgrade_warnings: Array = []

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

var trace_trusted: bool:
	get:
		return _trace_trusted
	set(value):
		if _sealed:
			return
		_trace_trusted = value

var replay_trusted: bool:
	get:
		return _replay_trusted
	set(value):
		if _sealed:
			return
		_replay_trusted = value

var manifest: BundleManifestDTO:
	get:
		return _manifest
	set(value):
		if _sealed:
			return
		_manifest = value

var decisions: Array:
	get:
		return _decisions
	set(value):
		if _sealed:
			return
		_decisions = value if value != null else []

var battle_events: Array:
	get:
		return _battle_events
	set(value):
		if _sealed:
			return
		_battle_events = value if value != null else []

var warnings: Array:
	get:
		return _warnings
	set(value):
		if _sealed:
			return
		_warnings = value if value != null else []

var config_manifest: Variant:
	get:
		return _config_manifest
	set(value):
		if _sealed:
			return
		_config_manifest = value

var downgrade_warnings: Array:
	get:
		return _downgrade_warnings
	set(value):
		if _sealed:
			return
		_downgrade_warnings = value if value != null else []


func seal() -> void:
	if _sealed:
		return
	if _manifest != null:
		_manifest.seal()
	for row in _decisions:
		if row is DecisionRowDTO:
			row.seal()
	for event in _battle_events:
		if event is BattleEventDTO:
			event.seal()
	for warning in _warnings:
		if warning is ExporterWarningDTO:
			warning.seal()
	if _config_manifest is ConfigManifestRawDTO:
		_config_manifest.seal()
	for downgrade in _downgrade_warnings:
		if downgrade is RefuseDiagnostic:
			downgrade.seal()
	_decisions.make_read_only()
	_battle_events.make_read_only()
	_warnings.make_read_only()
	_downgrade_warnings.make_read_only()
	_sealed = true
