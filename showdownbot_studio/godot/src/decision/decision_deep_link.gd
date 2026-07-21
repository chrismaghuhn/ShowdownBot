class_name DecisionDeepLink
extends RefCounted

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
	var sep := value.find(":")
	if sep <= 0 or sep >= value.length() - 1:
		r.reason = "malformed_decision_arg"
		return r
	var battle_id := value.substr(0, sep)
	var index_text := value.substr(sep + 1)
	if battle_id.is_empty() or not index_text.is_valid_int():
		r.reason = "malformed_decision_arg"
		return r
	r.ok = true
	r.battle_id = battle_id
	r.decision_index = index_text.to_int()
	return r


static func resolve(bundle: BundleDTO, battle_id: String, decision_index: int) -> ApplyResult:
	var r := ApplyResult.new()
	if bundle == null or not bundle.trace_trusted:
		r.reason = "trace_not_trusted"
		return r
	if bundle.manifest == null or str(bundle.manifest.battle_id) != battle_id:
		r.reason = "battle_id_mismatch"
		return r
	var found := -1
	for i in range(bundle.decisions.size()):
		var d: DecisionRowDTO = bundle.decisions[i]
		if d.decision_index == decision_index:
			if found >= 0:
				r.reason = "ambiguous_decision_index"
				return r
			found = i
	if found < 0:
		r.reason = "decision_index_not_found"
		return r
	r.ok = true
	r.decision_row_index = found
	return r
