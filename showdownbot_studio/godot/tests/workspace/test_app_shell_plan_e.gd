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
