class_name AppShell
extends Control

@onready var _path_edit: LineEdit = $VBox/PathRow/PathEdit
@onready var _open_button: Button = $VBox/PathRow/OpenButton
@onready var _state_banner: StateBanner = $VBox/StateBanner
@onready var _status_label: Label = $VBox/StatusLabel
@onready var _replay_workspace: ReplayWorkspace = $VBox/ReplayWorkspace
@onready var _decision_workspace: DecisionWorkspace = $VBox/DecisionWorkspace
@onready var _loader: BundleLoader = $BundleLoader

var _current_bundle: BundleDTO = null
var _current_refuse: RefuseDiagnostic = null
var _pending_deep_link: DecisionDeepLink.ParseResult = null
var _deep_link_refuse_reason: String = ""


func _ready() -> void:
	_open_button.pressed.connect(_on_open_pressed)
	_loader.completed.connect(_on_completed)
	_loader.refused.connect(_on_refused)
	_loader.cancelled.connect(_on_cancelled)
	# decision_controller.gd:4 — refresh prominent banner on selection changes.
	_decision_workspace.get_decision_controller().decision_selection_changed.connect(
		_on_decision_selection_changed
	)
	_refresh_state_banner()
	parse_cli_args()


func parse_cli_args(args: PackedStringArray = PackedStringArray()) -> void:
	_pending_deep_link = null
	_deep_link_refuse_reason = ""
	var source := args if not args.is_empty() else OS.get_cmdline_user_args()
	var index := 0
	var saw_decision := false
	while index < source.size():
		var token := String(source[index])
		if token == "--decision":
			if saw_decision:
				# B3: multiple --decision → refuse (no last-wins).
				_pending_deep_link = DecisionDeepLink.ParseResult.new()
				_pending_deep_link.ok = false
				_pending_deep_link.reason = DecisionDeepLink.REASON_AMBIGUOUS_DECISION_ARG
				if index + 1 < source.size() and not String(source[index + 1]).begins_with("-"):
					index += 2
				else:
					index += 1
				continue
			saw_decision = true
			if index + 1 >= source.size():
				_pending_deep_link = DecisionDeepLink.ParseResult.new()
				_pending_deep_link.ok = false
				_pending_deep_link.reason = DecisionDeepLink.REASON_MALFORMED_DECISION_ARG
				index += 1
				continue
			_pending_deep_link = DecisionDeepLink.parse_arg(String(source[index + 1]))
			index += 2
			continue
		index += 1


func get_deep_link_refuse_reason() -> String:
	return _deep_link_refuse_reason


func open_bundle_path(path: String) -> void:
	_path_edit.text = path
	_start_load(path)


func get_replay_workspace() -> ReplayWorkspace:
	return _replay_workspace


func get_decision_workspace() -> DecisionWorkspace:
	return _decision_workspace


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
	var d: DecisionRowDTO = _decision_workspace.get_decision_controller().get_selected_decision()
	if d == null:
		return -1
	return d.decision_index


func _on_open_pressed() -> void:
	var path := _path_edit.text.strip_edges()
	if path.is_empty():
		_set_status("Enter a bundle directory path")
		return
	_start_load(path)


func _start_load(path: String) -> void:
	_current_bundle = null
	_current_refuse = null
	_deep_link_refuse_reason = ""
	_replay_workspace.clear()
	_replay_workspace.set_loading(true)
	_decision_workspace.clear()
	_decision_workspace.set_loading(true)
	_set_status("Loading...")
	_refresh_state_banner()
	_loader.load_async(path)


func _on_completed(bundle: BundleDTO) -> void:
	_current_bundle = bundle
	_current_refuse = null
	var replay: ReplayDTO = BattleTimeline.build(bundle)
	_replay_workspace.reset(replay, bundle)
	_decision_workspace.reset(bundle, _replay_workspace.get_timeline_controller())
	_apply_pending_deep_link(bundle)
	if _deep_link_refuse_reason.is_empty():
		_set_status(_format_loaded_status(bundle))
	_refresh_state_banner()


func _apply_pending_deep_link(bundle: BundleDTO) -> void:
	if _pending_deep_link == null:
		_deep_link_refuse_reason = ""
		return
	var pending := _pending_deep_link
	_pending_deep_link = null
	if not pending.ok:
		_deep_link_refuse_reason = pending.reason
		_set_status("Deep link refused: %s" % _deep_link_refuse_reason)
		return
	var applied := DecisionDeepLink.resolve(bundle, pending.battle_id, pending.decision_index)
	if not applied.ok:
		_deep_link_refuse_reason = applied.reason
		_set_status("Deep link refused: %s" % _deep_link_refuse_reason)
		return
	_deep_link_refuse_reason = ""
	_decision_workspace.get_decision_controller().select_decision_row(applied.decision_row_index)


func _on_refused(diagnostic: RefuseDiagnostic) -> void:
	_current_bundle = null
	_current_refuse = diagnostic
	_replay_workspace.clear()
	_decision_workspace.clear()
	_set_status("Refused: %s" % diagnostic.reason)
	_refresh_state_banner()


func _on_cancelled() -> void:
	_current_bundle = null
	_current_refuse = null
	_replay_workspace.clear()
	_decision_workspace.clear()
	_set_status("Load cancelled")
	_refresh_state_banner()


func _on_decision_selection_changed(_decision_row_index: int) -> void:
	_refresh_state_banner()


func _refresh_state_banner() -> void:
	# Uses private _current_refuse (app_shell.gd:12) — no new public refuse getter (§0.11).
	var selected: DecisionRowDTO = null
	if _current_bundle != null:
		selected = _decision_workspace.get_decision_controller().get_selected_decision()
	var state := StateBannerPresenter.compute(_current_bundle, selected, _current_refuse)
	_state_banner.set_banner(state)


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
