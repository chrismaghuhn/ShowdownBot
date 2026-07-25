class_name StudioRoot
extends Control

## New application entry point (spec docs/specs/2026-07-25-phase3-client-design.md section
## 4.6): owns only navigation and workspace lifecycle. It never owns battle or credential
## state -- those stay inside battle/ and session/ once those modules exist (M1c, M2a), reached
## only through the three communication paths (section 4.2). F0 registers exactly one
## workspace; StudioRoot's fuller cross-workspace settings-ownership story (global scale/
## density/theme, currently owned end-to-end by AppShell/WorkspaceLayout for the single
## Phase-0 workspace) is deferred until a second real workspace (LiveClientWorkspace, M1d)
## exists to share it with -- see this plan's Task 18 notes.

const OFFLINE_VIEWER_WORKSPACE_ID := "offline_viewer"

@onready var _router: WorkspaceRouter = $WorkspaceRouter
@onready var _offline_viewer: OfflineViewerWorkspace = $WorkspaceRouter/OfflineViewerWorkspace


func _ready() -> void:
	_router.register_workspace(OFFLINE_VIEWER_WORKSPACE_ID, _offline_viewer)
	_router.show_workspace(OFFLINE_VIEWER_WORKSPACE_ID)


func get_router() -> WorkspaceRouter:
	return _router


func get_offline_viewer_workspace() -> OfflineViewerWorkspace:
	return _offline_viewer
