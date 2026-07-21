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


func test_fixture01_switch_applies_species_and_hp() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var replay := BattleTimeline.build(bundle)
	var board := ReplayPresenter.build_board(bundle, replay, 2)
	assert_bool(board.has_replay).is_true()
	assert_bool(board.has_recorded_state).is_true()
	assert_str(str(board.get_slot("p1", "a")["species"])).is_equal("Pikachu")
	assert_int(int(board.get_slot("p1", "a")["hp_current"])).is_equal(35)
	assert_int(int(board.get_slot("p1", "a")["hp_maximum"])).is_equal(35)


func test_fixture01_decision_before_first_event_keeps_has_replay() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var replay := BattleTimeline.build(bundle)
	var board := ReplayPresenter.build_board(bundle, replay, 0)
	assert_bool(board.has_replay).is_true()
	assert_bool(board.has_recorded_state).is_false()
	assert_object(board.get_slot("p1", "a")["species"]).is_null()


func test_trace_only_board_empty() -> void:
	var bundle := _fixture_bundle("bundles/fixture-05")
	var replay := BattleTimeline.build(bundle)
	var board := ReplayPresenter.build_board(bundle, replay, 0)
	assert_bool(board.has_replay).is_false()
	assert_bool(board.has_recorded_state).is_false()
	assert_object(board.get_slot("p1", "a")["species"]).is_null()


func test_replay_only_board_from_events() -> void:
	var bundle := _fixture_bundle("bundles/fixture-04")
	var replay := BattleTimeline.build(bundle)
	var at_switch := ReplayPresenter.build_board(bundle, replay, 1)
	assert_bool(at_switch.has_replay).is_true()
	assert_str(str(at_switch.get_slot("p1", "a")["species"])).is_equal("Pikachu")
	assert_int(int(at_switch.get_slot("p1", "a")["hp_current"])).is_equal(35)
	assert_int(int(at_switch.get_slot("p1", "a")["hp_maximum"])).is_equal(35)
	var at_move := ReplayPresenter.build_board(bundle, replay, 3)
	assert_str(str(at_move.last_move)).is_equal("Tackle")
	assert_int(int(at_move.turn_number)).is_equal(2)


func test_decision_cursor_does_not_invent_hp() -> void:
	var events: Array = [
		_make_event(1, "switch", {
			"pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": "Pikachu",
			"hp_current": 35, "hp_maximum": 35, "hp_fainted": false,
		}),
		_make_event(2, "damage", {
			"pokemon_side": "p1", "pokemon_slot": "a",
			"hp_current": 20, "hp_maximum": 35, "hp_fainted": false,
		}),
	]
	var decisions: Array = [
		_make_decision(1, 3, true),
	]
	var bundle := _make_minimal_bundle_with_decisions(decisions, events)
	var replay := BattleTimeline.build(bundle)
	var decision_i := -1
	for i in range(replay.entries.size()):
		if replay.entries[i].kind == TimelineEntryKind.DECISION:
			decision_i = i
			break
	assert_int(decision_i).is_greater(0)
	var at_decision := ReplayPresenter.build_board(bundle, replay, decision_i)
	var at_prior_event := ReplayPresenter.build_board(bundle, replay, decision_i - 1)
	assert_that(at_decision.get_slot("p1", "a")["hp_current"]).is_equal(
		at_prior_event.get_slot("p1", "a")["hp_current"]
	)
	assert_that(at_decision.get_slot("p1", "a")["hp_maximum"]).is_equal(
		at_prior_event.get_slot("p1", "a")["hp_maximum"]
	)
	assert_that(at_decision.get_slot("p1", "a")["species"]).is_equal(
		at_prior_event.get_slot("p1", "a")["species"]
	)


func test_damage_heal_sethp_update_hp() -> void:
	var events: Array = [
		_make_event(1, "switch", {
			"pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": "Pikachu",
			"hp_current": 35, "hp_maximum": 35, "hp_fainted": false,
		}),
		_make_event(2, "damage", {
			"pokemon_side": "p1", "pokemon_slot": "a",
			"hp_current": 20, "hp_maximum": 35, "hp_fainted": false,
		}),
		_make_event(3, "heal", {
			"pokemon_side": "p1", "pokemon_slot": "a",
			"hp_current": 30, "hp_maximum": 35, "hp_fainted": false,
		}),
		_make_event(4, "sethp", {
			"pokemon_side": "p1", "pokemon_slot": "a",
			"hp_current": 10, "hp_maximum": 35, "hp_fainted": false,
		}),
	]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	assert_int(int(ReplayPresenter.build_board(bundle, replay, 1).get_slot("p1", "a")["hp_current"])).is_equal(20)
	assert_int(int(ReplayPresenter.build_board(bundle, replay, 2).get_slot("p1", "a")["hp_current"])).is_equal(30)
	assert_int(int(ReplayPresenter.build_board(bundle, replay, 3).get_slot("p1", "a")["hp_current"])).is_equal(10)


