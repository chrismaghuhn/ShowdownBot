extends GdUnitTestSuite

var _fake: FakeSocketPeerPort
var _transport: WebSocketTransport
var _room_state_machine: RoomStateMachine


func before_test() -> void:
	_fake = FakeSocketPeerPort.new()
	_transport = WebSocketTransport.new(func(): return _fake)
	add_child(_transport)
	_room_state_machine = RoomStateMachine.new(_transport)


func after_test() -> void:
	remove_child(_transport)
	_transport.free()


func _connect_join_and_activate(room_id: String) -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	_room_state_machine.request_join(room_id)
	_room_state_machine.join_confirmed()


func test_reconnecting_while_active_moves_room_state_to_joining_automatically() -> void:
	_connect_join_and_activate("battle-1")
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # transport -> RECONNECTING
	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.JOINING)


func test_reconnect_succeeding_emits_automatic_rejoin_requested_for_the_same_room() -> void:
	_connect_join_and_activate("battle-1")
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # -> RECONNECTING, RoomState -> JOINING
	var emitted_room_ids: Array[String] = []
	_room_state_machine.automatic_rejoin_requested.connect(func(room_id: String): emitted_room_ids.append(room_id))
	# Two _process() calls, matching Task 7's attempt-in-flight fix: the first opens the new
	# peer (still RECONNECTING that same frame); the second observes it as OPEN -> CONNECTED.
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	assert_int(emitted_room_ids.size()).is_equal(1)
	assert_str(emitted_room_ids[0]).is_equal("battle-1")


## Owner finding 7a (M1 hardening, 2026-07-26): this test used to set ready_state = OPEN and then
## run only the SINGLE _process() call that opens the reconnect peer via backoff -- but
## WebSocketTransport._process() returns immediately after _open_socket() on that call (Task 7's
## attempt-in-flight fix), without polling in the same frame. The transport therefore never
## actually reached CONNECTED in this test; "no automatic rejoin" was trivially true for the wrong
## reason (the success path was never driven at all), not because no room was ever joined. Drives
## the required SECOND poll (matching every other test in this file's own documented two-call
## pattern) and asserts CONNECTED was actually reached before asserting on rejoin.
## Owner finding 7a (M1 hardening, 2026-07-26): this test used to set ready_state = OPEN and then
## run only the SINGLE _process() call that opens the reconnect peer via backoff -- but
## WebSocketTransport._process() returns immediately after _open_socket() on that call (Task 7's
## attempt-in-flight fix), without polling in the same frame. The transport therefore never
## actually reached CONNECTED here; "no automatic rejoin" was trivially true for the wrong reason
## (the success path was never driven at all), not because no room was ever joined. Confirmed by
## a red run: asserting CONNECTED right after the single process call failed (state was still
## RECONNECTING). Now drives the required SECOND poll, matching every other test in this file's
## own documented two-call pattern, and asserts CONNECTED was actually reached before asserting on
## rejoin.
func test_no_automatic_rejoin_is_emitted_when_no_room_was_ever_joined() -> void:
	var emitted_room_ids: Array[String] = []
	_room_state_machine.automatic_rejoin_requested.connect(func(room_id: String): emitted_room_ids.append(room_id))
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # opens the new peer
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)  # observes OPEN -> CONNECTED
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)
	assert_int(emitted_room_ids.size()).is_equal(0)


## Owner finding 7a (M1 hardening, 2026-07-26): same gap as the test above -- this used to set
## ready_state = OPEN and run only the single backoff-elapsed process call, never actually
## reaching CONNECTED (confirmed by a red run: the added CONNECTED assertion failed, state was
## still RECONNECTING). Drives the required second poll and asserts CONNECTED was actually
## reached -- proof of "no unauthorized sends" now covers the REAL completed success path, not a
## reconnect attempt that never finished.
func test_room_state_machine_never_calls_send_raw_text_itself() -> void:
	# Structural proof of item C's fix: even across a full reconnect-and-rejoin cycle, this
	# class's own fake transport never records a sent text -- only SpectatorRoomGateway (Task 28)
	# ever does, and it is not present in this test at all.
	_connect_join_and_activate("battle-1")
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # opens the new peer
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)  # observes OPEN -> CONNECTED
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)
	assert_int(_fake.sent_texts.size()).is_equal(0)


func test_interrupted_first_join_is_retried_after_reconnect() -> void:
	# Pins a deliberate edge the quality review flagged (2026-07-26, see the guard's own doc
	# comment in room_state_machine.gd): a FIRST request_join() that is never confirmed
	# (join_confirmed() is never called here) because a connection drop lands first still ends
	# up emitting automatic_rejoin_requested once the reconnect succeeds -- the guard only checks
	# "_state == JOINING", which this interrupted-first-join scenario satisfies just as much as
	# connection_reconnecting()'s own ACTIVE -> JOINING transition does. This is intentional: the
	# user's join intent should survive a drop that happens to land before the server's own join
	# confirmation arrives, so it is retried the same way an ACTIVE-room rejoin is.
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	_room_state_machine.request_join("battle-1")  # JOINING -- never confirmed
	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.JOINING)

	var emitted_room_ids: Array[String] = []
	_room_state_machine.automatic_rejoin_requested.connect(func(room_id: String): emitted_room_ids.append(room_id))

	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # transport -> RECONNECTING; RoomState stays JOINING (already was)
	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.JOINING)

	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # opens the new peer
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)  # observes OPEN -> CONNECTED

	assert_int(emitted_room_ids.size()).is_equal(1)
	assert_str(emitted_room_ids[0]).is_equal("battle-1")
