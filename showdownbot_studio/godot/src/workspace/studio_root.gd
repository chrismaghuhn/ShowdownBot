class_name StudioRoot
extends VBoxContainer

## New application entry point (spec docs/specs/2026-07-25-phase3-client-design.md section
## 4.6): owns only navigation and workspace lifecycle. It never owns battle or credential
## state -- those stay inside battle/ and session/ once those modules exist (M1c, M2a), reached
## only through the three communication paths (section 4.2). F0 registers exactly one
## workspace; M1d (Task 30) adds LiveClientWorkspace as a second, reachable through a real
## NavBar button -- StudioRoot's fuller cross-workspace settings-ownership story (global scale/
## density/theme, currently owned end-to-end by AppShell/WorkspaceLayout for the single
## Phase-0 workspace) stays deferred until a later slice needs to share it.
##
## Layout fix (owner review, 2026-07-26, sixth pass, P1): the root used to be a bare Control with
## NavBar at layout_mode = 1 and no anchors, sitting right next to WorkspaceRouter which had
## anchors_preset = 15 (full rect) -- the router covered the whole window, including the nav bar,
## so the nav buttons were visually overlapped by workspace content and not reliably clickable.
## The root is now a VBoxContainer (same idiom as every other layout fix in this codebase: a
## Container-typed root with layout_mode = 2 children): NavBar sits at its own natural height,
## and WorkspaceRouter (size_flags_vertical = 3) fills all remaining vertical space below it,
## never overlapping. WorkspaceRouter itself stays a plain Control (not a container) -- its
## show/hide logic (WorkspaceRouter.show_workspace(), unchanged) toggles `.visible` on whichever
## child should be the single full-rect "page"; a Container would instead try to ARRANGE its
## children into separate positions, which is wrong for a page router where every child must be
## able to occupy the ENTIRE router area on its own turn. Each workspace instance inside the
## router now carries the same explicit full-rect anchors (anchors_preset = 15) that
## OfflineViewerWorkspace already had -- LiveClientWorkspace's instance previously had none at
## all and rendered collapsed (verified: 64x64 instead of filling the router).

const OFFLINE_VIEWER_WORKSPACE_ID := "offline_viewer"
const LIVE_CLIENT_WORKSPACE_ID := "live_client"

@onready var _nav_bar: HBoxContainer = $NavBar
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


func get_offline_viewer_nav_button() -> Button:
	return _offline_viewer_nav_button


## Test-only seam for the composition-layout geometry probe (owner review, 2026-07-26, sixth
## pass, P1): exposes the real NavBar node so a test can measure its actual laid-out global rect
## against the router's, rather than inferring correctness only from the individual nav buttons.
func get_nav_bar_for_test() -> Control:
	return _nav_bar
