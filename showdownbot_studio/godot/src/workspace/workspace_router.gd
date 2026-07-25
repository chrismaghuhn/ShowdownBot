class_name WorkspaceRouter
extends Control

## Switches between registered top-level workspaces (spec
## docs/specs/2026-07-25-phase3-client-design.md section 4.6). Holds no domain state of its
## own -- no battle, credential, or team-bundle data lives here, only the registry of which
## Control node is currently visible. F0 registers exactly one workspace
## (OfflineViewerWorkspace, godot/src/workspace/offline_viewer_workspace.gd); LiveClientWorkspace
## does not exist until M1d, so this registry is keyed by String id rather than hardcoding an
## assumption of exactly two workspaces.

signal active_workspace_changed(workspace_id: String)

var _workspaces: Dictionary[String, Control] = {}
var _active_id: String = ""


func register_workspace(workspace_id: String, workspace: Control) -> void:
	_workspaces[workspace_id] = workspace
	workspace.visible = false
	if workspace.get_parent() != self:
		add_child(workspace)


func show_workspace(workspace_id: String) -> void:
	if not _workspaces.has(workspace_id):
		push_error("WorkspaceRouter: unknown workspace id %s" % workspace_id)
		return
	for id in _workspaces.keys():
		_workspaces[id].visible = (id == workspace_id)
	_active_id = workspace_id
	active_workspace_changed.emit(workspace_id)


func get_active_workspace_id() -> String:
	return _active_id


func get_registered_workspace_ids() -> Array[String]:
	var ids: Array[String] = []
	for id in _workspaces.keys():
		ids.append(id)
	return ids


func get_workspace(workspace_id: String) -> Control:
	return _workspaces.get(workspace_id, null)
