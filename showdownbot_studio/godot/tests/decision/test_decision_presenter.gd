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


func _make_file_entry(present: bool = true) -> FileEntryDTO:
	var entry := FileEntryDTO.new()
	entry.path = "battle.jsonl" if present else null
	entry.present = present
	entry.required = present
	entry.sha256 = "abc" if present else null
	return entry


func _make_files_table() -> FilesTableDTO:
	var table := FilesTableDTO.new()
	table.battle_log = _make_file_entry(true)
	table.decision_trace = _make_file_entry(true)
	table.warnings = _make_file_entry(false)
	table.config_manifest = _make_file_entry(false)
	return table


func _make_privacy() -> PrivacyDTO:
	var privacy := PrivacyDTO.new()
	privacy.profile = "portable-pseudonymous-v1"
	privacy.chat = "excluded"
	privacy.private_messages = "excluded"
	privacy.player_names = "seat-pseudonyms"
	privacy.source_url = "excluded"
	privacy.raw_source_included = false
	return privacy


func _make_source_provenance() -> SourceProvenanceDTO:
	var provenance := SourceProvenanceDTO.new()
	provenance.dirty = false
	provenance.our_side = "p1"
	provenance.config_id = "cfg-1"
	provenance.schedule_hash = "sched"
	provenance.seed_index = 0
	return provenance


func _make_manifest() -> BundleManifestDTO:
	var manifest := BundleManifestDTO.new()
	manifest.schema_major = 1
	manifest.schema_minor = 0
	manifest.required_capabilities = PackedStringArray(["viewer-v0"])
	manifest.exporter_name = "test-exporter"
	manifest.exporter_version = "0.0.0"
	manifest.battle_id = "battle-1"
	manifest.format_id = "gen9ou"
	manifest.git_sha = "deadbeef"
	manifest.config_hash = "cfg-hash"
	manifest.trace_schema_version = BundleMode.TRACE_VERSION_V3
	manifest.privacy = _make_privacy()
	manifest.source_hashes_battle_log = "hash-bl"
	manifest.source_hashes_decision_trace = "hash-dt"
	manifest.files = _make_files_table()
	manifest.source_provenance = _make_source_provenance()
	return manifest


func _make_event(protocol_index: int, type: String, fields: Dictionary = {}) -> BattleEventDTO:
	var e := BattleEventDTO.new()
	e.protocol_index = protocol_index
	e.type = type
	for key in fields.keys():
		e.set(key, fields[key])
	return e


func _make_decision(decision_index: int, request_protocol_index: Variant, valid: bool) -> DecisionRowDTO:
	var d := DecisionRowDTO.new()
	d.decision_index = decision_index
	d.request_protocol_index = request_protocol_index
	d.decision_valid = valid
	d.turn_number = 1
	d.decision_phase = BundleMode.PHASE_REGULAR_TURN
	d.decision_latency_ms = 0.0
	d.observable_state_hash = "obs"
	d.request_hash = "req"
	d.state_summary = {}
	d.normalized_action = {}
	d.actual_choose_string = "move 1"
	d.fallback_used = false
	d.warning_count = 0
	return d


func _make_replay_only_bundle(events: Array) -> BundleDTO:
	var bundle := BundleDTO.new()
	bundle.declared_mode = BundleMode.REPLAY_ONLY
	bundle.effective_mode = BundleMode.REPLAY_ONLY
	bundle.replay_trusted = true
	bundle.trace_trusted = false
	bundle.manifest = _make_manifest()
	bundle.warnings = []
	bundle.downgrade_warnings = []
	bundle.config_manifest = null
	var sealed_events: Array = []
	for item in events:
		var e: BattleEventDTO = item
		e.seal()
		sealed_events.append(e)
	bundle.battle_events = sealed_events
	bundle.decisions = []
	bundle.seal()
	return bundle


func _make_minimal_bundle_with_decisions(decisions: Array, events: Array) -> BundleDTO:
	var bundle := BundleDTO.new()
	bundle.declared_mode = BundleMode.REPLAY_TRACE
	bundle.effective_mode = BundleMode.REPLAY_TRACE
	bundle.replay_trusted = true
	bundle.trace_trusted = true
	bundle.manifest = _make_manifest()
	bundle.warnings = []
	bundle.downgrade_warnings = []
	bundle.config_manifest = null
	var sealed_events: Array = []
	for item in events:
		var e: BattleEventDTO = item
		e.seal()
		sealed_events.append(e)
	var sealed_decisions: Array = []
	for item in decisions:
		var d: DecisionRowDTO = item
		d.seal()
		sealed_decisions.append(d)
	bundle.battle_events = sealed_events
	bundle.decisions = sealed_decisions
	bundle.seal()
	return bundle


