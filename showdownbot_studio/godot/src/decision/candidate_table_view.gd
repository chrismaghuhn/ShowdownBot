class_name CandidateTableView
extends VBoxContainer

signal candidate_selected(candidate_index: int)

@onready var _filter_edit: LineEdit = $FilterRow/FilterLineEdit
@onready var _chosen_only: CheckBox = $FilterRow/ChosenOnlyCheckBox
@onready var _sort: OptionButton = $SortOption
@onready var _list: ItemList = $CandidateList

var _decision: DecisionRowDTO = null
var _mode: String = DecisionPresenter.SORT_RANK
var _filter_text: String = ""
var _chosen_only_on: bool = false
## Index into decision.candidates (−1 = none). Independent of chosen marker.
var _selected_candidate_index: int = -1
## Parallel to ItemList rows: candidates array index for each visible item.
var _visible_candidate_indices: PackedInt32Array = PackedInt32Array()


func _ready() -> void:
	_sort.clear()
	_sort.add_item(DecisionPresenter.SORT_RANK)
	_sort.add_item(DecisionPresenter.SORT_SCORE)
	_sort.add_item(DecisionPresenter.SORT_LABEL)
	_sort.add_item(DecisionPresenter.SORT_KEY)
	_sort.add_item(DecisionPresenter.SORT_CHOSEN_FIRST)
	_sort.item_selected.connect(_on_sort_selected)
	_list.item_selected.connect(_on_item_selected)
	_filter_edit.text_changed.connect(_on_filter_text_changed)
	_chosen_only.toggled.connect(_on_chosen_only_toggled)


func bind(decision: DecisionRowDTO) -> void:
	_decision = decision
	_reset_selection_for_decision()
	_rebuild()
	candidate_selected.emit(_selected_candidate_index)


func clear_view() -> void:
	_decision = null
	_selected_candidate_index = -1
	_visible_candidate_indices = PackedInt32Array()
	_list.clear()
	candidate_selected.emit(-1)


func get_item_count() -> int:
	return _list.item_count


func get_selected_candidate_index() -> int:
	return _selected_candidate_index


func get_selected_candidate() -> CandidateDTO:
	if _decision == null or _selected_candidate_index < 0:
		return null
	if _selected_candidate_index >= _decision.candidates.size():
		return null
	return _decision.candidates[_selected_candidate_index]


func get_chosen_item_index() -> int:
	# Visual list index of chosen marker among currently visible rows, or -1.
	if _decision == null:
		return -1
	var chosen_row := DecisionPresenter.resolve_chosen_row_index(_decision)
	if chosen_row < 0:
		return -1
	for visual_i in range(_visible_candidate_indices.size()):
		if int(_visible_candidate_indices[visual_i]) == chosen_row:
			return visual_i
	return -1


func get_sort_mode() -> String:
	return _mode


func set_sort_mode(mode: String) -> void:
	_mode = mode
	for i in range(_sort.item_count):
		if _sort.get_item_text(i) == mode:
			_sort.select(i)
			break
	_rebuild()


func focus_selected() -> void:
	# Plan D API for "jump to selected candidate"; Plan E binds the shortcut.
	var visual := _visual_index_for_candidate(_selected_candidate_index)
	if visual < 0:
		return
	_list.select(visual)
	_list.ensure_current_is_visible()


func select_candidate_index(candidate_index: int) -> void:
	# Test/API seam: select by candidates[] index without simulating InputEvent.
	if _decision == null or candidate_index < 0 or candidate_index >= _decision.candidates.size():
		return
	var visual := _visual_index_for_candidate(candidate_index)
	if visual < 0:
		return
	_list.select(visual)
	_on_item_selected(visual)


func get_filter_line_edit() -> LineEdit:
	return _filter_edit


func set_filter_text(text: String) -> void:
	# Test/API seam — same path as FilterLineEdit.text_changed.
	_filter_edit.text = text
	_on_filter_text_changed(text)


func set_chosen_only(pressed: bool) -> void:
	_chosen_only.button_pressed = pressed
	_on_chosen_only_toggled(pressed)


func _on_sort_selected(index: int) -> void:
	_mode = _sort.get_item_text(index)
	_rebuild()


func _on_filter_text_changed(text: String) -> void:
	_filter_text = text
	_reset_selection_for_decision()
	_rebuild()
	# Must notify: reset alone does not emit; detail would otherwise stay on prior selection.
	candidate_selected.emit(_selected_candidate_index)


func _on_chosen_only_toggled(pressed: bool) -> void:
	_chosen_only_on = pressed
	_reset_selection_for_decision()
	_rebuild()
	candidate_selected.emit(_selected_candidate_index)


func _on_item_selected(visual_index: int) -> void:
	if visual_index < 0 or visual_index >= _visible_candidate_indices.size():
		return
	_selected_candidate_index = int(_visible_candidate_indices[visual_index])
	candidate_selected.emit(_selected_candidate_index)


func _reset_selection_for_decision() -> void:
	if _decision == null:
		_selected_candidate_index = -1
		return
	var chosen := DecisionPresenter.resolve_chosen_row_index(_decision)
	_selected_candidate_index = chosen if chosen >= 0 else -1


func _visual_index_for_candidate(candidate_index: int) -> int:
	if candidate_index < 0:
		return -1
	for i in range(_visible_candidate_indices.size()):
		if int(_visible_candidate_indices[i]) == candidate_index:
			return i
	return -1


func _passes_filter(candidate_index: int, chosen_row: int) -> bool:
	var c: CandidateDTO = _decision.candidates[candidate_index]
	if _chosen_only_on and candidate_index != chosen_row:
		return false
	if _filter_text.is_empty():
		return true
	var needle := _filter_text.to_lower()
	var label := c.candidate_id.to_lower()
	var key_text := DecisionPresenter.optional_text(c.candidate_key).to_lower()
	return label.contains(needle) or key_text.contains(needle)


func _rebuild() -> void:
	_list.clear()
	_visible_candidate_indices = PackedInt32Array()
	if _decision == null:
		return
	var chosen_row := DecisionPresenter.resolve_chosen_row_index(_decision)
	var order := DecisionPresenter.sorted_candidate_indices(_decision, _mode)
	for i in range(order.size()):
		var row_i: int = int(order[i])
		if not _passes_filter(row_i, chosen_row):
			continue
		var c: CandidateDTO = _decision.candidates[row_i]
		var key_text := DecisionPresenter.optional_text(c.candidate_key)
		var marker := "* " if row_i == chosen_row else "  "
		var line := "%s[%d] %s | %s | %.4f" % [
			marker, c.rank, c.candidate_id, key_text, c.aggregate_score
		]
		_list.add_item(line)
		_visible_candidate_indices.append(row_i)
	var visual := _visual_index_for_candidate(_selected_candidate_index)
	if visual >= 0:
		_list.select(visual)
	elif _selected_candidate_index >= 0:
		# Filtered out: drop selection; callers (bind/filter/chosen-only) emit after _rebuild.
		_selected_candidate_index = -1
