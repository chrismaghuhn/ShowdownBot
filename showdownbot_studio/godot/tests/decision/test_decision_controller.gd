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


func _make_untrusted_bundle_with_decisions(decisions: Array, events: Array) -> BundleDTO:
	# Constructed only: decisions present but trace_trusted=false (loader would not emit this).
	var bundle := BundleDTO.new()
	bundle.declared_mode = BundleMode.REPLAY_TRACE
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
	var sealed_decisions: Array = []
	for item in decisions:
		var d: DecisionRowDTO = item
		d.seal()
		sealed_decisions.append(d)
	bundle.battle_events = sealed_events
	bundle.decisions = sealed_decisions
	bundle.seal()
	return bundle


func test_timeline_decision_selects_row() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var replay := BattleTimeline.build(bundle)
	var ctl := TimelineController.new()
	add_child(ctl)
	var dec := DecisionController.new()
	add_child(dec)
	dec.reset(bundle, ctl)
	ctl.reset(replay, bundle)
	await await_idle_frame()
	var decision_entry := -1
	var expected_row := -1
	for i in range(replay.entries.size()):
		var entry: TimelineEntryDTO = replay.entries[i]
		if entry.kind == TimelineEntryKind.DECISION:
			decision_entry = i
			expected_row = entry.decision_row_index
			break
	assert_int(decision_entry).is_greater(-1)
	ctl.select(decision_entry)
	await await_idle_frame()
	assert_int(dec.get_selected_decision_row_index()).is_equal(expected_row)


func test_timeline_event_keeps_row() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var replay := BattleTimeline.build(bundle)
	var ctl := TimelineController.new()
	add_child(ctl)
	var dec := DecisionController.new()
	add_child(dec)
	dec.reset(bundle, ctl)
	ctl.reset(replay, bundle)
	await await_idle_frame()
	var decision_entry := -1
	for i in range(replay.entries.size()):
		if replay.entries[i].kind == TimelineEntryKind.DECISION:
			decision_entry = i
			break
	assert_int(decision_entry).is_greater(-1)
	ctl.select(decision_entry)
	await await_idle_frame()
	var row_after_decision := dec.get_selected_decision_row_index()
	var event_entry := -1
	for i in range(replay.entries.size()):
		if replay.entries[i].kind == TimelineEntryKind.EVENT:
			event_entry = i
			break
	ctl.select(event_entry)
	await await_idle_frame()
	assert_int(dec.get_selected_decision_row_index()).is_equal(row_after_decision)


func test_select_row_syncs_timeline() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var replay := BattleTimeline.build(bundle)
	var ctl := TimelineController.new()
	add_child(ctl)
	var dec := DecisionController.new()
	add_child(dec)
	ctl.reset(replay, bundle)
	dec.reset(bundle, ctl)
	var cursor_after_reset := ctl.get_selected_entry_index()
	var target_row := 0
	for i in range(bundle.decisions.size()):
		if bundle.decisions[i].candidates.size() > 0:
			target_row = i
			break
	dec.select_decision_row(target_row)
	await await_idle_frame()
	var entry := DecisionPresenter.timeline_entry_for_decision_row(replay, target_row)
	assert_int(ctl.get_selected_entry_index()).is_equal(entry)
	assert_int(cursor_after_reset).is_equal(0)


func test_clear_emits_minus_one() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var replay := BattleTimeline.build(bundle)
	var ctl := TimelineController.new()
	add_child(ctl)
	var dec := DecisionController.new()
	add_child(dec)
	dec.reset(bundle, ctl)
	ctl.reset(replay, bundle)
	await await_idle_frame()
	var emitted := [-2]
	dec.decision_selection_changed.connect(func(row_i: int) -> void: emitted[0] = row_i)
	dec.clear()
	assert_int(dec.get_selected_decision_row_index()).is_equal(-1)
	assert_int(emitted[0]).is_equal(-1)


func test_replay_only_reset_no_selection() -> void:
	var events: Array = [_make_event(1, "turn", {"amount": 1})]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	var ctl := TimelineController.new()
	add_child(ctl)
	var dec := DecisionController.new()
	add_child(dec)
	ctl.reset(replay, bundle)
	dec.reset(bundle, ctl)
	await await_idle_frame()
	assert_int(dec.get_selected_decision_row_index()).is_equal(-1)


