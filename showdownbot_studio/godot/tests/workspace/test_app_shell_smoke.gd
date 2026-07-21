extends GdUnitTestSuite

const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"
const _UNIT_FIXTURES := "res://tests/fixtures/unit"
const _APP_SHELL_SCENE := preload("res://src/workspace/app_shell.tscn")


func _fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_FIXTURES_ROOT.path_join(relative))


func _unit_fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_UNIT_FIXTURES.path_join(relative))


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


func test_fixture01_open_trusted() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)

	assert_str(shell.get_declared_mode()).is_equal(BundleMode.REPLAY_TRACE)
	assert_str(shell.get_effective_mode()).is_equal(BundleMode.REPLAY_TRACE)
	assert_bool(shell.get_trace_trusted()).is_true()
	assert_bool(shell.get_replay_trusted()).is_true()
	assert_int(shell.get_decision_count()).is_equal(3)
	assert_str(shell.get_status_text()).contains("REPLAY_TRACE")


func test_fixture04_replay_only_effective_mode() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-04"))
	await _await_shell_settled(shell)

	assert_str(shell.get_declared_mode()).is_equal(BundleMode.REPLAY_ONLY)
	assert_str(shell.get_effective_mode()).is_equal(BundleMode.REPLAY_ONLY)
	assert_bool(shell.get_replay_trusted()).is_true()
	assert_bool(shell.get_trace_trusted()).is_false()
	assert_str(shell.get_status_text()).contains("REPLAY_ONLY")


func test_fixture05_trace_only_effective_mode() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-05"))
	await _await_shell_settled(shell)

	assert_str(shell.get_declared_mode()).is_equal(BundleMode.TRACE_ONLY)
	assert_str(shell.get_effective_mode()).is_equal(BundleMode.TRACE_ONLY)
	assert_bool(shell.get_trace_trusted()).is_true()
	assert_bool(shell.get_replay_trusted()).is_false()
	assert_str(shell.get_status_text()).contains("TRACE_ONLY")


func test_fixture06_refuse_reason() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("sources/fixture-06/bundle"))
	await _await_shell_settled(shell)

	assert_str(shell.get_refuse_reason()).is_equal("hash_mismatch")
	assert_str(shell.get_status_text()).contains("hash_mismatch")
	assert_object(shell.get_loaded_bundle()).is_null()


func test_downgrade_warning_when_declared_ne_effective() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_unit_fixture_path("unsupported-trace-downgrade"))
	await _await_shell_settled(shell)

	assert_str(shell.get_declared_mode()).is_equal(BundleMode.REPLAY_TRACE)
	assert_str(shell.get_effective_mode()).is_equal(BundleMode.REPLAY_ONLY)
	assert_bool(shell.get_trace_trusted()).is_false()
	assert_bool(shell.get_replay_trusted()).is_true()
	assert_int(shell.get_downgrade_warning_reasons().size()).is_equal(1)
	assert_str(shell.get_downgrade_warning_reasons()[0]).is_equal("unsupported_trace_schema_version")
	assert_str(shell.get_status_text()).contains("downgrade")
	assert_str(shell.get_status_text()).contains("unsupported_trace_schema_version")


func test_cli_stub_records_decision_without_navigation() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.parse_cli_args(["--decision", "2"])

	assert_int(shell.cli_decision_index).is_equal(2)
	assert_int(shell.get_selected_decision_index()).is_equal(-1)
