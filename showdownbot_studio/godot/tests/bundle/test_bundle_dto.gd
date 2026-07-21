extends GdUnitTestSuite


func _make_file_entry(present: bool = true) -> FileEntryDTO:
	var entry := FileEntryDTO.new()
	entry.path = "battle.jsonl" if present else null
	entry.present = present
	entry.required = present
	entry.sha256 = "abc" if present else null
	return entry


func _make_files_table() -> FilesTableDTO:
	var table := FilesTableDTO.new()
	table.battle_log = _make_file_entry(true)
	table.decision_trace = _make_file_entry(true)
	table.warnings = _make_file_entry(false)
	table.config_manifest = _make_file_entry(false)
	return table


func _make_privacy() -> PrivacyDTO:
	var privacy := PrivacyDTO.new()
	privacy.profile = "portable-pseudonymous-v1"
	privacy.chat = "excluded"
	privacy.private_messages = "excluded"
	privacy.player_names = "seat-pseudonyms"
	privacy.source_url = "excluded"
	privacy.raw_source_included = false
	return privacy


func _make_source_provenance() -> SourceProvenanceDTO:
	var provenance := SourceProvenanceDTO.new()
	provenance.dirty = false
	provenance.our_side = "p1"
	provenance.config_id = "cfg-1"
	provenance.schedule_hash = "sched"
	provenance.seed_index = 0
	provenance.unknown_fields = {"extra": "kept"}
	return provenance


func _make_manifest() -> BundleManifestDTO:
	var manifest := BundleManifestDTO.new()
	manifest.schema_major = 1
	manifest.schema_minor = 0
	manifest.required_capabilities = PackedStringArray(["viewer-v0"])
	manifest.exporter_name = "test-exporter"
	manifest.exporter_version = "0.0.0"
	manifest.battle_id = "battle-1"
	manifest.format_id = "gen9ou"
	manifest.git_sha = "deadbeef"
	manifest.config_hash = "cfg-hash"
	manifest.trace_schema_version = BundleMode.TRACE_VERSION_V3
	manifest.privacy = _make_privacy()
	manifest.source_hashes_battle_log = "hash-bl"
	manifest.source_hashes_decision_trace = "hash-dt"
	manifest.files = _make_files_table()
	manifest.source_provenance = _make_source_provenance()
	manifest.unknown_fields = {"manifest_extra": 1}
	return manifest


func test_class_names_resolve_globally() -> void:
	assert_object(JsonNumbers.new()).is_not_null()
	assert_object(BundleMode.new()).is_not_null()
	assert_object(FileEntryDTO.new()).is_not_null()
	assert_object(FilesTableDTO.new()).is_not_null()
	assert_object(PrivacyDTO.new()).is_not_null()
	assert_object(SourceProvenanceDTO.new()).is_not_null()
	assert_object(BundleManifestDTO.new()).is_not_null()
	assert_object(CandidateDTO.new()).is_not_null()
	assert_object(DecisionRowDTO.new()).is_not_null()
	assert_object(BattleEventDTO.new()).is_not_null()
	assert_object(ExporterWarningDTO.new()).is_not_null()
	assert_object(ConfigManifestRawDTO.new()).is_not_null()
	assert_object(BundleDTO.new()).is_not_null()
	assert_object(RefuseDiagnostic.new()).is_not_null()
	assert_object(ValidationResult.new()).is_not_null()


func test_sealed_rejects_field_assignment() -> void:
	var entry := FileEntryDTO.new()
	entry.path = "battle.jsonl"
	entry.seal()
	entry.path = "mutated.jsonl"
	assert_str(entry.path).is_equal("battle.jsonl")


func test_sealed_nested_dict_rejects_mutation() -> void:
	var row := DecisionRowDTO.new()
	row.state_summary = {"turn": 1}
	row.unknown_fields = {"extra": true}
	row.seal()
	await assert_error(func() -> void: row.state_summary["turn"] = 99).is_runtime_error(
		"Invalid assignment on read-only value (on base: 'Dictionary')."
	)
	await assert_error(func() -> void: row.unknown_fields["extra"] = false).is_runtime_error(
		"Invalid assignment on read-only value (on base: 'Dictionary')."
	)
	assert_int(row.state_summary["turn"]).is_equal(1)
	assert_bool(row.unknown_fields["extra"]).is_true()


func test_sealed_nested_unknown_fields_deep_freeze() -> void:
	var candidate := CandidateDTO.new()
	candidate.candidate_id = "move"
	candidate.rank = 0
	candidate.aggregate_score = 1.0
	candidate.unknown_fields = {"nested": {"a": 1}}
	candidate.seal()
	await assert_error(func() -> void: candidate.unknown_fields["nested"]["a"] = 2).is_runtime_error(
		"Invalid assignment on read-only value (on base: 'Dictionary')."
	)
	assert_int(candidate.unknown_fields["nested"]["a"]).is_equal(1)

	var event := BattleEventDTO.new()
	event.protocol_index = 1
	event.type = "move"
	event.details = {"nested": {"b": 2}}
	event.seal()
	await assert_error(func() -> void: event.details["nested"]["b"] = 9).is_runtime_error(
		"Invalid assignment on read-only value (on base: 'Dictionary')."
	)
	assert_int(event.details["nested"]["b"]).is_equal(2)


func test_battle_variant_setter_decouples_shared_container() -> void:
	var shared := {"nested": {"b": 2}}
	var event := BattleEventDTO.new()
	event.protocol_index = 1
	event.type = "move"
	event.details = shared
	shared["nested"]["b"] = 9
	assert_int(event.details["nested"]["b"]).is_equal(2)
	assert_bool(is_same(event.details, shared)).is_false()


