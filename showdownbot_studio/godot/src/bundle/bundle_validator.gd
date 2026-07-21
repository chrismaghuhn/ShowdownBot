class_name BundleValidator
extends RefCounted

const _MANIFEST_NAME := "manifest.json"

const _KNOWN_MANIFEST_KEYS := {
	"battle_id": true,
	"config_hash": true,
	"exporter": true,
	"files": true,
	"format_id": true,
	"git_sha": true,
	"privacy": true,
	"required_capabilities": true,
	"source_hashes": true,
	"source_provenance": true,
	"trace_schema_version": true,
	"viewer_bundle_schema": true,
}

const _KNOWN_DECISION_KEYS := {
	"actual_choose_string": true,
	"aggregation": true,
	"candidates": true,
	"chosen_candidate_id": true,
	"chosen_candidate_key": true,
	"chosen_mega_slot": true,
	"chosen_rank": true,
	"chosen_tera_slot": true,
	"decision_index": true,
	"decision_latency_ms": true,
	"decision_phase": true,
	"fallback_reason": true,
	"fallback_used": true,
	"normalized_action": true,
	"observable_state_hash": true,
	"request_hash": true,
	"request_protocol_index": true,
	"selection_stage": true,
	"state_summary": true,
	"top1_top2_margin": true,
	"turn_number": true,
	"warning_count": true,
}

const _KNOWN_CANDIDATE_KEYS := {
	"aggregate_score": true,
	"candidate_id": true,
	"candidate_key": true,
	"rank": true,
}

const _KNOWN_BATTLE_EVENT_KEYS := {
	"amount": true,
	"details": true,
	"hp": true,
	"pokemon": true,
	"protocol_index": true,
	"side": true,
	"tags": true,
	"target": true,
	"type": true,
	"value": true,
}

const _KNOWN_WARNING_OBJECT_KEYS := {
	"code": true,
	"decision_index": true,
	"message": true,
}

const _DECISION_PHASES := {
	BundleMode.PHASE_TEAM_PREVIEW: true,
	BundleMode.PHASE_FORCED_REPLACEMENT: true,
	BundleMode.PHASE_REGULAR_TURN: true,
}


