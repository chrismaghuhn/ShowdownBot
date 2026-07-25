class_name AppShell
extends Control

@onready var _path_edit: LineEdit = $VBox/PathRow/PathEdit
@onready var _open_button: Button = $VBox/PathRow/OpenButton
@onready var _scale_option: OptionButton = $VBox/ScaleRow/ScaleOption
@onready var _density_toggle: Button = $VBox/ScaleRow/DensityToggleButton
@onready var _state_banner: StateBanner = $VBox/StateBanner
@onready var _status_label: Label = $VBox/StatusLabel
@onready var _layout: WorkspaceLayout = $VBox/WorkspaceLayout
@onready var _replay_workspace: ReplayWorkspace = $VBox/WorkspaceLayout/MainSplit/ReplayWorkspace
@onready var _decision_workspace: DecisionWorkspace = (
	$VBox/WorkspaceLayout/MainSplit/RightSplit/DecisionWorkspace
)
@onready var _shortcuts: WorkspaceShortcuts = $WorkspaceShortcuts
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
	_shortcuts.configure(
		_replay_workspace.get_timeline_controller(),
		_decision_workspace.get_decision_controller(),
		_decision_workspace.get_candidate_table_view(),
		_layout
	)
	# §0.8 reachable presets: OptionButton (75/100/150/200) + density toggle,
	# both thin wrappers over WorkspaceLayout's own API (no state duplicated
	# here beyond the widgets' displayed selection).
	for preset in WorkspaceLayout.SCALE_PRESETS:
		_scale_option.add_item("%d%%" % int(round(preset * 100.0)))
	_scale_option.item_selected.connect(_on_scale_option_selected)
	_density_toggle.pressed.connect(_on_density_toggle_pressed)
	_layout.scale_changed.connect(_on_layout_scale_changed)
	_layout.density_changed.connect(_on_layout_density_changed)
	# §0.8 chrome must scale too (2026-07-25): the runtime theme is owned by
	# WorkspaceLayout but applied here, at the shell root, so PathRow/ScaleRow/
	# StateBanner/StatusLabel — siblings of WorkspaceLayout, not descendants —
	# inherit it as well.
	theme = _layout.get_runtime_theme()
	_sync_scale_density_controls()
	_refresh_state_banner()
	_update_min_window_size()
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


func get_layout() -> WorkspaceLayout:
	return _layout


## Computed, not tabled (owner decision, 2026-07-25 — a table goes stale the
## moment a row is added to a dock): the real minimum the whole shell needs at
## its current scale/density, read straight from the live Control tree
## (VBox's own aggregation — a real VBoxContainer already propagates its
## children's minimum size correctly). Never goes below the
## WorkspaceLayout.MIN_WINDOW_SIZE floor (§0.13 Choice Point A), only above it.
func compute_min_window_size() -> Vector2i:
	var vbox: Control = $VBox
	var needed := vbox.get_combined_minimum_size()
	# VBox sits 8px inset from AppShell's own edges on every side (app_shell.tscn
	# offset_left/top = 8, offset_right/bottom = -8) — the window needs that
	# padding back on top of what VBox itself reports.
	needed += Vector2(16.0, 16.0)
	var floor_size := WorkspaceLayout.MIN_WINDOW_SIZE
	return Vector2i(
		maxi(int(ceil(needed.x)), floor_size.x),
		maxi(int(ceil(needed.y)), floor_size.y),
	)


func _update_min_window_size() -> void:
	DisplayServer.window_set_min_size(compute_min_window_size())


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
	_set_diagnostics_bundle(null)
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
	_set_diagnostics_bundle(bundle)


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
	_set_diagnostics_bundle(null)


func _on_cancelled() -> void:
	_current_bundle = null
	_current_refuse = null
	_replay_workspace.clear()
	_decision_workspace.clear()
	_set_status("Load cancelled")
	_refresh_state_banner()
	_set_diagnostics_bundle(null)


func _on_decision_selection_changed(_decision_row_index: int) -> void:
	_refresh_state_banner()


func _refresh_state_banner() -> void:
	# Uses private _current_refuse (app_shell.gd:12) — no new public refuse getter (§0.11).
	var selected: DecisionRowDTO = null
	if _current_bundle != null:
		selected = _decision_workspace.get_decision_controller().get_selected_decision()
	var state := StateBannerPresenter.compute(_current_bundle, selected, _current_refuse)
	_state_banner.set_banner(state)


func _set_diagnostics_bundle(bundle: BundleDTO) -> void:
	# bind_bundle(null) clears (ProvenancePresenter/DiagnosticsPresenter.present
	# both return [] for a null bundle) — same shape as Replay/Decision clear().
	_layout.get_diagnostics_dock().bind_bundle(bundle)


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


func _on_scale_option_selected(index: int) -> void:
	_layout.set_ui_scale(WorkspaceLayout.SCALE_PRESETS[index])


func _on_density_toggle_pressed() -> void:
	var next := (
		WorkspaceLayout.DENSITY_COMFORTABLE
		if _layout.get_density() == WorkspaceLayout.DENSITY_COMPACT
		else WorkspaceLayout.DENSITY_COMPACT
	)
	_layout.set_density(next)


func _on_layout_scale_changed(_factor: float) -> void:
	_sync_scale_density_controls()
	_update_min_window_size()


func _on_layout_density_changed(_mode: String) -> void:
	_sync_scale_density_controls()
	_update_min_window_size()


## Keeps ScaleOption/DensityToggleButton showing the layout's actual state —
## including after a keyboard-driven reset_to_safe() (§0.6 Ctrl+Shift+0), not
## only after a click on these controls themselves.
func _sync_scale_density_controls() -> void:
	var current_scale := _layout.get_ui_scale()
	for i in range(WorkspaceLayout.SCALE_PRESETS.size()):
		if is_equal_approx(WorkspaceLayout.SCALE_PRESETS[i], current_scale):
			_scale_option.selected = i
			break
	_density_toggle.text = "Density: %s" % _layout.get_density().capitalize()
