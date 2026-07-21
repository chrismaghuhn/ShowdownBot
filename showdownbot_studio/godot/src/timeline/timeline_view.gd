class_name TimelineView
extends VBoxContainer

@onready var _loading: Label = $LoadingLabel
@onready var _list: ItemList = $EntryList
@onready var _prev: Button = $Controls/PrevButton
@onready var _next: Button = $Controls/NextButton
@onready var _start: Button = $Controls/StartButton
@onready var _end: Button = $Controls/EndButton
@onready var _play: Button = $Controls/PlayButton

var _controller: TimelineController = null
var _labels: PackedStringArray = PackedStringArray()


func set_controller(controller: TimelineController) -> void:
	_controller = controller
	if not _prev.pressed.is_connected(_controller.step_prev):
		_prev.pressed.connect(_controller.step_prev)
		_next.pressed.connect(_controller.step_next)
		_start.pressed.connect(_controller.jump_start)
		_end.pressed.connect(_controller.jump_end)
		_play.pressed.connect(_controller.toggle_play)
	if not _list.item_selected.is_connected(_on_item_selected):
		_list.item_selected.connect(_on_item_selected)


func _on_item_selected(index: int) -> void:
	if _controller == null:
		return
	_controller.select(index)


func bind(replay: ReplayDTO, bundle: BundleDTO) -> void:
	_list.clear()
	_labels = PackedStringArray()
	if replay == null or bundle == null:
		return
	for i in range(replay.entries.size()):
		var label := _label_for(replay.entries[i], bundle)
		_labels.append(label)
		_list.add_item(label)


func set_selected_entry_index(entry_index: int) -> void:
	if entry_index < 0 or entry_index >= _list.item_count:
		_list.deselect_all()
		return
	_list.select(entry_index)


func set_loading(active: bool) -> void:
	_loading.text = "Loading..." if active else ""


func set_controls_enabled(enabled: bool) -> void:
	_prev.disabled = not enabled
	_next.disabled = not enabled
	_start.disabled = not enabled
	_end.disabled = not enabled
	_play.disabled = not enabled


func get_visible_label(entry_index: int) -> String:
	if entry_index < 0 or entry_index >= _labels.size():
		return ""
	return _labels[entry_index]


func _label_for(entry: TimelineEntryDTO, bundle: BundleDTO) -> String:
	if entry.kind == TimelineEntryKind.EVENT:
		var ev: BattleEventDTO = bundle.battle_events[entry.event_index]
		if ev.type == "turn":
			return "turn %s" % str(ev.amount) if typeof(ev.amount) == TYPE_INT else "turn"
		if ev.type == "move":
			return "move %s" % str(ev.details) if typeof(ev.details) == TYPE_STRING else "move"
		return ev.type
	var row: DecisionRowDTO = bundle.decisions[entry.decision_row_index]
	var base := "decision #%d" % row.decision_index
	if entry.kind == TimelineEntryKind.DECISION_WITHOUT_REPLAY_EVENT:
		base += " (no replay event)"
	if not row.decision_valid:
		base += " (invalid)"
	return base
