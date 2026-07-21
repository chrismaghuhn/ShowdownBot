extends GdUnitTestSuite

const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"
const _UNIT_FIXTURES := "res://tests/fixtures/unit"
const _APP_SHELL_SCENE := preload("res://src/workspace/app_shell.tscn")


func _fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_FIXTURES_ROOT.path_join(relative))


func _unit_fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_UNIT_FIXTURES.path_join(relative))


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


func _decision_ids_in_timeline(replay: ReplayDTO, bundle: BundleDTO) -> Array:
	var ids: Array = []
	for e in replay.entries:
		if e.kind == TimelineEntryKind.DECISION or e.kind == TimelineEntryKind.DECISION_WITHOUT_REPLAY_EVENT:
			ids.append(bundle.decisions[e.decision_row_index].decision_index)
	return ids


func test_fixture01_join_order_deterministic() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var a: ReplayDTO = BattleTimeline.build(bundle)
	var b: ReplayDTO = BattleTimeline.build(bundle)
	assert_int(a.entries.size()).is_equal(b.entries.size())
	assert_str(a.entries[0].kind).is_equal(TimelineEntryKind.DECISION)
	assert_int(a.entries[0].decision_row_index).is_equal(0)
	assert_str(a.entries[1].kind).is_equal(TimelineEntryKind.EVENT)
	assert_int(a.entries[2].event_index).is_equal(1)  # switch
	for i in range(a.entries.size()):
		assert_str(a.entries[i].kind).is_equal(b.entries[i].kind)
		assert_int(a.entries[i].event_index).is_equal(b.entries[i].event_index)
		assert_int(a.entries[i].decision_row_index).is_equal(b.entries[i].decision_row_index)
		assert_that(a.entries[i].protocol_anchor).is_equal(b.entries[i].protocol_anchor)


func test_fixture01_decision_after_last_event_lt_rpi() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var replay: ReplayDTO = BattleTimeline.build(bundle)
	var last: TimelineEntryDTO = replay.entries[replay.entries.size() - 1]
	assert_str(last.kind).is_equal(TimelineEntryKind.DECISION)
	assert_int(last.decision_row_index).is_equal(2)
	var last_event_pi: int = bundle.battle_events[bundle.battle_events.size() - 1].protocol_index
	var rpi: int = int(bundle.decisions[last.decision_row_index].request_protocol_index)
	assert_bool(last_event_pi < rpi).is_true()
	var prev: TimelineEntryDTO = replay.entries[replay.entries.size() - 2]
	assert_str(prev.kind).is_equal(TimelineEntryKind.EVENT)
	assert_int(prev.event_index).is_equal(bundle.battle_events.size() - 1)


func test_fixture04_replay_only_events_only() -> void:
	var bundle := _fixture_bundle("bundles/fixture-04")
	var replay: ReplayDTO = BattleTimeline.build(bundle)
	assert_int(replay.entries.size()).is_equal(bundle.battle_events.size())
	assert_int(replay.entries.size()).is_greater(0)
	for e in replay.entries:
		assert_str(e.kind).is_equal(TimelineEntryKind.EVENT)
		assert_int(e.decision_row_index).is_equal(-1)


func test_fixture05_trace_only_decisions_without_replay() -> void:
	var bundle := _fixture_bundle("bundles/fixture-05")
	var replay: ReplayDTO = BattleTimeline.build(bundle)
	assert_int(replay.entries.size()).is_equal(bundle.decisions.size())
	assert_int(replay.entries.size()).is_greater(0)
	for e in replay.entries:
		assert_str(e.kind).is_equal(TimelineEntryKind.DECISION_WITHOUT_REPLAY_EVENT)
		assert_int(e.event_index).is_equal(-1)


func test_null_rpi_never_attaches_to_neighbor_event() -> void:
	var bundle := _make_minimal_bundle_with_decisions([
		_make_decision(1, null, true),
	], [
		_make_event(4, "turn", {"amount": 1}),
		_make_event(10, "turn", {"amount": 2}),
	])
	var replay: ReplayDTO = BattleTimeline.build(bundle)
	assert_int(replay.entries.size()).is_equal(3)
	assert_str(replay.entries[0].kind).is_equal(TimelineEntryKind.EVENT)
	assert_str(replay.entries[1].kind).is_equal(TimelineEntryKind.EVENT)
	assert_str(replay.entries[2].kind).is_equal(TimelineEntryKind.DECISION_WITHOUT_REPLAY_EVENT)
	assert_int(replay.entries[2].decision_row_index).is_equal(0)
	assert_that(replay.entries[2].protocol_anchor).is_equal(null)


