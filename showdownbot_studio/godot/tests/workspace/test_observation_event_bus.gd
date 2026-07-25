extends GdUnitTestSuite


func test_publish_connection_state_changed_notifies_subscribers() -> void:
	var bus := ObservationEventBus.new()
	var received: Array = []
	bus.connection_state_changed.connect(func(old_state, new_state): received.append([old_state, new_state]))
	bus.publish_connection_state_changed(ConnectionStateMachine.State.DISCONNECTED, ConnectionStateMachine.State.CONNECTING)
	assert_int(received.size()).is_equal(1)


func test_publish_battle_state_published_notifies_subscribers() -> void:
	var bus := ObservationEventBus.new()
	var received: Array[LiveBattleSnapshot] = []
	bus.battle_state_published.connect(func(snapshot: LiveBattleSnapshot): received.append(snapshot))
	var snapshot := LiveBattleSnapshot.new()
	bus.publish_battle_state_published(snapshot)
	assert_int(received.size()).is_equal(1)
	assert_object(received[0]).is_same(snapshot)


func test_publish_battle_completed_notifies_subscribers() -> void:
	var bus := ObservationEventBus.new()
	var received: Array[String] = []
	bus.battle_completed.connect(func(room_id: String): received.append(room_id))
	bus.publish_battle_completed("battle-1")
	assert_str(received[0]).is_equal("battle-1")
