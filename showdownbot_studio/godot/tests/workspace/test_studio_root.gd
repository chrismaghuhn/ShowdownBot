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


## --- Owner review (2026-07-26, sixth pass), P1: third instance of the same layout-defect class
## (RoomEntryPanel's own inner controls, then LiveClientWorkspace's own panel composition, now
## StudioRoot's OWN composition). StudioRoot was a bare Control; NavBar sat at layout_mode = 1
## with no anchors/offsets while WorkspaceRouter had anchors_preset = 15 (full rect) right next to
## it -- the router covered the whole window INCLUDING the nav bar, so the "Offline Viewer" /
## "Live Client" buttons were visually overlapped by workspace content and not reliably clickable.
## Worse, the LiveClientWorkspace instance inside the router had layout_mode = 1 with no anchors
## at all (unlike OfflineViewerWorkspace's anchors_preset = 15), so even reaching the live tab
## would show a collapsed workspace. The earlier geometry probes instantiated LiveClientWorkspace
## STANDALONE and could never catch a defect in this one-level-up COMPOSITION -- this probes the
## real, fully instantiated StudioRoot scene instead.
func test_nav_bar_and_router_never_overlap_and_each_workspace_fills_the_router() -> void:
	var root := _spawn_root()
	# The headless test viewport otherwise defaults far too small (64x64 -- smaller than NavBar's
	# own minimum size) for a "fills the available area" assertion to mean anything: StudioRoot's
	# own anchors would report a container-minimum-driven size instead of a real, generous window
	# size. DisplayServer window geometry is stubbed headless, but Window/Control layout math is
	# not -- resize the root Window directly and let containers re-layout (same idiom as
	# test_app_shell_plan_e.gd's test_primary_controls_reachable_at_1280x720).
	get_tree().root.size = Vector2i(1280, 720)
	await await_idle_frame()
	await await_idle_frame()

	var nav_rect := root.get_nav_bar_for_test().get_global_rect()
	var router_rect := root.get_router().get_global_rect()
	assert_float(nav_rect.size.x).is_greater(0.0)
	assert_float(nav_rect.size.y).is_greater(0.0)
	assert_float(router_rect.size.x).is_greater(0.0)
	assert_float(router_rect.size.y).is_greater(0.0)
	# (a) the nav bar must never be covered by the router.
	assert_bool(nav_rect.intersects(router_rect)).is_false()

	var offline_button_rect := root.get_offline_viewer_nav_button().get_global_rect()
	var live_button_rect := root.get_live_client_nav_button().get_global_rect()

	# (b) Offline Viewer is the default active workspace -- its rect must be real and fill the
	# router area exactly (same size as the router's own rect).
	var offline_rect := root.get_offline_viewer_workspace().get_global_rect()
	assert_float(offline_rect.size.x).is_greater(0.0)
	assert_float(offline_rect.size.y).is_greater(0.0)
	assert_vector(offline_rect.size).is_equal(router_rect.size)
	# (c) the nav buttons must remain hit-testable -- not covered by the active workspace.
	assert_bool(offline_rect.intersects(offline_button_rect)).is_false()
	assert_bool(offline_rect.intersects(live_button_rect)).is_false()

	# Switch to Live Client: (b) its rect must also be real and fill the router identically;
	# (c) the nav buttons must still not be covered.
	root.get_live_client_nav_button().pressed.emit()
	await await_idle_frame()
	await await_idle_frame()
	var live_rect := root.get_live_client_workspace().get_global_rect()
	assert_float(live_rect.size.x).is_greater(0.0)
	assert_float(live_rect.size.y).is_greater(0.0)
	assert_vector(live_rect.size).is_equal(router_rect.size)
	assert_bool(live_rect.intersects(offline_button_rect)).is_false()
	assert_bool(live_rect.intersects(live_button_rect)).is_false()


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
