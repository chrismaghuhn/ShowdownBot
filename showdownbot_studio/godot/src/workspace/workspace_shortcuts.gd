class_name WorkspaceShortcuts
extends Node

## Plan E Task E4/E5 — single keyboard-shortcut layer over existing Plan C/D
## APIs plus WorkspaceLayout (§0.6 "Input ownership": one WorkspaceShortcuts
## layer, no scattered _input across Plan D views). §4.4 4-ref shape: layout is
## optional (defaults null) so pre-E5 call sites with 3 refs still compile.

var _timeline: TimelineController = null
var _decision: DecisionController = null
var _table: CandidateTableView = null
var _layout: WorkspaceLayout = null


func configure(
		timeline: TimelineController,
		decision: DecisionController,
		table: CandidateTableView,
		layout: WorkspaceLayout = null
) -> void:
	_timeline = timeline
	_decision = decision
	_table = table
	_layout = layout


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not event.pressed or event.echo:
		return
	var key: InputEventKey = event
	var text_field_focused := _is_text_field_focused()
	match key.keycode:
		KEY_LEFT:
			if text_field_focused or _timeline == null:
				return
			_timeline.step_prev()
		KEY_RIGHT:
			if text_field_focused or _timeline == null:
				return
			_timeline.step_next()
		KEY_SPACE:
			if text_field_focused or _timeline == null:
				return
			_timeline.toggle_play()
		KEY_UP:
			if not key.ctrl_pressed or _decision == null:
				return
			_decision.jump_prev_decision()
		KEY_DOWN:
			if not key.ctrl_pressed or _decision == null:
				return
			_decision.jump_next("decision")
		KEY_F:
			if not key.ctrl_pressed or _table == null:
				return
			_table.get_filter_line_edit().grab_focus()
		KEY_L:
			if not key.ctrl_pressed or _table == null:
				return
			_table.focus_selected()
		KEY_D:
			if not (key.ctrl_pressed and key.shift_pressed) or _layout == null:
				return
			_layout.focus_diagnostics()
		KEY_0:
			if not (key.ctrl_pressed and key.shift_pressed) or _layout == null:
				return
			_layout.reset_to_safe()
		_:
			return
	var vp := get_viewport()
	if vp != null:
		vp.set_input_as_handled()


func _is_text_field_focused() -> bool:
	var vp := get_viewport()
	if vp == null:
		return false
	var focused := vp.gui_get_focus_owner()
	return focused is LineEdit or focused is TextEdit
