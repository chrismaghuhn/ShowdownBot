class_name ReplayWorkspace
extends VBoxContainer

@onready var _board_view: AbstractBoardView = $Board
@onready var _timeline_view: TimelineView = $Timeline
@onready var _controller: TimelineController = $TimelineController

var _presenter := ReplayPresenter.new()
var _board: BoardModel = null
var _replay: ReplayDTO = null
var _bundle: BundleDTO = null


func _ready() -> void:
	_timeline_view.set_controller(_controller)
	_controller.selection_changed.connect(_on_selection_changed)
	clear()


func clear() -> void:
	_controller.clear()
	_replay = null
	_bundle = null
	_board = null
	_timeline_view.bind(null, null)
	_board_view.bind(null)
	set_loading(false)
	_timeline_view.set_controls_enabled(false)


func set_loading(active: bool) -> void:
	_timeline_view.set_loading(active)
	_board_view.set_loading(active)


func reset(replay: ReplayDTO, bundle: BundleDTO) -> void:
	_replay = replay
	_bundle = bundle
	set_loading(false)
	_timeline_view.bind(replay, bundle)
	_timeline_view.set_controls_enabled(replay.entries.size() > 0)
	_controller.reset(replay, bundle)  # emits selection_changed → board bind


func get_timeline_controller() -> TimelineController:
	return _controller


func get_timeline_view() -> TimelineView:
	return _timeline_view


func get_board_view() -> AbstractBoardView:
	return _board_view


func get_board_model() -> BoardModel:
	return _board


func _on_selection_changed(entry_index: int) -> void:
	_timeline_view.set_selected_entry_index(entry_index)
	if _replay == null or _bundle == null or entry_index < 0:
		_board = null
		_board_view.bind(null)
		return
	_board = ReplayPresenter.build_board(_bundle, _replay, entry_index)
	_board_view.bind(_board)
