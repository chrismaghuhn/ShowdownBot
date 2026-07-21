class_name DecisionController
extends Node

signal decision_selection_changed(decision_row_index: int)

var _bundle: BundleDTO = null
var _timeline: TimelineController = null
var _selected_row: int = -1
var _suppress_timeline_echo: bool = false


func reset(bundle: BundleDTO, timeline: TimelineController) -> void:
	if _timeline != null and _timeline.selection_changed.is_connected(on_timeline_selection):
		_timeline.selection_changed.disconnect(on_timeline_selection)
	_suppress_timeline_echo = false
	_selected_row = -1
	# Fail-closed: never retain an untrusted bundle for navigation (B1).
	if bundle == null or not bundle.trace_trusted:
		_bundle = null
		_timeline = timeline
		if _timeline != null:
			_timeline.selection_changed.connect(on_timeline_selection)
		decision_selection_changed.emit(_selected_row)
		return
	_bundle = bundle
	_timeline = timeline
	if _timeline != null:
		_timeline.selection_changed.connect(on_timeline_selection)
	if bundle.decisions.size() > 0:
		_selected_row = DecisionPresenter.first_row_by_decision_index(bundle)
	decision_selection_changed.emit(_selected_row)
	# Do NOT sync timeline here — Plan C keeps entry 0 / -1 (§0.6).


func clear() -> void:
	if _timeline != null and _timeline.selection_changed.is_connected(on_timeline_selection):
		_timeline.selection_changed.disconnect(on_timeline_selection)
	_suppress_timeline_echo = false
	_bundle = null
	_timeline = null
	_selected_row = -1
	decision_selection_changed.emit(_selected_row)


func on_timeline_selection(entry_index: int) -> void:
	if _suppress_timeline_echo:
		return
	if not _is_trace_live() or _timeline == null:
		return
	var replay: ReplayDTO = _timeline.get_replay()
	if replay == null or entry_index < 0 or entry_index >= replay.entries.size():
		return
	var entry: TimelineEntryDTO = replay.entries[entry_index]
	if entry.kind == TimelineEntryKind.EVENT:
		return
	if entry.decision_row_index < 0:
		return
	_set_row(entry.decision_row_index, false)


func select_decision_row(row_i: int) -> void:
	_set_row(row_i, true)


func jump_next(kind: String) -> void:
	if not _is_trace_live() or _selected_row < 0:
		return
	var cur: DecisionRowDTO = _bundle.decisions[_selected_row]
	var next_row := DecisionPresenter.find_next_nav_row(_bundle, cur.decision_index, kind)
	if next_row >= 0:
		select_decision_row(next_row)


func jump_prev_decision() -> void:
	if not _is_trace_live() or _selected_row < 0:
		return
	var cur: DecisionRowDTO = _bundle.decisions[_selected_row]
	var prev_row := DecisionPresenter.find_prev_decision_row(_bundle, cur.decision_index)
	if prev_row >= 0:
		select_decision_row(prev_row)


func get_selected_decision_row_index() -> int:
	return _selected_row


func get_selected_decision() -> DecisionRowDTO:
	if not _is_trace_live() or _selected_row < 0:
		return null
	return _bundle.decisions[_selected_row]


func has_next(kind: String) -> bool:
	if not _is_trace_live() or _selected_row < 0:
		return false
	var cur: DecisionRowDTO = _bundle.decisions[_selected_row]
	return DecisionPresenter.find_next_nav_row(_bundle, cur.decision_index, kind) >= 0


func has_prev_decision() -> bool:
	if not _is_trace_live() or _selected_row < 0:
		return false
	var cur: DecisionRowDTO = _bundle.decisions[_selected_row]
	return DecisionPresenter.find_prev_decision_row(_bundle, cur.decision_index) >= 0


func _is_trace_live() -> bool:
	return _bundle != null and _bundle.trace_trusted


func _set_row(row_i: int, sync_timeline: bool) -> void:
	if not _is_trace_live() or row_i < 0 or row_i >= _bundle.decisions.size():
		return
	if row_i == _selected_row:
		if sync_timeline:
			_sync_timeline_to_row(row_i)
		return
	_selected_row = row_i
	decision_selection_changed.emit(_selected_row)
	if sync_timeline:
		_sync_timeline_to_row(row_i)


func _sync_timeline_to_row(row_i: int) -> void:
	if _timeline == null or row_i < 0:
		return
	var entry_i := DecisionPresenter.timeline_entry_for_decision_row(
		_timeline.get_replay(), row_i
	)
	if entry_i < 0:
		return
	_suppress_timeline_echo = true
	_timeline.select(entry_i)
	_suppress_timeline_echo = false
