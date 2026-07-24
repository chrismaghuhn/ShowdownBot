extends GdUnitTestSuite

const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"
const _APP_SHELL_SCENE := preload("res://src/workspace/app_shell.tscn")


func _fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_FIXTURES_ROOT.path_join(relative))


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


func _spawn_shortcuts(shell: AppShell) -> WorkspaceShortcuts:
	var shortcuts := WorkspaceShortcuts.new()
	add_child(shortcuts)
	shortcuts.configure(
		shell.get_replay_workspace().get_timeline_controller(),
		shell.get_decision_workspace().get_decision_controller(),
		shell.get_decision_workspace().get_candidate_table_view()
	)
	return shortcuts


func _key(keycode: int) -> InputEventKey:
	var e := InputEventKey.new()
	e.keycode = keycode
	e.pressed = true
	return e


func _ctrl_key(keycode: int) -> InputEventKey:
	var e := _key(keycode)
	e.ctrl_pressed = true
	return e


func test_timeline_step_next_via_shortcut() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_object(shell.get_loaded_bundle()).is_not_null()
	var timeline := shell.get_replay_workspace().get_timeline_controller()
	var start := timeline.get_selected_entry_index()
	var shortcuts := _spawn_shortcuts(shell)
	shortcuts._unhandled_input(_key(KEY_RIGHT))
	assert_int(timeline.get_selected_entry_index()).is_equal(start + 1)


func test_decision_jump_next_via_shortcut() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_object(shell.get_loaded_bundle()).is_not_null()
	var dec := shell.get_decision_workspace().get_decision_controller()
	var bundle := shell.get_loaded_bundle()
	var start_row := DecisionPresenter.first_row_by_decision_index(bundle)
	dec.select_decision_row(start_row)
	await await_idle_frame()
	var start_index: int = dec.get_selected_decision().decision_index
	var expected_row := DecisionPresenter.find_next_nav_row(bundle, start_index, "decision")
	assert_int(expected_row).is_greater_equal(0)
	var shortcuts := _spawn_shortcuts(shell)
	shortcuts._unhandled_input(_ctrl_key(KEY_DOWN))
	await await_idle_frame()
	assert_int(dec.get_selected_decision().decision_index).is_equal(
		bundle.decisions[expected_row].decision_index
	)


func test_toggle_play_via_shortcut() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_object(shell.get_loaded_bundle()).is_not_null()
	var timeline := shell.get_replay_workspace().get_timeline_controller()
	assert_bool(timeline.is_playing()).is_false()
	var shortcuts := _spawn_shortcuts(shell)
	shortcuts._unhandled_input(_key(KEY_SPACE))
	assert_bool(timeline.is_playing()).is_true()
	shortcuts._unhandled_input(_key(KEY_SPACE))
	assert_bool(timeline.is_playing()).is_false()


func test_focus_filter_grabs_plan_d_line_edit() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_object(shell.get_loaded_bundle()).is_not_null()
	var table := shell.get_decision_workspace().get_candidate_table_view()
	var shortcuts := _spawn_shortcuts(shell)
	shortcuts._unhandled_input(_ctrl_key(KEY_F))
	var focused := shell.get_viewport().gui_get_focus_owner()
	assert_object(focused).is_same(table.get_filter_line_edit())


func test_focus_selected_candidate() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_object(shell.get_loaded_bundle()).is_not_null()
	var ws := shell.get_decision_workspace()
	var table := ws.get_candidate_table_view()
	var d: DecisionRowDTO = ws.get_decision_controller().get_selected_decision()
	if d == null or d.candidates.size() < 2 or not d.decision_valid:
		var bundle := shell.get_loaded_bundle()
		for i in range(bundle.decisions.size()):
			var row: DecisionRowDTO = bundle.decisions[i]
			if row.candidates.size() >= 2 and row.decision_valid:
				ws.get_decision_controller().select_decision_row(i)
				await await_idle_frame()
				d = row
				break
	assert_object(d).is_not_null()
	var chosen := DecisionPresenter.resolve_chosen_row_index(d)
	var other := 0 if chosen != 0 else 1
	table.select_candidate_index(other)
	var list: ItemList = table.get_node("CandidateList")
	list.deselect_all()
	assert_int(list.get_selected_items().size()).is_equal(0)
	var shortcuts := _spawn_shortcuts(shell)
	shortcuts._unhandled_input(_ctrl_key(KEY_L))
	assert_int(list.get_selected_items().size()).is_equal(1)
	assert_int(table.get_selected_candidate_index()).is_equal(other)


func test_filter_focus_suppresses_space_play() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_object(shell.get_loaded_bundle()).is_not_null()
	var table := shell.get_decision_workspace().get_candidate_table_view()
	var timeline := shell.get_replay_workspace().get_timeline_controller()
	table.get_filter_line_edit().grab_focus()
	var shortcuts := _spawn_shortcuts(shell)
	assert_bool(timeline.is_playing()).is_false()
	shortcuts._unhandled_input(_key(KEY_SPACE))
	assert_bool(timeline.is_playing()).is_false()


func test_no_second_filter_control() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	var ws := shell.get_decision_workspace()
	assert_int(_count_nodes_named(ws, "FilterLineEdit")).is_equal(1)


func _count_nodes_named(node: Node, target_name: String) -> int:
	var count := 0
	if String(node.name) == target_name:
		count += 1
	for child in node.get_children():
		count += _count_nodes_named(child, target_name)
	return count
