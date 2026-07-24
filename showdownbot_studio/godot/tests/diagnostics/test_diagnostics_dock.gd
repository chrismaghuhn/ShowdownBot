extends GdUnitTestSuite

## Plan E §5.3 — DiagnosticsDock.
## Task E2 scope only: 3 of the 4 named §5.3 cases. `test_hash_surfaces_use_monospace`
## and `StudioMonoFont` are Task E6 scope (plan §6 Task E2 GREEN line lists
## ProvenancePresenter / DiagnosticsPresenter / DiagnosticsDock only; Task E6 owns the
## monospace RED/GREEN + helper) and are deliberately NOT part of this branch.

const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"
const _DOCK_SCENE := preload("res://src/diagnostics/diagnostics_dock.tscn")


func _fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_FIXTURES_ROOT.path_join(relative))


func _fixture_bundle(rel: String) -> BundleDTO:
	var path := _fixture_path(rel)
	var result: ValidationResult = BundleValidator.validate_dir(path)
	assert_object(result.bundle).is_not_null()
	return result.bundle


func _spawn_dock() -> DiagnosticsDock:
	var dock: DiagnosticsDock = _DOCK_SCENE.instantiate()
	add_child(dock)
	return dock


func test_raw_tab_bounded() -> void:
	var dock := _spawn_dock()
	await await_idle_frame()

	var huge := "x".repeat(500000)
	dock.bind_raw_text(huge)
	var raw := dock.get_raw_text()

	assert_int(raw.length()).is_less(huge.length())
	assert_str(raw).ends_with(DiagnosticsDock.TRUNCATION_MARKER)
	# No per-line Control proliferation for a huge blob: rendered by a single TextEdit.
	assert_bool(dock.get_raw_control() is TextEdit).is_true()


func test_warnings_show_text_and_icon() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var dock := _spawn_dock()
	await await_idle_frame()
	dock.bind_bundle(bundle)

	# fixture-01/warnings.json ships 3 aggregation_mode_not_recorded exporter warnings.
	assert_int(dock.get_warning_row_count()).is_greater(0)
	for i in range(dock.get_warning_row_count()):
		assert_str(dock.get_warning_text_at(i)).is_not_empty()
		var icon := dock.get_warning_icon_control_at(i)
		assert_object(icon).is_not_null()
		assert_bool(icon.visible).is_true()


func test_no_filesystem_paths_in_raw() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var dock := _spawn_dock()
	await await_idle_frame()
	dock.bind_bundle(bundle)

	var raw := dock.get_raw_text()
	assert_str(raw).not_contains(_fixture_path("bundles/fixture-01"))
