extends GdUnitTestSuite

## Gate-11 rate-limit review finding (docs/security/RATE_LIMIT_REVIEW.md section 2/4): before this
## fix, _on_peer_open() reset _reconnect_attempt to 0 on EVERY successful open, regardless of how
## briefly the connection actually held. A connection that opens and immediately drops therefore
## never advanced past RECONNECT_BACKOFF_SCHEDULE_S[0] -- the schedule could never exhaust, and a
## flapping link would reconnect roughly once per second forever (no session-wide cap), reaching
## the pinned server's 500-connections-per-30-minutes-per-IP ban threshold in about 8 minutes.
## The fix: a successful open only resets the backoff schedule once the connection has stayed OPEN
## continuously for MIN_STABLE_CONNECTION_S. A drop before that threshold counts as a failed
## attempt and advances the schedule normally.

var _fake: FakeSocketPeerPort
var _transport: WebSocketTransport


func before_test() -> void:
	_fake = FakeSocketPeerPort.new()
	_transport = WebSocketTransport.new(func(): return _fake)
	add_child(_transport)


func after_test() -> void:
	remove_child(_transport)
	_transport.free()


## RED-FIRST discriminating test: against the pre-fix code, _on_peer_open() resets the attempt
## counter to 0 on every open no matter how briefly the connection held, so this loop would keep
## reopening at RECONNECT_BACKOFF_SCHEDULE_S[0] = 1.0s forever and EXHAUSTED would never be
## reached -- the final assertion below fails against that code.
func test_flapping_connection_escalates_through_full_backoff_schedule_to_exhausted() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)

	for backoff_s in WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S:
		# Drop well inside the stability window (0.016s, vs. a 30s+ threshold) -- the
		# connection never held long enough to be trusted, so this must count as a failed
		# attempt and advance the schedule, not reset it.
		_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
		_transport._process(0.016)
		assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)

		var urls_before := _fake.connect_urls.size()
		_fake.ready_state = SocketPeerPort.ReadyState.CONNECTING
		# Just short of THIS step's own backoff: no new peer yet. A non-escalating
		# implementation (stuck replaying backoff[0] = 1.0s forever) would already have
		# opened a new peer well before this point once backoff_s > 1.0s -- this is the
		# assertion that actually proves escalation, not just eventual exhaustion.
		_transport._process(backoff_s - 0.1)
		assert_int(_fake.connect_urls.size()).is_equal(urls_before)
		# Now cross this step's backoff: exactly one new peer opens.
		_transport._process(0.2)
		assert_int(_fake.connect_urls.size()).is_equal(urls_before + 1)

		_fake.ready_state = SocketPeerPort.ReadyState.OPEN
		_transport._process(0.016)
		assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)

	# The full 5-entry schedule has now been consumed once each, never refunded (no open
	# ever held the stability window) -- the next drop must exhaust it.
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.EXHAUSTED)


## No-regression case: the legitimate long-session reconnect. A connection that holds open
## continuously for at least MIN_STABLE_CONNECTION_S is trusted again -- when it later drops,
## the very next backoff must be the schedule's first step, not wherever the schedule had
## previously escalated to.
func test_connection_held_past_stability_threshold_resets_backoff_to_first_step() -> void:
	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)  # initial attempt fails synchronously -> RECONNECTING, backoff[0] scheduled
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)

	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # attempt 2 fails too -> backoff[1] scheduled
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)

	# Attempt 3 succeeds and this time the connection actually holds.
	_fake.ready_state = SocketPeerPort.ReadyState.CONNECTING
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[1] + 0.1)  # attempt opens
	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
	_transport._process(0.016)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)

	# Hold it open continuously past the stability threshold.
	_transport._process(WebSocketTransport.MIN_STABLE_CONNECTION_S + 0.1)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)

	# Now it drops. Because it held long enough to be trusted, the very next backoff must be
	# the schedule's first step again (1.0s), not the third step it would otherwise be at.
	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
	_transport._process(0.016)
	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)

	var urls_before := _fake.connect_urls.size()
	_fake.ready_state = SocketPeerPort.ReadyState.CONNECTING
	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # fires only if reset to step 0
	assert_int(_fake.connect_urls.size()).is_equal(urls_before + 1)
