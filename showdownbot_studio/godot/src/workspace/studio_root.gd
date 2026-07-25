class_name StudioRoot
extends Control

## New application entry point (spec docs/specs/2026-07-25-phase3-client-design.md section
## 4.6): owns only navigation and workspace lifecycle. It never owns battle or credential
## state -- those stay inside battle/ and session/ once those modules exist (M1c, M2a), reached
## only through the three communication paths (section 4.2). F0 registers exactly one
## workspace; M1d (Task 30) adds LiveClientWorkspace as a second, reachable through a real
## NavBar button -- StudioRoot's fuller cross-workspace settings-ownership story (global scale/
## density/theme, currently owned end-to-end by AppShell/WorkspaceLayout for the single
## Phase-0 workspace) stays deferred until a later slice needs to share it.

const OFFLINE_VIEWER_WORKSPACE_ID := "offline_viewer"
const LIVE_CLIENT_WORKSPACE_ID := "live_client"

@onready var _router: WorkspaceRouter = $WorkspaceRouter
@onready var _offline_viewer: OfflineViewerWorkspace = $WorkspaceRouter/OfflineViewerWorkspace
@onready var _live_client: LiveClientWorkspace = $WorkspaceRouter/LiveClientWorkspace
@onready var _offline_viewer_nav_button: Button = $NavBar/OfflineViewerButton
@onready var _live_client_nav_button: Button = $NavBar/LiveClientButton


func _ready() -> void:
	_router.register_workspace(OFFLINE_VIEWER_WORKSPACE_ID, _offline_viewer)
	_router.register_workspace(LIVE_CLIENT_WORKSPACE_ID, _live_client)
	_router.show_workspace(OFFLINE_VIEWER_WORKSPACE_ID)
	_offline_viewer_nav_button.pressed.connect(func(): _router.show_workspace(OFFLINE_VIEWER_WORKSPACE_ID))
	_live_client_nav_button.pressed.connect(func(): _router.show_workspace(LIVE_CLIENT_WORKSPACE_ID))


func get_router() -> WorkspaceRouter:
	return _router


func get_offline_viewer_workspace() -> OfflineViewerWorkspace:
	return _offline_viewer


func get_live_client_workspace() -> LiveClientWorkspace:
	return _live_client


func get_live_client_nav_button() -> Button:
	return _live_client_nav_button
