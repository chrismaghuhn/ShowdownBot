class_name CandidateDTO
extends RefCounted

var _sealed: bool = false
var _candidate_id: String = ""
var _rank: int = 0
var _aggregate_score: float = 0.0
var _candidate_key: Variant = null
var _unknown_fields: Dictionary = {}

var candidate_id: String:
	get:
		return _candidate_id
	set(value):
		if _sealed:
			return
		_candidate_id = value

var rank: int:
	get:
		return _rank
	set(value):
		if _sealed:
			return
		_rank = value

var aggregate_score: float:
	get:
		return _aggregate_score
	set(value):
		if _sealed:
			return
		_aggregate_score = value

var candidate_key: Variant:
	get:
		return _candidate_key
	set(value):
		if _sealed:
			return
		_candidate_key = value

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
	_unknown_fields.make_read_only()
	_sealed = true