static func validate_dir(path: String) -> ValidationResult:
	var bundle_root := path.replace("\\", "/").trim_suffix("/")
	if bundle_root.is_empty():
		return _refuse("malformed_path", "empty bundle path", "")

	var manifest_path := bundle_root.path_join(_MANIFEST_NAME)
	if not FileAccess.file_exists(manifest_path):
		return _refuse("missing_manifest", "manifest.json not found", _MANIFEST_NAME)

	var manifest_parse := _read_json_file(manifest_path)
	if not manifest_parse.ok:
		return _refuse(manifest_parse.reason, manifest_parse.message, _MANIFEST_NAME)
	var manifest_raw: Dictionary = manifest_parse.value
	if typeof(manifest_raw) != TYPE_DICTIONARY:
		return _refuse("malformed_type", "manifest must be an object", _MANIFEST_NAME)

	var files_raw: Variant = manifest_raw.get("files")
	if typeof(files_raw) != TYPE_DICTIONARY:
		return _refuse("malformed_type", "files must be an object", "files")
	var files_dict: Dictionary = files_raw

	var files_keys := files_dict.keys()
	if files_keys.size() != BundleMode.FILE_KEYS.size():
		var unknown_extra: Array = []
		for key in files_keys:
			if not BundleMode.FILE_KEYS.has(key):
				unknown_extra.append(key)
		if not unknown_extra.is_empty():
			return _refuse(
				"unknown_logical_key",
				"unknown files keys: %s" % str(unknown_extra),
				"files"
			)
		return _refuse("malformed_manifest", "files must have exactly four logical keys", "files")

	for logical_key in BundleMode.FILE_KEYS:
		if not files_dict.has(logical_key):
			return _refuse(
				"malformed_manifest",
				"missing files key: %s" % logical_key,
				"files.%s" % logical_key
			)

	var parsed_entries: Dictionary = {}
	var declared_names: Dictionary = {}
	var seen_paths: Dictionary = {}

	for logical_key in BundleMode.FILE_KEYS:
		var entry_raw: Variant = files_dict[logical_key]
		if typeof(entry_raw) != TYPE_DICTIONARY:
			return _refuse("malformed_type", "files.%s must be an object" % logical_key, logical_key)

		var entry: Dictionary = entry_raw
		var present_parse := _require_bool(entry.get("present"), "files.%s.present" % logical_key)
		if not present_parse.ok:
			return _refuse_from_parse(present_parse, logical_key)
		var required_parse := _require_bool(entry.get("required"), "files.%s.required" % logical_key)
		if not required_parse.ok:
			return _refuse_from_parse(required_parse, logical_key)

		var present: bool = present_parse.value
		var required: bool = required_parse.value
		var rel_path: Variant = entry.get("path")
		var declared_sha: Variant = entry.get("sha256")
		var canonical := _canonical_path(logical_key)

		if present:
			if rel_path == null:
				return _refuse(
					"malformed_manifest",
					"%s: present without path" % logical_key,
					logical_key
				)
			if typeof(rel_path) != TYPE_STRING:
				return _refuse(
					"malformed_type",
					"files.%s.path must be a string" % logical_key,
					logical_key
				)
			var rel := rel_path as String
			var path_check := _validate_rel_path(rel)
			if not path_check.ok:
				return _refuse(path_check.reason, path_check.message, rel)
			if rel != canonical:
				return _refuse(
					"noncanonical_path",
					"%s must map to %s, got %s" % [logical_key, canonical, rel],
					rel
				)
			if seen_paths.has(rel):
				return _refuse("duplicate_path", "path reused: %s" % rel, rel)
			seen_paths[rel] = true
			parsed_entries[logical_key] = {
				"present": true,
				"required": required,
				"path": rel,
				"sha256": declared_sha,
			}
			declared_names[rel] = true
		else:
			if rel_path != null or declared_sha != null:
				return _refuse(
					"malformed_manifest",
					"%s: absent must have null path/sha256" % logical_key,
					logical_key
				)
			parsed_entries[logical_key] = {
				"present": false,
				"required": required,
				"path": null,
				"sha256": null,
			}

	for logical_key in [BundleMode.FILE_WARNINGS, BundleMode.FILE_CONFIG_MANIFEST]:
		var entry: Dictionary = parsed_entries[logical_key]
		if entry.required:
			return _refuse(
				"malformed_manifest",
				"%s must not be required" % logical_key,
				logical_key
			)

	var declared_mode_parse := _derive_declared_mode(parsed_entries)
	if not declared_mode_parse.ok:
		return _refuse(declared_mode_parse.reason, declared_mode_parse.message, "files")
	var declared_mode: String = declared_mode_parse.value

	for logical_key in BundleMode.FILE_KEYS:
		var entry: Dictionary = parsed_entries[logical_key]
		if not entry.present:
			continue
		var filename: String = entry.path
		var link_check := PathContainment.refuse_if_reparse_point(bundle_root, filename)
		if link_check.refuse:
			return _refuse(link_check.reason, link_check.message, link_check.offender)

	for logical_key in BundleMode.FILE_KEYS:
		var entry: Dictionary = parsed_entries[logical_key]
		if not entry.present:
			continue
		var filename: String = entry.path
		var file_path := bundle_root.path_join(filename)
		if not FileAccess.file_exists(file_path):
			return _refuse("missing_file", "missing %s" % filename, filename)
		var got_hash := _sha256_file(file_path)
		var expected: Variant = entry.sha256
		if typeof(expected) != TYPE_STRING or (expected as String) != got_hash:
			return _refuse("hash_mismatch", "%s hash mismatch" % filename, filename)

	var dir := DirAccess.open(bundle_root)
	if dir == null:
		return _refuse("malformed_path", "cannot open bundle directory", bundle_root)
	dir.list_dir_begin()
	var entry_name := dir.get_next()
	while entry_name != "":
		if entry_name == "." or entry_name == "..":
			entry_name = dir.get_next()
			continue
		var full := bundle_root.path_join(entry_name)
		if DirAccess.dir_exists_absolute(full):
			dir.list_dir_end()
			return _refuse("undeclared_subdirectory", "subdirectory not allowed: %s" % entry_name, entry_name)
		if entry_name != _MANIFEST_NAME and not declared_names.has(entry_name):
			dir.list_dir_end()
			return _refuse("undeclared_file", "undeclared file %s" % entry_name, entry_name)
		entry_name = dir.get_next()
	dir.list_dir_end()

	var schema_raw: Variant = manifest_raw.get("viewer_bundle_schema")
	if typeof(schema_raw) != TYPE_DICTIONARY:
		return _refuse("malformed_type", "viewer_bundle_schema must be an object", "viewer_bundle_schema")
	var major_parse := JsonNumbers.parse_json_int(schema_raw.get("major"), "viewer_bundle_schema.major")
	if not major_parse.ok:
		return _refuse_from_json(major_parse, "viewer_bundle_schema.major")
	if major_parse.value != BundleMode.SCHEMA_MAJOR_SUPPORTED:
		return _refuse(
			"unsupported_major",
			"unsupported major %s; supported: [%s]" % [str(major_parse.value), BundleMode.SCHEMA_MAJOR_SUPPORTED],
			"viewer_bundle_schema.major"
		)
	var minor_parse := JsonNumbers.parse_json_int(schema_raw.get("minor"), "viewer_bundle_schema.minor")
	if not minor_parse.ok:
		return _refuse_from_json(minor_parse, "viewer_bundle_schema.minor")

	var capabilities: Variant = manifest_raw.get("required_capabilities")
	if capabilities == null:
		capabilities = []
	if typeof(capabilities) != TYPE_ARRAY:
		return _refuse("malformed_type", "required_capabilities must be an array", "required_capabilities")
	for cap in capabilities as Array:
		return _refuse("unsupported_capability", "unsupported capability %s" % str(cap), str(cap))

	var nullability := _check_nullability(manifest_raw, declared_mode)
	if not nullability.ok:
		return _refuse(nullability.reason, nullability.message, nullability.offender)

	var manifest_dto := _build_manifest_dto(manifest_raw, parsed_entries, major_parse.value, minor_parse.value)
	if manifest_dto == null:
		return _refuse("malformed_type", "manifest field parse failed", "manifest.json")

	var trace_version: Variant = manifest_raw.get("trace_schema_version")
	var decision_trace_present: bool = parsed_entries[BundleMode.FILE_DECISION_TRACE].present
	var battle_log_present: bool = parsed_entries[BundleMode.FILE_BATTLE_LOG].present

	var trace_trusted := false
	var replay_trusted := battle_log_present
	var effective_mode := declared_mode
	var downgrade_warnings: Array = []

	if decision_trace_present:
		if trace_version == BundleMode.TRACE_VERSION_V2 or trace_version == BundleMode.TRACE_VERSION_V3:
			trace_trusted = true
			effective_mode = declared_mode
		else:
			if battle_log_present:
				trace_trusted = false
				replay_trusted = true
				effective_mode = BundleMode.REPLAY_ONLY
				var downgrade := RefuseDiagnostic.new()
				downgrade.reason = "unsupported_trace_schema_version"
				downgrade.message = "unsupported trace_schema_version %s" % str(trace_version)
				downgrade.offender = BundleMode.PATH_DECISION_TRACE
				downgrade_warnings.append(downgrade)
			else:
				return _refuse(
					"unsupported_trace_schema_version",
					"unsupported trace_schema_version %s" % str(trace_version),
					BundleMode.PATH_DECISION_TRACE
				)
	else:
		if trace_version != null:
			return _refuse(
				"nullability",
				"trace_schema_version must be null when decision_trace absent",
				"trace_schema_version"
			)

	var decisions: Array = []
	if trace_trusted:
		var decisions_path := bundle_root.path_join(BundleMode.PATH_DECISION_TRACE)
		var decisions_parse := _parse_decisions_jsonl(decisions_path)
		if not decisions_parse.ok:
			return _refuse(decisions_parse.reason, decisions_parse.message, decisions_parse.offender)
		decisions = decisions_parse.value

	var warnings: Array = []
	if parsed_entries[BundleMode.FILE_WARNINGS].present:
		var warnings_path := bundle_root.path_join(BundleMode.PATH_WARNINGS)
		var warnings_parse := _parse_warnings_json(warnings_path)
		if not warnings_parse.ok:
			return _refuse(warnings_parse.reason, warnings_parse.message, warnings_parse.offender)
		warnings = warnings_parse.value

	var battle_events: Array = []
	if replay_trusted:
		var battle_path := bundle_root.path_join(BundleMode.PATH_BATTLE_LOG)
		var battle_parse := _parse_battle_jsonl(battle_path)
		if not battle_parse.ok:
			return _refuse(battle_parse.reason, battle_parse.message, battle_parse.offender)
		battle_events = battle_parse.value

	var config_manifest: Variant = null
	if parsed_entries[BundleMode.FILE_CONFIG_MANIFEST].present:
		var config_path := bundle_root.path_join(BundleMode.PATH_CONFIG_MANIFEST)
		var config_parse := _read_json_file(config_path)
		if not config_parse.ok:
			return _refuse(config_parse.reason, config_parse.message, BundleMode.PATH_CONFIG_MANIFEST)
		var raw := ConfigManifestRawDTO.new()
		raw.root = config_parse.value if typeof(config_parse.value) == TYPE_DICTIONARY else {}
		config_manifest = raw

	var bundle := BundleDTO.new()
	bundle.declared_mode = declared_mode
	bundle.effective_mode = effective_mode
	bundle.trace_trusted = trace_trusted
	bundle.replay_trusted = replay_trusted
	bundle.manifest = manifest_dto
	bundle.decisions = decisions
	bundle.battle_events = battle_events
	bundle.warnings = warnings
	bundle.config_manifest = config_manifest
	bundle.downgrade_warnings = downgrade_warnings.duplicate()
	bundle.seal()

	var result := ValidationResult.new()
	result.ok = true
	result.diagnostic = null
	result.declared_mode = declared_mode
	result.effective_mode = effective_mode
	result.trace_trusted = trace_trusted
	result.replay_trusted = replay_trusted
	result.bundle = bundle
	result.downgrade_warnings = downgrade_warnings.duplicate()
	result.seal()
	return result


