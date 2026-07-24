extends GdUnitTestSuite

## Plan E §5.6 — AppShell integration: banner correctness across fixtures,
## deep-link literal, keyboard-only smoke. Reuses the shared fixture/shell
## helpers established by the other test_app_shell_*.gd suites (§5 "do not
## invent a new loader") rather than a fresh one.

const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"
const _APP_SHELL_SCENE := preload("res://src/workspace/app_shell.tscn")


func _fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_FIXTURES_ROOT.path_join(relative))


func after_test() -> void:
	for child in get_children():
		if child is AppShell:
			remove_child(child)
			child.free()


func _spawn_shell() -> AppShell:
	var shell: AppShell = _APP_SHELL_SCENE.instantiate()
	add_child(shell)
	return shell


func _spawn_shell_ready() -> AppShell:
	var shell := _spawn_shell()
	await await_idle_frame()
	return shell


func _await_shell_settled(shell: AppShell, max_frames: int = 600) -> void:
	var frames := 0
	while shell.is_loading() and frames < max_frames:
		await await_idle_frame()
		frames += 1
	assert_bool(shell.is_loading()).is_false()


func _row_index_by_decision_index(bundle: BundleDTO, decision_index: int) -> int:
	for i in range(bundle.decisions.size()):
		var row: DecisionRowDTO = bundle.decisions[i]
		if row.decision_index == decision_index:
			return i
	assert_bool(false).override_failure_message(
		"fixture missing decision_index=%d" % decision_index
	).is_true()
	return -1


func _banner(shell: AppShell) -> StateBanner:
	return shell.get_node("VBox/StateBanner")


func _key(keycode: int) -> InputEventKey:
	var e := InputEventKey.new()
	e.keycode = keycode
	e.pressed = true
	return e


func _ctrl_key(keycode: int) -> InputEventKey:
	var e := _key(keycode)
	e.ctrl_pressed = true
	return e


func _global_rect(control: Control) -> Rect2:
	return Rect2(control.global_position, control.size)


func test_banner_visible_fixture01() -> void:
	# Plan D selects decision_index=0 (team_preview) by default (§5.6).
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_object(shell.get_loaded_bundle()).is_not_null()

	var banner := _banner(shell)
	assert_str(banner.get_state_text()).is_equal(StateBannerPresenter.TEAM_PREVIEW)
	assert_bool(banner.visible).is_true()


func test_banner_fixture04_trace_missing() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-04"))
	await _await_shell_settled(shell)
	assert_object(shell.get_loaded_bundle()).is_not_null()

	assert_str(_banner(shell).get_state_text()).is_equal(StateBannerPresenter.TRACE_MISSING)


func test_banner_fixture03_fallback_on_selected_row() -> void:
	# fixture-03 d2 is the Plan D fallback nav target (measured: fallback_used == true).
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-03"))
	await _await_shell_settled(shell)
	var bundle := shell.get_loaded_bundle()
	assert_object(bundle).is_not_null()

	var row_index := _row_index_by_decision_index(bundle, 2)
	var dec := shell.get_decision_workspace().get_decision_controller()
	dec.select_decision_row(row_index)
	await await_idle_frame()
	assert_bool(dec.get_selected_decision().fallback_used).is_true()

	assert_str(_banner(shell).get_state_text()).is_equal(StateBannerPresenter.FALLBACK_USED)


func test_banner_fixture05_forced_on_d4() -> void:
	# fixture-05 d4 is forced_replacement with fallback_used == false (measured).
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-05"))
	await _await_shell_settled(shell)
	var bundle := shell.get_loaded_bundle()
	assert_object(bundle).is_not_null()

	var row_index := _row_index_by_decision_index(bundle, 4)
	var dec := shell.get_decision_workspace().get_decision_controller()
	dec.select_decision_row(row_index)
	await await_idle_frame()
	var selected := dec.get_selected_decision()
	assert_str(selected.decision_phase).is_equal(BundleMode.PHASE_FORCED_REPLACEMENT)
	assert_bool(selected.fallback_used).is_false()

	assert_str(_banner(shell).get_state_text()).is_equal(StateBannerPresenter.FORCED_REPLACEMENT)


func test_banner_fixture06_refuse_hash_mismatch() -> void:
	# No bundles/fixture-06 — same path as test_app_shell_smoke.gd / test_bundle_validator.gd.
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("sources/fixture-06/bundle"))
	await _await_shell_settled(shell)

	assert_str(shell.get_refuse_reason()).is_equal("hash_mismatch")
	assert_str(_banner(shell).get_state_text()).is_equal(StateBannerPresenter.BUNDLE_INVALID)


func test_deep_link_refuse_uses_plan_d_reason() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.parse_cli_args(PackedStringArray(["--decision", "wrong-battle:1"]))
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_object(shell.get_loaded_bundle()).is_not_null()

	assert_str(shell.get_deep_link_refuse_reason()).is_equal("battle_id_mismatch")
	assert_str(shell.get_status_text()).contains("battle_id_mismatch")


func test_keyboard_only_smoke_fixture01() -> void:
	# open -> next decision -> focus filter -> type -> focus selected (no mouse API).
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_object(shell.get_loaded_bundle()).is_not_null()

	var dec := shell.get_decision_workspace().get_decision_controller()
	var table := shell.get_decision_workspace().get_candidate_table_view()
	var shortcuts: WorkspaceShortcuts = shell.get_node("WorkspaceShortcuts")

	var start_index: int = dec.get_selected_decision().decision_index
	shortcuts._unhandled_input(_ctrl_key(KEY_DOWN))
	await await_idle_frame()
	assert_int(dec.get_selected_decision().decision_index).is_not_equal(start_index)

	shortcuts._unhandled_input(_ctrl_key(KEY_F))
	assert_object(shell.get_viewport().gui_get_focus_owner()).is_same(table.get_filter_line_edit())

	table.set_filter_text("a")
	await await_idle_frame()
	table.set_filter_text("")
	await await_idle_frame()

	shortcuts._unhandled_input(_ctrl_key(KEY_L))
	assert_int(table.get_selected_candidate_index()).is_greater_equal(0)


