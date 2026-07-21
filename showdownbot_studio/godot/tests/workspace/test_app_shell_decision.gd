extends GdUnitTestSuite

const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"
const _APP_SHELL_SCENE := preload("res://src/workspace/app_shell.tscn")


func _fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_FIXTURES_ROOT.path_join(relative))


func _fixture_bundle(rel: String) -> BundleDTO:
	var path := _fixture_path(rel)
	var result: ValidationResult = BundleValidator.validate_dir(path)
	assert_object(result.bundle).is_not_null()
	return result.bundle


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


func test_fixture04_no_candidate_claims() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-04"))
	await _await_shell_settled(shell)
	var ws := shell.get_decision_workspace()
	assert_bool(ws.get_empty_state_visible()).is_true()
	assert_int(ws.get_candidate_table_view().get_item_count()).is_equal(0)


func test_fixture01_timeline_and_decision_nav_same_index() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	var replay_ws := shell.get_replay_workspace()
	var dec_ws := shell.get_decision_workspace()
	var timeline := replay_ws.get_timeline_controller()
	var replay: ReplayDTO = timeline.get_replay()
	var decision_entry := -1
	for i in range(replay.entries.size()):
		if replay.entries[i].kind == TimelineEntryKind.DECISION:
			decision_entry = i
			break
	timeline.select(decision_entry)
	await await_idle_frame()
	var from_timeline: int = dec_ws.get_decision_controller().get_selected_decision().decision_index
	dec_ws.get_decision_controller().jump_next("decision")
	await await_idle_frame()
	var from_decision: int = dec_ws.get_decision_controller().get_selected_decision().decision_index
	var entry_i := timeline.get_selected_entry_index()
	var row_i: int = replay.entries[entry_i].decision_row_index
	assert_int(shell.get_loaded_bundle().decisions[row_i].decision_index).is_equal(from_decision)
	assert_int(from_timeline).is_greater(-1)


func test_fixture03_fallback_nav() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-03"))
	await _await_shell_settled(shell)
	var dec := shell.get_decision_workspace().get_decision_controller()
	var bundle := shell.get_loaded_bundle()
	var start_row := DecisionPresenter.first_row_by_decision_index(bundle)
	dec.select_decision_row(start_row)
	await await_idle_frame()
	dec.jump_next("fallback")
	await await_idle_frame()
	var selected := dec.get_selected_decision()
	assert_object(selected).is_not_null()
	assert_bool(selected.fallback_used).is_true()


func test_fixture16_empty_candidates_clean() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-16"))
	await _await_shell_settled(shell)
	var bundle := shell.get_loaded_bundle()
	var empty_row := -1
	for i in range(bundle.decisions.size()):
		if bundle.decisions[i].candidates.is_empty():
			empty_row = i
			break
	assert_int(empty_row).is_greater(-1)
	shell.get_decision_workspace().get_decision_controller().select_decision_row(empty_row)
	await await_idle_frame()
	assert_int(shell.get_decision_workspace().get_candidate_table_view().get_item_count()).is_equal(0)


func test_fixture16_104_candidates_bind() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-16"))
	await _await_shell_settled(shell)
	var dec := shell.get_decision_workspace().get_decision_controller()
	var bundle := shell.get_loaded_bundle()
	var row_104 := -1
	for i in range(bundle.decisions.size()):
		if bundle.decisions[i].candidates.size() == 104:
			row_104 = i
			break
	assert_int(row_104).is_greater(-1)
	dec.select_decision_row(row_104)
	await await_idle_frame()
	assert_int(
		shell.get_decision_workspace().get_candidate_table_view().get_item_count()
	).is_equal(104)


func test_fixture01_reset_keeps_plan_c_timeline_cursor() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	var timeline := shell.get_replay_workspace().get_timeline_controller()
	var replay: ReplayDTO = timeline.get_replay()
	assert_int(timeline.get_selected_entry_index()).is_equal(0)
	assert_str(replay.entries[0].kind).is_not_equal("")
	var selected := shell.get_decision_workspace().get_decision_controller().get_selected_decision()
	assert_object(selected).is_not_null()
	assert_int(timeline.get_selected_entry_index()).is_equal(0)


func test_workspace_candidate_signal_updates_detail() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	var ws := shell.get_decision_workspace()
	var table := ws.get_candidate_table_view()
	var detail := ws.get_detail_view()
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
	await await_idle_frame()
	assert_bool(detail.get_candidate_id_text().contains(d.candidates[other].candidate_id)).is_true()
	assert_int(table.get_selected_candidate_index()).is_equal(other)


func test_workspace_filter_resyncs_detail() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	var ws := shell.get_decision_workspace()
	var table := ws.get_candidate_table_view()
	var detail := ws.get_detail_view()
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
	await await_idle_frame()
	assert_bool(detail.get_candidate_id_text().contains(d.candidates[other].candidate_id)).is_true()
	table.set_chosen_only(true)
	await await_idle_frame()
	assert_int(table.get_selected_candidate_index()).is_equal(chosen)
	assert_bool(detail.get_candidate_id_text().contains(d.candidates[chosen].candidate_id)).is_true()


func test_refuse_clears_decision_panel() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	shell.get_decision_workspace().get_decision_controller().select_decision_row(2)
	await await_idle_frame()
	assert_int(shell.get_decision_workspace().get_candidate_table_view().get_item_count()).is_greater(0)
	shell.open_bundle_path(_fixture_path("sources/fixture-06/bundle"))
	await _await_shell_settled(shell)
	var ws := shell.get_decision_workspace()
	assert_str(shell.get_refuse_reason()).is_equal("hash_mismatch")
	assert_object(shell.get_loaded_bundle()).is_null()
	assert_int(ws.get_candidate_table_view().get_item_count()).is_equal(0)
	assert_str(ws.get_header_text()).is_equal("")


