extends GdUnitTestSuite

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


func test_fixture01_open_builds_timeline_and_board() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)

	var ws: ReplayWorkspace = shell.get_replay_workspace()
	var ctl := ws.get_timeline_controller()
	var replay: ReplayDTO = ctl.get_replay()
	assert_object(replay).is_not_null()
	assert_int(replay.entries.size()).is_greater(0)

	ctl.select(2)
	await await_idle_frame()
	assert_str(ws.get_board_view().get_slot_species("p1", "a")).is_equal("Pikachu")


func test_fixture04_no_decision_entries() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-04"))
	await _await_shell_settled(shell)

	var ws: ReplayWorkspace = shell.get_replay_workspace()
	var replay: ReplayDTO = ws.get_timeline_controller().get_replay()
	assert_object(replay).is_not_null()
	assert_int(replay.entries.size()).is_greater(0)
	for i in range(replay.entries.size()):
		assert_str(replay.entries[i].kind).is_equal(TimelineEntryKind.EVENT)
		assert_bool(ws.get_timeline_view().get_visible_label(i).begins_with("decision")).is_false()


func test_fixture05_no_replay_board_state() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-05"))
	await _await_shell_settled(shell)

	var ws: ReplayWorkspace = shell.get_replay_workspace()
	assert_bool(ws.get_board_view().get_empty_state_visible()).is_true()
	assert_object(ws.get_board_model()).is_not_null()
	assert_bool(ws.get_board_model().has_replay).is_false()


func test_fixture06_refuse_clears_replay() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	shell.get_replay_workspace().get_timeline_controller().select(2)
	await await_idle_frame()
	assert_str(shell.get_replay_workspace().get_board_view().get_slot_species("p1", "a")).is_equal("Pikachu")

	shell.open_bundle_path(_fixture_path("sources/fixture-06/bundle"))
	await _await_shell_settled(shell)

	var ws: ReplayWorkspace = shell.get_replay_workspace()
	assert_str(shell.get_refuse_reason()).is_equal("hash_mismatch")
	assert_object(shell.get_loaded_bundle()).is_null()
	assert_object(ws.get_timeline_controller().get_replay()).is_null()
	assert_int(ws.get_timeline_controller().get_selected_entry_index()).is_equal(-1)
	assert_str(ws.get_timeline_view().get_visible_label(0)).is_equal("")
	assert_bool(ws.get_board_view().get_empty_state_visible()).is_true()
	assert_str(ws.get_board_view().get_slot_species("p1", "a")).is_equal("")


func test_cancel_clears_replay() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	shell.get_replay_workspace().get_timeline_controller().select(2)
	await await_idle_frame()
	assert_str(shell.get_replay_workspace().get_board_view().get_slot_species("p1", "a")).is_equal("Pikachu")

	var loader: BundleLoader = shell.get_node("BundleLoader")
	var hooks := BundleWorker.WorkerHooks.new()
	var release := Semaphore.new()
	hooks.on_before_terminal_enqueue = func() -> void:
		release.wait()
	loader.set_worker_hooks(hooks)

	shell.open_bundle_path(_fixture_path("bundles/fixture-04"))
	var frames := 0
	while not shell.is_loading() and frames < 600:
		await await_idle_frame()
		frames += 1
	assert_bool(shell.is_loading()).is_true()
	loader.cancel()
	release.post()
	await _await_shell_settled(shell)

	var ws: ReplayWorkspace = shell.get_replay_workspace()
	assert_object(shell.get_loaded_bundle()).is_null()
	assert_str(shell.get_status_text()).contains("cancelled")
	assert_object(ws.get_timeline_controller().get_replay()).is_null()
	assert_int(ws.get_timeline_controller().get_selected_entry_index()).is_equal(-1)
	assert_str(ws.get_board_view().get_slot_species("p1", "a")).is_equal("")


func test_start_load_clears_before_async() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	shell.get_replay_workspace().get_timeline_controller().select(2)
	await await_idle_frame()
	assert_str(shell.get_replay_workspace().get_board_view().get_slot_species("p1", "a")).is_equal("Pikachu")

	var loader: BundleLoader = shell.get_node("BundleLoader")
	var hooks := BundleWorker.WorkerHooks.new()
	var release := Semaphore.new()
	hooks.on_before_terminal_enqueue = func() -> void:
		release.wait()
	loader.set_worker_hooks(hooks)

	shell.open_bundle_path(_fixture_path("bundles/fixture-04"))
	var frames := 0
	while not shell.is_loading() and frames < 600:
		await await_idle_frame()
		frames += 1
	assert_bool(shell.is_loading()).is_true()

	var ws: ReplayWorkspace = shell.get_replay_workspace()
	assert_object(ws.get_timeline_controller().get_replay()).is_null()
	assert_str(ws.get_timeline_view().get_visible_label(0)).is_equal("")
	assert_str(ws.get_board_view().get_slot_species("p1", "a")).is_equal("")
	assert_str(ws.get_timeline_view().get_node("LoadingLabel").text).is_equal("Loading...")
	assert_str(ws.get_board_view().get_node("LoadingLabel").text).is_equal("Loading...")
	assert_bool(ws.get_timeline_view().get_node("Controls/PrevButton").disabled).is_true()
	assert_bool(ws.get_timeline_view().get_node("Controls/PlayButton").disabled).is_true()

	release.post()
	await _await_shell_settled(shell)


func test_bundle_switch_resets_cursor() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	var ctl := shell.get_replay_workspace().get_timeline_controller()
	ctl.select(2)
	await await_idle_frame()
	assert_int(ctl.get_selected_entry_index()).is_equal(2)

	shell.open_bundle_path(_fixture_path("bundles/fixture-04"))
	await _await_shell_settled(shell)
	ctl = shell.get_replay_workspace().get_timeline_controller()
	assert_int(ctl.get_selected_entry_index()).is_equal(0)
	assert_bool(ctl.is_playing()).is_false()


func test_bundle_switch_clears_board_species() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	shell.get_replay_workspace().get_timeline_controller().select(2)
	await await_idle_frame()
	assert_str(shell.get_replay_workspace().get_board_view().get_slot_species("p1", "a")).is_equal("Pikachu")
	shell.open_bundle_path(_fixture_path("bundles/fixture-05"))
	await _await_shell_settled(shell)
	assert_bool(shell.get_replay_workspace().get_board_view().get_empty_state_visible()).is_true()
	assert_str(shell.get_replay_workspace().get_board_view().get_slot_species("p1", "a")).is_equal("")


func test_selection_updates_board_across_event_boundary() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	var ws: ReplayWorkspace = shell.get_replay_workspace()
	var ctl := ws.get_timeline_controller()
	ctl.select(2)  # switch EVENT — Pikachu
	await await_idle_frame()
	assert_str(ws.get_board_view().get_slot_species("p1", "a")).is_equal("Pikachu")
	ctl.select(1)  # prior turn EVENT — no switch yet
	await await_idle_frame()
	assert_str(ws.get_board_view().get_slot_species("p1", "a")).is_equal("")
