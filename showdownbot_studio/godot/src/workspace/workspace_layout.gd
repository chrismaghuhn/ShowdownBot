class_name WorkspaceLayout
extends Control

## Density: "compact" | "comfortable" — plan §0.8 / §4.3.
const DENSITY_COMPACT := "compact"
const DENSITY_COMFORTABLE := "comfortable"

## Scale range [0.75, 2.0]; presets snap to 0.75 / 1.0 / 1.5 / 2.0 — plan §0.8 / §4.3.
const SCALE_MIN := 0.75
const SCALE_MAX := 2.0
const SCALE_PRESETS: Array[float] = [0.75, 1.0, 1.5, 2.0]

## Choice Point A CLOSED (plan §0.7 / §0.13) — 1280x720, not configurable.
const MIN_WINDOW_SIZE := Vector2i(1280, 720)

## split_offset restored by reset_to_safe() (§0.7 / §4.3). 0 is SplitContainer's
## own default (even split), not a hand-picked pixel value.
const _DEFAULT_SPLIT_OFFSET := 0

## Scale/density mechanism (§0.8): a runtime Theme applied to this Control,
## cascading to every descendant (docks) that doesn't set its own override.
## Verified empirically (not Window.content_scale_factor — that only rescales
## render/DPI, not Control.size/layout, so it produces zero observable effect
## for gdUnit's headless layout math): default_font_size drives real min-size
## growth through text metrics; "separation"/BoxContainer (HBox/VBoxContainer
## share it via theme type inheritance) drives spacing. See commit message.
const _BASE_FONT_SIZE := 16
const _SEPARATION_COMFORTABLE := 4
const _SEPARATION_COMPACT := 2

var _density: String = DENSITY_COMFORTABLE
var _ui_scale: float = 1.0
var _runtime_theme: Theme = Theme.new()

## Emitted after set_ui_scale/set_density (and reset_to_safe) actually applies
## — lets AppShell's preset controls (OptionButton, density toggle) stay in
## sync with keyboard-driven changes (Ctrl+Shift+0) without polling.
signal scale_changed(factor: float)
signal density_changed(mode: String)

# Dock scaffold — present when this node is the workspace_layout.tscn instance
# (§2 architecture: Replay + Decision + Diagnostics docks). Stay null under a
# bare WorkspaceLayout.new() (Task E3's tests), so every accessor below is
# null-checked rather than assumed present.
var _main_split: SplitContainer = null
var _right_split: SplitContainer = null
var _replay_dock: Control = null
var _decision_dock: Control = null
var _diagnostics_dock: DiagnosticsDock = null


func _ready() -> void:
	DisplayServer.window_set_min_size(MIN_WINDOW_SIZE)
	theme = _runtime_theme
	_apply_scale()
	_apply_density()
	_main_split = get_node_or_null("MainSplit") as SplitContainer
	_right_split = get_node_or_null("MainSplit/RightSplit") as SplitContainer
	_replay_dock = get_node_or_null("MainSplit/ReplayWorkspace") as Control
	_decision_dock = get_node_or_null("MainSplit/RightSplit/DecisionWorkspace") as Control
	_diagnostics_dock = get_node_or_null("MainSplit/RightSplit/DiagnosticsDock") as DiagnosticsDock
	if _diagnostics_dock != null:
		# Reveal + grab_focus() (focus_diagnostics(), §0.6 "Open diagnostics") needs
		# a focusable control; TabContainer does not default to FOCUS_ALL.
		_diagnostics_dock.focus_mode = Control.FOCUS_ALL


## Compact/Comfortable (§0.8): same information + same selection, only spacing
## changes. Applies as a "separation" theme constant (BoxContainer type — both
## HBoxContainer and VBoxContainer resolve it via theme type inheritance) so
## no row is hidden, removed, or reordered — only container gaps shrink/grow.
func set_density(mode: String) -> void:
	if mode != DENSITY_COMPACT and mode != DENSITY_COMFORTABLE:
		return
	_density = mode
	_apply_density()
	density_changed.emit(_density)


func get_density() -> String:
	return _density


## §0.8: 75%-200% user override. Applies as the runtime theme's
## default_font_size, which grows/shrinks every descendant Label/Button/etc.
## min-size through real text-metric layout (verified stronger than
## Window.content_scale_factor — see class-level comment).
func set_ui_scale(factor: float) -> void:
	_ui_scale = clampf(factor, SCALE_MIN, SCALE_MAX)
	_apply_scale()
	scale_changed.emit(_ui_scale)


func get_ui_scale() -> float:
	return _ui_scale


func _apply_scale() -> void:
	_runtime_theme.default_font_size = int(round(_BASE_FONT_SIZE * _ui_scale))


func _apply_density() -> void:
	var sep := _SEPARATION_COMPACT if _density == DENSITY_COMPACT else _SEPARATION_COMFORTABLE
	_runtime_theme.set_constant(&"separation", &"BoxContainer", sep)
	_runtime_theme.set_constant(&"h_separation", &"GridContainer", sep)
	_runtime_theme.set_constant(&"v_separation", &"GridContainer", sep)


func get_diagnostics_dock() -> DiagnosticsDock:
	return _diagnostics_dock


## Restores default split ratios, density Comfortable, scale 100%, all primary
## docks visible (§0.7 / §4.3 reset-to-safe). No-op on any dock this instance
## doesn't own (e.g. a bare WorkspaceLayout.new() in Task E3 tests).
func reset_to_safe() -> void:
	set_density(DENSITY_COMFORTABLE)
	set_ui_scale(1.0)
	for split in [_main_split, _right_split]:
		if split != null:
			split.split_offset = _DEFAULT_SPLIT_OFFSET
			split.collapsed = false
	for dock in [_replay_dock, _decision_dock, _diagnostics_dock]:
		if dock != null:
			dock.visible = true


## Reveals and focuses the diagnostics dock (§0.6 "Open diagnostics"). No-op if
## this instance owns no diagnostics dock.
func focus_diagnostics() -> void:
	if _diagnostics_dock == null:
		return
	_diagnostics_dock.visible = true
	if _right_split != null:
		_right_split.collapsed = false
	_diagnostics_dock.grab_focus()