static func _canonical_path(logical_key: String) -> String:
	match logical_key:
		BundleMode.FILE_BATTLE_LOG:
			return BundleMode.PATH_BATTLE_LOG
		BundleMode.FILE_DECISION_TRACE:
			return BundleMode.PATH_DECISION_TRACE
		BundleMode.FILE_WARNINGS:
			return BundleMode.PATH_WARNINGS
		BundleMode.FILE_CONFIG_MANIFEST:
			return BundleMode.PATH_CONFIG_MANIFEST
		_:
			return ""


static func _derive_declared_mode(parsed_entries: Dictionary) -> Dictionary:
	var bl: Dictionary = parsed_entries[BundleMode.FILE_BATTLE_LOG]
	var dt: Dictionary = parsed_entries[BundleMode.FILE_DECISION_TRACE]
	if bl.required != bl.present or dt.required != dt.present:
		return {"ok": false, "reason": "malformed_manifest", "message": "required != present on mode keys"}
	if bl.present and dt.present:
		return {"ok": true, "value": BundleMode.REPLAY_TRACE}
	if bl.present:
		return {"ok": true, "value": BundleMode.REPLAY_ONLY}
	if dt.present:
		return {"ok": true, "value": BundleMode.TRACE_ONLY}
	return {"ok": false, "reason": "missing_mode", "message": "bundle has neither battle_log nor decision_trace"}


