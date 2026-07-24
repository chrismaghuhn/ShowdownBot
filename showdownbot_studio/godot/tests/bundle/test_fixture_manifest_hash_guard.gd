extends GdUnitTestSuite

# Guard: every fixture manifest.json's declared sha256 must match its file's actual bytes.
# Verify-only -- never recomputes or rewrites a mismatch (that would delete the check it
# exists to be; see python/reseal_manifest_hashes.py for the deliberate, hand-run tool that
# does the healing). Two known exceptions exist, both asserted positively below (their own
# tests prove the expected condition still holds), never just excluded from the sweep:
#
# - fixtures/viewer-v0/sources/fixture-06/bundle is DELIBERATELY hash-mismatched -- it is
#   what test_fixture06_hash_mismatch (this directory) and test_app_shell_smoke.gd's
#   test_fixture06_refuse_reason exist to exercise.
# - fixtures/viewer-v0/sources/fixture-08/bundle DELIBERATELY declares decision_trace
#   present:true while the file is absent from disk (bundle contract §14 fixture 8 /
#   §11.1.1 invariant 5) -- it is what test_fixture08_missing_mandatory_file_refuses (this
#   directory) exercises. That's a distinct condition from a hash mismatch (there is no
#   file to hash at all), so it gets its own label, "missing_on_disk", rather than being
#   folded into "hash_mismatch".

# Measured: 11 res://tests/fixtures/unit + 6 bundles/* + 7 sources-bundle dirs
# (fixture-06 plus Plan F's fixtures 7, 8, 12, 22a, 22b, 23).
const _MIN_MANIFEST_COUNT := 24


func _fixture06_manifest_path() -> String:
	return ProjectSettings.globalize_path(
		"res://../fixtures/viewer-v0/sources/fixture-06/bundle/manifest.json"
	).replace("\\", "/")


func _fixture08_manifest_path() -> String:
	return ProjectSettings.globalize_path(
		"res://../fixtures/viewer-v0/sources/fixture-08/bundle/manifest.json"
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


func _bad_keys(manifest_path: String) -> Dictionary:
	# Map each present:true logical key to its problem, if any. A file absent on disk
	# ("missing_on_disk") is a distinct, legitimate fixture state (fixture-08's own
	# condition) from a byte-level hash drift ("hash_mismatch", fixture-06's condition) --
	# different labels so real drift can never be masked as an expected miss.
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
		var file_path := base_dir.path_join(entry["path"])
		if not FileAccess.file_exists(file_path):
			bad[key] = "missing_on_disk"
			continue
		var actual := _sha256_file(file_path)
		if actual != entry.get("sha256"):
			bad[key] = "hash_mismatch"
	return bad


func test_manifest_scan_finds_expected_fixtures() -> void:
	# A scan that silently under-matches (wrong depth, wrong root) is worse than no guard
	# at all -- it reports green while checking nothing. Fail loudly instead.
	assert_int(_manifests().size()).is_greater_equal(_MIN_MANIFEST_COUNT)


func test_all_fixture_manifest_hashes_match_except_known_exception() -> void:
	var fixture06 := _fixture06_manifest_path()
	var fixture08 := _fixture08_manifest_path()
	var mismatches: Dictionary = {}
	for manifest_path in _manifests():
		var bad := _bad_keys(manifest_path)
		var expected: Dictionary = {}
		if String(manifest_path) == fixture06:
			expected = {"decision_trace": "hash_mismatch"}
		elif String(manifest_path) == fixture08:
			expected = {"decision_trace": "missing_on_disk"}
		if bad != expected:
			mismatches[manifest_path] = bad
	assert_dict(mismatches).is_empty()


func test_fixture06_bundle_is_still_deliberately_mismatched() -> void:
	var fixture06 := _fixture06_manifest_path()
	assert_bool(FileAccess.file_exists(fixture06)).is_true()
	var bad := _bad_keys(fixture06)
	assert_dict(bad).is_equal({"decision_trace": "hash_mismatch"})


func test_fixture08_bundle_still_declares_missing_required_file() -> void:
	var fixture08 := _fixture08_manifest_path()
	assert_bool(FileAccess.file_exists(fixture08)).is_true()
	var bad := _bad_keys(fixture08)
	assert_dict(bad).is_equal({"decision_trace": "missing_on_disk"})
