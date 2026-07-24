class_name WorkspaceLayout
extends Control

## Density: "compact" | "comfortable" — plan §0.8 / §4.3.
const DENSITY_COMPACT := "compact"
const DENSITY_COMFORTABLE := "comfortable"

## Scale range [0.75, 2.0]; presets snap to 0.75 / 1.0 / 1.5 / 2.0 — plan §0.8 / §4.3.
const SCALE_MIN := 0.75
const SCALE_MAX := 2.0

## Choice Point A CLOSED (plan §0.7 / §0.13) — 1280x720, not configurable.
const MIN_WINDOW_SIZE := Vector2i(1280, 720)

var _density: String = DENSITY_COMFORTABLE
var _ui_scale: float = 1.0


func _ready() -> void:
	DisplayServer.window_set_min_size(MIN_WINDOW_SIZE)


func set_density(mode: String) -> void:
	if mode != DENSITY_COMPACT and mode != DENSITY_COMFORTABLE:
		return
	_density = mode


func get_density() -> String:
	return _density


func set_ui_scale(factor: float) -> void:
	_ui_scale = clampf(factor, SCALE_MIN, SCALE_MAX)


func get_ui_scale() -> float:
	return _ui_scale
