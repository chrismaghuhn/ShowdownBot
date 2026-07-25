# Workspace (`godot/src/workspace/`)

## Purpose

Hosts the application shell: the entry point, top-level workspace routing, and the workspace
containers themselves. This is the module named in `docs/architecture/MODULE_CATALOG.md`'s
"Workspace" row. It owns navigation and workspace lifecycle only — never battle or credential
state (spec `2026-07-25-phase3-client-design.md` section 4.6).

## Public interface

Existing (Phase 0):

- `AppShell` — the complete, closed Viewer-v0 shell (bundle path, replay/decision workspaces,
  diagnostics dock). Since F0 it is no longer the main scene, but its content and behavior are
  unchanged; it renders inside `OfflineViewerWorkspace`.

New (F0, this scaffold):

- `StudioRoot` — the application entry point and main scene (`studio_root.tscn`,
  `project.godot` `run/main_scene`). Owns navigation, global safe settings, window/theme
  management, and workspace lifecycle. Holds no domain state.
- `WorkspaceRouter` — an ID-keyed workspace registry: `register_workspace(id, workspace)`,
  `show_workspace(id)`, `get_active_workspace_id()`. Switches visibility between registered
  workspaces and holds no domain state of its own.
- `OfflineViewerWorkspace` — wraps the existing `AppShell` content unchanged as the first
  registered workspace.

Data flow: engine bootstrap → `StudioRoot` → `WorkspaceRouter` → `OfflineViewerWorkspace`
(→ existing `AppShell` content). `LiveClientWorkspace` (Connection, Spectator, Matchmaking,
HumanBattle areas) is deliberately absent until M1d; the router runs single-workspace until then.

## Dependencies

`OfflineViewerWorkspace` embeds the existing `AppShell` scene; `StudioRoot`/`WorkspaceRouter`
depend on nothing outside this module. No file here may own battle or credential state, and none
may import `HumanBattleCommandGateway` or any privileged-command type outside the future
HumanBattle area's controller (AGENTS.md rules 3-4; spec section 4.2.3).

## Rule for future workspaces

New top-level surfaces (M1d's `LiveClientWorkspace` first) register with `WorkspaceRouter` under
their own ID and keep all domain state in their owning modules (`battle/`, `session/`, ...);
the workspace layer composes `ui/panels/` components and routes — nothing else.