static func _validate_rel_path(rel_path: String) -> Dictionary:
	if rel_path.is_empty():
		return {"ok": false, "reason": "malformed_path", "message": "empty path"}
	if rel_path.begins_with("/") or rel_path.begins_with("\\"):
		return {"ok": false, "reason": "malformed_path", "message": "leading separator in path"}
	if "\\" in rel_path:
		return {"ok": false, "reason": "malformed_path", "message": "non-portable path"}
	if rel_path.contains(".."):
		return {"ok": false, "reason": "malformed_path", "message": "path escape"}
	var parts := rel_path.split("/")
	if parts.size() != 1 or parts[0].is_empty():
		return {"ok": false, "reason": "malformed_path", "message": "subdirectory path not allowed"}
	return {"ok": true}


static func _check_nullability(manifest_raw: Dictionary, declared_mode: String) -> Dictionary:
	if declared_mode == BundleMode.REPLAY_ONLY:
		if manifest_raw.get("trace_schema_version") != null:
			return _nullability_fail("trace_schema_version must be null in replay-only", "trace_schema_version")
		var source_hashes: Variant = manifest_raw.get("source_hashes")
		if typeof(source_hashes) == TYPE_DICTIONARY:
			if source_hashes.get("decision_trace") != null:
				return _nullability_fail(
					"source_hashes.decision_trace must be null",
					"source_hashes.decision_trace"
				)
		var sp: Variant = manifest_raw.get("source_provenance")
		if typeof(sp) == TYPE_DICTIONARY and sp.get("our_side") != null:
			return _nullability_fail("our_side must be null in replay-only", "source_provenance.our_side")
	if declared_mode == BundleMode.TRACE_ONLY:
		var source_hashes2: Variant = manifest_raw.get("source_hashes")
		if typeof(source_hashes2) == TYPE_DICTIONARY and source_hashes2.get("battle_log") != null:
			return _nullability_fail("source_hashes.battle_log must be null", "source_hashes.battle_log")
	return {"ok": true}


static func _nullability_fail(message: String, offender: String) -> Dictionary:
	return {"ok": false, "reason": "nullability", "message": message, "offender": offender}


static func _build_manifest_dto(
	manifest_raw: Dictionary,
	parsed_entries: Dictionary,
	schema_major: int,
	schema_minor: int
) -> BundleManifestDTO:
	var exporter_raw: Variant = manifest_raw.get("exporter")
	if typeof(exporter_raw) != TYPE_DICTIONARY:
		return null
	var exporter: Dictionary = exporter_raw
	if typeof(exporter.get("name")) != TYPE_STRING or typeof(exporter.get("version")) != TYPE_STRING:
		return null

	var privacy_raw: Variant = manifest_raw.get("privacy")
	if typeof(privacy_raw) != TYPE_DICTIONARY:
		return null
	var privacy_dict: Dictionary = privacy_raw
	var raw_bool: Variant = privacy_dict.get("raw_source_included")
	if typeof(raw_bool) != TYPE_BOOL:
		return null

	var privacy := PrivacyDTO.new()
	privacy.profile = str(privacy_dict.get("profile", ""))
	privacy.chat = str(privacy_dict.get("chat", ""))
	privacy.private_messages = str(privacy_dict.get("private_messages", ""))
	privacy.player_names = str(privacy_dict.get("player_names", ""))
	privacy.source_url = str(privacy_dict.get("source_url", ""))
	privacy.raw_source_included = raw_bool

	var sp_raw: Variant = manifest_raw.get("source_provenance")
	if typeof(sp_raw) != TYPE_DICTIONARY:
		return null
	var sp: Dictionary = sp_raw
	if typeof(sp.get("config_id")) != TYPE_STRING or typeof(sp.get("schedule_hash")) != TYPE_STRING:
		return null
	var seed_parse := JsonNumbers.parse_json_int(sp.get("seed_index"), "source_provenance.seed_index")
	if not seed_parse.ok:
		return null

	var provenance := SourceProvenanceDTO.new()
	provenance.dirty = sp.get("dirty")
	provenance.our_side = sp.get("our_side")
	provenance.config_id = sp.get("config_id")
	provenance.schedule_hash = sp.get("schedule_hash")
	provenance.seed_index = seed_parse.value
	provenance.showdown_commit = sp.get("showdown_commit")
	provenance.server_patch_hash = sp.get("server_patch_hash")
	provenance.unknown_fields = _collect_unknown(sp, {
		"dirty": true,
		"our_side": true,
		"config_id": true,
		"schedule_hash": true,
		"seed_index": true,
		"showdown_commit": true,
		"server_patch_hash": true,
	})

	var files_table := FilesTableDTO.new()
	files_table.battle_log = _file_entry_from_parsed(parsed_entries[BundleMode.FILE_BATTLE_LOG])
	files_table.decision_trace = _file_entry_from_parsed(parsed_entries[BundleMode.FILE_DECISION_TRACE])
	files_table.warnings = _file_entry_from_parsed(parsed_entries[BundleMode.FILE_WARNINGS])
	files_table.config_manifest = _file_entry_from_parsed(parsed_entries[BundleMode.FILE_CONFIG_MANIFEST])

	var source_hashes_raw: Variant = manifest_raw.get("source_hashes")
	var battle_log_hash: Variant = null
	var decision_trace_hash: Variant = null
	if typeof(source_hashes_raw) == TYPE_DICTIONARY:
		battle_log_hash = source_hashes_raw.get("battle_log")
		decision_trace_hash = source_hashes_raw.get("decision_trace")

	for required_key in ["battle_id", "format_id", "git_sha", "config_hash"]:
		if typeof(manifest_raw.get(required_key)) != TYPE_STRING:
			return null

	var manifest := BundleManifestDTO.new()
	manifest.schema_major = schema_major
	manifest.schema_minor = schema_minor
	manifest.required_capabilities = PackedStringArray()
	var caps: Variant = manifest_raw.get("required_capabilities")
	if typeof(caps) == TYPE_ARRAY:
		for cap in caps:
			if typeof(cap) == TYPE_STRING:
				manifest.required_capabilities.append(cap)
	manifest.exporter_name = exporter.get("name")
	manifest.exporter_version = exporter.get("version")
	manifest.battle_id = manifest_raw.get("battle_id")
	manifest.format_id = manifest_raw.get("format_id")
	manifest.git_sha = manifest_raw.get("git_sha")
	manifest.config_hash = manifest_raw.get("config_hash")
	manifest.trace_schema_version = manifest_raw.get("trace_schema_version")
	manifest.privacy = privacy
	manifest.source_hashes_battle_log = battle_log_hash
	manifest.source_hashes_decision_trace = decision_trace_hash
	manifest.files = files_table
	manifest.source_provenance = provenance
	manifest.unknown_fields = _collect_unknown(manifest_raw, _KNOWN_MANIFEST_KEYS)
	return manifest