func test_faint_and_status_curestatus() -> void:
	var events: Array = [
		_make_event(1, "switch", {
			"pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": "Pikachu",
			"hp_current": 35, "hp_maximum": 35, "hp_fainted": false,
		}),
		_make_event(2, "status", {
			"pokemon_side": "p1", "pokemon_slot": "a", "details": "brn",
		}),
		_make_event(3, "curestatus", {
			"pokemon_side": "p1", "pokemon_slot": "a",
		}),
		_make_event(4, "faint", {"pokemon_side": "p1", "pokemon_slot": "a"}),
	]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	var after_status := ReplayPresenter.build_board(bundle, replay, 1)
	assert_str(str(after_status.get_slot("p1", "a")["hp_status"])).is_equal("brn")
	var after_cure := ReplayPresenter.build_board(bundle, replay, 2)
	assert_object(after_cure.get_slot("p1", "a")["hp_status"]).is_null()
	var after_faint := ReplayPresenter.build_board(bundle, replay, 3)
	assert_bool(bool(after_faint.get_slot("p1", "a")["hp_fainted"])).is_true()
	assert_int(int(after_faint.get_slot("p1", "a")["hp_current"])).is_equal(0)


func test_switch_replaces_prior_status() -> void:
	var events: Array = [
		_make_event(1, "switch", {
			"pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": "BurnedMon",
			"hp_current": 100, "hp_maximum": 100, "hp_fainted": false, "hp_status": "brn",
		}),
		_make_event(2, "switch", {
			"pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": "HealthyMon",
			"hp_current": 80, "hp_maximum": 80, "hp_fainted": false, "hp_status": null,
		}),
	]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	var board := ReplayPresenter.build_board(bundle, replay, 1)
	assert_str(str(board.get_slot("p1", "a")["species"])).is_equal("HealthyMon")
	assert_object(board.get_slot("p1", "a")["hp_status"]).is_null()


func test_faint_forces_zero_hp_after_positive() -> void:
	var events: Array = [
		_make_event(1, "switch", {
			"pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": "Pikachu",
			"hp_current": 35, "hp_maximum": 35, "hp_fainted": false,
		}),
		_make_event(2, "damage", {
			"pokemon_side": "p1", "pokemon_slot": "a",
			"hp_current": 20, "hp_maximum": 35, "hp_fainted": false,
		}),
		_make_event(3, "faint", {"pokemon_side": "p1", "pokemon_slot": "a"}),
	]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	var board := ReplayPresenter.build_board(bundle, replay, 2)
	assert_bool(bool(board.get_slot("p1", "a")["hp_fainted"])).is_true()
	assert_int(int(board.get_slot("p1", "a")["hp_current"])).is_equal(0)


func test_unknown_side_is_noop() -> void:
	var events: Array = [
		_make_event(1, "switch", {
			"pokemon_side": "p3", "pokemon_slot": "a", "pokemon_species": "X",
			"hp_current": 10, "hp_maximum": 10, "hp_fainted": false,
		}),
	]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	var board := ReplayPresenter.build_board(bundle, replay, 0)
	assert_object(board.get_slot("p1", "a")["species"]).is_null()
	assert_object(board.get_slot("p2", "a")["species"]).is_null()


func test_numeric_slot_is_noop() -> void:
	var events: Array = [
		_make_event(1, "switch", {
			"pokemon_side": "p1", "pokemon_slot": 0, "pokemon_species": "X",
			"hp_current": 10, "hp_maximum": 10, "hp_fainted": false,
		}),
	]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	var board := ReplayPresenter.build_board(bundle, replay, 0)
	assert_object(board.get_slot("p1", "a")["species"]).is_null()
	assert_object(board.get_slot("p1", "b")["species"]).is_null()


