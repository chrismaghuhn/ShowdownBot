class_name TimelineController
extends Node

signal selection_changed(entry_index: int)
signal playback_changed(playing: bool)

var _replay: ReplayDTO = null
var _bundle: BundleDTO = null
var _selected: int = -1
var _playing: bool = false
var _timer: Timer


func _ready() -> void:
	_timer = Timer.new()
	_timer.wait_time = 0.25
	_timer.one_shot = false
	add_child(_timer)
	_timer.timeout.connect(_on_timer_timeout)


func reset(replay: ReplayDTO, bundle: BundleDTO) -> void:
	pause()
	_replay = replay
	_bundle = bundle
	_selected = 0 if replay.entries.size() > 0 else -1
	selection_changed.emit(_selected)


func clear() -> void:
	pause()
	_replay = null
	_bundle = null
	_selected = -1
	selection_changed.emit(_selected)


func select(entry_index: int) -> void:
	if _replay == null or _replay.entries.is_empty():
		return
	var next := clampi(entry_index, 0, _replay.entries.size() - 1)
	if next == _selected:
		return
	_selected = next
	selection_changed.emit(_selected)


func step_prev() -> void:
	select(_selected - 1)


func step_next() -> void:
	select(_selected + 1)


func jump_start() -> void:
	select(0)


func jump_end() -> void:
	if _replay == null or _replay.entries.is_empty():
		return
	select(_replay.entries.size() - 1)


func play() -> void:
	if _replay == null or _replay.entries.is_empty():
		return
	_playing = true
	_timer.start()
	playback_changed.emit(true)


func pause() -> void:
	_playing = false
	if _timer != null:
		_timer.stop()
	playback_changed.emit(false)


func toggle_play() -> void:
	if _playing:
		pause()
	else:
		play()


func get_selected_entry_index() -> int:
	return _selected


func is_playing() -> bool:
	return _playing


func get_replay() -> ReplayDTO:
	return _replay


func get_bundle() -> BundleDTO:
	return _bundle


func set_timer_wait_time(seconds: float) -> void:
	_timer.wait_time = seconds


func _on_timer_timeout() -> void:
	if _replay == null:
		pause()
		return
	if _selected >= _replay.entries.size() - 1:
		pause()
		return
	step_next()
