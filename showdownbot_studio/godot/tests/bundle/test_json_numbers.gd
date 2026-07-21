extends GdUnitTestSuite


func test_parse_json_int_accepts_int() -> void:
	var result := JsonNumbers.parse_json_int(42, "turn_number")
	assert_dict(result).contains_key_value("ok", true)
	assert_int(result["value"]).is_equal(42)


func test_parse_json_int_accepts_integral_float() -> void:
	var result := JsonNumbers.parse_json_int(42.0, "protocol_index")
	assert_dict(result).contains_key_value("ok", true)
	assert_int(result["value"]).is_equal(42)


func test_parse_json_int_accepts_max_safe_int() -> void:
	var result := JsonNumbers.parse_json_int(9007199254740991, "protocol_index")
	assert_dict(result).contains_key_value("ok", true)
	assert_int(result["value"]).is_equal(9007199254740991)


func test_parse_json_int_rejects_fractional() -> void:
	var result := JsonNumbers.parse_json_int(1.5, "decision_index")
	assert_dict(result).contains_key_value("ok", false)
	assert_str(result["reason"]).contains("malformed_integer")


func test_parse_json_int_rejects_infinity() -> void:
	var pos_inf := JsonNumbers.parse_json_int(INF, "rank")
	assert_dict(pos_inf).contains_key_value("ok", false)

	var neg_inf := JsonNumbers.parse_json_int(-INF, "rank")
	assert_dict(neg_inf).contains_key_value("ok", false)


func test_parse_json_int_rejects_nan() -> void:
	var result := JsonNumbers.parse_json_int(NAN, "rank")
	assert_dict(result).contains_key_value("ok", false)


func test_parse_json_int_rejects_above_safe_range() -> void:
	var result := JsonNumbers.parse_json_int(9007199254740992.0, "decision_index")
	assert_dict(result).contains_key_value("ok", false)
	assert_str(result["reason"]).contains("malformed_integer")


func test_parse_json_int_rejects_below_safe_range() -> void:
	var result := JsonNumbers.parse_json_int(-9007199254740992.0, "decision_index")
	assert_dict(result).contains_key_value("ok", false)
	assert_str(result["reason"]).contains("malformed_integer")


func test_parse_json_int_rejects_bool() -> void:
	var result := JsonNumbers.parse_json_int(true, "present")
	assert_dict(result).contains_key_value("ok", false)
	assert_str(result["reason"]).contains("malformed_type")


func test_parse_json_int_rejects_string() -> void:
	var result := JsonNumbers.parse_json_int("42", "decision_index")
	assert_dict(result).contains_key_value("ok", false)
	assert_str(result["reason"]).contains("malformed_type")


func test_parse_json_float_accepts_float() -> void:
	var result := JsonNumbers.parse_json_float(1.25, "decision_latency_ms")
	assert_dict(result).contains_key_value("ok", true)
	assert_float(result["value"]).is_equal(1.25)


func test_parse_json_float_accepts_int() -> void:
	var result := JsonNumbers.parse_json_float(7, "aggregate_score")
	assert_dict(result).contains_key_value("ok", true)
	assert_float(result["value"]).is_equal(7.0)


func test_parse_json_float_rejects_infinity() -> void:
	var result := JsonNumbers.parse_json_float(INF, "top1_top2_margin")
	assert_dict(result).contains_key_value("ok", false)


func test_parse_json_float_rejects_bool() -> void:
	var result := JsonNumbers.parse_json_float(false, "decision_latency_ms")
	assert_dict(result).contains_key_value("ok", false)
	assert_str(result["reason"]).contains("malformed_type")