func test_weather_terrain_vs_trick_room_field_conditions() -> void:
	var events: Array = [
		_make_event(1, "fieldstart", {"value": "Electric Terrain"}),
		_make_event(2, "fieldstart", {"value": "Trick Room"}),
		_make_event(3, "fieldend", {"value": "Trick Room"}),
		_make_event(4, "fieldend", {"value": "Electric Terrain"}),
	]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	var after_both := ReplayPresenter.build_board(bundle, replay, 1)
	assert_str(str(after_both.terrain)).is_equal("Electric Terrain")
	assert_int(after_both.field_conditions.size()).is_equal(1)
	assert_str(after_both.field_conditions[0]).is_equal("Trick Room")
	var after_tr_end := ReplayPresenter.build_board(bundle, replay, 2)
	assert_str(str(after_tr_end.terrain)).is_equal("Electric Terrain")
	assert_int(after_tr_end.field_conditions.size()).is_equal(0)
	var after_terrain_end := ReplayPresenter.build_board(bundle, replay, 3)
	assert_object(after_terrain_end.terrain).is_null()
	assert_int(after_terrain_end.field_conditions.size()).is_equal(0)


func test_side_conditions_start_end() -> void:
	var events: Array = [
		_make_event(1, "sidestart", {"side": "p1", "value": "Stealth Rock"}),
		_make_event(2, "sidestart", {"side": "p2", "details": "Spikes"}),
		_make_event(3, "sideend", {"side": "p1", "value": "Stealth Rock"}),
	]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	var after_both := ReplayPresenter.build_board(bundle, replay, 1)
	assert_int(after_both.side_conditions["p1"].size()).is_equal(1)
	assert_str(after_both.side_conditions["p1"][0]).is_equal("Stealth Rock")
	assert_int(after_both.side_conditions["p2"].size()).is_equal(1)
	assert_str(after_both.side_conditions["p2"][0]).is_equal("Spikes")
	var after_end := ReplayPresenter.build_board(bundle, replay, 2)
	assert_int(after_end.side_conditions["p1"].size()).is_equal(0)
	assert_int(after_end.side_conditions["p2"].size()).is_equal(1)


func test_detailschange_updates_species() -> void:
	var events: Array = [
		_make_event(1, "switch", {
			"pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": "Aegislash",
			"hp_current": 50, "hp_maximum": 50, "hp_fainted": false,
		}),
		_make_event(2, "detailschange", {
			"pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": "Aegislash-Blade",
			"hp_current": 40, "hp_maximum": 50,
		}),
	]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	var board := ReplayPresenter.build_board(bundle, replay, 1)
	assert_str(str(board.get_slot("p1", "a")["species"])).is_equal("Aegislash-Blade")
	assert_int(int(board.get_slot("p1", "a")["hp_current"])).is_equal(40)
	assert_int(int(board.get_slot("p1", "a")["hp_maximum"])).is_equal(50)


func test_reverse_navigation_drops_future_state() -> void:
	var events: Array = [
		_make_event(1, "switch", {
			"pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": "Pikachu",
			"hp_current": 35, "hp_maximum": 35, "hp_fainted": false,
		}),
		_make_event(2, "damage", {
			"pokemon_side": "p1", "pokemon_slot": "a",
			"hp_current": 20, "hp_maximum": 35, "hp_fainted": false,
		}),
		_make_event(3, "status", {
			"pokemon_side": "p1", "pokemon_slot": "a", "details": "brn",
		}),
	]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	var at_end := ReplayPresenter.build_board(bundle, replay, 2)
	assert_int(int(at_end.get_slot("p1", "a")["hp_current"])).is_equal(20)
	assert_str(str(at_end.get_slot("p1", "a")["hp_status"])).is_equal("brn")
	var at_switch := ReplayPresenter.build_board(bundle, replay, 0)
	assert_int(int(at_switch.get_slot("p1", "a")["hp_current"])).is_equal(35)
	assert_object(at_switch.get_slot("p1", "a")["hp_status"]).is_null()


func test_build_board_returns_fresh_model() -> void:
	var events: Array = [
		_make_event(1, "switch", {
			"pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": "Pikachu",
			"hp_current": 35, "hp_maximum": 35, "hp_fainted": false,
		}),
	]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	var a := ReplayPresenter.build_board(bundle, replay, 0)
	var b := ReplayPresenter.build_board(bundle, replay, 0)
	assert_bool(a == b).is_false()
	a.get_slot("p1", "a")["species"] = "Mutated"
	assert_str(str(b.get_slot("p1", "a")["species"])).is_equal("Pikachu")
