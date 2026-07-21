class_name DecisionPresenter
extends RefCounted

const AGGREGATION_NOT_RECORDED := "aggregation mode not recorded"
const NOT_RECORDED := "not recorded"
const EMPTY_TRACE_TEXT := "No decision trace in this bundle"
const SORT_RANK := "rank"
const SORT_SCORE := "score"
const SORT_LABEL := "label"
const SORT_KEY := "key"
const SORT_CHOSEN_FIRST := "chosen_first"


static func resolve_chosen_row_index(decision: DecisionRowDTO) -> int:
	if decision == null or not decision.decision_valid:
		return -1
	if decision.candidates.is_empty():
		return -1
	if decision.chosen_candidate_key == null:
		return -1
	var key := str(decision.chosen_candidate_key)
	var found := -1
	for i in range(decision.candidates.size()):
		var c: CandidateDTO = decision.candidates[i]
		if c.candidate_key != null and str(c.candidate_key) == key:
			if found >= 0:
				return -1
			found = i
	return found


static func aggregation_headline(decision: DecisionRowDTO) -> String:
	if decision.aggregation_mode == null \
			and decision.aggregation_risk_lambda == null \
			and decision.aggregation_must_react_lambda == null:
		return AGGREGATION_NOT_RECORDED
	if decision.aggregation_mode == null:
		return NOT_RECORDED
	return str(decision.aggregation_mode)


static func optional_text(value: Variant) -> String:
	return NOT_RECORDED if value == null else str(value)


static func header_text(decision: DecisionRowDTO) -> String:
	if decision == null:
		return ""
	var base := "decision #%d" % decision.decision_index
	if not decision.decision_valid:
		base += " (invalid)"
	return base


static func sorted_candidate_indices(decision: DecisionRowDTO, mode: String) -> PackedInt32Array:
	var idxs: Array = []
	for i in range(decision.candidates.size()):
		idxs.append(i)
	var chosen := resolve_chosen_row_index(decision)
	idxs.sort_custom(func(a, b):
		var ca: CandidateDTO = decision.candidates[a]
		var cb: CandidateDTO = decision.candidates[b]
		match mode:
			SORT_SCORE:
				if ca.aggregate_score == cb.aggregate_score:
					return ca.rank < cb.rank
				return ca.aggregate_score > cb.aggregate_score
			SORT_LABEL:
				var la := ca.candidate_id
				var lb := cb.candidate_id
				if la == lb:
					return ca.rank < cb.rank
				return la < lb
			SORT_KEY:
				var ka := "" if ca.candidate_key == null else str(ca.candidate_key)
				var kb := "" if cb.candidate_key == null else str(cb.candidate_key)
				if ka == kb:
					return ca.rank < cb.rank
				return ka < kb
			SORT_CHOSEN_FIRST:
				var a_ch: bool = a == chosen
				var b_ch: bool = b == chosen
				if a_ch != b_ch:
					return a_ch
				return ca.rank < cb.rank
			_:
				return ca.rank < cb.rank
	)
	var out := PackedInt32Array()
	for i in idxs:
		out.append(int(i))
	return out


static func find_next_nav_row(
		bundle: BundleDTO,
		current_decision_index: int,
		kind: String
) -> int:
	var best_row := -1
	var best_id := 2147483647
	for row_i in range(bundle.decisions.size()):
		var d: DecisionRowDTO = bundle.decisions[row_i]
		if d.decision_index <= current_decision_index:
			continue
		var ok := false
		match kind:
			"decision":
				ok = true
			"close":
				ok = d.top1_top2_margin != null
			"fallback":
				ok = d.fallback_used
			"warning":
				ok = d.warning_count > 0
			_:
				ok = false
		if ok and d.decision_index < best_id:
			best_id = d.decision_index
			best_row = row_i
	return best_row


static func find_prev_decision_row(bundle: BundleDTO, current_decision_index: int) -> int:
	var best_row := -1
	var best_id := -2147483648
	for row_i in range(bundle.decisions.size()):
		var d: DecisionRowDTO = bundle.decisions[row_i]
		if d.decision_index >= current_decision_index:
			continue
		if d.decision_index > best_id:
			best_id = d.decision_index
			best_row = row_i
	return best_row


static func timeline_entry_for_decision_row(replay: ReplayDTO, decision_row_index: int) -> int:
	if replay == null:
		return -1
	for i in range(replay.entries.size()):
		var e: TimelineEntryDTO = replay.entries[i]
		if e.kind == TimelineEntryKind.DECISION \
				or e.kind == TimelineEntryKind.DECISION_WITHOUT_REPLAY_EVENT:
			if e.decision_row_index == decision_row_index:
				return i
	return -1


static func first_row_by_decision_index(bundle: BundleDTO) -> int:
	if bundle == null or bundle.decisions.is_empty():
		return -1
	var best_row := 0
	var best_id: int = bundle.decisions[0].decision_index
	for i in range(1, bundle.decisions.size()):
		var d: DecisionRowDTO = bundle.decisions[i]
		if d.decision_index < best_id:
			best_id = d.decision_index
			best_row = i
	return best_row


static func format_state_summary(decision: DecisionRowDTO) -> String:
	if decision == null or decision.state_summary.is_empty():
		return NOT_RECORDED
	var keys: Array = decision.state_summary.keys()
	keys.sort()
	var lines: PackedStringArray = PackedStringArray()
	for k in keys:
		lines.append("%s: %s" % [str(k), str(decision.state_summary[k])])
	return "\n".join(lines)
