extends GdUnitTestSuite

const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"
const _UNIT_FIXTURES := "res://tests/fixtures/unit"


func _fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_FIXTURES_ROOT.path_join(relative))


func _unit_fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_UNIT_FIXTURES.path_join(relative))


func _copy_dir_recursive(src: String, dst: String) -> void:
	DirAccess.make_dir_recursive_absolute(dst)
	var dir := DirAccess.open(src)
	assert_object(dir).is_not_null()
	dir.list_dir_begin()
	var name := dir.get_next()
	while name != "":
		if name == "." or name == "..":
			name = dir.get_next()
			continue
		var src_path := src.path_join(name)
		var dst_path := dst.path_join(name)
		if DirAccess.dir_exists_absolute(src_path):
			_copy_dir_recursive(src_path, dst_path)
		else:
			DirAccess.copy_absolute(src_path, dst_path)
		name = dir.get_next()
	dir.list_dir_end()


func _copy_fixture01_to_temp(suffix: String) -> String:
	var dst := OS.get_cache_dir().path_join("gdunit_bundle_%s_%d" % [suffix, Time.get_ticks_usec()])
	_copy_dir_recursive(_fixture_path("bundles/fixture-01"), dst)
	return dst


func _write_json(path: String, data: Variant) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	assert_object(file).is_not_null()
	file.store_string(JSON.stringify(data))


func _read_json(path: String) -> Variant:
	var json := JSON.new()
	assert_int(json.parse(FileAccess.get_file_as_string(path))).is_equal(OK)
	return json.data


func _assert_refuse(result: ValidationResult, expected_reason: String) -> void:
	assert_bool(result.ok).is_false()
	assert_object(result.diagnostic).is_not_null()
	assert_str(result.diagnostic.reason).is_equal(expected_reason)


func test_fixture01_trusted() -> void:
	var result: ValidationResult = BundleValidator.validate_dir(_fixture_path("bundles/fixture-01"))
	assert_bool(result.ok).is_true()
	assert_str(result.declared_mode).is_equal(BundleMode.REPLAY_TRACE)
	assert_str(result.effective_mode).is_equal(BundleMode.REPLAY_TRACE)
	assert_bool(result.trace_trusted).is_true()
	assert_bool(result.replay_trusted).is_true()
	assert_object(result.bundle).is_not_null()
	assert_int(result.bundle.decisions.size()).is_equal(3)
	assert_int(result.bundle.warnings.size()).is_equal(3)
	for warning in result.bundle.warnings:
		assert_object(warning.message).is_null()
	assert_int(result.bundle.battle_events.size()).is_greater(0)


func test_fixture04_replay_only() -> void:
	var result: ValidationResult = BundleValidator.validate_dir(_fixture_path("bundles/fixture-04"))
	assert_bool(result.ok).is_true()
	assert_str(result.declared_mode).is_equal(BundleMode.REPLAY_ONLY)
	assert_str(result.effective_mode).is_equal(BundleMode.REPLAY_ONLY)
	assert_bool(result.trace_trusted).is_false()
	assert_bool(result.replay_trusted).is_true()
	assert_int(result.bundle.decisions.size()).is_equal(0)


func test_fixture05_trace_only() -> void:
	var result: ValidationResult = BundleValidator.validate_dir(_fixture_path("bundles/fixture-05"))
	assert_bool(result.ok).is_true()
	assert_str(result.declared_mode).is_equal(BundleMode.TRACE_ONLY)
	assert_str(result.effective_mode).is_equal(BundleMode.TRACE_ONLY)
	assert_bool(result.trace_trusted).is_true()
	assert_bool(result.replay_trusted).is_false()
	assert_int(result.bundle.battle_events.size()).is_equal(0)


func test_fixture06_hash_mismatch() -> void:
	var result: ValidationResult = BundleValidator.validate_dir(_fixture_path("sources/fixture-06/bundle"))
	_assert_refuse(result, "hash_mismatch")


func test_refuse_string_boolean_present() -> void:
	var bundle_dir := _copy_fixture01_to_temp("string_bool")
	var manifest: Dictionary = _read_json(bundle_dir.path_join("manifest.json"))
	manifest["files"]["battle_log"]["present"] = "true"
	manifest["files"]["battle_log"]["required"] = "true"
	_write_json(bundle_dir.path_join("manifest.json"), manifest)
	_assert_refuse(BundleValidator.validate_dir(bundle_dir), "malformed_type")


func test_refuse_extra_files_key() -> void:
	var result: ValidationResult = BundleValidator.validate_dir(_unit_fixture_path("refuse-extra-files-key"))
	_assert_refuse(result, "unknown_logical_key")


func test_refuse_noncanonical_path() -> void:
	var result: ValidationResult = BundleValidator.validate_dir(_unit_fixture_path("refuse-noncanonical-path"))
	_assert_refuse(result, "noncanonical_path")


func test_refuse_duplicate_path() -> void:
	var result: ValidationResult = BundleValidator.validate_dir(_unit_fixture_path("refuse-duplicate-path"))
	var reason: String = result.diagnostic.reason
	assert_bool(reason == "duplicate_path" or reason == "noncanonical_path").is_true()


