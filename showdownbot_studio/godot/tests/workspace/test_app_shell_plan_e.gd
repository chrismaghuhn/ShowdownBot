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
	assert_object(shell.get_loaded_bundle()).is_not_null()
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


func test_chrome_minimum_size_grows_with_scale() -> void:
	# Proves the theme moved to AppShell (2026-07-25): PathRow is a sibling of
	# WorkspaceLayout under VBox, not a descendant of it, so before this fix a
	# scale change had zero effect on it (WorkspaceLayout applied the theme to
	# itself only). Real capture evidence of the pre-fix state:
	# docs/plans/evidence/viewer-v0-f-manual-checklist.md.
	var shell: AppShell = await _spawn_shell_ready()
	var path_row: Control = shell.get_node("VBox/PathRow")

	shell.get_layout().set_ui_scale(1.0)
	await await_idle_frame()
	await await_idle_frame()
	var min_100 := path_row.get_combined_minimum_size()

	shell.get_layout().set_ui_scale(1.5)
	await await_idle_frame()
	await await_idle_frame()
	var min_150 := path_row.get_combined_minimum_size()

	assert_float(min_150.x).is_greater(min_100.x)
	assert_float(min_150.y).is_greater(min_100.y)


func test_compute_min_window_size_floor_and_scale_growth() -> void:
	# §4 of the brief: computed, not tabled; never below the 1280x720 floor,
	# strictly more once scale pushes real content past it.
	#
	# Uses 100% -> 200% (SCALE_MAX), not the brief's illustrative 150%: verified
	# by direct probe (godot/_debug_minsize.gd, throwaway, not committed —
	# see report) that this headless engine's TextServer under-measures string
	# *width* by a roughly constant ~26% vs a real (non-headless) window, while
	# it matches the report's real-window HEIGHT numbers exactly (627/858/1089
	# at 100/150/200%). At 150% the under-measured width (1192px) still sits
	# under the 1280 floor, so both endpoints would read 1280 and the "strictly
	# more" assertion would be comparing floor-vs-floor, not a real regression
	# — a headless-only artifact, same shape as Plan F §0.5's documented
	# blind spot, not evidence the production code fails to grow. 200% clears
	# the floor headlessly too (1571px measured), so the assertion is
	# meaningful in both environments. The real-window capture (§0.7, this
	# report) is the actual evidence for 150%.
	var shell: AppShell = await _spawn_shell_ready()

	shell.get_layout().set_ui_scale(1.0)
	await await_idle_frame()
	await await_idle_frame()
	var min_100 := shell.compute_min_window_size()
	assert_int(min_100.x).is_greater_equal(1280)
	assert_int(min_100.y).is_greater_equal(720)

	shell.get_layout().set_ui_scale(2.0)
	await await_idle_frame()
	await await_idle_frame()
	var min_200 := shell.compute_min_window_size()
	assert_int(min_200.x).is_greater(min_100.x)
	assert_int(min_200.y).is_greater(min_100.y)


func test_candidate_table_minimum_size_invariant_to_row_count() -> void:
	# Bounded-rendering check (index §5 rule 7 — "no one Control per unbounded
	# row, 104-candidate fixture is the proof"): CandidateTableView's own
	# minimum size must not grow with candidate count. fixture-16 has a
	# 104-candidate decision (test_app_shell_decision.gd:
	# test_fixture16_104_candidates_bind) alongside small/zero-candidate ones
	# in the same bundle — comparing within one bundle isolates row-count from
	# unrelated per-bundle text (path, hashes) that legitimately varies size a
	# little between different bundles.
	#
	# NOTE — a real, separate, pre-existing, OUT-OF-SCOPE gap this probe also
	# found (verified by direct probe, godot/_debug_minsize.gd, throwaway, not
	# committed — see report): the whole-SHELL computed minimum is NOT
	# content-invariant, because DecisionDetailView's Candidate tab
	# (decision_detail_view.tscn: CandidateIdLabel / CandidateKeyLabel,
	# decision_detail_view.gd:52-55 bind_candidate()) renders candidate_id /
	# candidate_key with no autowrap_mode. fixture-16's 104-candidate row has
	# candidate_key strings up to 286 chars; selecting that row balloons the
	# shell's computed minimum from ~1280x720 to ~2096x720 headlessly. That is
	# a bounded-rendering violation in DecisionDetailView, not in this task's
	# layout-propagation/window-sizing scope — not fixed here.
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-16"))
	await _await_shell_settled(shell)
	var bundle := shell.get_loaded_bundle()
	assert_object(bundle).is_not_null()
	var dec := shell.get_decision_workspace().get_decision_controller()
	var table := shell.get_decision_workspace().get_candidate_table_view()

	await await_idle_frame()
	var min_default := table.get_combined_minimum_size()

	var row_104 := -1
	for i in range(bundle.decisions.size()):
		if bundle.decisions[i].candidates.size() == 104:
			row_104 = i
			break
	assert_int(row_104).is_greater(-1)
	dec.select_decision_row(row_104)
	await await_idle_frame()
	await await_idle_frame()
	assert_int(table.get_item_count()).is_equal(104)
	var min_104_rows := table.get_combined_minimum_size()

	assert_vector(min_104_rows).is_equal(min_default)


func test_shell_min_width_stays_bounded_after_timeline_selects_long_key_decision() -> void:
	# Regression for the owner-reported "screen shifts right" bug. Root cause
	# (measured on main, this fix's report): DecisionDetailView's
	# CandidateKeyLabel / ChosenKeyLabel render candidate_key with no
	# truncation, and fixture-01 decision_index=1 has a chosen candidate whose
	# candidate_key is ~286 chars -- ballooning the shell's computed minimum
	# width to ~2208px in a 1920px window (see
	# test_candidate_table_minimum_size_invariant_to_row_count's note above,
	# which found the same gap and deliberately left it out of that task's
	# scope).
	#
	# Selects via TimelineController.select(), the way the owner actually
	# clicks a timeline entry -- not DecisionController.select_decision_row()
	# directly. Both routes converge on DecisionController._set_row() and
	# should settle identically, but the owner's repro is real-window timeline
	# clicks, so this pins that exact path rather than a same-outcome proxy.
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	var bundle := shell.get_loaded_bundle()
	assert_object(bundle).is_not_null()

	var row_index := _row_index_by_decision_index(bundle, 1)
	assert_bool(bundle.decisions[row_index].chosen_candidate_key != null).is_true()

	var timeline := shell.get_replay_workspace().get_timeline_controller()
	var entry_index := DecisionPresenter.timeline_entry_for_decision_row(
		timeline.get_replay(), row_index
	)
	assert_int(entry_index).is_greater(-1)

	timeline.select(entry_index)
	await await_idle_frame()
	await await_idle_frame()
	assert_int(shell.get_selected_decision_index()).is_equal(1)

	var min_size := shell.compute_min_window_size()
	assert_int(min_size.x).override_failure_message(
		"shell minimum width must stay <= 1280 (the min-window floor) after "
		+ "selecting decision #1 via the timeline; got %d" % min_size.x
	).is_less_equal(1280)
