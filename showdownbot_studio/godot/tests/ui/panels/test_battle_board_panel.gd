extends GdUnitTestSuite


func test_bind_renders_through_the_shared_board_view() -> void:
	var panel: BattleBoardPanel = preload("res://src/ui/panels/battle_board_panel.tscn").instantiate()
	add_child(panel)
	var live := LiveBattleSnapshot.new().with_slot("p1", "a", LiveBattleSlotSnapshot.new("Pikachu"))
	panel.bind(live)
	assert_str(panel.get_board_view().get_slot_species("p1", "a")).is_equal("Pikachu")
	panel.free()


func test_bind_null_shows_empty_state() -> void:
	var panel: BattleBoardPanel = preload("res://src/ui/panels/battle_board_panel.tscn").instantiate()
	add_child(panel)
	panel.bind(null)
	assert_bool(panel.get_board_view().get_empty_state_visible()).is_true()
	panel.free()