func test_refuse_subdirectory() -> void:
	var bundle_dir := _copy_fixture01_to_temp("subdir")
	DirAccess.make_dir_absolute(bundle_dir.path_join("nested"))
	var result: ValidationResult = BundleValidator.validate_dir(bundle_dir)
	_assert_refuse(result, "undeclared_subdirectory")


func test_refuse_symlink_or_junction_payload(
	do_skip := OS.get_name() != "Windows",
	skip_reason := "Plan F: symlink creation requires Windows"
) -> void:
	var bundle_dir := _copy_fixture01_to_temp("symlink")
	var target_dir := bundle_dir.path_join("_link_target")
	DirAccess.make_dir_absolute(target_dir)
	DirAccess.remove_absolute(bundle_dir.path_join("battle.jsonl"))
	var output: Array = []
	var exit_code := OS.execute(
		"cmd.exe",
		["/c", "mklink", bundle_dir.path_join("battle.jsonl"), target_dir],
		output,
		true,
		false
	)
	if exit_code != 0:
		# Plan F: re-run with elevation when mklink requires privilege.
		return
	var result: ValidationResult = BundleValidator.validate_dir(bundle_dir)
	_assert_refuse(result, "symlink_or_reparse_refused")


func test_junction_named_battle_jsonl_is_reparse_not_subdir(
	do_skip := OS.get_name() != "Windows",
	skip_reason := "Plan F: junction creation requires Windows"
) -> void:
	var bundle_dir := _copy_fixture01_to_temp("junction")
	var target_dir := bundle_dir.path_join("_junction_target")
	DirAccess.make_dir_absolute(target_dir)
	DirAccess.remove_absolute(bundle_dir.path_join("battle.jsonl"))
	var output: Array = []
	var exit_code := OS.execute(
		"cmd.exe",
		["/c", "mklink", "/J", bundle_dir.path_join("battle.jsonl"), target_dir],
		output,
		true,
		false
	)
	if exit_code != 0:
		# Plan F: re-run with elevation when mklink /J requires privilege.
		return
	var result: ValidationResult = BundleValidator.validate_dir(bundle_dir)
	_assert_refuse(result, "symlink_or_reparse_refused")
	assert_str(result.diagnostic.reason).is_not_equal("undeclared_subdirectory")


func test_unsupported_trace_downgrades_effective_mode() -> void:
	var result: ValidationResult = BundleValidator.validate_dir(_unit_fixture_path("unsupported-trace-downgrade"))
	assert_bool(result.ok).is_true()
	assert_str(result.declared_mode).is_equal(BundleMode.REPLAY_TRACE)
	assert_str(result.effective_mode).is_equal(BundleMode.REPLAY_ONLY)
	assert_bool(result.trace_trusted).is_false()
	assert_bool(result.replay_trusted).is_true()
	assert_int(result.downgrade_warnings.size()).is_equal(1)
	assert_str(result.downgrade_warnings[0].reason).is_equal("unsupported_trace_schema_version")


func test_unsupported_trace_without_replay_refuses() -> void:
	var result: ValidationResult = BundleValidator.validate_dir(_unit_fixture_path("unsupported-trace-no-replay"))
	_assert_refuse(result, "unsupported_trace_schema_version")


func test_refuse_duplicate_decision_index() -> void:
	var result: ValidationResult = BundleValidator.validate_dir(_unit_fixture_path("refuse-duplicate-decision-index"))
	_assert_refuse(result, "duplicate_decision_index")


func test_refuse_jsonl_parse_error() -> void:
	var result: ValidationResult = BundleValidator.validate_dir(_unit_fixture_path("refuse-jsonl-parse-error"))
	_assert_refuse(result, "jsonl_parse_error")


func test_refuse_non_integral_decision_index() -> void:
	var result: ValidationResult = BundleValidator.validate_dir(_unit_fixture_path("refuse-non-integral-decision-index"))
	_assert_refuse(result, "malformed_integer")


func test_refuse_malformed_warning_object() -> void:
	var result: ValidationResult = BundleValidator.validate_dir(_unit_fixture_path("refuse-malformed-warning"))
	_assert_refuse(result, "malformed_warning")


func test_chosen_key_missing_marks_invalid() -> void:
	var result: ValidationResult = BundleValidator.validate_dir(_unit_fixture_path("chosen-key-missing-invalid"))
	assert_bool(result.ok).is_true()
	var found_invalid := false
	for row in result.bundle.decisions:
		if row is DecisionRowDTO and not row.decision_valid:
			found_invalid = true
	assert_bool(found_invalid).is_true()


func test_unknown_optional_preserved() -> void:
	var result: ValidationResult = BundleValidator.validate_dir(_unit_fixture_path("unknown-optional-preserved"))
	assert_bool(result.ok).is_true()
	assert_int(result.bundle.decisions.size()).is_greater(0)
	var row: DecisionRowDTO = result.bundle.decisions[0]
	assert_bool(row.unknown_fields.has("future_trace_field")).is_true()


func test_decision_rows_do_not_require_battle_id_or_our_side() -> void:
	var result: ValidationResult = BundleValidator.validate_dir(_fixture_path("bundles/fixture-01"))
	assert_bool(result.ok).is_true()
	assert_int(result.bundle.decisions.size()).is_equal(3)
	for row in result.bundle.decisions:
		assert_that(row).is_instanceof(DecisionRowDTO)
