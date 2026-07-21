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


func _spawn_view() -> TimelineView:
	var view: TimelineView = preload("res://src/timeline/timeline_view.tscn").instantiate()
	add_child(view)
	return view


func test_bind_event_labels_use_type_turn_move() -> void:
	var view := _spawn_view()
	var bundle := _make_replay_only_bundle([
		_make_event(1, "turn", {"amount": 1}),
		_make_event(2, "move", {"details": "Tackle"}),
		_make_event(3, "switch", {
			"pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": "Pikachu",
		}),
	])
	var replay := BattleTimeline.build(bundle)
	view.bind(replay, bundle)
	assert_str(view.get_visible_label(0)).is_equal("turn 1")
	assert_str(view.get_visible_label(1)).is_equal("move Tackle")
	assert_str(view.get_visible_label(2)).is_equal("switch")


func test_bind_decision_labels_use_fachliche_id() -> void:
	var view := _spawn_view()
	var bundle := _make_minimal_bundle_with_decisions([
		_make_decision(2, 5, true),
		_make_decision(7, 12, true),
	], [
		_make_event(4, "turn", {"amount": 1}),
		_make_event(20, "turn", {"amount": 2}),
	])
	var replay := BattleTimeline.build(bundle)
	view.bind(replay, bundle)
	var labels: PackedStringArray = PackedStringArray()
	for i in range(replay.entries.size()):
		labels.append(view.get_visible_label(i))
	assert_bool("decision #2" in labels).is_true()
	assert_bool("decision #7" in labels).is_true()


func test_bind_invalid_decision_suffix() -> void:
	var view := _spawn_view()
	var bundle := _make_minimal_bundle_with_decisions([
		_make_decision(1, null, false),
	], [
		_make_event(4, "turn", {"amount": 1}),
	])
	var replay := BattleTimeline.build(bundle)
	view.bind(replay, bundle)
	var found := false
	for i in range(replay.entries.size()):
		var label := view.get_visible_label(i)
		if label.contains("(invalid)"):
			found = true
			assert_bool(label.contains("decision #1")).is_true()
	assert_bool(found).is_true()


func test_set_loading_shows_and_clears() -> void:
	var view := _spawn_view()
	view.set_loading(true)
	assert_str(view.get_node("LoadingLabel").text).is_equal("Loading...")
	view.set_loading(false)
	assert_str(view.get_node("LoadingLabel").text).is_equal("")


func test_controls_disabled_when_set() -> void:
	var view := _spawn_view()
	view.set_controls_enabled(false)
	assert_bool(view.get_node("Controls/PrevButton").disabled).is_true()
	assert_bool(view.get_node("Controls/NextButton").disabled).is_true()
	assert_bool(view.get_node("Controls/StartButton").disabled).is_true()
	assert_bool(view.get_node("Controls/EndButton").disabled).is_true()
	assert_bool(view.get_node("Controls/PlayButton").disabled).is_true()
	view.set_controls_enabled(true)
	assert_bool(view.get_node("Controls/PrevButton").disabled).is_false()


func test_item_selected_calls_controller_select() -> void:
	var view: TimelineView = preload("res://src/timeline/timeline_view.tscn").instantiate()
	add_child(view)
	var controller := TimelineController.new()
	add_child(controller)
	view.set_controller(controller)
	var bundle := _make_replay_only_bundle([
		_make_event(1, "turn", {"amount": 1}),
		_make_event(2, "turn", {"amount": 2}),
		_make_event(3, "turn", {"amount": 3}),
	])
	var replay := BattleTimeline.build(bundle)
	controller.reset(replay, bundle)
	view.bind(replay, bundle)
	view.get_node("EntryList").select(2)
	view.get_node("EntryList").item_selected.emit(2)
	await await_idle_frame()
	assert_int(controller.get_selected_entry_index()).is_equal(2)
