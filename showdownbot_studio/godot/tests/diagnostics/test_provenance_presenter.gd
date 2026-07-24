extends GdUnitTestSuite

## Plan E §5.2 — ProvenancePresenter (Task E2 scope only; see plan §4.2 / §0.9).

const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"


func _fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_FIXTURES_ROOT.path_join(relative))


func _fixture_bundle(rel: String) -> BundleDTO:
	var path := _fixture_path(rel)
	var result: ValidationResult = BundleValidator.validate_dir(path)
	assert_object(result.bundle).is_not_null()
	return result.bundle


func _row_value(rows: Array, label: String) -> Variant:
	for row in rows:
		if row.label == label:
			return row.value
	return null


func test_fixture01_shows_battle_id_and_hashes() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var rows := ProvenancePresenter.present(bundle)

	var battle_id: Variant = _row_value(rows, "battle_id")
	assert_str(battle_id).is_not_null()
	assert_str(battle_id).is_equal(bundle.manifest.battle_id)

	var config_hash: Variant = _row_value(rows, "config_hash")
	assert_str(config_hash).is_not_null()
	assert_bool(
		config_hash == bundle.manifest.config_hash
		or config_hash == DecisionPresenter.NOT_RECORDED
	).is_true()


func test_dirty_tri_state_null() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	# fixture-01 manifest.json ships source_provenance.dirty == null.
	assert_object(bundle.manifest.source_provenance.dirty).is_null()

	var rows := ProvenancePresenter.present(bundle)
	var dirty_value: Variant = _row_value(rows, "dirty")
	assert_str(dirty_value).is_equal("dirty state not recorded")
	assert_str(dirty_value).is_not_equal("dirty: false")
	assert_str(dirty_value).is_not_equal("clean")


func test_exporter_version_shown() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var rows := ProvenancePresenter.present(bundle)
	var exporter_version: Variant = _row_value(rows, "exporter_version")
	assert_str(exporter_version).is_not_null()
	assert_str(exporter_version).is_equal(bundle.manifest.exporter_version)