static func _file_entry_from_parsed(parsed: Dictionary) -> FileEntryDTO:
	var entry := FileEntryDTO.new()
	entry.path = parsed.path
	entry.present = parsed.present
	entry.required = parsed.required
	entry.sha256 = parsed.sha256
	return entry


static func _parse_decisions_jsonl(path: String) -> Dictionary:
	var text := FileAccess.get_file_as_string(path)
	if text.is_empty() and not FileAccess.file_exists(path):
		return {"ok": false, "reason": "missing_file", "message": "missing decisions", "offender": path}
	var rows: Array = []
	var seen_indices: Dictionary = {}
	for line in text.split("\n"):
		var trimmed := line.strip_edges()
		if trimmed.is_empty():
			continue
		var json := JSON.new()
		if json.parse(trimmed) != OK:
			return {
				"ok": false,
				"reason": "jsonl_parse_error",
				"message": "decisions.jsonl parse error",
				"offender": BundleMode.PATH_DECISION_TRACE,
			}
		if typeof(json.data) != TYPE_DICTIONARY:
			return {
				"ok": false,
				"reason": "jsonl_parse_error",
				"message": "decisions.jsonl row must be object",
				"offender": BundleMode.PATH_DECISION_TRACE,
			}
		var row_parse := _parse_decision_row(json.data as Dictionary)
		if not row_parse.ok:
			return row_parse
		var row: DecisionRowDTO = row_parse.value
		if seen_indices.has(row.decision_index):
			return {
				"ok": false,
				"reason": "duplicate_decision_index",
				"message": "duplicate decision_index %d" % row.decision_index,
				"offender": BundleMode.PATH_DECISION_TRACE,
			}
		seen_indices[row.decision_index] = true
		rows.append(row)
	return {"ok": true, "value": rows}