func test_empty_candidates_no_chosen_row() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var d: DecisionRowDTO = null
	for row in bundle.decisions:
		if row.candidates.is_empty():
			d = row
			break
	assert_object(d).is_not_null()
	assert_int(DecisionPresenter.resolve_chosen_row_index(d)).is_equal(-1)


func test_valid_chosen_key_unique() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var d: DecisionRowDTO = null
	for row in bundle.decisions:
		if row.candidates.size() >= 1 and row.chosen_candidate_key != null:
			d = row
			break
	assert_object(d).is_not_null()
	var chosen := DecisionPresenter.resolve_chosen_row_index(d)
	assert_int(chosen).is_greater(-1)
	assert_str(str(d.candidates[chosen].candidate_key)).is_equal(str(d.chosen_candidate_key))


func test_invalid_decision_no_highlight() -> void:
	var d := DecisionRowDTO.new()
	d.decision_index = 9
	d.turn_number = 1
	d.decision_phase = BundleMode.PHASE_REGULAR_TURN
	d.decision_latency_ms = 1.0
	d.observable_state_hash = "obs"
	d.request_hash = "req"
	d.state_summary = {}
	d.normalized_action = {}
	d.actual_choose_string = "move 1"
	d.candidates = [
		_make_candidate("A", 1, 1.0, "key-a"),
		_make_candidate("B", 2, 0.5, "key-b"),
	]
	d.chosen_candidate_key = "key-missing"
	d.fallback_used = false
	d.warning_count = 0
	d.decision_valid = false
	d.seal()
	assert_int(DecisionPresenter.resolve_chosen_row_index(d)).is_equal(-1)


func test_never_label_matches_chosen_id() -> void:
	var d := DecisionRowDTO.new()
	d.decision_index = 9
	d.turn_number = 1
	d.decision_phase = BundleMode.PHASE_REGULAR_TURN
	d.decision_latency_ms = 1.0
	d.observable_state_hash = "obs"
	d.request_hash = "req"
	d.state_summary = {}
	d.normalized_action = {}
	d.actual_choose_string = "move 1"
	d.candidates = [_make_candidate("looks-chosen", 1, 1.0, "structural-a")]
	d.chosen_candidate_key = "structural-missing"
	d.chosen_candidate_id = "looks-chosen"
	d.fallback_used = false
	d.warning_count = 0
	d.decision_valid = true  # must reach key scan; label must not win
	d.seal()
	assert_int(DecisionPresenter.resolve_chosen_row_index(d)).is_equal(-1)


func test_aggregation_all_null_label() -> void:
	var bundle := _fixture_bundle("bundles/fixture-03")
	var d: DecisionRowDTO = bundle.decisions[0]
	assert_str(DecisionPresenter.aggregation_headline(d)).is_equal(
		DecisionPresenter.AGGREGATION_NOT_RECORDED
	)


func test_optional_null_is_not_recorded() -> void:
	assert_str(DecisionPresenter.optional_text(null)).is_equal(DecisionPresenter.NOT_RECORDED)


func test_sort_modes_preserve_chosen_identity() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var d: DecisionRowDTO = null
	for row in bundle.decisions:
		if row.candidates.size() >= 2 and row.decision_valid:
			d = row
			break
	assert_object(d).is_not_null()
	var chosen := DecisionPresenter.resolve_chosen_row_index(d)
	assert_int(chosen).is_greater(-1)
	var key := str(d.candidates[chosen].candidate_key)
	for mode in [
		DecisionPresenter.SORT_RANK, DecisionPresenter.SORT_SCORE,
		DecisionPresenter.SORT_LABEL, DecisionPresenter.SORT_KEY,
		DecisionPresenter.SORT_CHOSEN_FIRST,
	]:
		var order := DecisionPresenter.sorted_candidate_indices(d, mode)
		var seen := false
		for idx in order:
			if int(idx) == chosen:
				seen = true
				assert_str(str(d.candidates[int(idx)].candidate_key)).is_equal(key)
		assert_bool(seen).is_true()