func test_scale_preset_option_button_drives_layout_scale() -> void:
	# §0.8 "snap buttons/menu: 75 / 100 / 150 / 200" — the reachable control
	# surface, not just the WorkspaceLayout API it wraps.
	var shell: AppShell = await _spawn_shell_ready()
	var scale_option: OptionButton = shell.get_node("VBox/ScaleRow/ScaleOption")
	assert_int(scale_option.item_count).is_equal(4)

	var index_150 := WorkspaceLayout.SCALE_PRESETS.find(1.5)
	scale_option.select(index_150)
	scale_option.item_selected.emit(index_150)
	await await_idle_frame()

	assert_float(shell.get_layout().get_ui_scale()).is_equal(1.5)


func test_density_toggle_button_flips_layout_density() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	var toggle: Button = shell.get_node("VBox/ScaleRow/DensityToggleButton")
	assert_str(shell.get_layout().get_density()).is_equal(WorkspaceLayout.DENSITY_COMFORTABLE)

	toggle.pressed.emit()
	await await_idle_frame()
	assert_str(shell.get_layout().get_density()).is_equal(WorkspaceLayout.DENSITY_COMPACT)
	assert_str(toggle.text).contains("Compact")

	toggle.pressed.emit()
	await await_idle_frame()
	assert_str(shell.get_layout().get_density()).is_equal(WorkspaceLayout.DENSITY_COMFORTABLE)
	assert_str(toggle.text).contains("Comfortable")


func test_reset_shortcut_resyncs_scale_and_density_controls() -> void:
	# Ctrl+Shift+0 drives WorkspaceLayout directly (not through these widgets);
	# the preset controls must still reflect the real post-reset state.
	var shell: AppShell = await _spawn_shell_ready()
	var scale_option: OptionButton = shell.get_node("VBox/ScaleRow/ScaleOption")
	var toggle: Button = shell.get_node("VBox/ScaleRow/DensityToggleButton")
	var shortcuts: WorkspaceShortcuts = shell.get_node("WorkspaceShortcuts")

	shell.get_layout().set_ui_scale(2.0)
	shell.get_layout().set_density(WorkspaceLayout.DENSITY_COMPACT)
	await await_idle_frame()
	assert_int(scale_option.selected).is_equal(WorkspaceLayout.SCALE_PRESETS.find(2.0))
	assert_str(toggle.text).contains("Compact")

	shortcuts._unhandled_input(_ctrl_shift_key(KEY_0))
	await await_idle_frame()

	assert_int(scale_option.selected).is_equal(WorkspaceLayout.SCALE_PRESETS.find(1.0))
	assert_str(toggle.text).contains("Comfortable")


func _ctrl_shift_key(keycode: int) -> InputEventKey:
	var e := _ctrl_key(keycode)
	e.shift_pressed = true
	return e


func test_primary_controls_reachable_at_1280x720() -> void:
	# Plan §0.7 binding: "timeline controls and path/open (file) row remain
	# reachable"; Plan E §7 acceptance: "primary controls reachable at
	# 1280x720". DisplayServer window geometry is stubbed headless
	# (test_workspace_layout.gd:111-118), but Window/Control layout math is
	# not — resize the root Window directly and let containers re-layout.
	var shell: AppShell = await _spawn_shell_ready()
	get_tree().root.size = Vector2i(1280, 720)
	await await_idle_frame()
	await await_idle_frame()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	await await_idle_frame()
	await await_idle_frame()

	var viewport_rect := Rect2(Vector2.ZERO, Vector2(get_tree().root.size))

	var play_button: Control = (
		shell.get_replay_workspace().get_timeline_view().get_node("Controls/PlayButton")
	)
	assert_bool(viewport_rect.encloses(_global_rect(play_button))).override_failure_message(
		"transport PlayButton at %s must stay inside the %s window (was it pushed off the bottom?)"
		% [str(_global_rect(play_button)), str(viewport_rect)]
	).is_true()

	var path_row: Control = shell.get_node("VBox/PathRow")
	assert_bool(viewport_rect.encloses(_global_rect(path_row))).override_failure_message(
		"PathRow (Open) at %s must stay inside the %s window"
		% [str(_global_rect(path_row)), str(viewport_rect)]
	).is_true()

	# DiagnosticsDock Provenance: the dock itself must not overflow the window,
	# and its last row ("dirty") must be reachable by scrolling within it —
	# not merely present somewhere off-screen (§0.9 / §5.3).
	var diagnostics := shell.get_layout().get_diagnostics_dock()
	diagnostics.current_tab = 0  # Provenance
	await await_idle_frame()
	assert_bool(viewport_rect.encloses(_global_rect(diagnostics))).override_failure_message(
		"DiagnosticsDock at %s must stay inside the %s window"
		% [str(_global_rect(diagnostics)), str(viewport_rect)]
	).is_true()

	var scroll: ScrollContainer = diagnostics.get_node("Provenance")
	scroll.scroll_vertical = 1000000
	await await_idle_frame()
	var last_row := diagnostics.get_provenance_value_control_at(
		diagnostics.get_provenance_row_count() - 1
	)
	assert_bool(_global_rect(scroll).encloses(_global_rect(last_row))).override_failure_message(
		"provenance 'dirty' row at %s must be reachable by scrolling within %s"
		% [str(_global_rect(last_row)), str(_global_rect(scroll))]
	).is_true()
