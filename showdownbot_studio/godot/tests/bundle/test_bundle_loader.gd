extends GdUnitTestSuite

const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"


func _fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_FIXTURES_ROOT.path_join(relative))


func after_test() -> void:
	for child in get_children():
		if child is BundleLoader:
			remove_child(child)
			child.free()


func _add_loader(hooks: BundleWorker.WorkerHooks = null) -> BundleLoader:
	var loader := BundleLoader.new()
	if hooks != null:
		loader.set_worker_hooks(hooks)
	add_child(loader)
	return loader


func _await_until(condition: Callable, max_frames: int = 600) -> void:
	var frames := 0
	while not condition.call() and frames < max_frames:
		await await_idle_frame()
		frames += 1
	assert_bool(condition.call()).is_true()


func _await_state(loader: BundleLoader, expected: BundleLoader.State, max_frames: int = 600) -> void:
	await _await_until(func() -> bool: return loader.get_state() == expected, max_frames)


func test_fixture01_load_completed_sealed() -> void:
	var loader := _add_loader()
	loader.load_async(_fixture_path("bundles/fixture-01"))
	var published: BundleDTO = await await_signal_on(loader, "completed", [], 5000)

	assert_object(published).is_not_null()
	assert_str(published.declared_mode).is_equal(BundleMode.REPLAY_TRACE)
	assert_str(published.effective_mode).is_equal(BundleMode.REPLAY_TRACE)
	assert_int(published.decisions.size()).is_equal(3)
	assert_int(loader.get_state()).is_equal(BundleLoader.State.COMPLETED)

	var before := published.manifest.battle_id
	published.manifest.battle_id = "mutated"
	assert_str(published.manifest.battle_id).is_equal(before)

	published.decisions.append(DecisionRowDTO.new())
	assert_int(published.decisions.size()).is_equal(3)


func test_stale_result_dropped_after_cancel() -> void:
	var hooks := BundleWorker.WorkerHooks.new()
	var release := Semaphore.new()
	hooks.on_before_terminal_enqueue = func() -> void:
		release.wait()

	var loader := _add_loader(hooks)
	var counts := {"completed": 0, "cancelled": 0}
	loader.completed.connect(func(_bundle: BundleDTO) -> void: counts.completed += 1)
	loader.cancelled.connect(func() -> void: counts.cancelled += 1)

	loader.load_async(_fixture_path("bundles/fixture-01"))
	await _await_state(loader, BundleLoader.State.LOADING)
	loader.load_async(_fixture_path("bundles/fixture-04"))
	release.post()
	await _await_state(loader, BundleLoader.State.COMPLETED)

	assert_int(counts.completed).is_equal(1)
	assert_int(counts.cancelled).is_equal(1)
	assert_bool(loader.is_worker_thread_joined()).is_true()


func test_cancel_never_publishes_partial_dto() -> void:
	var hooks := BundleWorker.WorkerHooks.new()
	var release := Semaphore.new()
	hooks.on_before_terminal_enqueue = func() -> void:
		release.wait()

	var loader := _add_loader(hooks)
	var counts := {"completed": 0, "cancelled": 0}
	loader.completed.connect(func(_bundle: BundleDTO) -> void: counts.completed += 1)
	loader.cancelled.connect(func() -> void: counts.cancelled += 1)

	loader.load_async(_fixture_path("bundles/fixture-01"))
	await _await_state(loader, BundleLoader.State.LOADING)
	loader.cancel()
	release.post()
	await _await_state(loader, BundleLoader.State.CANCELLED)

	assert_int(counts.completed).is_equal(0)
	assert_int(counts.cancelled).is_equal(1)


func test_progress_emitted_only_on_main_thread() -> void:
	var loader := _add_loader()
	var main_thread_id := OS.get_main_thread_id()

	loader.load_async(_fixture_path("bundles/fixture-01"))
	await await_signal_on(loader, "completed", [], 5000)

	assert_int(loader.get_last_progress_emit_thread_id()).is_equal(main_thread_id)
	assert_int(loader.get_last_progress_emit_thread_id()).is_not_equal(-1)


func test_worker_returns_without_terminal_envelope_refuses() -> void:
	var hooks := BundleWorker.WorkerHooks.new()
	hooks.omit_terminal_envelope = true

	var loader := _add_loader(hooks)
	loader.load_async(_fixture_path("bundles/fixture-01"))
	var diagnostic: RefuseDiagnostic = await await_signal_on(loader, "refused", [], 5000)

	assert_object(diagnostic).is_not_null()
	assert_str(diagnostic.reason).is_equal("internal_loader_error")
	assert_str(diagnostic.message).contains("terminal envelope")
	assert_int(loader.get_state()).is_equal(BundleLoader.State.REFUSED)
	assert_bool(loader.is_worker_thread_joined()).is_true()


func test_worker_has_no_node_reference() -> void:
	var worker_script: GDScript = preload("res://src/bundle/bundle_worker.gd")
	assert_str(worker_script.get_global_name()).is_equal("BundleWorker")
	assert_str(worker_script.get_instance_base_type()).is_equal("RefCounted")
	assert_object(BundleWorker.new()).is_instanceof(RefCounted)
	# Thread entry is static BundleWorker.thread_main — not a BundleLoader Node method.
	var entry: Callable = BundleWorker.thread_main
	assert_bool(entry.is_valid()).is_true()
	var bound: Object = entry.get_object()
	if bound != null:
		assert_str(bound.get_class()).is_not_equal("Node")
		assert_bool(bound is BundleLoader).is_false()


