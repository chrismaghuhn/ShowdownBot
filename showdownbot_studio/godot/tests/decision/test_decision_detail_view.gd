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
	while not shell.is_settled() and frames < max_frames:
		await await_idle_frame()
		frames += 1
	assert_bool(shell.is_settled()).is_true()


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


func test_candidate_key_label_stays_narrow_and_exposes_full_value_via_tooltip() -> void:
	# Root cause of the "screen shifts right" bug (owner-reported, reproduced):
	# a Label's minimum size includes its full text width unless told
	# otherwise. candidate_key strings run ~286 chars (fixture-01
	# decision_index=1), which alone pushed this label's minimum width past
	# 1900px. §0.8 requires visual truncate + tooltip/full detail, never a
	# truncated copy path — so the full value must still be reachable, just
	# not via the label's on-screen width.
	var view: DecisionDetailView = preload("res://src/decision/decision_detail_view.tscn").instantiate()
	add_child(view)
	await await_idle_frame()
	var long_key := "x".repeat(286)
	var c := _make_candidate("cand-a", 1, 1.0, long_key)
	view.bind_candidate(c)
	await await_idle_frame()
	var label: Label = view.get_node("Candidate/CandidateKeyLabel")
	assert_str(label.tooltip_text).contains(long_key)
	assert_float(label.get_combined_minimum_size().x).is_less(500.0)


func test_chosen_key_label_stays_narrow_and_exposes_full_value_via_tooltip() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var d: DecisionRowDTO = _bundle_decision_by_index(bundle, 1)
	assert_object(d).is_not_null()
	var view: DecisionDetailView = preload("res://src/decision/decision_detail_view.tscn").instantiate()
	add_child(view)
	await await_idle_frame()
	view.bind_decision(d)
	await await_idle_frame()
	var label: Label = view.get_node("Overview/ChosenKeyLabel")
	assert_str(label.tooltip_text).contains(str(d.chosen_candidate_key))
	assert_float(label.get_combined_minimum_size().x).is_less(500.0)


func _bundle_decision_by_index(bundle: BundleDTO, decision_index: int) -> DecisionRowDTO:
	for row in bundle.decisions:
		if row.decision_index == decision_index:
			return row
	return null
