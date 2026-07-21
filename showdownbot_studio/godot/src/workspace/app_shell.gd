class_name AppShell
extends Control

@onready var _path_edit: LineEdit = $VBox/PathRow/PathEdit
@onready var _open_button: Button = $VBox/PathRow/OpenButton
@onready var _status_label: Label = $VBox/StatusLabel
@onready var _loader: BundleLoader = $BundleLoader

var cli_decision_index: int = -1

var _current_bundle: BundleDTO = null
var _current_refuse: RefuseDiagnostic = null
var _selected_decision_index: int = -1


func _ready() -> void:
	_open_button.pressed.connect(_on_open_pressed)
	_loader.completed.connect(_on_completed)
	_loader.refused.connect(_on_refused)
	_loader.cancelled.connect(_on_cancelled)
	parse_cli_args()


func parse_cli_args(args: PackedStringArray = PackedStringArray()) -> void:
	cli_decision_index = -1
	var source := args if not args.is_empty() else OS.get_cmdline_user_args()
	var index := 0
	while index < source.size():
		var token := String(source[index])
		if token == "--decision" and index + 1 < source.size():
			var value := String(source[index + 1])
			if value.is_valid_int():
				cli_decision_index = value.to_int()
			index += 2
			continue
		index += 1


func open_bundle_path(path: String) -> void:
	_path_edit.text = path
	_start_load(path)


func is_loading() -> bool:
	return _loader.get_state() == BundleLoader.State.LOADING


func get_loaded_bundle() -> BundleDTO:
	return _current_bundle


func get_declared_mode() -> String:
	if _current_bundle == null:
		return ""
	return _current_bundle.declared_mode


func get_effective_mode() -> String:
	if _current_bundle == null:
		return ""
	return _current_bundle.effective_mode


func get_trace_trusted() -> bool:
	if _current_bundle == null:
		return false
	return _current_bundle.trace_trusted


func get_replay_trusted() -> bool:
	if _current_bundle == null:
		return false
	return _current_bundle.replay_trusted


func get_decision_count() -> int:
	if _current_bundle == null:
		return 0
	return _current_bundle.decisions.size()


func get_refuse_reason() -> String:
	if _current_refuse == null:
		return ""
	return _current_refuse.reason


func get_downgrade_warning_reasons() -> Array:
	var reasons: Array = []
	if _current_bundle == null:
		return reasons
	for item in _current_bundle.downgrade_warnings:
		if item is RefuseDiagnostic:
			reasons.append(item.reason)
	return reasons


func get_status_text() -> String:
	return _status_label.text


func get_selected_decision_index() -> int:
	return _selected_decision_index


func _on_open_pressed() -> void:
	var path := _path_edit.text.strip_edges()
	if path.is_empty():
		_set_status("Enter a bundle directory path")
		return
	_start_load(path)


func _start_load(path: String) -> void:
	_current_bundle = null
	_current_refuse = null
	_set_status("Loading...")
	_loader.load_async(path)


func _on_completed(bundle: BundleDTO) -> void:
	_current_bundle = bundle
	_current_refuse = null
	_set_status(_format_loaded_status(bundle))


func _on_refused(diagnostic: RefuseDiagnostic) -> void:
	_current_bundle = null
	_current_refuse = diagnostic
	_set_status("Refused: %s" % diagnostic.reason)


func _on_cancelled() -> void:
	_current_bundle = null
	_current_refuse = null
	_set_status("Load cancelled")


func _format_loaded_status(bundle: BundleDTO) -> String:
	var parts: PackedStringArray = PackedStringArray([
		"Loaded",
		"declared=%s" % bundle.declared_mode,
		"effective=%s" % bundle.effective_mode,
	])
	if bundle.declared_mode != bundle.effective_mode:
		for item in bundle.downgrade_warnings:
			if item is RefuseDiagnostic:
				parts.append("downgrade: %s" % item.reason)
	return " | ".join(parts)


func _set_status(text: String) -> void:
	_status_label.text = text