func test_sealed_nested_array_rejects_mutation() -> void:
	var bundle := BundleDTO.new()
	bundle.decisions = []
	var row := DecisionRowDTO.new()
	row.decision_index = 0
	row.turn_number = 1
	row.decision_phase = BundleMode.PHASE_REGULAR_TURN
	row.decision_latency_ms = 1.0
	row.observable_state_hash = "h1"
	row.request_hash = "h2"
	row.state_summary = {}
	row.normalized_action = {}
	row.actual_choose_string = "move 1"
	row.fallback_used = false
	row.warning_count = 0
	row.decision_valid = true
	bundle.decisions.append(row)
	bundle.seal()
	bundle.decisions.append(DecisionRowDTO.new())
	assert_int(bundle.decisions.size()).is_equal(1)


func test_declared_mode_differs_from_effective_mode() -> void:
	var bundle := BundleDTO.new()
	bundle.declared_mode = BundleMode.REPLAY_TRACE
	bundle.effective_mode = BundleMode.REPLAY_ONLY
	bundle.trace_trusted = false
	bundle.replay_trusted = true
	bundle.manifest = _make_manifest()
	bundle.warnings = []
	var downgrade := RefuseDiagnostic.new()
	downgrade.reason = "unsupported_trace_schema_version"
	downgrade.message = "trace version not trusted"
	downgrade.offender = "decisions.jsonl"
	bundle.downgrade_warnings = [downgrade]
	bundle.seal()
	assert_str(bundle.declared_mode).is_equal(BundleMode.REPLAY_TRACE)
	assert_str(bundle.effective_mode).is_equal(BundleMode.REPLAY_ONLY)
	assert_bool(bundle.trace_trusted).is_false()
	assert_bool(bundle.replay_trusted).is_true()
	assert_int(bundle.downgrade_warnings.size()).is_equal(1)


func test_exporter_warning_without_message() -> void:
	var warning := ExporterWarningDTO.new()
	warning.code = "missing_candidate_match"
	warning.decision_index = 3
	warning.seal()
	assert_str(warning.code).is_equal("missing_candidate_match")
	assert_int(warning.decision_index).is_equal(3)
	assert_object(warning.message).is_null()


func test_config_manifest_raw_dto() -> void:
	var raw := ConfigManifestRawDTO.new()
	raw.root = {"engine": {"name": "showdown"}, "nested": {"a": 1}}
	raw.seal()
	await assert_error(func() -> void: raw.root["engine"]["name"] = "mutated").is_runtime_error(
		"Invalid assignment on read-only value (on base: 'Dictionary')."
	)
	assert_str(raw.root["engine"]["name"]).is_equal("showdown")


func test_unknown_fields_preserved_on_dtos() -> void:
	var candidate := CandidateDTO.new()
	candidate.candidate_id = "c1"
	candidate.rank = 1
	candidate.aggregate_score = 0.5
	candidate.unknown_fields = {"future_key": "future_value"}
	candidate.seal()
	assert_str(candidate.unknown_fields["future_key"]).is_equal("future_value")


func test_validation_result_ok_shape() -> void:
	var bundle := BundleDTO.new()
	bundle.declared_mode = BundleMode.REPLAY_TRACE
	bundle.effective_mode = BundleMode.REPLAY_TRACE
	bundle.trace_trusted = true
	bundle.replay_trusted = true
	bundle.manifest = _make_manifest()
	bundle.warnings = []
	bundle.seal()

	var result := ValidationResult.new()
	result.ok = true
	result.diagnostic = null
	result.declared_mode = BundleMode.REPLAY_TRACE
	result.effective_mode = BundleMode.REPLAY_TRACE
	result.trace_trusted = true
	result.replay_trusted = true
	result.bundle = bundle
	result.downgrade_warnings = []
	result.seal()

	assert_bool(result.ok).is_true()
	assert_object(result.diagnostic).is_null()
	assert_object(result.bundle).is_not_null()
	assert_str(result.declared_mode).is_equal(BundleMode.REPLAY_TRACE)


func test_validation_result_refuse_shape_with_diagnostic() -> void:
	var diagnostic := RefuseDiagnostic.new()
	diagnostic.reason = "hash_mismatch"
	diagnostic.message = "sha256 mismatch for battle.jsonl"
	diagnostic.offender = "battle.jsonl"
	diagnostic.seal()

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

	assert_bool(result.ok).is_false()
	assert_object(result.diagnostic).is_not_null()
	assert_str(result.diagnostic.reason).is_equal("hash_mismatch")
	assert_str(result.diagnostic.message).contains("sha256")
	assert_object(result.bundle).is_null()


func test_published_dto_not_aliased_to_worker_buffer() -> void:
	var worker_summary := {"turn": 1, "side": "p1"}
	var row := DecisionRowDTO.new()
	row.decision_index = 0
	row.turn_number = 1
	row.decision_phase = BundleMode.PHASE_REGULAR_TURN
	row.decision_latency_ms = 1.0
	row.observable_state_hash = "h1"
	row.request_hash = "h2"
	row.state_summary = worker_summary.duplicate(true)
	row.normalized_action = {}
	row.actual_choose_string = "move 1"
	row.fallback_used = false
	row.warning_count = 0
	row.decision_valid = true
	row.seal()

	worker_summary["turn"] = 99
	assert_int(row.state_summary["turn"]).is_equal(1)
