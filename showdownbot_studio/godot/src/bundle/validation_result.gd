class_name ValidationResult
extends RefCounted

var _sealed: bool = false
var _ok: bool = false
var _diagnostic: RefuseDiagnostic = null
var _declared_mode: Variant = null
var _effective_mode: Variant = null
var _trace_trusted: bool = false
var _replay_trusted: bool = false
var _bundle: BundleDTO = null
var _downgrade_warnings: Array = []

var ok: bool:
	get:
		return _ok
	set(value):
		if _sealed:
			return
		_ok = value

var diagnostic: RefuseDiagnostic:
	get:
		return _diagnostic
	set(value):
		if _sealed:
			return
		_diagnostic = value

var declared_mode: Variant:
	get:
		return _declared_mode
	set(value):
		if _sealed:
			return
		_declared_mode = value

var effective_mode: Variant:
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

var bundle: BundleDTO:
	get:
		return _bundle
	set(value):
		if _sealed:
			return
		_bundle = value

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
	if _diagnostic != null:
		_diagnostic.seal()
	if _bundle != null:
		_bundle.seal()
	for warning in _downgrade_warnings:
		if warning is RefuseDiagnostic:
			warning.seal()
	_downgrade_warnings.make_read_only()
	_sealed = true
