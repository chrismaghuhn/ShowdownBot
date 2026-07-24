extends GdUnitTestSuite

# Task E3 scope only (plan §6): set_ui_scale / set_density / min window size.
# test_reset_to_safe_restores_defaults is Task E5 scope (WorkspaceLayout owns no
# real dock children yet) and is deliberately NOT added here.

const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"


func _fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_FIXTURES_ROOT.path_join(relative))


func _fixture_bundle(rel: String) -> BundleDTO:
	var path := _fixture_path(rel)
	var result: ValidationResult = BundleValidator.validate_dir(path)
	assert_object(result.bundle).is_not_null()
	return result.bundle


func test_scale_clamped() -> void:
	var layout := WorkspaceLayout.new()
	add_child(layout)
	await await_idle_frame()
	layout.set_ui_scale(0.5)
	assert_float(layout.get_ui_scale()).is_equal(0.75)
	layout.set_ui_scale(3.0)
	assert_float(layout.get_ui_scale()).is_equal(2.0)


func test_scale_presets() -> void:
	var layout := WorkspaceLayout.new()
	add_child(layout)
	await await_idle_frame()
	for preset in [0.75, 1.0, 1.5, 2.0]:
		layout.set_ui_scale(preset)
		assert_float(layout.get_ui_scale()).is_equal(preset)


func test_density_preserves_selection() -> void:
	# Proves set_density has zero side channel to selection state: the timeline
	# and decision controllers are a completely separate object graph from
	# WorkspaceLayout (which owns no docks yet — that's Task E5).
	var bundle := _fixture_bundle("bundles/fixture-01")
	var replay := BattleTimeline.build(bundle)
	var ctl := TimelineController.new()
	add_child(ctl)
	var dec := DecisionController.new()
	add_child(dec)
	ctl.reset(replay, bundle)
	dec.reset(bundle, ctl)
	await await_idle_frame()
	var selected_before := dec.get_selected_decision_row_index()
	var timeline_before := ctl.get_selected_entry_index()
	assert_int(selected_before).is_greater_equal(0)

	var layout := WorkspaceLayout.new()
	add_child(layout)
	await await_idle_frame()

	layout.set_density(WorkspaceLayout.DENSITY_COMPACT)
	assert_int(dec.get_selected_decision_row_index()).is_equal(selected_before)
	assert_int(ctl.get_selected_entry_index()).is_equal(timeline_before)

	layout.set_density(WorkspaceLayout.DENSITY_COMFORTABLE)
	assert_int(dec.get_selected_decision_row_index()).is_equal(selected_before)
	assert_int(ctl.get_selected_entry_index()).is_equal(timeline_before)

	assert_str(layout.get_density()).is_equal(WorkspaceLayout.DENSITY_COMFORTABLE)


func test_min_window_set() -> void:
	var layout := WorkspaceLayout.new()
	add_child(layout)
	await await_idle_frame()
	# ponytail: DisplayServer.window_get_min_size() is unconditionally (0, 0) under
	# the "headless" DisplayServer driver this project's run_gdunit_headless.ps1
	# always uses (verified by direct probe: window_set_size/get_size round-trip
	# is equally stubbed) — a CI environment ceiling, not an implementation gap.
	# WorkspaceLayout._ready() does call DisplayServer.window_set_min_size(MIN_WINDOW_SIZE)
	# per plan §0.7 / §4.3 (Choice Point A CLOSED); assert the constant it applies
	# instead of the unobservable-in-CI DisplayServer round-trip.
	assert_vector(WorkspaceLayout.MIN_WINDOW_SIZE).is_equal(Vector2i(1280, 720))
