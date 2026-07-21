extends GdUnitTestSuite

## Plan E §5.1 — StateBannerPresenter (16 cases). Baseline tip case count: 189.

const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"


func _fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_FIXTURES_ROOT.path_join(relative))


func _fixture_bundle(rel: String) -> BundleDTO:
	var path := _fixture_path(rel)
	var result: ValidationResult = BundleValidator.validate_dir(path)
	assert_object(result.bundle).is_not_null()
	return result.bundle


func _make_refuse(reason: String = "hash_mismatch") -> RefuseDiagnostic:
	var d := RefuseDiagnostic.new()
	d.reason = reason
	d.message = "synthetic refuse for presenter test"
	d.offender = "test"
	d.seal()
	return d


func _make_decision(phase: String, fallback_used: bool = false) -> DecisionRowDTO:
	var d := DecisionRowDTO.new()
	d.decision_index = 0
	d.turn_number = 1
	d.decision_phase = phase
	d.decision_latency_ms = 0.0
	d.observable_state_hash = "obs"
	d.request_hash = "req"
	d.state_summary = {}
	d.normalized_action = {}
	d.actual_choose_string = "move 1"
	d.fallback_used = fallback_used
	d.warning_count = 0
	d.decision_valid = true
	return d


func _make_bundle(trace_trusted: bool, downgrade_warnings: Array = []) -> BundleDTO:
	var b := BundleDTO.new()
	b.declared_mode = BundleMode.REPLAY_TRACE
	b.effective_mode = BundleMode.REPLAY_TRACE if trace_trusted else BundleMode.REPLAY_ONLY
	b.trace_trusted = trace_trusted
	b.replay_trusted = true
	b.warnings = []
	b.downgrade_warnings = downgrade_warnings
	b.decisions = []
	b.battle_events = []
	return b


func _row_by_decision_index(bundle: BundleDTO, decision_index: int) -> DecisionRowDTO:
	for item in bundle.decisions:
		var row: DecisionRowDTO = item
		if row.decision_index == decision_index:
			return row
	assert_bool(false).override_failure_message(
		"fixture missing decision_index=%d" % decision_index
	).is_true()
	return null


func _row_with_fallback(bundle: BundleDTO) -> DecisionRowDTO:
	for item in bundle.decisions:
		var row: DecisionRowDTO = item
		if row.fallback_used:
			return row
	assert_bool(false).override_failure_message("fixture missing fallback_used row").is_true()
	return null


func test_refuse_is_bundle_invalid() -> void:
	var refuse := _make_refuse()
	var state := StateBannerPresenter.compute(null, null, refuse)
	assert_str(state).is_equal(StateBannerPresenter.BUNDLE_INVALID)


func test_fixture04_trace_missing() -> void:
	var bundle := _fixture_bundle("bundles/fixture-04")
	assert_bool(bundle.trace_trusted).is_false()
	var state := StateBannerPresenter.compute(bundle, null, null)
	assert_str(state).is_equal(StateBannerPresenter.TRACE_MISSING)


func test_waiting_when_no_selection() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	assert_bool(bundle.trace_trusted).is_true()
	assert_bool(bundle.downgrade_warnings.is_empty()).is_true()
	var state := StateBannerPresenter.compute(bundle, null, null)
	assert_str(state).is_equal(StateBannerPresenter.WAITING_NO_DECISION)


func test_fallback_used() -> void:
	var bundle := _fixture_bundle("bundles/fixture-03")
	assert_bool(bundle.trace_trusted).is_true()
	var selected := _row_with_fallback(bundle)
	assert_bool(selected.fallback_used).is_true()
	var state := StateBannerPresenter.compute(bundle, selected, null)
	assert_str(state).is_equal(StateBannerPresenter.FALLBACK_USED)


func test_phase_team_preview() -> void:
	# Real sealed row via Loader → Validator allowlist (bundle_validator.gd:73–75).
	var bundle := _fixture_bundle("bundles/fixture-01")
	var selected := _row_by_decision_index(bundle, 0)
	assert_str(selected.decision_phase).is_equal(BundleMode.PHASE_TEAM_PREVIEW)
	assert_bool(selected.fallback_used).is_false()
	var state := StateBannerPresenter.compute(bundle, selected, null)
	assert_str(state).is_equal(StateBannerPresenter.TEAM_PREVIEW)


func test_phase_forced_replacement() -> void:
	# Real sealed row via full load chain (same rationale as team_preview).
	var bundle := _fixture_bundle("bundles/fixture-01")
	var selected := _row_by_decision_index(bundle, 1)
	assert_str(selected.decision_phase).is_equal(BundleMode.PHASE_FORCED_REPLACEMENT)
	assert_bool(selected.fallback_used).is_false()
	var state := StateBannerPresenter.compute(bundle, selected, null)
	assert_str(state).is_equal(StateBannerPresenter.FORCED_REPLACEMENT)


