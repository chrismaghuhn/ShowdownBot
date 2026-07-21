extends GdUnitTestSuite

const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"


func _fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_FIXTURES_ROOT.path_join(relative))


func _fixture_bundle(rel: String) -> BundleDTO:
	var path := _fixture_path(rel)
	var result: ValidationResult = BundleValidator.validate_dir(path)
	assert_object(result.bundle).is_not_null()
	return result.bundle


func test_parse_ok() -> void:
	var r := DecisionDeepLink.parse_arg("synthetic00000001:1")
	assert_bool(r.ok).is_true()
	assert_str(r.battle_id).is_equal("synthetic00000001")
	assert_int(r.decision_index).is_equal(1)


func test_parse_rejects_bare_int() -> void:
	var r := DecisionDeepLink.parse_arg("2")
	assert_bool(r.ok).is_false()
	assert_str(r.reason).is_equal("malformed_decision_arg")


func test_parse_rejects_empty_string() -> void:
	var r := DecisionDeepLink.parse_arg("")
	assert_bool(r.ok).is_false()
	assert_str(r.reason).is_equal("malformed_decision_arg")


func test_parse_rejects_missing_colon() -> void:
	var r := DecisionDeepLink.parse_arg("abc")
	assert_bool(r.ok).is_false()
	assert_str(r.reason).is_equal("malformed_decision_arg")


func test_parse_splits_at_last_colon() -> void:
	# B4: battle_id may contain colons; split on the last separator only.
	var r := DecisionDeepLink.parse_arg("a:b:3")
	assert_bool(r.ok).is_true()
	assert_str(r.battle_id).is_equal("a:b")
	assert_int(r.decision_index).is_equal(3)


func test_resolve_success_fixture01() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var target: DecisionRowDTO = bundle.decisions[1]
	var applied := DecisionDeepLink.resolve(
		bundle, bundle.manifest.battle_id, target.decision_index
	)
	assert_bool(applied.ok).is_true()
	assert_int(applied.decision_row_index).is_equal(1)


func test_resolve_battle_id_mismatch() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var applied := DecisionDeepLink.resolve(bundle, "wrong-battle", 1)
	assert_bool(applied.ok).is_false()
	assert_str(applied.reason).is_equal("battle_id_mismatch")


func test_resolve_missing_index() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var applied := DecisionDeepLink.resolve(bundle, bundle.manifest.battle_id, 999999)
	assert_bool(applied.ok).is_false()
	assert_str(applied.reason).is_equal("decision_index_not_found")


func test_resolve_trace_not_trusted() -> void:
	var bundle := _fixture_bundle("bundles/fixture-04")
	var applied := DecisionDeepLink.resolve(bundle, bundle.manifest.battle_id, 0)
	assert_bool(applied.ok).is_false()
	assert_str(applied.reason).is_equal("trace_not_trusted")
