class_name StateBannerPresenter
extends RefCounted

const BUNDLE_INVALID := "BUNDLE INVALID"
const TRACE_MISSING := "TRACE MISSING"
const STATE_DEGRADED := "STATE DEGRADED"
const WAITING_NO_DECISION := "WAITING / NO DECISION ROW"
const FALLBACK_USED := "FALLBACK USED"
const FORCED_REPLACEMENT := "FORCED REPLACEMENT"
const TEAM_PREVIEW := "TEAM PREVIEW"
const DECISION_RECORDED := "DECISION RECORDED"


## Returns one of the consts above.
static func compute(
		bundle: BundleDTO,
		selected: DecisionRowDTO,
		refuse: RefuseDiagnostic
) -> String:
	# Priority table §0.5 — implement exactly; no extra states in v0.
	# 1: refuse wins even when bundle is non-null (presenter precedence 1v2).
	#    bundle == null covers "no successful load" (shell refuse clears bundle).
	if refuse != null or bundle == null:
		return BUNDLE_INVALID
	if not bundle.trace_trusted:
		return TRACE_MISSING
	if not bundle.downgrade_warnings.is_empty():
		return STATE_DEGRADED
	if selected == null:
		return WAITING_NO_DECISION
	if selected.fallback_used:
		return FALLBACK_USED
	if selected.decision_phase == BundleMode.PHASE_FORCED_REPLACEMENT:
		return FORCED_REPLACEMENT
	if selected.decision_phase == BundleMode.PHASE_TEAM_PREVIEW:
		return TEAM_PREVIEW
	# After 6–7, allowlist leaves only PHASE_REGULAR_TURN (bundle_validator.gd:73–75).
	return DECISION_RECORDED


static func dirty_label(dirty: Variant) -> String:
	if dirty == null:
		return "dirty state not recorded"
	return "dirty: true" if dirty else "dirty: false"
