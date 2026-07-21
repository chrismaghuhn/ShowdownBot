extends GdUnitTestSuite

const _WORKSPACE_SCENE := preload("res://src/replay/replay_workspace.tscn")


func after_test() -> void:
	for child in get_children():
		if child is ReplayWorkspace:
			remove_child(child)
			child.free()


func _spawn_workspace() -> ReplayWorkspace:
	var ws: ReplayWorkspace = _WORKSPACE_SCENE.instantiate()
	add_child(ws)
	return ws


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
	table.decision_trace = _make_file_entry(false)
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
	manifest.source_hashes_decision_trace = null
	manifest.files = _make_files_table()
	manifest.source_provenance = _make_source_provenance()
	return manifest


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


func test_empty_trusted_replay_keeps_has_replay_without_banner() -> void:
	var ws := _spawn_workspace()
	await await_idle_frame()
	var bundle := _make_replay_only_bundle([])
	var replay := BattleTimeline.build(bundle)
	assert_bool(replay.replay_trusted).is_true()
	assert_int(replay.entries.size()).is_equal(0)

	ws.reset(replay, bundle)
	await await_idle_frame()

	assert_int(ws.get_timeline_controller().get_selected_entry_index()).is_equal(-1)
	assert_object(ws.get_board_model()).is_not_null()
	assert_bool(ws.get_board_model().has_replay).is_true()
	assert_bool(ws.get_board_view().get_empty_state_visible()).is_false()
	assert_bool(ws.get_timeline_view().get_node("Controls/PrevButton").disabled).is_true()
	assert_bool(ws.get_timeline_view().get_node("Controls/PlayButton").disabled).is_true()
