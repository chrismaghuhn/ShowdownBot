extends GdUnitTestSuite

# NOTE: 127.0.0.1, not "localhost" -- verified locally (Task 34) that Godot's WebSocketPeer
# resolving "localhost" on this Windows host tries IPv6 (::1) first, where the pinned
# pokemon-showdown server (Node, bound to 0.0.0.0 only) never answers -- the handshake then
# hangs in STATE_CONNECTING indefinitely instead of failing fast. The literal IPv4 address
# sidesteps the resolution order entirely and is what the real local run below used.
const _LOCAL_SERVER_URL := "ws://127.0.0.1:8000/showdown/websocket"


func test_spectating_a_real_local_battle_observes_real_content_not_just_room_state() -> void:
	var workspace: LiveClientWorkspace = preload("res://src/workspace/live_client_workspace.tscn").instantiate()
	add_child(workspace)
	workspace.get_transport().connect_to_server(_LOCAL_SERVER_URL)
	var frames := 0
	while workspace.get_transport().get_state() != ConnectionStateMachine.State.CONNECTED and frames < 600:
		await await_idle_frame()
		frames += 1
	assert_int(workspace.get_transport().get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)
	workspace.get_room_entry_panel().set_input_text_for_test(OS.get_environment("STUDIO_E2E_ROOM_ID"))
	workspace.get_room_entry_panel().press_watch_for_test()
	frames = 0
	while workspace.get_room_state_machine().get_state() != RoomStateMachine.State.ACTIVE and frames < 600:
		await await_idle_frame()
		frames += 1
	assert_int(workspace.get_room_state_machine().get_state()).is_equal(RoomStateMachine.State.ACTIVE)
	# Fixed (item F): RoomState.ACTIVE alone only proves the room was joined, not that anything
	# real was ever observed in it -- the seeder keeps the battle running past this point
	# (Task 33's keep-alive mode), so wait for at least one real battle event (the timeline
	# growing) and assert on real content, not merely a state-machine value.
	frames = 0
	while workspace.get_projection_for_test().get_timeline().size() == 0 and frames < 1200:
		await await_idle_frame()
		frames += 1
	assert_bool(workspace.get_projection_for_test().get_timeline().size() > 0).is_true()
	var snapshot := workspace.get_projection_for_test().get_current_snapshot()
	# NOTE: the plan's own sample compared str(species) != "" here. GDScript's str(null) returns
	# the literal text "<null>", not "", so that comparison is always true regardless of whether
	# any real species was ever observed -- a vacuous assertion. Comparing the Variant fields
	# directly against null (never converting to String first) is what actually proves content.
	var p1a_species: Variant = snapshot.get_slot("p1", "a").species
	var p2a_species: Variant = snapshot.get_slot("p2", "a").species
	var has_real_content := (
		snapshot.turn != null
		or p1a_species != null
		or p2a_species != null
	)
	assert_bool(has_real_content).is_true()
	workspace.free()