func test_effective_mode_not_declared_alone() -> void:
	var result: ValidationResult = BundleValidator.validate_dir(
		_unit_fixture_path("unsupported-trace-downgrade")
	)
	assert_object(result.bundle).is_not_null()
	var bundle: BundleDTO = result.bundle
	assert_str(bundle.declared_mode).is_equal(BundleMode.REPLAY_TRACE)
	assert_str(bundle.effective_mode).is_equal(BundleMode.REPLAY_ONLY)
	assert_bool(bundle.replay_trusted).is_true()
	assert_bool(bundle.trace_trusted).is_false()
	var replay: ReplayDTO = BattleTimeline.build(bundle)
	assert_str(replay.declared_mode).is_equal(BundleMode.REPLAY_TRACE)
	assert_str(replay.effective_mode).is_equal(BundleMode.REPLAY_ONLY)
	assert_bool(replay.replay_trusted).is_true()
	assert_bool(replay.trace_trusted).is_false()
	assert_int(replay.entries.size()).is_equal(bundle.battle_events.size())
	for e in replay.entries:
		assert_str(e.kind).is_equal(TimelineEntryKind.EVENT)


func test_invalid_decision_marked_not_dropped() -> void:
	var bundle := _make_minimal_bundle_with_decisions([
		_make_decision(1, 5, false),
	], [
		_make_event(4, "turn", {"amount": 1}),
		_make_event(10, "turn", {"amount": 2}),
	])
	assert_bool(bundle.decisions[0].decision_valid).is_false()
	var replay: ReplayDTO = BattleTimeline.build(bundle)
	var found := false
	for e in replay.entries:
		if e.kind == TimelineEntryKind.DECISION and e.decision_row_index == 0:
			found = true
	assert_bool(found).is_true()


func test_noncontiguous_decision_ids_preserve_row_index() -> void:
	var bundle := _make_minimal_bundle_with_decisions([
		_make_decision(2, 10, true),
		_make_decision(7, 20, true),
	], [
		_make_event(0, "turn", {"amount": 1}),
		_make_event(15, "turn", {"amount": 2}),
	])
	var replay: ReplayDTO = BattleTimeline.build(bundle)
	var decision_entries: Array = []
	for e in replay.entries:
		if e.kind == TimelineEntryKind.DECISION:
			decision_entries.append(e)
	assert_int(decision_entries.size()).is_equal(2)
	assert_int(decision_entries[0].decision_row_index).is_equal(0)
	assert_int(decision_entries[1].decision_row_index).is_equal(1)
	assert_int(bundle.decisions[decision_entries[0].decision_row_index].decision_index).is_equal(2)
	assert_int(bundle.decisions[decision_entries[1].decision_row_index].decision_index).is_equal(7)


func test_same_rpi_decisions_stay_ascending() -> void:
	var bundle := _make_minimal_bundle_with_decisions([
		_make_decision(2, 10, true),
		_make_decision(7, 10, true),
	], [
		_make_event(4, "turn", {"amount": 1}),
		_make_event(20, "turn", {"amount": 2}),
	])
	var replay := BattleTimeline.build(bundle)
	assert_that(_decision_ids_in_timeline(replay, bundle)).is_equal([2, 7])


func test_same_event_gap_different_rpi_stay_ascending() -> void:
	var bundle := _make_minimal_bundle_with_decisions([
		_make_decision(2, 5, true),
		_make_decision(7, 12, true),
	], [
		_make_event(4, "turn", {"amount": 1}),
		_make_event(20, "turn", {"amount": 2}),
	])
	var replay := BattleTimeline.build(bundle)
	# Both land after event pi=4 and before event pi=20; ascending ids preserved.
	assert_that(_decision_ids_in_timeline(replay, bundle)).is_equal([2, 7])
	assert_str(replay.entries[0].kind).is_equal(TimelineEntryKind.EVENT)
	assert_str(replay.entries[1].kind).is_equal(TimelineEntryKind.DECISION)
	assert_str(replay.entries[2].kind).is_equal(TimelineEntryKind.DECISION)
	assert_str(replay.entries[3].kind).is_equal(TimelineEntryKind.EVENT)


func test_nonnull_rpi_inserts_before_null_rpi_tail() -> void:
	# Process ascending: id=2 null-rpi first (tail), then id=7 non-null rpi.
	# Non-null must still insert before the null-rpi tail, not after it.
	var bundle := _make_minimal_bundle_with_decisions([
		_make_decision(2, null, true),
		_make_decision(7, 5, true),
	], [
		_make_event(4, "turn", {"amount": 1}),
		_make_event(20, "turn", {"amount": 2}),
	])
	var replay := BattleTimeline.build(bundle)
	var kinds: Array = []
	var ids: Array = []
	for e in replay.entries:
		kinds.append(e.kind)
		if e.kind != TimelineEntryKind.EVENT:
			ids.append(bundle.decisions[e.decision_row_index].decision_index)
	assert_that(ids).is_equal([7, 2])
	assert_str(kinds[kinds.size() - 1]).is_equal(TimelineEntryKind.DECISION_WITHOUT_REPLAY_EVENT)