func test_next_close_skips_null_margin() -> void:
	var d0 := DecisionRowDTO.new()
	d0.decision_index = 0
	d0.turn_number = 1
	d0.decision_phase = BundleMode.PHASE_REGULAR_TURN
	d0.decision_latency_ms = 0.0
	d0.observable_state_hash = "o"
	d0.request_hash = "r"
	d0.state_summary = {}
	d0.normalized_action = {}
	d0.actual_choose_string = ""
	d0.candidates = []
	d0.top1_top2_margin = null
	d0.fallback_used = false
	d0.warning_count = 0
	d0.decision_valid = true
	d0.seal()
	var d1 := DecisionRowDTO.new()
	d1.decision_index = 1
	d1.turn_number = 1
	d1.decision_phase = BundleMode.PHASE_REGULAR_TURN
	d1.decision_latency_ms = 0.0
	d1.observable_state_hash = "o"
	d1.request_hash = "r"
	d1.state_summary = {}
	d1.normalized_action = {}
	d1.actual_choose_string = "move 1"
	d1.candidates = [
		_make_candidate("A", 1, 10.0, "a"),
		_make_candidate("B", 2, 7.0, "b"),
	]
	d1.chosen_candidate_key = "a"
	d1.top1_top2_margin = 3.0
	d1.fallback_used = false
	d1.warning_count = 0
	d1.decision_valid = true
	d1.seal()
	var bundle := BundleDTO.new()
	bundle.declared_mode = BundleMode.TRACE_ONLY
	bundle.effective_mode = BundleMode.TRACE_ONLY
	bundle.replay_trusted = false
	bundle.trace_trusted = true
	bundle.manifest = _make_manifest()
	bundle.warnings = []
	bundle.downgrade_warnings = []
	bundle.config_manifest = null
	bundle.battle_events = []
	bundle.decisions = [d0, d1]
	bundle.seal()
	var row := DecisionPresenter.find_next_nav_row(bundle, -1, "close")
	assert_int(row).is_equal(1)
	assert_float(float(bundle.decisions[row].top1_top2_margin)).is_equal(3.0)


func test_next_fallback_fixture03() -> void:
	var bundle := _fixture_bundle("bundles/fixture-03")
	var start_id: int = bundle.decisions[
		DecisionPresenter.first_row_by_decision_index(bundle)
	].decision_index
	var row := DecisionPresenter.find_next_nav_row(bundle, start_id - 1, "fallback")
	assert_int(row).is_greater(-1)
	assert_bool(bundle.decisions[row].fallback_used).is_true()


func test_next_warning_when_count_positive() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var start_id: int = bundle.decisions[
		DecisionPresenter.first_row_by_decision_index(bundle)
	].decision_index
	var row := DecisionPresenter.find_next_nav_row(bundle, start_id - 1, "warning")
	assert_int(row).is_greater(-1)
	assert_int(bundle.decisions[row].warning_count).is_greater(0)


func test_timeline_entry_for_decision_row() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var replay := BattleTimeline.build(bundle)
	for row_i in range(bundle.decisions.size()):
		var entry_i := DecisionPresenter.timeline_entry_for_decision_row(replay, row_i)
		if entry_i < 0:
			continue
		var entry: TimelineEntryDTO = replay.entries[entry_i]
		assert_int(entry.decision_row_index).is_equal(row_i)
		assert_bool(
			entry.kind == TimelineEntryKind.DECISION
			or entry.kind == TimelineEntryKind.DECISION_WITHOUT_REPLAY_EVENT
		).is_true()


func test_first_row_by_decision_index() -> void:
	var d5 := DecisionRowDTO.new()
	d5.decision_index = 5
	d5.turn_number = 1
	d5.decision_phase = BundleMode.PHASE_REGULAR_TURN
	d5.decision_latency_ms = 0.0
	d5.observable_state_hash = "o"
	d5.request_hash = "r"
	d5.state_summary = {}
	d5.normalized_action = {}
	d5.actual_choose_string = ""
	d5.candidates = []
	d5.fallback_used = false
	d5.warning_count = 0
	d5.decision_valid = true
	d5.seal()
	var d10 := DecisionRowDTO.new()
	d10.decision_index = 10
	d10.turn_number = 1
	d10.decision_phase = BundleMode.PHASE_REGULAR_TURN
	d10.decision_latency_ms = 0.0
	d10.observable_state_hash = "o"
	d10.request_hash = "r"
	d10.state_summary = {}
	d10.normalized_action = {}
	d10.actual_choose_string = ""
	d10.candidates = []
	d10.fallback_used = false
	d10.warning_count = 0
	d10.decision_valid = true
	d10.seal()
	var d2 := DecisionRowDTO.new()
	d2.decision_index = 2
	d2.turn_number = 1
	d2.decision_phase = BundleMode.PHASE_REGULAR_TURN
	d2.decision_latency_ms = 0.0
	d2.observable_state_hash = "o"
	d2.request_hash = "r"
	d2.state_summary = {}
	d2.normalized_action = {}
	d2.actual_choose_string = ""
	d2.candidates = []
	d2.fallback_used = false
	d2.warning_count = 0
	d2.decision_valid = true
	d2.seal()
	var bundle := BundleDTO.new()
	bundle.declared_mode = BundleMode.TRACE_ONLY
	bundle.effective_mode = BundleMode.TRACE_ONLY
	bundle.replay_trusted = false
	bundle.trace_trusted = true
	bundle.manifest = _make_manifest()
	bundle.warnings = []
	bundle.downgrade_warnings = []
	bundle.config_manifest = null
	bundle.battle_events = []
	bundle.decisions = [d5, d10, d2]
	bundle.seal()
	var row := DecisionPresenter.first_row_by_decision_index(bundle)
	assert_int(row).is_equal(2)
	assert_int(bundle.decisions[row].decision_index).is_equal(2)
