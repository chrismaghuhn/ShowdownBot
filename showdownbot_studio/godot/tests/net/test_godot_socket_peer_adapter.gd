extends GdUnitTestSuite


func test_fresh_adapter_reports_closed_ready_state() -> void:
	var adapter := GodotSocketPeerAdapter.new()
	assert_int(adapter.get_ready_state()).is_equal(SocketPeerPort.ReadyState.CLOSED)


func test_fresh_adapter_reports_zero_available_packets() -> void:
	var adapter := GodotSocketPeerAdapter.new()
	assert_int(adapter.get_available_packet_count()).is_equal(0)


func test_adapter_is_a_socket_peer_port() -> void:
	assert_bool(GodotSocketPeerAdapter.new() is SocketPeerPort).is_true()


func test_configure_heartbeat_interval_does_not_error() -> void:
	var adapter := GodotSocketPeerAdapter.new()
	adapter.configure_heartbeat_interval(20.0)  # forwards to the real WebSocketPeer.heartbeat_interval
