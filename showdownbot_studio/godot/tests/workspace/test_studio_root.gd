extends GdUnitTestSuite

const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"
const _STUDIO_ROOT_SCENE := preload("res://src/workspace/studio_root.tscn")


func _fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_FIXTURES_ROOT.path_join(relative))


func after_test() -> void:
	for child in get_children():
		if child is StudioRoot:
			remove_child(child)
			child.free()


func _spawn_root() -> StudioRoot:
	var root: StudioRoot = _STUDIO_ROOT_SCENE.instantiate()
	add_child(root)
	return root


func test_studio_root_shows_offline_viewer_workspace_by_default() -> void:
	var root := _spawn_root()
	await await_idle_frame()
	assert_str(root.get_router().get_active_workspace_id()).is_equal(StudioRoot.OFFLINE_VIEWER_WORKSPACE_ID)
	assert_bool(root.get_offline_viewer_workspace().visible).is_true()


func test_studio_root_router_has_exactly_two_registered_workspaces() -> void:
	var root := _spawn_root()
	await await_idle_frame()
	assert_int(root.get_router().get_registered_workspace_ids().size()).is_equal(2)


func test_offline_viewer_workspace_opens_fixture01_through_wrapped_app_shell() -> void:
	var root := _spawn_root()
	await await_idle_frame()
	var shell: AppShell = root.get_offline_viewer_workspace().get_app_shell()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	var frames := 0
	while not shell.is_settled() and frames < 600:
		await await_idle_frame()
		frames += 1
	assert_bool(shell.is_settled()).is_true()
	assert_str(shell.get_declared_mode()).is_equal(BundleMode.REPLAY_TRACE)
	assert_int(shell.get_decision_count()).is_equal(3)
