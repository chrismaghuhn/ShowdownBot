class_name DecisionDeepLink
extends RefCounted

const REASON_MALFORMED_DECISION_ARG := "malformed_decision_arg"
const REASON_AMBIGUOUS_DECISION_ARG := "ambiguous_decision_arg"
const REASON_BATTLE_ID_MISMATCH := "battle_id_mismatch"
const REASON_DECISION_INDEX_NOT_FOUND := "decision_index_not_found"
const REASON_AMBIGUOUS_DECISION_INDEX := "ambiguous_decision_index"
const REASON_TRACE_NOT_TRUSTED := "trace_not_trusted"


class ParseResult extends RefCounted:
	var ok: bool = false
	var battle_id: String = ""
	var decision_index: int = 0
	var reason: String = ""


class ApplyResult extends RefCounted:
	var ok: bool = false
	var decision_row_index: int = -1
	var reason: String = ""


static func parse_arg(value: String) -> ParseResult:
	var r := ParseResult.new()
	var sep := value.rfind(":")
	if sep <= 0 or sep >= value.length() - 1:
		r.reason = REASON_MALFORMED_DECISION_ARG
		return r
	var battle_id := value.substr(0, sep)
	var index_text := value.substr(sep + 1)
	if battle_id.is_empty() or not index_text.is_valid_int():
		r.reason = REASON_MALFORMED_DECISION_ARG
		return r
	r.ok = true
	r.battle_id = battle_id
	r.decision_index = index_text.to_int()
	return r


static func resolve(bundle: BundleDTO, battle_id: String, decision_index: int) -> ApplyResult:
	var r := ApplyResult.new()
	if bundle == null or not bundle.trace_trusted:
		r.reason = REASON_TRACE_NOT_TRUSTED
		return r
	if bundle.manifest == null or str(bundle.manifest.battle_id) != battle_id:
		r.reason = REASON_BATTLE_ID_MISMATCH
		return r
	var found := -1
	for i in range(bundle.decisions.size()):
		var d: DecisionRowDTO = bundle.decisions[i]
		if d.decision_index == decision_index:
			if found >= 0:
				# Defense-in-depth only: BundleValidator already refuses duplicate
				# decision_index (see fixtures/unit/refuse-duplicate-decision-index/).
				# This branch is not a production-covered path and must not be
				# counted as one.
				r.reason = REASON_AMBIGUOUS_DECISION_INDEX
				return r
			found = i
	if found < 0:
		r.reason = REASON_DECISION_INDEX_NOT_FOUND
		return r
	r.ok = true
	r.decision_row_index = found
	return r
