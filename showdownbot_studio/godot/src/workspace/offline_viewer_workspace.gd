class_name OfflineViewerWorkspace
extends Control

## Wraps the existing AppShell content unchanged (spec
## docs/specs/2026-07-25-phase3-client-design.md section 4.6): Phase 0's viewer keeps working
## exactly as it does today. This class adds a routing seam above AppShell, never a
## modification inside it -- app_shell.gd and app_shell.tscn are untouched by this task.

@onready var _app_shell: AppShell = $AppShell


func get_app_shell() -> AppShell:
	return _app_shell
