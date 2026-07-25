extends GdUnitTestSuite

# Task E3: set_ui_scale / set_density / min window size (bare WorkspaceLayout.new(),
# no real docks needed). Task E5 adds test_reset_to_safe_restores_defaults, which
# needs the real split/dock scaffold — it spawns workspace_layout.tscn instead.

const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"
const _LAYOUT_SCENE := preload("res://src/workspace/workspace_layout.tscn")


func _fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_FIXTURES_ROOT.path_join(relative))


func _spawn_layout_scene() -> WorkspaceLayout:
	var layout: WorkspaceLayout = _LAYOUT_SCENE.instantiate()
	add_child(layout)
	# 2026-07-25: WorkspaceLayout no longer applies its own runtime theme to
	# itself (AppShell does, at the shell root, so chrome scales too — see
	# app_shell.gd:_ready()). Standalone-scene tests here exercise the scale/
	# density mechanism in isolation, so replicate that one line of wiring
	# rather than dragging in the whole AppShell scene.
	layout.theme = layout.get_runtime_theme()
	return layout


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


func test_scale_produces_observable_control_size_change() -> void:
	# Not a setter/getter round-trip: measures a real laid-out control (the
	# transport PlayButton, owned by WorkspaceLayout's ReplayWorkspace dock)
	# whose theme-resolved font size and min-size-driven Control.size must
	# actually differ between 100% and 150% once layout settles.
	var layout := _spawn_layout_scene()
	await await_idle_frame()
	var play_button: Button = layout.get_node(
		"MainSplit/ReplayWorkspace/Timeline/Controls/PlayButton"
	)

	layout.set_ui_scale(1.0)
	await await_idle_frame()
	await await_idle_frame()
	var font_size_100 := play_button.get_theme_font_size(&"font_size")
	var size_100 := play_button.size

	layout.set_ui_scale(1.5)
	await await_idle_frame()
	await await_idle_frame()
	var font_size_150 := play_button.get_theme_font_size(&"font_size")
	var size_150 := play_button.size

	assert_int(font_size_150).is_greater(font_size_100)
	assert_float(size_150.x).is_greater(size_100.x)
	assert_float(size_150.y).is_greater(size_100.y)


func test_density_produces_observable_separation_change() -> void:
	# Not a tautology: measures the theme-resolved "separation" constant on a
	# real container WorkspaceLayout owns (the transport HBoxContainer), which
	# must differ between compact and comfortable once layout settles.
	var layout := _spawn_layout_scene()
	await await_idle_frame()
	var controls_row: HBoxContainer = layout.get_node(
		"MainSplit/ReplayWorkspace/Timeline/Controls"
	)

	layout.set_density(WorkspaceLayout.DENSITY_COMFORTABLE)
	await await_idle_frame()
	var sep_comfortable := controls_row.get_theme_constant(&"separation")

	layout.set_density(WorkspaceLayout.DENSITY_COMPACT)
	await await_idle_frame()
	var sep_compact := controls_row.get_theme_constant(&"separation")

	assert_int(sep_compact).is_less(sep_comfortable)


func test_density_preserves_information_and_row_counts() -> void:
	# §0.8: "same information + same selection; only spacing/font metrics
	# change." Drives the real docks WorkspaceLayout owns (candidate table +
	# diagnostics provenance) with a loaded fixture and asserts row counts and
	# selection are byte-for-byte identical across a density flip — compact
	# must not hide/remove/reorder anything.
	var layout := _spawn_layout_scene()
	await await_idle_frame()
	var bundle := _fixture_bundle("bundles/fixture-01")
	var replay := BattleTimeline.build(bundle)

	var replay_ws: ReplayWorkspace = layout.get_node("MainSplit/ReplayWorkspace")
	replay_ws.reset(replay, bundle)
	var decision_ws: DecisionWorkspace = layout.get_node(
		"MainSplit/RightSplit/DecisionWorkspace"
	)
	decision_ws.reset(bundle, replay_ws.get_timeline_controller())
	var diagnostics := layout.get_diagnostics_dock()
	diagnostics.bind_bundle(bundle)
	await await_idle_frame()

	var dec := decision_ws.get_decision_controller()
	var table := decision_ws.get_candidate_table_view()
	# fixture-01 decision_index=0 (default selection, team_preview) has zero
	# candidates; decision_index=2 (regular_turn) has 2 — select it so
	# candidate_rows_before is actually non-zero and the row-count assertion
	# below is meaningful.
	for i in range(bundle.decisions.size()):
		var row: DecisionRowDTO = bundle.decisions[i]
		if row.decision_index == 2:
			dec.select_decision_row(i)
			break
	await await_idle_frame()
	var selected_before := dec.get_selected_decision_row_index()
	var timeline_before := replay_ws.get_timeline_controller().get_selected_entry_index()
	var candidate_rows_before := table.get_item_count()
	var provenance_rows_before := diagnostics.get_provenance_row_count()
	assert_int(candidate_rows_before).is_greater(0)
	assert_int(provenance_rows_before).is_greater(0)

	layout.set_density(WorkspaceLayout.DENSITY_COMPACT)
	await await_idle_frame()

	assert_int(dec.get_selected_decision_row_index()).is_equal(selected_before)
	assert_int(
		replay_ws.get_timeline_controller().get_selected_entry_index()
	).is_equal(timeline_before)
	assert_int(table.get_item_count()).is_equal(candidate_rows_before)
	assert_int(diagnostics.get_provenance_row_count()).is_equal(provenance_rows_before)

	layout.set_density(WorkspaceLayout.DENSITY_COMFORTABLE)
	await await_idle_frame()
	assert_int(table.get_item_count()).is_equal(candidate_rows_before)
	assert_int(diagnostics.get_provenance_row_count()).is_equal(provenance_rows_before)


