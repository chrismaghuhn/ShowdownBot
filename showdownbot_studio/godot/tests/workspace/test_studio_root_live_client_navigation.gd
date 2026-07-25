extends GdUnitTestSuite

const _STUDIO_ROOT_SCENE := preload("res://src/workspace/studio_root.tscn")


func after_test() -> void:
	for child in get_children():
		if child is StudioRoot:
			remove_child(child)
			child.free()


func test_clicking_live_client_nav_button_switches_the_active_workspace() -> void:
	var root: StudioRoot = _STUDIO_ROOT_SCENE.instantiate()
	add_child(root)
	await await_idle_frame()
	root.get_live_client_nav_button().pressed.emit()
	assert_str(root.get_router().get_active_workspace_id()).is_equal(StudioRoot.LIVE_CLIENT_WORKSPACE_ID)


func test_connect_button_inside_live_client_workspace_calls_connect_to_showdown() -> void:
	var root: StudioRoot = _STUDIO_ROOT_SCENE.instantiate()
	add_child(root)
	await await_idle_frame()
	root.get_live_client_nav_button().pressed.emit()
	root.get_live_client_workspace().get_connect_button_for_test().pressed.emit()
	assert_int(root.get_live_client_workspace().get_transport().get_state()).is_equal(ConnectionStateMachine.State.CONNECTING)
