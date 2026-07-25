extends GdUnitTestSuite


func test_shows_connecting_text_on_state_change() -> void:
	var panel: ConnectionStatusPanel = preload("res://src/ui/panels/connection_status_panel.tscn").instantiate()
	add_child(panel)
	panel.on_connection_state_changed(ConnectionStateMachine.State.DISCONNECTED, ConnectionStateMachine.State.CONNECTING)
	assert_str(panel.get_status_text()).is_equal("Connecting...")
	panel.free()