static func _parse_decision_row(raw: Dictionary) -> Dictionary:
	var idx_parse := JsonNumbers.parse_json_int(raw.get("decision_index"), "decision_index")
	if not idx_parse.ok:
		return _parse_fail_from_json(idx_parse, BundleMode.PATH_DECISION_TRACE)
	var turn_parse := JsonNumbers.parse_json_int(raw.get("turn_number"), "turn_number")
	if not turn_parse.ok:
		return _parse_fail_from_json(turn_parse, BundleMode.PATH_DECISION_TRACE)
	if typeof(raw.get("decision_phase")) != TYPE_STRING:
		return {
			"ok": false,
			"reason": "malformed_type",
			"message": "decision_phase must be string",
			"offender": BundleMode.PATH_DECISION_TRACE,
		}
	var phase: String = raw.get("decision_phase")
	if not _DECISION_PHASES.has(phase):
		return {
			"ok": false,
			"reason": "malformed_type",
			"message": "unknown decision_phase %s" % phase,
			"offender": BundleMode.PATH_DECISION_TRACE,
		}
	var latency_parse := JsonNumbers.parse_json_float(
		raw.get("decision_latency_ms"),
		"decision_latency_ms"
	)
	if not latency_parse.ok:
		return _parse_fail_from_json(latency_parse, BundleMode.PATH_DECISION_TRACE)
	for required_str in ["observable_state_hash", "request_hash", "actual_choose_string"]:
		if typeof(raw.get(required_str)) != TYPE_STRING:
			return {
				"ok": false,
				"reason": "malformed_type",
				"message": "%s must be string" % required_str,
				"offender": BundleMode.PATH_DECISION_TRACE,
			}
	if typeof(raw.get("state_summary")) != TYPE_DICTIONARY:
		return {
			"ok": false,
			"reason": "malformed_type",
			"message": "state_summary must be object",
			"offender": BundleMode.PATH_DECISION_TRACE,
		}
	if typeof(raw.get("normalized_action")) != TYPE_DICTIONARY:
		return {
			"ok": false,
			"reason": "malformed_type",
			"message": "normalized_action must be object",
			"offender": BundleMode.PATH_DECISION_TRACE,
		}
	if typeof(raw.get("fallback_used")) != TYPE_BOOL:
		return {
			"ok": false,
			"reason": "malformed_type",
			"message": "fallback_used must be bool",
			"offender": BundleMode.PATH_DECISION_TRACE,
		}
	var warning_count_parse := JsonNumbers.parse_json_int(raw.get("warning_count"), "warning_count")
	if not warning_count_parse.ok:
		return _parse_fail_from_json(warning_count_parse, BundleMode.PATH_DECISION_TRACE)

	var row := DecisionRowDTO.new()
	row.decision_index = idx_parse.value
	row.turn_number = turn_parse.value
	row.decision_phase = phase
	row.decision_latency_ms = latency_parse.value
	row.observable_state_hash = raw.get("observable_state_hash")
	row.request_hash = raw.get("request_hash")
	row.state_summary = raw.get("state_summary")
	row.normalized_action = raw.get("normalized_action")
	row.actual_choose_string = raw.get("actual_choose_string")
	row.fallback_used = raw.get("fallback_used")
	row.warning_count = warning_count_parse.value
	row.selection_stage = raw.get("selection_stage")
	row.fallback_reason = raw.get("fallback_reason")
	row.chosen_candidate_key = raw.get("chosen_candidate_key")
	row.chosen_candidate_id = raw.get("chosen_candidate_id")

	var rank_parse := _parse_optional_int(raw.get("chosen_rank"), "chosen_rank")
	if not rank_parse.ok:
		return rank_parse
	row.chosen_rank = rank_parse.value
	var tera_parse := _parse_optional_int(raw.get("chosen_tera_slot"), "chosen_tera_slot")
	if not tera_parse.ok:
		return tera_parse
	row.chosen_tera_slot = tera_parse.value
	var mega_parse := _parse_optional_int(raw.get("chosen_mega_slot"), "chosen_mega_slot")
	if not mega_parse.ok:
		return mega_parse
	row.chosen_mega_slot = mega_parse.value
	var req_idx_parse := _parse_optional_int(raw.get("request_protocol_index"), "request_protocol_index")
	if not req_idx_parse.ok:
		return req_idx_parse
	row.request_protocol_index = req_idx_parse.value
	var margin_parse := _parse_optional_float(raw.get("top1_top2_margin"), "top1_top2_margin")
	if not margin_parse.ok:
		return margin_parse
	row.top1_top2_margin = margin_parse.value

	var aggregation: Variant = raw.get("aggregation")
	if aggregation != null:
		if typeof(aggregation) != TYPE_DICTIONARY:
			return {
				"ok": false,
				"reason": "malformed_type",
				"message": "aggregation must be object",
				"offender": BundleMode.PATH_DECISION_TRACE,
			}
		var agg: Dictionary = aggregation
		row.aggregation_mode = agg.get("mode")
		row.aggregation_risk_lambda = agg.get("risk_lambda")
		row.aggregation_must_react_lambda = agg.get("must_react_lambda")

	var candidates_raw: Variant = raw.get("candidates")
	if candidates_raw == null:
		candidates_raw = []
	if typeof(candidates_raw) != TYPE_ARRAY:
		return {
			"ok": false,
			"reason": "malformed_type",
			"message": "candidates must be array",
			"offender": BundleMode.PATH_DECISION_TRACE,
		}
	var candidates: Array = candidates_raw
	var candidate_keys_seen: Dictionary = {}
	var parsed_candidates: Array = []
	for candidate_raw in candidates:
		if typeof(candidate_raw) != TYPE_DICTIONARY:
			return {
				"ok": false,
				"reason": "malformed_type",
				"message": "candidate must be object",
				"offender": BundleMode.PATH_DECISION_TRACE,
			}
		var cand_parse := _parse_candidate(candidate_raw as Dictionary)
		if not cand_parse.ok:
			return cand_parse
		var cand: CandidateDTO = cand_parse.value
		if cand.candidate_key != null:
			var key_str := str(cand.candidate_key)
			if candidate_keys_seen.has(key_str):
				return {
					"ok": false,
					"reason": "duplicate_candidate_key",
					"message": "duplicate candidate_key in decision %d" % row.decision_index,
					"offender": BundleMode.PATH_DECISION_TRACE,
				}
			candidate_keys_seen[key_str] = true
		parsed_candidates.append(cand)
	row.candidates = parsed_candidates

	var has_chosen := (
		row.chosen_candidate_key != null
		or row.chosen_candidate_id != null
		or row.chosen_rank != null
	)
	if parsed_candidates.is_empty():
		if has_chosen:
			return {
				"ok": false,
				"reason": "chosen_integrity",
				"message": "chosen fields set with empty candidates",
				"offender": BundleMode.PATH_DECISION_TRACE,
			}
		row.decision_valid = true
	else:
		if row.chosen_candidate_key == null:
			row.decision_valid = false
		else:
			var matches := 0
			for cand in parsed_candidates:
				if cand.candidate_key == row.chosen_candidate_key:
					matches += 1
			if matches == 0:
				row.decision_valid = false
			elif matches > 1:
				return {
					"ok": false,
					"reason": "ambiguous_chosen_candidate",
					"message": "ambiguous chosen_candidate_key in decision %d" % row.decision_index,
					"offender": BundleMode.PATH_DECISION_TRACE,
				}
			else:
				row.decision_valid = true

	row.unknown_fields = _collect_unknown(raw, _KNOWN_DECISION_KEYS)
	return {"ok": true, "value": row}


