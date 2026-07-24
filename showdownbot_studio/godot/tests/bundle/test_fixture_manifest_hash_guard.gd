extends GdUnitTestSuite

# Guard: every fixture manifest.json's declared sha256 must match its file's actual bytes.
# Verify-only -- never recomputes or rewrites a mismatch (that would delete the check it
# exists to be; see python/reseal_manifest_hashes.py for the deliberate, hand-run tool that
# does the healing). The one known exception is fixtures/viewer-v0/sources/fixture-06/bundle,
# which is DELIBERATELY mismatched -- it is what test_fixture06_hash_mismatch (this
# directory) and test_app_shell_smoke.gd's test_fixture06_refuse_reason exist to exercise.
# That exception is asserted positively below (its own test proves it still mismatches),
# not just excluded from the sweep.

# Measured: 11 res://tests/fixtures/unit + 6 bundles/* + 1 sources/fixture-06/bundle.
const _MIN_MANIFEST_COUNT := 18


func _fixture06_manifest_path() -> String:
	return ProjectSettings.globalize_path(
		"res://../fixtures/viewer-v0/sources/fixture-06/bundle/manifest.json"
	).replace("\\", "/")


# Manifests live at different depths (fixtures/viewer-v0/bundles/*/manifest.json is one
# level deep, fixtures/viewer-v0/sources/fixture-06/bundle/manifest.json is two), so walk
# recursively rather than list one fixed depth -- a fixed-depth scan against the sources/
# root silently returns nothing.
func _find_manifests(root: String) -> Array:
	var found: Array = []
	var dir := DirAccess.open(root)
	if dir == null:
		return found
	dir.list_dir_begin()
	var entry_name := dir.get_next()
	while entry_name != "":
		if entry_name == "." or entry_name == "..":
			entry_name = dir.get_next()
			continue
		var full := root.path_join(entry_name)
		if DirAccess.dir_exists_absolute(full):
			found.append_array(_find_manifests(full))
		elif entry_name == "manifest.json":
			found.append(full.replace("\\", "/"))
		entry_name = dir.get_next()
	dir.list_dir_end()
	return found


func _manifests() -> Array:
	var roots := [
		ProjectSettings.globalize_path("res://tests/fixtures/unit"),
		ProjectSettings.globalize_path("res://../fixtures/viewer-v0/bundles"),
		ProjectSettings.globalize_path("res://../fixtures/viewer-v0/sources"),
	]
	var found: Array = []
	for root in roots:
		found.append_array(_find_manifests(root))
	return found


func _sha256_file(path: String) -> String:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return ""
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	while file.get_position() < file.get_length():
		ctx.update(file.get_buffer(mini(65536, file.get_length() - file.get_position())))
	return ctx.finish().hex_encode()


func _mismatched_keys(manifest_path: String) -> Dictionary:
	var json := JSON.new()
	assert_int(json.parse(FileAccess.get_file_as_string(manifest_path))).is_equal(OK)
	var manifest: Dictionary = json.data
	var base_dir := manifest_path.get_base_dir()
	var bad: Dictionary = {}
	var files: Dictionary = manifest.get("files", {})
	for key in files.keys():
		var entry: Dictionary = files[key]
		if not entry.get("present", false):
			continue
		var actual := _sha256_file(base_dir.path_join(entry["path"]))
		if actual != entry.get("sha256"):
			bad[key] = true
	return bad


func test_manifest_scan_finds_expected_fixtures() -> void:
	# A scan that silently under-matches (wrong depth, wrong root) is worse than no guard
	# at all -- it reports green while checking nothing. Fail loudly instead.
	assert_int(_manifests().size()).is_greater_equal(_MIN_MANIFEST_COUNT)


func test_all_fixture_manifest_hashes_match_except_known_exception() -> void:
	var fixture06 := _fixture06_manifest_path()
	var mismatches: Dictionary = {}
	for manifest_path in _manifests():
		var bad := _mismatched_keys(manifest_path)
		if String(manifest_path) == fixture06:
			if bad.size() != 1 or not bad.has("decision_trace"):
				mismatches[manifest_path] = bad
		elif not bad.is_empty():
			mismatches[manifest_path] = bad
	assert_dict(mismatches).is_empty()


func test_fixture06_bundle_is_still_deliberately_mismatched() -> void:
	var fixture06 := _fixture06_manifest_path()
	assert_bool(FileAccess.file_exists(fixture06)).is_true()
	var bad := _mismatched_keys(fixture06)
	assert_bool(bad.has("decision_trace")).is_true()
	assert_int(bad.size()).is_equal(1)
