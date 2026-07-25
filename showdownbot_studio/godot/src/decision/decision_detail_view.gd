class_name DecisionDetailView
extends TabContainer

@onready var _aggregation: Label = $Overview/AggregationLabel
@onready var _risk: Label = $Overview/RiskLambdaLabel
@onready var _must_react: Label = $Overview/MustReactLambdaLabel
@onready var _latency: Label = $Overview/LatencyLabel
@onready var _choose: Label = $Overview/ChooseStringLabel
@onready var _chosen_key: Label = $Overview/ChosenKeyLabel
@onready var _chosen_id: Label = $Overview/ChosenIdLabel
@onready var _request_hash: Label = $Overview/RequestHashLabel
@onready var _observable_hash: Label = $Overview/ObservableHashLabel
@onready var _cand_id: Label = $Candidate/CandidateIdLabel
@onready var _cand_rank: Label = $Candidate/CandidateRankLabel
@onready var _cand_score: Label = $Candidate/CandidateScoreLabel
@onready var _cand_key: Label = $Candidate/CandidateKeyLabel
@onready var _state_summary: Label = $StateSummary/StateSummaryLabel

var _decision: DecisionRowDTO = null


func _ready() -> void:
	# §0.8 "Visual truncate + tooltip/full detail": candidate_key runs to
	# ~286 chars (JSON), which otherwise makes this Label's minimum width the
	# full text width and pushes the whole shell wider than the window (the
	# owner-reported "screen shifts right" bug). clip_text stops the full
	# text width from entering the minimum size; text_overrun_behavior draws
	# the visible ellipsis. The full value is never touched -- only display
	# -- and stays reachable via tooltip_text (set in bind_*, see below) and
	# the Raw tab.
	for lbl in [_chosen_key, _cand_key]:
		lbl.clip_text = true
		lbl.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS


func bind_decision(decision: DecisionRowDTO) -> void:
	_decision = decision
	if decision == null:
		clear_view()
		return
	_aggregation.text = "aggregation: %s" % DecisionPresenter.aggregation_headline(decision)
	_risk.text = "risk_lambda: %s" % DecisionPresenter.optional_text(
		decision.aggregation_risk_lambda
	)
	_must_react.text = "must_react_lambda: %s" % DecisionPresenter.optional_text(
		decision.aggregation_must_react_lambda
	)
	_latency.text = "latency_ms: %s" % str(decision.decision_latency_ms)
	_choose.text = "actual_choose: %s" % decision.actual_choose_string
	_chosen_key.text = "chosen_key: %s" % DecisionPresenter.optional_text(
		decision.chosen_candidate_key
	)
	_chosen_key.tooltip_text = _chosen_key.text
	_chosen_id.text = "chosen_id (label, not identity): %s" % DecisionPresenter.optional_text(
		decision.chosen_candidate_id
	)
	_request_hash.text = "request_hash: %s" % decision.request_hash
	_observable_hash.text = "observable_state_hash: %s" % decision.observable_state_hash
	_state_summary.text = DecisionPresenter.format_state_summary(decision)


func bind_candidate(candidate: CandidateDTO) -> void:
	if candidate == null:
		_cand_id.text = "candidate: %s" % DecisionPresenter.NOT_RECORDED
		_cand_rank.text = ""
		_cand_score.text = ""
		_cand_key.text = ""
		_cand_key.tooltip_text = ""
		return
	_cand_id.text = "candidate_id: %s" % candidate.candidate_id
	_cand_rank.text = "rank: %d" % candidate.rank
	_cand_score.text = "aggregate_score: %.4f" % candidate.aggregate_score
	_cand_key.text = "candidate_key: %s" % DecisionPresenter.optional_text(candidate.candidate_key)
	_cand_key.tooltip_text = _cand_key.text


func clear_view() -> void:
	_decision = null
	for lbl in [
		_aggregation, _risk, _must_react, _latency, _choose, _chosen_key, _chosen_id,
		_request_hash, _observable_hash, _cand_id, _cand_rank, _cand_score, _cand_key,
		_state_summary,
	]:
		lbl.text = ""
	_chosen_key.tooltip_text = ""
	_cand_key.tooltip_text = ""


func get_aggregation_text() -> String:
	return _aggregation.text


func get_latency_text() -> String:
	return _latency.text


func get_candidate_id_text() -> String:
	return _cand_id.text