func test_reset_to_safe_restores_defaults() -> void:
	var layout := _spawn_layout_scene()
	await await_idle_frame()
	var main_split: SplitContainer = layout.get_node("MainSplit")
	var right_split: SplitContainer = layout.get_node("MainSplit/RightSplit")
	var diagnostics := layout.get_diagnostics_dock()
	assert_object(diagnostics).is_not_null()
	var play_button: Button = layout.get_node(
		"MainSplit/ReplayWorkspace/Timeline/Controls/PlayButton"
	)
	var controls_row: HBoxContainer = layout.get_node(
		"MainSplit/ReplayWorkspace/Timeline/Controls"
	)
	await await_idle_frame()
	var baseline_font_size := play_button.get_theme_font_size(&"font_size")
	var baseline_separation := controls_row.get_theme_constant(&"separation")

	# Drive away from defaults: scale, density, split ratios, collapse, visibility.
	layout.set_ui_scale(1.5)
	layout.set_density(WorkspaceLayout.DENSITY_COMPACT)
	main_split.split_offset = 222
	main_split.collapsed = true
	right_split.split_offset = 111
	right_split.collapsed = true
	diagnostics.visible = false
	await await_idle_frame()
	# Custom state must actually differ before reset — otherwise the reset
	# assertions below would pass vacuously even against the old no-op.
	assert_int(play_button.get_theme_font_size(&"font_size")).is_not_equal(baseline_font_size)
	assert_int(controls_row.get_theme_constant(&"separation")).is_not_equal(baseline_separation)

	layout.reset_to_safe()
	await await_idle_frame()
	await await_idle_frame()

	assert_float(layout.get_ui_scale()).is_equal(1.0)
	assert_str(layout.get_density()).is_equal(WorkspaceLayout.DENSITY_COMFORTABLE)
	assert_int(main_split.split_offset).is_equal(0)
	assert_bool(main_split.collapsed).is_false()
	assert_int(right_split.split_offset).is_equal(0)
	assert_bool(right_split.collapsed).is_false()
	assert_bool(diagnostics.visible).is_true()
	# Real effect, not just the stored getters: font size and separation must
	# actually be back at their pre-custom values.
	assert_int(play_button.get_theme_font_size(&"font_size")).is_equal(baseline_font_size)
	assert_int(controls_row.get_theme_constant(&"separation")).is_equal(baseline_separation)


func test_min_window_set() -> void:
	var layout := WorkspaceLayout.new()
	add_child(layout)
	await await_idle_frame()
	# ponytail: DisplayServer.window_get_min_size() is unconditionally (0, 0) under
	# the "headless" DisplayServer driver this project's run_gdunit_headless.ps1
	# always uses (verified by direct probe: window_set_size/get_size round-trip
	# is equally stubbed) — a CI environment ceiling, not an implementation gap.
	# 2026-07-25: DisplayServer.window_set_min_size is now called by
	# AppShell._update_min_window_size() (computed from the real tree, §0.13
	# Choice Point A amendment), not unconditionally from WorkspaceLayout._ready()
	# — see test_app_shell_plan_e.gd's test_compute_min_window_size_* suite for
	# that behavior. This test only pins the floor constant it must never go
	# below, which is still unobservable-in-CI as a DisplayServer round-trip.
	assert_vector(WorkspaceLayout.MIN_WINDOW_SIZE).is_equal(Vector2i(1280, 720))


func test_layout_combined_minimum_size_grows_with_scale() -> void:
	# The propagation fix itself: before WorkspaceLayout became a real
	# Container, this returned ~Vector2.ZERO regardless of scale (a bare
	# Control never aggregates its children's minimum size) — see
	# workspace_layout.gd class comment / the 2026-07-25 commit.
	var layout := _spawn_layout_scene()
	await await_idle_frame()
	await await_idle_frame()

	layout.set_ui_scale(1.0)
	await await_idle_frame()
	await await_idle_frame()
	var min_100 := layout.get_combined_minimum_size()

	layout.set_ui_scale(1.5)
	await await_idle_frame()
	await await_idle_frame()
	var min_150 := layout.get_combined_minimum_size()

	assert_float(min_150.x).is_greater(min_100.x)
	assert_float(min_150.y).is_greater(min_100.y)