func test_untrusted_bundle_rejects_navigation() -> void:
	# B1: DecisionController must fail-closed without relying on DecisionWorkspace.
	var events: Array = [_make_event(1, "turn", {"amount": 1})]
	var decisions: Array = [_make_decision(0, 1, true), _make_decision(1, 1, true)]
	var trusted := _make_minimal_bundle_with_decisions(decisions, events)
	var untrusted := _make_untrusted_bundle_with_decisions(decisions, events)
	# Build timeline from trusted shape so DECISION entries exist; controller gets untrusted.
	var replay := BattleTimeline.build(trusted)
	var ctl := TimelineController.new()
	add_child(ctl)
	var dec := DecisionController.new()
	add_child(dec)
	ctl.reset(replay, trusted)
	dec.reset(untrusted, ctl)
	await await_idle_frame()
	assert_int(dec.get_selected_decision_row_index()).is_equal(-1)
	dec.select_decision_row(0)
	assert_int(dec.get_selected_decision_row_index()).is_equal(-1)
	dec.jump_next("decision")
	assert_int(dec.get_selected_decision_row_index()).is_equal(-1)
	dec.jump_prev_decision()
	assert_int(dec.get_selected_decision_row_index()).is_equal(-1)
	assert_object(dec.get_selected_decision()).is_null()
	# Timeline DECISION entry must not resurrect a selection (echo path gated by trust).
	var decision_entry := -1
	for i in range(replay.entries.size()):
		if replay.entries[i].kind == TimelineEntryKind.DECISION \
				or replay.entries[i].kind == TimelineEntryKind.DECISION_WITHOUT_REPLAY_EVENT:
			decision_entry = i
			break
	assert_int(decision_entry).is_greater(-1)
	ctl.select(decision_entry)
	await await_idle_frame()
	assert_int(dec.get_selected_decision_row_index()).is_equal(-1)


func test_reset_does_not_move_timeline_cursor() -> void:
	var events: Array = [
		_make_event(1, "turn", {"amount": 1}),
		_make_event(2, "turn", {"amount": 2}),
	]
	var decisions: Array = [_make_decision(5, 2, true)]
	var bundle := _make_minimal_bundle_with_decisions(decisions, events)
	var replay := BattleTimeline.build(bundle)
	var ctl := TimelineController.new()
	add_child(ctl)
	var dec := DecisionController.new()
	add_child(dec)
	ctl.reset(replay, bundle)
	assert_int(ctl.get_selected_entry_index()).is_equal(0)
	assert_str(replay.entries[0].kind).is_equal(TimelineEntryKind.EVENT)
	dec.reset(bundle, ctl)
	await await_idle_frame()
	assert_int(ctl.get_selected_entry_index()).is_equal(0)
	assert_int(dec.get_selected_decision().decision_index).is_equal(5)


func test_jump_next_fallback() -> void:
	var bundle := _fixture_bundle("bundles/fixture-03")
	var replay := BattleTimeline.build(bundle)
	var ctl := TimelineController.new()
	add_child(ctl)
	var dec := DecisionController.new()
	add_child(dec)
	ctl.reset(replay, bundle)
	dec.reset(bundle, ctl)
	await await_idle_frame()
	var start_row := DecisionPresenter.first_row_by_decision_index(bundle)
	dec.select_decision_row(start_row)
	dec.jump_next("fallback")
	await await_idle_frame()
	assert_bool(bundle.decisions[dec.get_selected_decision_row_index()].fallback_used).is_true()


func test_nav_buttons_no_wrap() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var replay := BattleTimeline.build(bundle)
	var ctl := TimelineController.new()
	add_child(ctl)
	var dec := DecisionController.new()
	add_child(dec)
	ctl.reset(replay, bundle)
	dec.reset(bundle, ctl)
	await await_idle_frame()
	var last_row := -1
	var last_id := -2147483648
	for i in range(bundle.decisions.size()):
		var d: DecisionRowDTO = bundle.decisions[i]
		if d.decision_index > last_id:
			last_id = d.decision_index
			last_row = i
	dec.select_decision_row(last_row)
	assert_bool(dec.has_next("decision")).is_false()
