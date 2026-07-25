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

New (M1d):

- `ObservationEventBus` — the read-only observation-event bus (spec section 4.2.2):
  `connection_state_changed`, `battle_state_published`, `battle_completed`. Never carries
  commands, credentials, or the raw `ProtocolEventDTO` stream. See
  `schemas/observation-event-bus-v1.md` for the full contract.
- `LiveClientWorkspace` — the Connection + Spectator areas' composition root. Composes `net/`,
  `protocol/`, `battle/LiveBattleProjection`, `ObservationEventBus`, and the `ui/panels/`
  spectate panels (`RoomEntryPanel`, `ConnectionStatusPanel`, `BattleBoardPanel`,
  `LiveBattleLogPanel`); holds no derived battle state itself and never calls `send_raw_text`
  directly — room commands go only through `ui/panels/SpectatorRoomGateway`. Every decoded event
  is filtered on `event.room_id` against the currently joined room before it reaches the
  projection or any panel. Registered with `WorkspaceRouter` under `StudioRoot.LIVE_CLIENT_WORKSPACE_ID`
  and reachable through `StudioRoot`'s NavBar "Live Client" button — not only registered in the
  router, but actually navigable.

Data flow: engine bootstrap → `StudioRoot` → `WorkspaceRouter` → `OfflineViewerWorkspace`
(→ existing `AppShell` content) or `LiveClientWorkspace` (→ `net/`/`protocol/`/`battle/`/
`ui/panels/`), switched by the NavBar.

## Dependencies

`OfflineViewerWorkspace` embeds the existing `AppShell` scene; `StudioRoot`/`WorkspaceRouter`
depend on nothing outside this module. `LiveClientWorkspace` depends on `net/WebSocketTransport`,
`protocol/ProtocolDecoder`/`RoomStateMachine`, `battle/LiveBattleProjection`, and
`ui/panels/`'s spectate panels and `SpectatorRoomGateway`. No file here may own battle or
credential state, and none may import `HumanBattleCommandGateway` or any privileged-command type
outside the future HumanBattle area's controller (AGENTS.md rules 3-4; spec section 4.2.3).

## Rule for future workspaces

New top-level surfaces (M1d's `LiveClientWorkspace` first) register with `WorkspaceRouter` under
their own ID and keep all domain state in their owning modules (`battle/`, `session/`, ...);
the workspace layer composes `ui/panels/` components and routes — nothing else.
