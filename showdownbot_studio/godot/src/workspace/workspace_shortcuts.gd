class_name WorkspaceShortcuts
extends Node

## Plan E Task E4 — single keyboard-shortcut layer over existing Plan C/D APIs
## (§0.6 "Input ownership": one WorkspaceShortcuts layer, no scattered _input
## across Plan D views).
##
## ponytail: §4.4 describes a 4-ref end-state constructor that also takes
## shell.get_layout() -> WorkspaceLayout, wiring "Open diagnostics" and
## "Reset layout/scale". AppShell has no get_layout() yet (that scene-tree
## mount is Task E5's job), so this narrows to the 3 refs buildable today.
## Upgrade to the 4-ref shape once E5 mounts WorkspaceLayout into AppShell.

var _timeline: TimelineController = null
var _decision: DecisionController = null
var _table: CandidateTableView = null


func configure(
		timeline: TimelineController,
		decision: DecisionController,
		table: CandidateTableView
) -> void:
	_timeline = timeline
	_decision = decision
	_table = table


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