func _copy_dir_recursive(src: String, dst: String) -> void:
	DirAccess.make_dir_recursive_absolute(dst)
	var dir := DirAccess.open(src)
	assert_object(dir).is_not_null()
	dir.list_dir_begin()
	var name := dir.get_next()
	while name != "":
		if name == "." or name == "..":
			name = dir.get_next()
			continue
		var src_path := src.path_join(name)
		var dst_path := dst.path_join(name)
		if DirAccess.dir_exists_absolute(src_path):
			_copy_dir_recursive(src_path, dst_path)
		else:
			DirAccess.copy_absolute(src_path, dst_path)
		name = dir.get_next()
	dir.list_dir_end()


func _rehash_payload(bundle_dir: String, logical_key: String, file_path: String) -> void:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(FileAccess.get_file_as_bytes(file_path))
	var digest := ctx.finish().hex_encode()
	var json := JSON.new()
	assert_int(json.parse(FileAccess.get_file_as_string(bundle_dir.path_join("manifest.json")))).is_equal(OK)
	var manifest: Dictionary = json.data
	manifest["files"][logical_key]["sha256"] = digest
	var out := FileAccess.open(bundle_dir.path_join("manifest.json"), FileAccess.WRITE)
	out.store_string(JSON.stringify(manifest))
	out.close()


func test_published_dto_not_aliased_to_worker_buffer() -> void:
	# Fixture-01 details are strings; inject a container so aliasing is observable via is_same().
	var bundle_dir := OS.get_cache_dir().path_join(
		"gdunit_loader_alias_%d" % Time.get_ticks_usec()
	)
	_copy_dir_recursive(_fixture_path("bundles/fixture-01"), bundle_dir)
	var battle_path := bundle_dir.path_join("battle.jsonl")
	var lines: PackedStringArray = FileAccess.get_file_as_string(battle_path).split("\n")
	var rewritten: PackedStringArray = PackedStringArray()
	var mutated := false
	for line in lines:
		var trimmed := line.strip_edges()
		if trimmed.is_empty():
			continue
		var json := JSON.new()
		assert_int(json.parse(trimmed)).is_equal(OK)
		var row: Dictionary = json.data
		if not mutated and row.get("type") == "move":
			row["details"] = {"alias_probe": true, "nested": {"n": 1}}
			mutated = true
		rewritten.append(JSON.stringify(row))
	assert_bool(mutated).is_true()
	var battle_out := FileAccess.open(battle_path, FileAccess.WRITE)
	battle_out.store_string("\n".join(rewritten) + "\n")
	battle_out.close()
	_rehash_payload(bundle_dir, "battle_log", battle_path)

	var hooks := BundleWorker.WorkerHooks.new()
	var capture := {"worker_bundle": null}
	hooks.on_after_validate = func(result: ValidationResult) -> void:
		capture.worker_bundle = result.bundle

	var loader := _add_loader(hooks)
	loader.load_async(bundle_dir)
	var published: BundleDTO = await await_signal_on(loader, "completed", [], 5000)

	assert_object(capture.worker_bundle).is_not_null()
	assert_int(published.get_instance_id()).is_not_equal(capture.worker_bundle.get_instance_id())

	var worker_details: Variant = null
	var published_details: Variant = null
	for event in capture.worker_bundle.battle_events:
		if typeof(event.details) == TYPE_DICTIONARY and event.details.has("alias_probe"):
			worker_details = event.details
			break
	for event in published.battle_events:
		if typeof(event.details) == TYPE_DICTIONARY and event.details.has("alias_probe"):
			published_details = event.details
			break
	assert_object(worker_details).is_not_null()
	assert_object(published_details).is_not_null()
	assert_bool(is_same(worker_details, published_details)).is_false()
	assert_bool(published_details["alias_probe"]).is_true()


func test_finished_thread_wait_to_finish_on_main() -> void:
	var loader := _add_loader()
	loader.load_async(_fixture_path("bundles/fixture-01"))
	await await_signal_on(loader, "completed", [], 5000)

	assert_bool(loader.is_worker_thread_joined()).is_true()
	assert_int(OS.get_thread_caller_id()).is_equal(OS.get_main_thread_id())


func test_second_load_async_returns_before_prior_barrier_releases() -> void:
	var hooks := BundleWorker.WorkerHooks.new()
	var entered := Semaphore.new()
	var release := Semaphore.new()
	var block_terminal_once := {"active": true}
	hooks.on_before_terminal_enqueue = func() -> void:
		if not block_terminal_once.active:
			return
		block_terminal_once.active = false
		entered.post()
		release.wait()

	var loader := _add_loader(hooks)
	var counts := {"completed": 0, "cancelled": 0}
	loader.completed.connect(func(_bundle: BundleDTO) -> void: counts.completed += 1)
	loader.cancelled.connect(func() -> void: counts.cancelled += 1)

	loader.load_async(_fixture_path("bundles/fixture-01"))
	entered.wait()

	loader.load_async(_fixture_path("bundles/fixture-04"))
	assert_bool(loader.is_worker_thread_joined()).is_false()

	release.post()
	await _await_state(loader, BundleLoader.State.COMPLETED)

	assert_int(counts.completed).is_equal(1)
	assert_int(counts.cancelled).is_equal(1)
	assert_bool(loader.is_worker_thread_joined()).is_true()


func test_exit_tree_cancels_and_joins_synchronously() -> void:
	var loader := _add_loader()
	loader.load_async(_fixture_path("bundles/fixture-01"))
	remove_child(loader)
	assert_bool(loader.is_worker_thread_joined()).is_true()
	loader.free()
