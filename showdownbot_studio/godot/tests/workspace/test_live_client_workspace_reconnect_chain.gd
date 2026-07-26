extends GdUnitTestSuite

## Closes the watchlist's M1e step-6 gap: Task 39's own reconnect proof wired net/+protocol/+
## battle/ directly and had NO gateway in the test at all (by design, to isolate the rebuild from
## the send) -- so it could never prove SpectatorRoomGateway actually encodes+sends the rejoin
## command. This test composes the REAL production LiveClientWorkspace (which owns the real
## SpectatorRoomGateway, RoomStateMachine, WebSocketTransport, ProtocolDecoder, and
## LiveBattleProjection exactly as spec section 4.3/4.7 wires them) against only a fake socket
## port, and asserts all ten watchlist steps observably -- including that the fake port actually
## RECORDS the rejoin's sent text (step 6), and that the resent history is only queued AFTER that
## send is observed (closing the 6-then-7 causal-link gap: the two were previously only ever
## proven true independently, never in a single causal chain). No production file is modified by
## this test.

var _fake: FakeSocketPeerPort
var _workspace: LiveClientWorkspace


func before_test() -> void:
	_fake = FakeSocketPeerPort.new()
	_workspace = preload("res://src/workspace/live_client_workspace.tscn").instantiate()
	add_child(_workspace)
	_workspace.configure_transport_for_test(func(): return _fake)


func after_test() -> void:
	remove_child(_workspace)
	_workspace.free()


func test_full_ten_step_reconnect_chain_through_the_real_production_wiring() -> void:
	# -- Step 0 (setup, not itself one of the ten): connect, human "Watch" join, first battle
	# init through the real decode path, exactly as test_live_client_workspace.gd's own
	# test_watch_sends_the_join_command_through_the_gateway_not_directly does.
	_workspace.get_transport().connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_workspace.get_transport()._process(0.016)
	_workspace.get_room_entry_panel().set_input_text_for_test("battle-1")
	_workspace.get_room_entry_panel().press_watch_for_test()
	assert_int(_fake.sent_texts.size()).is_equal(1)
	assert_str(_fake.sent_texts[0]).is_equal("|/join battle-1")

	_fake.queued_packets = [">battle-1\n|init|battle\n|turn|1\n|switch|p1a: Pikachu|Pikachu, L50, M|100/100"]
	_workspace.get_transport()._process(0.016)
	assert_int(_workspace.get_room_state_machine().get_state()).is_equal(RoomStateMachine.State.ACTIVE)
	assert_int(_workspace.get_projection_for_test().get_timeline().size()).is_equal(3)  # init, turn, switch

	# Poison the state through the REAL decode path (Task 38/39's poisoned-state pattern, reused
	# here). A raw, genuinely-unrecognized protocol line never reaches event_decoded at all (it
	# is classified UNKNOWN_EVENT and only fires line_not_understood -- protocol/'s own three-way
	# classification, M1b), so "move" stands in for Task 38/39's synthetic "OLD_ONLY_EVENT": a
	# real DECODED_STATE_EVENT that LiveBattleReducer still has no match arm for, the actual
	# real-decode-path equivalent of "a decoded event that must not survive a rebuild."
	_fake.queued_packets = [">battle-1\n|turn|99\n|switch|p1a: FakeMon|FakeMon, L50, M|1/1\n|move|p1a: FakeMon|Fake Move|p2a: Ditto"]
	_workspace.get_transport()._process(0.016)
	assert_int(_workspace.get_projection_for_test().get_current_snapshot().turn).is_equal(99)
	assert_int(_workspace.get_projection_for_test().get_timeline().size()).is_equal(6)

	# -- Watchlist step 1: transport reaches RECONNECTING.
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_workspace.get_transport()._process(0.016)
	assert_int(_workspace.get_transport().get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)
	assert_int(_workspace.get_room_state_machine().get_state()).is_equal(RoomStateMachine.State.JOINING)

	# -- Watchlist step 2: one reconnect peer is opened after backoff (exactly one new
	# connect_to_url call -- matching Task 7's attempt-in-flight fix and the M1a watchlist row
	# "a reconnect attempt may open exactly one peer after each backoff period").
	var connect_urls_before := _fake.connect_urls.size()
	_workspace.get_transport()._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)
	assert_int(_fake.connect_urls.size()).is_equal(connect_urls_before + 1)
	# Still RECONNECTING this same frame -- the peer was opened but not yet observed OPEN.
	assert_int(_workspace.get_transport().get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)

	# -- Watchlist step 3: that same peer is polled until OPEN; step 4: transport reaches
	# CONNECTED. Connect the rejoin listener BEFORE the poll that flips it, so this test observes
	# the emission itself, not just its side effects.
	var rejoin_requested_room_ids: Array[String] = []
	_workspace.get_room_state_machine().automatic_rejoin_requested.connect(
		func(room_id: String): rejoin_requested_room_ids.append(room_id)
	)
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_workspace.get_transport()._process(0.016)
	assert_int(_workspace.get_transport().get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)

	# -- Watchlist step 5: RoomStateMachine emits automatic_rejoin_requested(room_id).
	assert_int(rejoin_requested_room_ids.size()).is_equal(1)
	assert_str(rejoin_requested_room_ids[0]).is_equal("battle-1")

	# -- Watchlist step 6: SpectatorRoomGateway sends the rejoin command -- the REAL send, through
	# the REAL gateway, recorded on the fake port. This is what Task 39's test structurally could
	# not prove (it wired no gateway at all).
	assert_int(_fake.sent_texts.size()).is_equal(2)
	assert_str(_fake.sent_texts[1]).is_equal("|/join battle-1")

	# -- Watchlist step 7: the server resends authoritative room history -- queued only NOW, AFTER
	# step 6's send was observed above, so this test proves the causal order (send THEN resend),
	# not merely that both happen to be true somewhere in the same run (the gap the review named
	# "closing the 6->7 causal-link gap").
	_fake.queued_packets = [">battle-1\n|init|battle\n|turn|1\n|switch|p1a: Ditto|Ditto|50/50"]
	_workspace.get_transport()._process(0.016)

	# -- Watchlist step 8: the second battle init resets LiveBattleProjection; step 9: snapshot
	# and timeline are rebuilt SOLELY from the resent history -- none of the poisoned turn 99 /
	# FakeMon / move-line content survives, and the timeline is exactly the three resent lines.
	assert_int(_workspace.get_room_state_machine().get_state()).is_equal(RoomStateMachine.State.ACTIVE)
	var snapshot := _workspace.get_projection_for_test().get_current_snapshot()
	assert_int(snapshot.turn).is_equal(1)  # not 99
	assert_str(str(snapshot.get_slot("p1", "a").species)).is_equal("Ditto")  # not "FakeMon"
	var timeline := _workspace.get_projection_for_test().get_timeline()
	assert_int(timeline.size()).is_equal(3)  # init, turn, switch -- none of the prior 6
	for e in timeline:
		assert_str(e.event_type).is_not_equal("move")  # the poisoned move line is gone
	assert_str(_workspace.get_battle_board_panel().get_board_view().get_slot_species("p1", "a")).is_equal("Ditto")

	# -- Watchlist step 10: new live events continue afterward.
	_fake.queued_packets = [">battle-1\n|turn|2"]
	_workspace.get_transport()._process(0.016)
	assert_int(_workspace.get_projection_for_test().get_current_snapshot().turn).is_equal(2)
	assert_int(_workspace.get_projection_for_test().get_timeline().size()).is_equal(4)
