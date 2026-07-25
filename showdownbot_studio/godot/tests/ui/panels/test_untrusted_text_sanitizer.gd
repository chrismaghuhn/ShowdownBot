extends GdUnitTestSuite


func test_control_characters_are_stripped() -> void:
	# NOTE: the plan's own sample used "\x01"/"\x02" escapes, which GDScript's string literal
	# grammar does not support (no \xHH hex escape, unlike Python) -- a real parse error, not a
	# revision-note conflict. char(1)/char(2) build the identical control-character content.
	var sanitized := UntrustedTextSanitizer.sanitize("hello" + char(1) + char(2) + "world")
	assert_bool(sanitized.contains(char(1))).is_false()
	assert_str(sanitized).is_equal("helloworld")


func test_length_is_capped() -> void:
	var long_text := "a".repeat(1000)
	var sanitized := UntrustedTextSanitizer.sanitize(long_text)
	assert_int(sanitized.length()).is_equal(UntrustedTextSanitizer.MAX_LENGTH)


func test_normal_text_passes_through_unchanged() -> void:
	assert_str(UntrustedTextSanitizer.sanitize("Alice vs Bob")).is_equal("Alice vs Bob")
