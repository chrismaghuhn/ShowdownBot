class_name DecisionRowDTO
extends RefCounted

var _sealed: bool = false
var _decision_index: int = 0
var _turn_number: int = 0
var _decision_phase: String = ""
var _decision_latency_ms: float = 0.0
var _observable_state_hash: String = ""
var _request_hash: String = ""
var _state_summary: Dictionary = {}
var _normalized_action: Dictionary = {}
var _actual_choose_string: String = ""
var _candidates: Array = []
var _chosen_candidate_key: Variant = null
var _chosen_candidate_id: Variant = null
var _chosen_rank: Variant = null
var _chosen_tera_slot: Variant = null
var _chosen_mega_slot: Variant = null
var _selection_stage: Variant = null
var _fallback_reason: Variant = null
var _aggregation_mode: Variant = null
var _aggregation_risk_lambda: Variant = null
var _aggregation_must_react_lambda: Variant = null
var _request_protocol_index: Variant = null
var _top1_top2_margin: Variant = null
var _fallback_used: bool = false
var _warning_count: int = 0
var _decision_valid: bool = true
var _unknown_fields: Dictionary = {}

var decision_index: int:
	get:
		return _decision_index
	set(value):
		if _sealed:
			return
		_decision_index = value

var turn_number: int:
	get:
		return _turn_number
	set(value):
		if _sealed:
			return
		_turn_number = value

var decision_phase: String:
	get:
		return _decision_phase
	set(value):
		if _sealed:
			return
		_decision_phase = value

var decision_latency_ms: float:
	get:
		return _decision_latency_ms
	set(value):
		if _sealed:
			return
		_decision_latency_ms = value

var observable_state_hash: String:
	get:
		return _observable_state_hash
	set(value):
		if _sealed:
			return
		_observable_state_hash = value

var request_hash: String:
	get:
		return _request_hash
	set(value):
		if _sealed:
			return
		_request_hash = value

var state_summary: Dictionary:
	get:
		return _state_summary
	set(value):
		if _sealed:
			return
		_state_summary = value.duplicate(true) if value != null else {}

var normalized_action: Dictionary:
	get:
		return _normalized_action
	set(value):
		if _sealed:
			return
		_normalized_action = value.duplicate(true) if value != null else {}

var actual_choose_string: String:
	get:
		return _actual_choose_string
	set(value):
		if _sealed:
			return
		_actual_choose_string = value

var candidates: Array:
	get:
		return _candidates
	set(value):
		if _sealed:
			return
		_candidates = value if value != null else []

var chosen_candidate_key: Variant:
	get:
		return _chosen_candidate_key
	set(value):
		if _sealed:
			return
		_chosen_candidate_key = value

var chosen_candidate_id: Variant:
	get:
		return _chosen_candidate_id
	set(value):
		if _sealed:
			return
		_chosen_candidate_id = value

var chosen_rank: Variant:
	get:
		return _chosen_rank
	set(value):
		if _sealed:
			return
		_chosen_rank = value

var chosen_tera_slot: Variant:
	get:
		return _chosen_tera_slot
	set(value):
		if _sealed:
			return
		_chosen_tera_slot = value

var chosen_mega_slot: Variant:
	get:
		return _chosen_mega_slot
	set(value):
		if _sealed:
			return
		_chosen_mega_slot = value

var selection_stage: Variant:
	get:
		return _selection_stage
	set(value):
		if _sealed:
			return
		_selection_stage = value

var fallback_reason: Variant:
	get:
		return _fallback_reason
	set(value):
		if _sealed:
			return
		_fallback_reason = value

var aggregation_mode: Variant:
	get:
		return _aggregation_mode
	set(value):
		if _sealed:
			return
		_aggregation_mode = value

var aggregation_risk_lambda: Variant:
	get:
		return _aggregation_risk_lambda
	set(value):
		if _sealed:
			return
		_aggregation_risk_lambda = value

var aggregation_must_react_lambda: Variant:
	get:
		return _aggregation_must_react_lambda
	set(value):
		if _sealed:
			return
		_aggregation_must_react_lambda = value

var request_protocol_index: Variant:
	get:
		return _request_protocol_index
	set(value):
		if _sealed:
			return
		_request_protocol_index = value

var top1_top2_margin: Variant:
	get:
		return _top1_top2_margin
	set(value):
		if _sealed:
			return
		_top1_top2_margin = value

var fallback_used: bool:
	get:
		return _fallback_used
	set(value):
		if _sealed:
			return
		_fallback_used = value

var warning_count: int:
	get:
		return _warning_count
	set(value):
		if _sealed:
			return
		_warning_count = value

var decision_valid: bool:
	get:
		return _decision_valid
	set(value):
		if _sealed:
			return
		_decision_valid = value

var unknown_fields: Dictionary:
	get:
		return _unknown_fields
	set(value):
		if _sealed:
			return
		_unknown_fields = value if value != null else {}


func seal() -> void:
	if _sealed:
		return
	for candidate in _candidates:
		if candidate is CandidateDTO:
			candidate.seal()
	JsonNumbers.freeze_containers(_state_summary)
	JsonNumbers.freeze_containers(_normalized_action)
	JsonNumbers.freeze_containers(_unknown_fields)
	_candidates.make_read_only()
	_sealed = true
