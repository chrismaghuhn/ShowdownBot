class_name PathContainment
extends RefCounted

## DirAccess.is_link gate for bundle payload containment (Plan B §0.4).


static func is_reparse_point(bundle_root: String, filename: String) -> bool:
	if filename.is_empty():
		return false
	var dir := DirAccess.open(bundle_root)
	if dir == null:
		return false
	return dir.is_link(filename)


static func refuse_if_reparse_point(bundle_root: String, filename: String) -> Dictionary:
	if is_reparse_point(bundle_root, filename):
		return {
			"refuse": true,
			"reason": "symlink_or_reparse_refused",
			"message": "reparse point refused: %s" % filename,
			"offender": filename,
		}
	return {"refuse": false}
