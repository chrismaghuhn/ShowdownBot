class_name BundleManifestDTO
extends RefCounted

var _sealed: bool = false
var _schema_major: int = 0
var _schema_minor: int = 0
var _required_capabilities: PackedStringArray = PackedStringArray()
var _exporter_name: String = ""
var _exporter_version: String = ""
var _battle_id: String = ""
var _format_id: String = ""
var _git_sha: String = ""
var _config_hash: String = ""
var _trace_schema_version: Variant = null
var _privacy: PrivacyDTO
var _source_hashes_battle_log: Variant = null
var _source_hashes_decision_trace: Variant = null
var _files: FilesTableDTO
var _source_provenance: SourceProvenanceDTO
var _unknown_fields: Dictionary = {}

var schema_major: int:
	get:
		return _schema_major
	set(value):
		if _sealed:
			return
		_schema_major = value

var schema_minor: int:
	get:
		return _schema_minor
	set(value):
		if _sealed:
			return
		_schema_minor = value

var required_capabilities: PackedStringArray:
	get:
		return _required_capabilities
	set(value):
		if _sealed:
			return
		_required_capabilities = value

var exporter_name: String:
	get:
		return _exporter_name
	set(value):
		if _sealed:
			return
		_exporter_name = value

var exporter_version: String:
	get:
		return _exporter_version
	set(value):
		if _sealed:
			return
		_exporter_version = value

var battle_id: String:
	get:
		return _battle_id
	set(value):
		if _sealed:
			return
		_battle_id = value

var format_id: String:
	get:
		return _format_id
	set(value):
		if _sealed:
			return
		_format_id = value

var git_sha: String:
	get:
		return _git_sha
	set(value):
		if _sealed:
			return
		_git_sha = value

var config_hash: String:
	get:
		return _config_hash
	set(value):
		if _sealed:
			return
		_config_hash = value

var trace_schema_version: Variant:
	get:
		return _trace_schema_version
	set(value):
		if _sealed:
			return
		_trace_schema_version = value

var privacy: PrivacyDTO:
	get:
		return _privacy
	set(value):
		if _sealed:
			return
		_privacy = value

var source_hashes_battle_log: Variant:
	get:
		return _source_hashes_battle_log
	set(value):
		if _sealed:
			return
		_source_hashes_battle_log = value

var source_hashes_decision_trace: Variant:
	get:
		return _source_hashes_decision_trace
	set(value):
		if _sealed:
			return
		_source_hashes_decision_trace = value

var files: FilesTableDTO:
	get:
		return _files
	set(value):
		if _sealed:
			return
		_files = value

var source_provenance: SourceProvenanceDTO:
	get:
		return _source_provenance
	set(value):
		if _sealed:
			return
		_source_provenance = value

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
	if _privacy != null:
		_privacy.seal()
	if _files != null:
		_files.seal()
	if _source_provenance != null:
		_source_provenance.seal()
	_unknown_fields.make_read_only()
	_sealed = true
