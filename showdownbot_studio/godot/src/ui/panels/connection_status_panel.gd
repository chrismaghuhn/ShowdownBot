class_name ConnectionStatusPanel
extends Control

@onready var _label: Label = $StatusLabel


func on_connection_state_changed(_old_state: ConnectionStateMachine.State, new_state: ConnectionStateMachine.State) -> void:
	_label.text = ConnectionStateMachine.describe(new_state)


func get_status_text() -> String:
	return _label.text