func test_start_load_clears_decision_before_async() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	shell.get_decision_workspace().get_decision_controller().select_decision_row(2)
	await await_idle_frame()
	assert_int(shell.get_decision_workspace().get_candidate_table_view().get_item_count()).is_greater(0)
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
	assert_bool(shell.get_decision_workspace().get_empty_state_visible()).is_false()
	assert_int(shell.get_decision_workspace().get_candidate_table_view().get_item_count()).is_equal(0)
	assert_str(shell.get_decision_workspace().get_header_text()).is_equal("")
	release.post()
	await _await_shell_settled(shell)


func test_bundle_switch_01_to_04_hides_claims() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	shell.get_decision_workspace().get_decision_controller().select_decision_row(2)
	await await_idle_frame()
	assert_int(shell.get_decision_workspace().get_candidate_table_view().get_item_count()).is_greater(0)
	shell.open_bundle_path(_fixture_path("bundles/fixture-04"))
	await _await_shell_settled(shell)
	var ws := shell.get_decision_workspace()
	assert_bool(ws.get_empty_state_visible()).is_true()
	assert_int(ws.get_candidate_table_view().get_item_count()).is_equal(0)


func test_deep_link_success() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var target: DecisionRowDTO = bundle.decisions[1]
	var shell: AppShell = await _spawn_shell_ready()
	shell.parse_cli_args(PackedStringArray([
		"--decision", "%s:%d" % [bundle.manifest.battle_id, target.decision_index]
	]))
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_str(shell.get_deep_link_refuse_reason()).is_equal("")
	assert_int(shell.get_selected_decision_index()).is_equal(target.decision_index)


func test_deep_link_mismatch_refuses() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.parse_cli_args(PackedStringArray(["--decision", "wrong-battle:1"]))
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_str(shell.get_deep_link_refuse_reason()).is_equal("battle_id_mismatch")
	assert_bool(shell.get_status_text().contains("Deep link refused")).is_true()
	assert_object(shell.get_loaded_bundle()).is_not_null()


func test_deep_link_missing_value_malformed() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.parse_cli_args(PackedStringArray(["--decision"]))
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_str(shell.get_deep_link_refuse_reason()).is_equal("malformed_decision_arg")
	assert_object(shell.get_loaded_bundle()).is_not_null()


func test_deep_link_one_shot_not_reapplied_on_manual_open() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var target: DecisionRowDTO = bundle.decisions[1]
	var shell: AppShell = await _spawn_shell_ready()
	shell.parse_cli_args(PackedStringArray([
		"--decision", "%s:%d" % [bundle.manifest.battle_id, target.decision_index]
	]))
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_int(shell.get_selected_decision_index()).is_equal(target.decision_index)
	shell.open_bundle_path(_fixture_path("bundles/fixture-03"))
	await _await_shell_settled(shell)
	assert_str(shell.get_deep_link_refuse_reason()).is_equal("")
	assert_str(shell.get_loaded_bundle().manifest.battle_id).is_equal("synthetic00000003")


func test_deep_link_refuse_cleared_on_later_manual_open() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.parse_cli_args(PackedStringArray(["--decision", "wrong-battle:1"]))
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_str(shell.get_deep_link_refuse_reason()).is_equal("battle_id_mismatch")
	assert_bool(shell.get_status_text().contains("Deep link refused")).is_true()
	shell.open_bundle_path(_fixture_path("bundles/fixture-03"))
	await _await_shell_settled(shell)
	assert_str(shell.get_deep_link_refuse_reason()).is_equal("")
	assert_bool(shell.get_status_text().contains("Deep link refused")).is_false()
	assert_str(shell.get_loaded_bundle().manifest.battle_id).is_equal("synthetic00000003")


func test_deep_link_duplicate_decision_flag_refuses() -> void:
	# B3: multiple --decision must not last-wins; refuse like ambiguous_decision_index.
	var bundle := _fixture_bundle("bundles/fixture-01")
	var target: DecisionRowDTO = bundle.decisions[1]
	var first_row := DecisionPresenter.first_row_by_decision_index(bundle)
	var first_index: int = bundle.decisions[first_row].decision_index
	var shell: AppShell = await _spawn_shell_ready()
	shell.parse_cli_args(PackedStringArray([
		"--decision", "garbage:9",
		"--decision", "%s:%d" % [bundle.manifest.battle_id, target.decision_index],
	]))
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_str(shell.get_deep_link_refuse_reason()).is_equal("ambiguous_decision_arg")
	assert_bool(shell.get_status_text().contains("Deep link refused")).is_true()
	assert_object(shell.get_loaded_bundle()).is_not_null()
	assert_int(shell.get_selected_decision_index()).is_equal(first_index)


func test_deep_link_duplicate_valid_decision_flags_refuses() -> void:
	# Two syntactically valid --decision targets still refuse (no last-wins).
	var bundle := _fixture_bundle("bundles/fixture-01")
	var a: DecisionRowDTO = bundle.decisions[0]
	var b: DecisionRowDTO = bundle.decisions[1]
	var first_row := DecisionPresenter.first_row_by_decision_index(bundle)
	var first_index: int = bundle.decisions[first_row].decision_index
	var shell: AppShell = await _spawn_shell_ready()
	shell.parse_cli_args(PackedStringArray([
		"--decision", "%s:%d" % [bundle.manifest.battle_id, a.decision_index],
		"--decision", "%s:%d" % [bundle.manifest.battle_id, b.decision_index],
	]))
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_str(shell.get_deep_link_refuse_reason()).is_equal("ambiguous_decision_arg")
	assert_int(shell.get_selected_decision_index()).is_equal(first_index)
