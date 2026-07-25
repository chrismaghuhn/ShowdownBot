extends GdUnitTestSuite

## Pins the VALUES of user-visible string constants against literals.
##
## Every existing assertion on these strings compares the presenter's output to the same
## constant it came from:
##
##     assert_str(DecisionPresenter.optional_text(null)).is_equal(DecisionPresenter.NOT_RECORDED)
##
## That proves the function returns THE CONSTANT, which is worth proving. It can never prove
## the constant's VALUE -- change the constant and both sides of the assertion change with it.
##
## Measured on the merged build, not assumed:
##   NOT_RECORDED   := "0"         -> 276 cases, 0 failures
##   STATE_DEGRADED := "ALL GOOD"  -> 276 cases, 0 failures
##
## Both matter beyond tidiness. Bundle contract §15 gate 27 states the prohibition in exactly
## these terms -- "Absent optional data renders `not recorded`, never `0`, `false`, or `[]`" --
## and the Plan F honesty audit's §1 PASS verdict rests on the banner vocabulary being "a closed
## vocabulary of schema/mode state names, not decision-quality judgments". Neither was enforced
## by anything until this suite; a banner reading "ALL GOOD" where the data is degraded would
## have shipped green.


func test_not_recorded_literal_value() -> void:
	assert_str(DecisionPresenter.NOT_RECORDED).is_equal("not recorded")
	assert_str(DecisionPresenter.AGGREGATION_NOT_RECORDED).is_equal("aggregation mode not recorded")
	assert_str(DecisionPresenter.EMPTY_TRACE_TEXT).is_equal("No decision trace in this bundle")


func test_absence_text_is_never_a_falsy_looking_value() -> void:
	# Gate 27's own wording, asserted directly rather than trusted: the absence marker must
	# never be mistakable for recorded data.
	for forbidden: String in ["0", "false", "true", "[]", "{}", "null", "none", ""]:
		assert_str(DecisionPresenter.NOT_RECORDED.to_lower()).is_not_equal(forbidden)
		assert_str(DecisionPresenter.AGGREGATION_NOT_RECORDED.to_lower()).is_not_equal(forbidden)


func test_state_banner_vocabulary_literal_values() -> void:
	assert_str(StateBannerPresenter.BUNDLE_INVALID).is_equal("BUNDLE INVALID")
	assert_str(StateBannerPresenter.TRACE_MISSING).is_equal("TRACE MISSING")
	assert_str(StateBannerPresenter.STATE_DEGRADED).is_equal("STATE DEGRADED")
	assert_str(StateBannerPresenter.WAITING_NO_DECISION).is_equal("WAITING / NO DECISION ROW")
	assert_str(StateBannerPresenter.FALLBACK_USED).is_equal("FALLBACK USED")
	assert_str(StateBannerPresenter.FORCED_REPLACEMENT).is_equal("FORCED REPLACEMENT")
	assert_str(StateBannerPresenter.TEAM_PREVIEW).is_equal("TEAM PREVIEW")
	assert_str(StateBannerPresenter.DECISION_RECORDED).is_equal("DECISION RECORDED")


func test_banner_vocabulary_stays_a_state_vocabulary() -> void:
	# The honesty audit's §1 verdict depends on these naming a DATA STATE, never a judgment
	# about how good the bot's decision was. A rename to reassuring or evaluative wording is
	# the specific regression this guards -- it would otherwise pass every other test.
	var vocabulary: Array[String] = [
		StateBannerPresenter.BUNDLE_INVALID,
		StateBannerPresenter.TRACE_MISSING,
		StateBannerPresenter.STATE_DEGRADED,
		StateBannerPresenter.WAITING_NO_DECISION,
		StateBannerPresenter.FALLBACK_USED,
		StateBannerPresenter.FORCED_REPLACEMENT,
		StateBannerPresenter.TEAM_PREVIEW,
		StateBannerPresenter.DECISION_RECORDED,
	]
	var judgment_words: Array[String] = [
		"good", "bad", "best", "optimal", "correct", "wrong", "strong", "weak",
		"safe", "unsafe", "winning", "losing", "recommend", "confident", "accurate",
	]
	for term: String in vocabulary:
		var lowered := term.to_lower()
		for word: String in judgment_words:
			assert_bool(lowered.contains(word)).override_failure_message(
				"banner term '%s' contains judgment word '%s'" % [term, word]
			).is_false()
