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


func test_detail_shows_aggregation_not_recorded() -> void:
	var bundle := _fixture_bundle("bundles/fixture-03")
	var view: DecisionDetailView = preload("res://src/decision/decision_detail_view.tscn").instantiate()
	add_child(view)
	await await_idle_frame()
	view.bind_decision(bundle.decisions[0])
	assert_bool(
		view.get_aggregation_text().contains(DecisionPresenter.AGGREGATION_NOT_RECORDED)
	).is_true()


func test_detail_shows_latency_ms() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var d: DecisionRowDTO = bundle.decisions[0]
	var view: DecisionDetailView = preload("res://src/decision/decision_detail_view.tscn").instantiate()
	add_child(view)
	await await_idle_frame()
	view.bind_decision(d)
	assert_bool(view.get_latency_text().contains(str(d.decision_latency_ms))).is_true()


func test_chosen_id_caption_not_identity() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var d: DecisionRowDTO = null
	for row in bundle.decisions:
		if row.chosen_candidate_id != null:
			d = row
			break
	if d == null:
		d = bundle.decisions[0]
	var view: DecisionDetailView = preload("res://src/decision/decision_detail_view.tscn").instantiate()
	add_child(view)
	await await_idle_frame()
	view.bind_decision(d)
	var chosen_id_label: Label = view.get_node("Overview/ChosenIdLabel")
	assert_bool(chosen_id_label.text.contains("not identity")).is_true()
