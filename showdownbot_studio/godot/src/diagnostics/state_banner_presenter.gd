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
	# Priority 3: downgrade_warnings (validator :304–308) OR absent optional display
	# file on manifest.files — warnings / config_manifest only (see helper).
	if not bundle.downgrade_warnings.is_empty() or _absent_optional_display_file(bundle):
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


## True when warnings or config_manifest is optional and absent.
## Mode-peer absences (battle_log on TRACE_ONLY, decision_trace on REPLAY_ONLY) are
## not display degradation — unrestricted required==false&&present==false would
## paint every TRACE_ONLY load as STATE DEGRADED. Validator forces warnings /
## config_manifest optional (bundle_validator.gd:193–200); absent → continue
## with no downgrade_warnings (:209/:218).
static func _absent_optional_display_file(bundle: BundleDTO) -> bool:
	if bundle.manifest == null:
		return false
	var files: FilesTableDTO = bundle.manifest.files
	if files == null:
		return false
	for entry in [files.warnings, files.config_manifest]:
		if entry != null and not entry.required and not entry.present:
			return true
	return false