static func _parse_candidate(raw: Dictionary) -> Dictionary:
	if typeof(raw.get("candidate_id")) != TYPE_STRING:
		return {
			"ok": false,
			"reason": "malformed_type",
			"message": "candidate_id must be string",
			"offender": BundleMode.PATH_DECISION_TRACE,
		}
	var rank_parse := JsonNumbers.parse_json_int(raw.get("rank"), "rank")
	if not rank_parse.ok:
		return _parse_fail_from_json(rank_parse, BundleMode.PATH_DECISION_TRACE)
	var score_parse := JsonNumbers.parse_json_float(raw.get("aggregate_score"), "aggregate_score")
	if not score_parse.ok:
		return _parse_fail_from_json(score_parse, BundleMode.PATH_DECISION_TRACE)
	var candidate := CandidateDTO.new()
	candidate.candidate_id = raw.get("candidate_id")
	candidate.rank = rank_parse.value
	candidate.aggregate_score = score_parse.value
	candidate.candidate_key = raw.get("candidate_key")
	candidate.unknown_fields = _collect_unknown(raw, _KNOWN_CANDIDATE_KEYS)
	return {"ok": true, "value": candidate}


static func _parse_warnings_json(path: String) -> Dictionary:
	var parsed := _read_json_file(path)
	if not parsed.ok:
		return parsed
	if typeof(parsed.value) != TYPE_DICTIONARY:
		return {
			"ok": false,
			"reason": "malformed_type",
			"message": "warnings.json must be object",
			"offender": BundleMode.PATH_WARNINGS,
		}
	var root: Dictionary = parsed.value
	var warnings_raw: Variant = root.get("warnings")
	if warnings_raw == null:
		warnings_raw = []
	if typeof(warnings_raw) != TYPE_ARRAY:
		return {
			"ok": false,
			"reason": "malformed_type",
			"message": "warnings must be array",
			"offender": BundleMode.PATH_WARNINGS,
		}
	var out: Array = []
	for item in warnings_raw as Array:
		if typeof(item) != TYPE_DICTIONARY:
			return {
				"ok": false,
				"reason": "malformed_warning",
				"message": "warning element must be object",
				"offender": BundleMode.PATH_WARNINGS,
			}
		var warn_parse := _parse_warning_object(item as Dictionary)
		if not warn_parse.ok:
			return warn_parse
		out.append(warn_parse.value)
	return {"ok": true, "value": out}


static func _parse_warning_object(raw: Dictionary) -> Dictionary:
	if not raw.has("code") or not raw.has("decision_index"):
		return {
			"ok": false,
			"reason": "malformed_warning",
			"message": "warning missing mandatory keys",
			"offender": BundleMode.PATH_WARNINGS,
		}
	if typeof(raw.get("code")) != TYPE_STRING:
		return {
			"ok": false,
			"reason": "malformed_warning",
			"message": "warning code must be string",
			"offender": BundleMode.PATH_WARNINGS,
		}
	var decision_index_raw: Variant = raw.get("decision_index")
	var decision_index: Variant = null
	if decision_index_raw != null:
		var idx_parse := JsonNumbers.parse_json_int(decision_index_raw, "decision_index")
		if not idx_parse.ok:
			return _parse_fail_from_json(idx_parse, BundleMode.PATH_WARNINGS)
		decision_index = idx_parse.value
	var message_raw: Variant = raw.get("message", null)
	if raw.has("message") and message_raw != null and typeof(message_raw) != TYPE_STRING:
		return {
			"ok": false,
			"reason": "malformed_warning",
			"message": "warning message must be string or null",
			"offender": BundleMode.PATH_WARNINGS,
		}
	var warning := ExporterWarningDTO.new()
	warning.code = raw.get("code")
	warning.decision_index = decision_index
	warning.message = message_raw if raw.has("message") else null
	warning.unknown_fields = _collect_unknown(raw, _KNOWN_WARNING_OBJECT_KEYS)
	return {"ok": true, "value": warning}


static func _parse_battle_jsonl(path: String) -> Dictionary:
	var text := FileAccess.get_file_as_string(path)
	var events: Array = []
	var last_protocol_index := -1
	for line in text.split("\n"):
		var trimmed := line.strip_edges()
		if trimmed.is_empty():
			continue
		var json := JSON.new()
		if json.parse(trimmed) != OK:
			return {
				"ok": false,
				"reason": "jsonl_parse_error",
				"message": "battle.jsonl parse error",
				"offender": BundleMode.PATH_BATTLE_LOG,
			}
		if typeof(json.data) != TYPE_DICTIONARY:
			return {
				"ok": false,
				"reason": "jsonl_parse_error",
				"message": "battle.jsonl row must be object",
				"offender": BundleMode.PATH_BATTLE_LOG,
			}
		var event_parse := _parse_battle_event(json.data as Dictionary, last_protocol_index)
		if not event_parse.ok:
			return event_parse
		var event: BattleEventDTO = event_parse.value
		last_protocol_index = event.protocol_index
		events.append(event)
	return {"ok": true, "value": events}