func test_decision_recorded_regular() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var selected := _row_by_decision_index(bundle, 2)
	assert_str(selected.decision_phase).is_equal(BundleMode.PHASE_REGULAR_TURN)
	var state := StateBannerPresenter.compute(bundle, selected, null)
	assert_str(state).is_equal(StateBannerPresenter.DECISION_RECORDED)


func test_degraded_downgrade_warnings() -> void:
	# 3v4 sample: non-empty downgrade_warnings beats waiting (selected=null).
	var warn := _make_refuse("synthetic_downgrade")
	var bundle := _make_bundle(true, [warn])
	var state := StateBannerPresenter.compute(bundle, null, null)
	assert_str(state).is_equal(StateBannerPresenter.STATE_DEGRADED)


func test_dirty_null_label() -> void:
	assert_str(StateBannerPresenter.dirty_label(null)).is_equal("dirty state not recorded")


func test_precedence_1v2_refuse_beats_trace_missing() -> void:
	# Constructed: bundle and refuse both non-null (shell never holds this pair).
	var bundle := _make_bundle(false)
	assert_bool(bundle.trace_trusted).is_false()
	var refuse := _make_refuse()
	var state := StateBannerPresenter.compute(bundle, null, refuse)
	assert_str(state).is_equal(StateBannerPresenter.BUNDLE_INVALID)


func test_precedence_2v3_trace_missing_beats_degraded() -> void:
	var warn := _make_refuse("synthetic_downgrade")
	var bundle := _make_bundle(false, [warn])
	assert_bool(bundle.trace_trusted).is_false()
	assert_bool(bundle.downgrade_warnings.is_empty()).is_false()
	var state := StateBannerPresenter.compute(bundle, null, null)
	assert_str(state).is_equal(StateBannerPresenter.TRACE_MISSING)


func test_precedence_3v4_degraded_beats_waiting() -> void:
	# Both 3 and 4 match (trusted + downgrade + selected=null); 3 wins.
	var warn := _make_refuse("synthetic_downgrade")
	var bundle := _make_bundle(true, [warn])
	assert_bool(bundle.trace_trusted).is_true()
	assert_bool(bundle.downgrade_warnings.is_empty()).is_false()
	var state := StateBannerPresenter.compute(bundle, null, null)
	assert_str(state).is_equal(StateBannerPresenter.STATE_DEGRADED)


func test_precedence_4v5_waiting_vs_fallback_exclusive() -> void:
	# Unreachable simultaneous: 4 needs selected==null; 5 needs selected+fallback.
	# Document exclusivity by asserting both arms in this named case.
	var bundle := _make_bundle(true)
	assert_str(StateBannerPresenter.compute(bundle, null, null)).is_equal(
		StateBannerPresenter.WAITING_NO_DECISION
	)
	var selected := _make_decision(BundleMode.PHASE_REGULAR_TURN, true)
	assert_str(StateBannerPresenter.compute(bundle, selected, null)).is_equal(
		StateBannerPresenter.FALLBACK_USED
	)


func test_precedence_5v6_fallback_beats_forced() -> void:
	var bundle := _make_bundle(true)
	var selected := _make_decision(BundleMode.PHASE_FORCED_REPLACEMENT, true)
	assert_bool(selected.fallback_used).is_true()
	assert_str(selected.decision_phase).is_equal(BundleMode.PHASE_FORCED_REPLACEMENT)
	var state := StateBannerPresenter.compute(bundle, selected, null)
	assert_str(state).is_equal(StateBannerPresenter.FALLBACK_USED)


func test_precedence_6v7_phases_mutually_exclusive() -> void:
	# FORCED and TEAM cannot co-occur (validator allowlist bundle_validator.gd:73–75).
	# Assert each arm separately; document unreachable simultaneous.
	var bundle := _make_bundle(true)
	var forced := _make_decision(BundleMode.PHASE_FORCED_REPLACEMENT, false)
	assert_str(StateBannerPresenter.compute(bundle, forced, null)).is_equal(
		StateBannerPresenter.FORCED_REPLACEMENT
	)
	var team := _make_decision(BundleMode.PHASE_TEAM_PREVIEW, false)
	assert_str(StateBannerPresenter.compute(bundle, team, null)).is_equal(
		StateBannerPresenter.TEAM_PREVIEW
	)


func test_precedence_7v8_team_preview_beats_decision_recorded() -> void:
	var bundle := _make_bundle(true)
	var selected := _make_decision(BundleMode.PHASE_TEAM_PREVIEW, false)
	var state := StateBannerPresenter.compute(bundle, selected, null)
	assert_str(state).is_equal(StateBannerPresenter.TEAM_PREVIEW)
	assert_str(state).is_not_equal(StateBannerPresenter.DECISION_RECORDED)
