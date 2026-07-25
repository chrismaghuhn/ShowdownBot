extends GdUnitTestSuite


func test_encode_join_room() -> void:
	assert_str(ProtocolCommandEncoder.encode_join_room("battle-1")).is_equal("|/join battle-1")


func test_encode_leave_room() -> void:
	assert_str(ProtocolCommandEncoder.encode_leave_room("battle-1")).is_equal("|/leave battle-1")