static func _parse_battle_event(raw: Dictionary, last_protocol_index: int) -> Dictionary:
	var idx_parse := JsonNumbers.parse_json_int(raw.get("protocol_index"), "protocol_index")
	if not idx_parse.ok:
		return _parse_fail_from_json(idx_parse, BundleMode.PATH_BATTLE_LOG)
	if idx_parse.value <= last_protocol_index:
		return {
			"ok": false,
			"reason": "protocol_index_order",
			"message": "protocol_index not strictly increasing",
			"offender": BundleMode.PATH_BATTLE_LOG,
		}
	if typeof(raw.get("type")) != TYPE_STRING:
		return {
			"ok": false,
			"reason": "malformed_type",
			"message": "battle event type must be string",
			"offender": BundleMode.PATH_BATTLE_LOG,
		}
	var event := BattleEventDTO.new()
	event.protocol_index = idx_parse.value
	event.type = raw.get("type")
	event.details = raw.get("details")
	event.value = raw.get("value")
	event.side = raw.get("side")
	if raw.has("tags"):
		if typeof(raw.get("tags")) != TYPE_ARRAY:
			return {
				"ok": false,
				"reason": "malformed_type",
				"message": "tags must be array",
				"offender": BundleMode.PATH_BATTLE_LOG,
			}
		event.tags = PackedStringArray(raw.get("tags"))
	var amount_parse := _parse_optional_int(raw.get("amount"), "amount")
	if not amount_parse.ok:
		return amount_parse
	event.amount = amount_parse.value
	var pokemon: Variant = raw.get("pokemon")
	if typeof(pokemon) == TYPE_DICTIONARY:
		var p: Dictionary = pokemon
		event.pokemon_side = p.get("side")
		event.pokemon_slot = p.get("slot")
		event.pokemon_species = p.get("species")
	var target: Variant = raw.get("target")
	if typeof(target) == TYPE_DICTIONARY:
		var t: Dictionary = target
		event.target_side = t.get("side")
		event.target_slot = t.get("slot")
	var hp: Variant = raw.get("hp")
	if typeof(hp) == TYPE_DICTIONARY:
		var h: Dictionary = hp
		var cur_parse := _parse_optional_int(h.get("current"), "hp.current")
		if not cur_parse.ok:
			return cur_parse
		event.hp_current = cur_parse.value
		var max_parse := _parse_optional_int(h.get("maximum"), "hp.maximum")
		if not max_parse.ok:
			return max_parse
		event.hp_maximum = max_parse.value
		event.hp_fainted = h.get("fainted")
		event.hp_status = h.get("status")
	event.unknown_fields = _collect_unknown(raw, _KNOWN_BATTLE_EVENT_KEYS)
	return {"ok": true, "value": event}


static func _parse_optional_int(value: Variant, field_name: String) -> Dictionary:
	if value == null:
		return {"ok": true, "value": null}
	var parsed := JsonNumbers.parse_json_int(value, field_name)
	if not parsed.ok:
		return _parse_fail_from_json(parsed, BundleMode.PATH_DECISION_TRACE)
	return {"ok": true, "value": parsed.value}


static func _parse_optional_float(value: Variant, field_name: String) -> Dictionary:
	if value == null:
		return {"ok": true, "value": null}
	var parsed := JsonNumbers.parse_json_float(value, field_name)
	if not parsed.ok:
		return _parse_fail_from_json(parsed, BundleMode.PATH_DECISION_TRACE)
	return {"ok": true, "value": parsed.value}


static func _collect_unknown(raw: Dictionary, known: Dictionary) -> Dictionary:
	var out := {}
	for key in raw.keys():
		if not known.has(key):
			out[key] = raw[key]
	return out.duplicate(true)


static func _require_bool(value: Variant, label: String) -> Dictionary:
	if typeof(value) != TYPE_BOOL:
		return {"ok": false, "reason": "malformed_type", "message": "%s must be a boolean" % label}
	return {"ok": true, "value": value}


static func _read_json_file(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {"ok": false, "reason": "missing_file", "message": "missing %s" % path.get_file()}
	var text := FileAccess.get_file_as_string(path)
	var json := JSON.new()
	if json.parse(text) != OK:
		return {"ok": false, "reason": "malformed_type", "message": "JSON parse error in %s" % path.get_file()}
	return {"ok": true, "value": json.data}


static func _sha256_file(path: String) -> String:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return ""
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	while file.get_position() < file.get_length():
		ctx.update(file.get_buffer(mini(65536, file.get_length() - file.get_position())))
	return ctx.finish().hex_encode()


static func _refuse(reason: String, message: String, offender: String) -> ValidationResult:
	var diagnostic := RefuseDiagnostic.new()
	diagnostic.reason = reason
	diagnostic.message = message
	diagnostic.offender = offender
	var result := ValidationResult.new()
	result.ok = false
	result.diagnostic = diagnostic
	result.declared_mode = null
	result.effective_mode = null
	result.trace_trusted = false
	result.replay_trusted = false
	result.bundle = null
	result.downgrade_warnings = []
	result.seal()
	return result


static func _refuse_from_parse(parsed: Dictionary, offender: String) -> ValidationResult:
	return _refuse(parsed.reason, parsed.message, offender)


static func _refuse_from_json(parsed: Dictionary, offender: String) -> ValidationResult:
	return _refuse(_json_reason_code(parsed.reason), parsed.reason, offender)


static func _parse_fail_from_json(parsed: Dictionary, offender: String) -> Dictionary:
	return {
		"ok": false,
		"reason": _json_reason_code(parsed.reason),
		"message": parsed.reason,
		"offender": offender,
	}


static func _json_reason_code(reason: String) -> String:
	var colon := reason.find(":")
	if colon == -1:
		return reason
	return reason.substr(0, colon)
