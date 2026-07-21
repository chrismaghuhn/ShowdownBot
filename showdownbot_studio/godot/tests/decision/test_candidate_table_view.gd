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


func _make_candidate(candidate_id: String, rank: int, score: float, key: Variant) -> CandidateDTO:
	var c := CandidateDTO.new()
	c.candidate_id = candidate_id
	c.rank = rank
	c.aggregate_score = score
	c.candidate_key = key
	c.seal()
	return c


func test_table_bounded_104_candidates() -> void:
	var bundle := _fixture_bundle("bundles/fixture-16")
	var d: DecisionRowDTO = null
	for row in bundle.decisions:
		if row.candidates.size() == 104:
			d = row
			break
	assert_object(d).is_not_null()
	var view: CandidateTableView = preload("res://src/decision/candidate_table_view.tscn").instantiate()
	add_child(view)
	await await_idle_frame()
	view.bind(d)
	assert_int(view.get_item_count()).is_equal(104)


func test_empty_candidates_table_empty() -> void:
	var bundle := _fixture_bundle("bundles/fixture-16")
	var d: DecisionRowDTO = null
	for row in bundle.decisions:
		if row.candidates.is_empty():
			d = row
			break
	assert_object(d).is_not_null()
	var view: CandidateTableView = preload("res://src/decision/candidate_table_view.tscn").instantiate()
	add_child(view)
	await await_idle_frame()
	view.bind(d)
	assert_int(view.get_item_count()).is_equal(0)


func test_sort_keeps_chosen_marker() -> void:
	var view: CandidateTableView = preload("res://src/decision/candidate_table_view.tscn").instantiate()
	add_child(view)
	await await_idle_frame()
	var bundle := _fixture_bundle("bundles/fixture-01")
	var d: DecisionRowDTO = null
	for row in bundle.decisions:
		if row.candidates.size() >= 2 and row.decision_valid:
			d = row
			break
	assert_object(d).is_not_null()
	view.bind(d)
	var chosen := DecisionPresenter.resolve_chosen_row_index(d)
	for mode in [
		DecisionPresenter.SORT_SCORE,
		DecisionPresenter.SORT_LABEL,
		DecisionPresenter.SORT_CHOSEN_FIRST,
	]:
		view.set_sort_mode(mode)
		var visual := view.get_chosen_item_index()
		assert_int(visual).is_greater(-1)
		var list: ItemList = view.get_node("CandidateList")
		assert_bool(list.get_item_text(visual).begins_with("* ")).is_true()


func test_selected_ne_chosen_keeps_chosen_marker() -> void:
	var view: CandidateTableView = preload("res://src/decision/candidate_table_view.tscn").instantiate()
	add_child(view)
	await await_idle_frame()
	var bundle := _fixture_bundle("bundles/fixture-01")
	var d: DecisionRowDTO = null
	for row in bundle.decisions:
		if row.candidates.size() >= 2 and row.decision_valid:
			d = row
			break
	assert_object(d).is_not_null()
	view.bind(d)
	var chosen := DecisionPresenter.resolve_chosen_row_index(d)
	assert_int(chosen).is_greater(-1)
	var chosen_visual_before := view.get_chosen_item_index()
	assert_int(chosen_visual_before).is_greater(-1)
	var other := 0 if chosen != 0 else 1
	view.select_candidate_index(other)
	assert_int(view.get_selected_candidate_index()).is_equal(other)
	assert_int(view.get_selected_candidate_index()).is_not_equal(chosen)
	assert_int(view.get_chosen_item_index()).is_equal(chosen_visual_before)
	assert_int(DecisionPresenter.resolve_chosen_row_index(d)).is_equal(chosen)


func test_decision_bind_resets_selection() -> void:
	var view: CandidateTableView = preload("res://src/decision/candidate_table_view.tscn").instantiate()
	add_child(view)
	await await_idle_frame()
	var bundle := _fixture_bundle("bundles/fixture-01")
	var d: DecisionRowDTO = null
	for row in bundle.decisions:
		if row.candidates.size() >= 2 and row.decision_valid:
			d = row
			break
	assert_object(d).is_not_null()
	view.bind(d)
	var chosen := DecisionPresenter.resolve_chosen_row_index(d)
	assert_int(view.get_selected_candidate_index()).is_equal(chosen)
	var other := 0 if chosen != 0 else 1
	view.select_candidate_index(other)
	view.bind(d)
	assert_int(view.get_selected_candidate_index()).is_equal(chosen)


func test_filter_text_narrows_list() -> void:
	var view: CandidateTableView = preload("res://src/decision/candidate_table_view.tscn").instantiate()
	add_child(view)
	await await_idle_frame()
	var d := DecisionRowDTO.new()
	d.decision_index = 99
	d.turn_number = 1
	d.decision_phase = BundleMode.PHASE_REGULAR_TURN
	d.decision_latency_ms = 1.0
	d.observable_state_hash = "obs"
	d.request_hash = "req"
	d.state_summary = {}
	d.normalized_action = {}
	d.actual_choose_string = "move 1"
	d.candidates = [
		_make_candidate("alpha-label", 1, 1.0, "key-a"),
		_make_candidate("beta-label", 2, 0.5, "key-b"),
		_make_candidate("gamma-label", 3, 0.25, "key-c"),
	]
	d.chosen_candidate_key = "key-a"
	d.fallback_used = false
	d.warning_count = 0
	d.decision_valid = true
	d.seal()
	view.bind(d)
	var full_count := view.get_item_count()
	assert_int(full_count).is_equal(3)
	view.set_filter_text("alpha-label")
	assert_int(view.get_item_count()).is_less(full_count)
	assert_int(view.get_chosen_item_index()).is_equal(0)


func test_filter_chosen_only() -> void:
	var view: CandidateTableView = preload("res://src/decision/candidate_table_view.tscn").instantiate()
	add_child(view)
	await await_idle_frame()
	var bundle := _fixture_bundle("bundles/fixture-01")
	var d: DecisionRowDTO = null
	for row in bundle.decisions:
		if row.candidates.size() >= 2 and row.decision_valid:
			d = row
			break
	assert_object(d).is_not_null()
	view.bind(d)
	view.set_chosen_only(true)
	assert_int(view.get_item_count()).is_equal(1)
	assert_int(view.get_chosen_item_index()).is_equal(0)


func test_filter_resyncs_selection_signal() -> void:
	var view: CandidateTableView = preload("res://src/decision/candidate_table_view.tscn").instantiate()
	add_child(view)
	await await_idle_frame()
	var bundle := _fixture_bundle("bundles/fixture-01")
	var d: DecisionRowDTO = null
	for row in bundle.decisions:
		if row.candidates.size() >= 2 and row.decision_valid:
			d = row
			break
	assert_object(d).is_not_null()
	view.bind(d)
	var chosen := DecisionPresenter.resolve_chosen_row_index(d)
	var other := 0 if chosen != 0 else 1
	view.select_candidate_index(other)
	var emitted := [-2]
	view.candidate_selected.connect(func(i: int) -> void: emitted[0] = i)
	view.set_chosen_only(true)
	assert_int(emitted[0]).is_equal(chosen)
	assert_int(view.get_selected_candidate_index()).is_equal(chosen)
	assert_int(view.get_chosen_item_index()).is_greater(-1)
