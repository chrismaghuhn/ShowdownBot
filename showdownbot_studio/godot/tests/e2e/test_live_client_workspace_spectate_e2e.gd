extends GdUnitTestSuite

# NOTE: 127.0.0.1, not "localhost" -- verified locally (Task 34) that Godot's WebSocketPeer
# resolving "localhost" on this Windows host tries IPv6 (::1) first, where the pinned
# pokemon-showdown server (Node, bound to 0.0.0.0 only) never answers -- the handshake then
# hangs in STATE_CONNECTING indefinitely instead of failing fast. The literal IPv4 address
# sidesteps the resolution order entirely and is what the real local run below used.
const _LOCAL_SERVER_URL := "ws://127.0.0.1:8000/showdown/websocket"
const _LOCAL_SERVER_HOST := "127.0.0.1"
const _LOCAL_SERVER_PORT := 8000


## Self-skip seam (2026-07-26 fix): studio-windows.yml runs res://tests/ recursively with no
## local server provisioned -- only studio-live-local-e2e.yml starts one (this test's own real
## purpose). Without this, the full suite would go red on every ordinary CI run and every local
## run without the pinned server up. A fast, short-bounded raw TCP probe of the loopback address
## is the actual-reality signal (never a WebSocket handshake, never the CONNECT_TIMEOUT_S
## net/WebSocketTransport uses for a real, possibly-remote connection) -- if nothing answers on
## 127.0.0.1:8000, this suite has nothing to spectate and skips with an explicit reason instead
## of failing. studio-live-local-e2e.yml's own server is listening by the time this test runs, so
## the probe succeeds there and the real assertions below still execute for real.
func _local_server_is_reachable() -> bool:
	var probe := StreamPeerTCP.new()
	if probe.connect_to_host(_LOCAL_SERVER_HOST, _LOCAL_SERVER_PORT) != OK:
		return false
	var frames := 0
	while frames < 60:
		probe.poll()
		var status := probe.get_status()
		if status == StreamPeerTCP.STATUS_CONNECTED:
			probe.disconnect_from_host()
			return true
		if status == StreamPeerTCP.STATUS_ERROR:
			probe.disconnect_from_host()
			return false
		await await_idle_frame()
		frames += 1
	probe.disconnect_from_host()
	return false


## Mirrors tests/bundle/test_bundle_validator.gd's own existing _mark_skip helper exactly (the
## established in-repo convention for a runtime conditional skip, not a new mechanism) -- walks
## this suite's own children for the currently running _TestCase node and calls its real
## do_skip(true, reason), which gdUnit's own reporting (and this repo's truncation guard) already
## counts as executed+skipped, proven by the pre-existing skip elsewhere in this suite.
func _mark_skip(reason: String) -> void:
	for child in get_children():
		if child.has_method("do_skip") and child.has_method("test_name"):
			if String(child.test_name()) == __active_test_case:
				child.do_skip(true, reason)
				return


## Owner finding 8 (M1 hardening, 2026-07-26): the self-skip above means a server that dies
## mid-lane (or was never started at all by a broken workflow step) still yields a green run --
## the dedicated studio-live-local-e2e lane is exactly the ONE place that must never tolerate
## that silently. STUDIO_E2E_REQUIRED=1 is set ONLY by that workflow/orchestration script
## (run_live_e2e_ci.ps1), never by an ordinary local run or the studio-windows lane -- so this
## check changes behavior in the one place that actually requires the server, and nowhere else.
func _server_required_by_ci() -> bool:
	return OS.get_environment("STUDIO_E2E_REQUIRED") == "1"


func test_spectating_a_real_local_battle_observes_real_content_not_just_room_state() -> void:
	if not await _local_server_is_reachable():
		if _server_required_by_ci():
			fail(
				"STUDIO_E2E_REQUIRED=1 but no local pokemon-showdown server is reachable on %s:%d "
				% [_LOCAL_SERVER_HOST, _LOCAL_SERVER_PORT]
				+ "-- the dedicated live e2e lane must FAIL here, not skip green (a server dying "
				+ "mid-lane, or never starting, must never look like a passing run)"
			)
			return
		_mark_skip(
			"no local pokemon-showdown server reachable on %s:%d -- run "
			% [_LOCAL_SERVER_HOST, _LOCAL_SERVER_PORT]
			+ "showdownbot_studio/godot/tools/start_local_showdown_server.ps1 first "
			+ "(the studio-live-local-e2e CI lane always starts one before this runs)"
		)
		return
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
