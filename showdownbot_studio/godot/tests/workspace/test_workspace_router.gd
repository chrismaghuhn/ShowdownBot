extends GdUnitTestSuite


func after_test() -> void:
	for child in get_children():
		if child is WorkspaceRouter:
			remove_child(child)
			child.free()


func _make_router() -> WorkspaceRouter:
	var router := WorkspaceRouter.new()
	add_child(router)
	return router


func test_register_and_show_single_workspace() -> void:
	var router := _make_router()
	var ws := Control.new()
	router.register_workspace("only", ws)
	router.show_workspace("only")
	assert_str(router.get_active_workspace_id()).is_equal("only")
	assert_bool(ws.visible).is_true()
	ws.free()


func test_show_unknown_workspace_id_does_not_change_active_id() -> void:
	var router := _make_router()
	var ws := Control.new()
	router.register_workspace("only", ws)
	router.show_workspace("only")
	router.show_workspace("missing")
	assert_str(router.get_active_workspace_id()).is_equal("only")
	ws.free()


func test_registered_workspace_ids_reports_exactly_registered_set() -> void:
	var router := _make_router()
	var a := Control.new()
	var b := Control.new()
	router.register_workspace("a", a)
	router.register_workspace("b", b)
	assert_int(router.get_registered_workspace_ids().size()).is_equal(2)
	assert_bool(router.get_registered_workspace_ids().has("a")).is_true()
	assert_bool(router.get_registered_workspace_ids().has("b")).is_true()
	a.free()
	b.free()


func test_switching_workspace_hides_previous_and_shows_next() -> void:
	var router := _make_router()
	var a := Control.new()
	var b := Control.new()
	router.register_workspace("a", a)
	router.register_workspace("b", b)
	router.show_workspace("a")
	router.show_workspace("b")
	assert_bool(a.visible).is_false()
	assert_bool(b.visible).is_true()
	a.free()
	b.free()
