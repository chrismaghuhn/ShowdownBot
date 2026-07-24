extends GdUnitTestSuite

## Plan E §5.3 — DiagnosticsDock.
## All 4 named §5.3 cases. `test_hash_surfaces_use_monospace` is Task E6 scope
## (plan §6 Task E6 owns the monospace RED/GREEN + StudioMonoFont helper).

const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"
const _DOCK_SCENE := preload("res://src/diagnostics/diagnostics_dock.tscn")

## §0.9 hash-like provenance fields — must render monospace (§4.6 Auflage).
const _HASH_LABELS := [
	"git_sha", "config_hash", "source_hashes_battle_log", "source_hashes_decision_trace"
]


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


func _assert_control_is_monospace(control: Control) -> void:
	assert_bool(control.has_theme_font_override(&"font")).is_true()
	var font := control.get_theme_font(&"font")
	assert_bool(font is SystemFont).is_true()
	assert_bool("monospace" in (font as SystemFont).font_names).is_true()


func test_hash_surfaces_use_monospace() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var dock := _spawn_dock()
	await await_idle_frame()
	dock.bind_bundle(bundle)

	var checked_hash_row := false
	for i in range(dock.get_provenance_row_count()):
		var label := dock.get_provenance_label_at(i).trim_suffix(":")
		if label in _HASH_LABELS:
			checked_hash_row = true
			_assert_control_is_monospace(dock.get_provenance_value_control_at(i))
	assert_bool(checked_hash_row).is_true()

	_assert_control_is_monospace(dock.get_raw_control())
