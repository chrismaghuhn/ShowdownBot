class_name JsonNumbers
extends RefCounted

## JSON number parsing helpers for viewer bundle contract §5.
## Result pattern: every parse returns `{ ok: bool, value: Variant, reason: String }`.
## Callers must check `ok` before using `value`; no exceptions are thrown.

const MAX_SAFE_JSON_INT := 9007199254740991
const MIN_SAFE_JSON_INT := -9007199254740991


static func parse_json_int(value: Variant, field_name: String) -> Dictionary:
	var value_type := typeof(value)
	if value_type != TYPE_FLOAT and value_type != TYPE_INT:
		return _fail(
			"malformed_type: %s must be a JSON number, got %s" % [field_name, _type_name(value_type)]
		)

	if value_type == TYPE_INT:
		var as_int := value as int
		if as_int < MIN_SAFE_JSON_INT or as_int > MAX_SAFE_JSON_INT:
			return _fail("malformed_integer: %s out of safe integer range" % field_name)
		return _ok(as_int)

	var as_float := float(value)
	if not is_finite(as_float):
		return _fail("malformed_integer: %s must be finite" % field_name)

	if as_float != floor(as_float):
		return _fail("malformed_integer: %s must be integral" % field_name)

	if as_float < MIN_SAFE_JSON_INT or as_float > MAX_SAFE_JSON_INT:
		return _fail("malformed_integer: %s out of safe integer range" % field_name)

	return _ok(int(as_float))


static func parse_json_float(value: Variant, field_name: String) -> Dictionary:
	var value_type := typeof(value)
	if value_type != TYPE_FLOAT and value_type != TYPE_INT:
		return _fail(
			"malformed_type: %s must be a JSON number, got %s" % [field_name, _type_name(value_type)]
		)

	var as_float := float(value)
	if not is_finite(as_float):
		return _fail("malformed_type: %s must be finite" % field_name)

	return _ok(as_float)


static func _ok(value: Variant) -> Dictionary:
	return {"ok": true, "value": value, "reason": ""}


static func _fail(reason: String) -> Dictionary:
	return {"ok": false, "value": null, "reason": reason}


static func _type_name(value_type: int) -> String:
	match value_type:
		TYPE_BOOL:
			return "bool"
		TYPE_STRING:
			return "string"
		TYPE_NIL:
			return "null"
		_:
			return str(value_type)


static func freeze_containers(value: Variant) -> void:
	if value is Dictionary:
		var dict := value as Dictionary
		for key in dict.keys():
			freeze_containers(dict[key])
		dict.make_read_only()
	elif value is Array:
		var arr := value as Array
		for item in arr:
			freeze_containers(item)
		arr.make_read_only()
