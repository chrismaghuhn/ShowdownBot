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
	file.close()


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


func _mark_skip(reason: String) -> void:
	for child in get_children():
		if child.has_method("do_skip") and child.has_method("test_name"):
			if String(child.test_name()) == __active_test_case:
				child.do_skip(true, reason)
				return


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
		_mark_skip("Plan F: mklink requires privilege — re-run elevated")
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
		_mark_skip("Plan F: mklink /J requires privilege — re-run elevated")
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


func test_refuse_non_object_manifest() -> void:
	var bundle_dir := _copy_fixture01_to_temp("manifest_array")
	_write_json(bundle_dir.path_join("manifest.json"), [])
	_assert_refuse(BundleValidator.validate_dir(bundle_dir), "malformed_type")


func test_refuse_bad_privacy_profile() -> void:
	var bundle_dir := _copy_fixture01_to_temp("bad_privacy")
	var manifest: Dictionary = _read_json(bundle_dir.path_join("manifest.json"))
	manifest["privacy"]["profile"] = "not-a-profile"
	_write_json(bundle_dir.path_join("manifest.json"), manifest)
	_assert_refuse(BundleValidator.validate_dir(bundle_dir), "malformed_type")


func test_refuse_raw_source_included_true() -> void:
	var bundle_dir := _copy_fixture01_to_temp("raw_source")
	var manifest: Dictionary = _read_json(bundle_dir.path_join("manifest.json"))
	manifest["privacy"]["raw_source_included"] = true
	_write_json(bundle_dir.path_join("manifest.json"), manifest)
	_assert_refuse(BundleValidator.validate_dir(bundle_dir), "malformed_type")


func test_refuse_dirty_wrong_type() -> void:
	var bundle_dir := _copy_fixture01_to_temp("dirty_type")
	var manifest: Dictionary = _read_json(bundle_dir.path_join("manifest.json"))
	manifest["source_provenance"]["dirty"] = "yes"
	_write_json(bundle_dir.path_join("manifest.json"), manifest)
	_assert_refuse(BundleValidator.validate_dir(bundle_dir), "malformed_type")


func test_refuse_null_source_hash_when_present() -> void:
	var bundle_dir := _copy_fixture01_to_temp("null_source_hash")
	var manifest_path := bundle_dir.path_join("manifest.json")
	var text := FileAccess.get_file_as_string(manifest_path)
	var re := RegEx.new()
	re.compile('("source_hashes"\\s*:\\s*\\{\\s*"battle_log"\\s*:\\s*)"[0-9a-f]+"')
	var replaced := re.sub(text, "$1null", false)
	assert_str(replaced).is_not_equal(text)
	var file := FileAccess.open(manifest_path, FileAccess.WRITE)
	file.store_string(replaced)
	file.close()
	_assert_refuse(BundleValidator.validate_dir(bundle_dir), "nullability")


func test_refuse_non_object_config_manifest() -> void:
	var bundle_dir := _copy_fixture01_to_temp("config_array")
	var config_path := bundle_dir.path_join("config-manifest.json")
	var file := FileAccess.open(config_path, FileAccess.WRITE)
	file.store_string("[]")
	file.close()
	_rehash_payload(bundle_dir, "config_manifest", config_path)
	_assert_refuse(BundleValidator.validate_dir(bundle_dir), "malformed_type")


func test_refuse_fractional_pokemon_slot() -> void:
	var bundle_dir := _copy_fixture01_to_temp("frac_slot")
	var battle_path := bundle_dir.path_join("battle.jsonl")
	# Explicit numeric fractional slot (Showdown letter slots remain strings).
	var out := FileAccess.open(battle_path, FileAccess.WRITE)
	out.store_string(
		'{"protocol_index":1,"type":"switch","pokemon":{"side":"p1","slot":1.5,"species":"Pikachu"}}\n'
	)
	out.close()
	_rehash_payload(bundle_dir, "battle_log", battle_path)
	_assert_refuse(BundleValidator.validate_dir(bundle_dir), "malformed_integer")


func test_refuse_numeric_hp_fainted() -> void:
	var bundle_dir := _copy_fixture01_to_temp("hp_fainted_num")
	var battle_path := bundle_dir.path_join("battle.jsonl")
	var lines: PackedStringArray = FileAccess.get_file_as_string(battle_path).split("\n")
	var rewritten: PackedStringArray = PackedStringArray()
	var mutated := false
	for line in lines:
		var trimmed := line.strip_edges()
		if trimmed.is_empty():
			continue
		var json := JSON.new()
		assert_int(json.parse(trimmed)).is_equal(OK)
		var row: Dictionary = json.data
		if not mutated and row.has("hp") and typeof(row["hp"]) == TYPE_DICTIONARY:
			row["hp"]["fainted"] = 1
			mutated = true
		rewritten.append(JSON.stringify(row))
	assert_bool(mutated).is_true()
	var out := FileAccess.open(battle_path, FileAccess.WRITE)
	out.store_string("\n".join(rewritten) + "\n")
	out.close()
	_rehash_payload(bundle_dir, "battle_log", battle_path)
	_assert_refuse(BundleValidator.validate_dir(bundle_dir), "malformed_type")


func _rehash_payload(bundle_dir: String, logical_key: String, file_path: String) -> void:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(FileAccess.get_file_as_bytes(file_path))
	var digest := ctx.finish().hex_encode()
	var manifest: Dictionary = _read_json(bundle_dir.path_join("manifest.json"))
	manifest["files"][logical_key]["sha256"] = digest
	_write_json(bundle_dir.path_join("manifest.json"), manifest)


func test_refuse_empty_candidates_with_chosen_tera_slot() -> void:
	var bundle_dir := _copy_fixture01_to_temp("chosen_tera_empty")
	var decisions_path := bundle_dir.path_join("decisions.jsonl")
	var lines: PackedStringArray = FileAccess.get_file_as_string(decisions_path).split("\n")
	var rewritten: PackedStringArray = PackedStringArray()
	var mutated := false
	for line in lines:
		var trimmed := line.strip_edges()
		if trimmed.is_empty():
			continue
		var json := JSON.new()
		assert_int(json.parse(trimmed)).is_equal(OK)
		var row: Dictionary = json.data
		if not mutated:
			row["candidates"] = []
			row["chosen_candidate_key"] = null
			row["chosen_candidate_id"] = null
			row["chosen_rank"] = null
			row["chosen_tera_slot"] = 1
			row["chosen_mega_slot"] = null
			mutated = true
		rewritten.append(JSON.stringify(row))
	assert_bool(mutated).is_true()
	var out := FileAccess.open(decisions_path, FileAccess.WRITE)
	out.store_string("\n".join(rewritten) + "\n")
	out.close()
	_rehash_payload(bundle_dir, "decision_trace", decisions_path)
	_assert_refuse(BundleValidator.validate_dir(bundle_dir), "chosen_integrity")
