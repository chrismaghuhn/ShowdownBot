# Phase 3 Module Catalog

**Status:** binding F0 deliverable (spec `2026-07-25-phase3-client-design.md` section 3.3, section 4.1)

## Purpose

One row per module named in spec section 4.1: its owner directory, its job, its planned public
interface, which of the three communication paths (spec section 4.2) it is allowed to use, when it
is introduced, and what it must never do. This is the document a maintainer reads before touching
any module tree, per `AGENTS.md` rule 2 ("every module ships a short README...") applied at the
phase level before any of these directories have production code in them yet.

## Module table

| Module | Directory | Owner (job) | Public interface (planned) | Allowed communication paths | Introduced in | Must not do |
|---|---|---|---|---|---|---|
| Net | `godot/src/net/` | `WebSocketTransport` (connection, reconnect, heartbeat, `ConnectionState`); `LoginHttpTransport` (single HTTPS login exchange) | `WebSocketTransport.connect()/disconnect()`, `ConnectionState` signal; `LoginHttpTransport.login(credential) -> LoginResult` | Direct dependency (default); publishes `ConnectionState` changes onto the `ObservationEventBus` | M1a (WebSocket), M1e (reconnect), M2a (login transport) | Parse or encode protocol text; hold battle state; hold `CredentialProvider` state |
| Protocol | `godot/src/protocol/` | The only module permitted to encode outbound Showdown protocol commands or decode inbound protocol text, into/from typed DTOs under `protocol/dto/`, including the `CanonicalProtocolEventStream` | Decoder entry point consuming raw text; general command encoder; `protocol/dto/*` typed DTOs | Direct dependency (default); hands `CanonicalProtocolEventStream` directly to `battle/` and `replay/` | M1b (decoder, general encoder, room join/leave), M1e (reconnect), M2b (`FormatCatalogDTO`), M2c/M2e/M2f (remaining command families) | Render UI; hold connection sockets; decide whether a human is allowed to send a given command |
| Session | `godot/src/session/` | `CredentialProvider`, `LoginCoordinator`, `SessionState`; team-bundle loading (`TeamBundleV1`); `session/dto/` | `CredentialProvider` interface; `LoginCoordinator.login()`; `SessionState` state machine; team-bundle loader | Direct dependency (default) | M2a–M2b | Touch raw protocol text; render UI |
| Battle | `godot/src/battle/` | Pure, deterministic, idempotent `LiveBattleReducer` producing immutable `LiveBattleSnapshot` values from `battle/dto/` DTOs, consuming `CanonicalProtocolEventStream` directly | `LiveBattleReducer.apply(event) -> LiveBattleSnapshot`; `battle/dto/*` typed DTOs | Direct dependency (default); publishes "battle state published"/"battle completed" onto the `ObservationEventBus` | M1c, M1e (reconnect rebuild) | Contain UI nodes; recompute mechanics/damage/legality; hold or import `HumanBattleCommandGateway` |
| UI panels | `godot/src/ui/panels/` | Board, timeline, move choice, battle chat, connection status; renders via `BoardPresentationAdapter` | Panel scenes/controllers subscribing to the `ObservationEventBus` and to direct battle-state dependencies; the human battle controller holds `HumanBattleCommandGateway` (from M2d) | Subscribes to `ObservationEventBus` (render only); direct dependency for battle-state reads; holds the privileged gateway (M2d onward, human battle controller only) | M1d (board, timeline, connection status), M2d–M2f (move choice, chat) | Produce protocol text directly; decide legality |
| Replay | `godot/src/replay/` | Record a finished live battle via `LiveRecordingSink` and `ReplayExportGateway`; reuses `BoardPresentationAdapter`/`AbstractBoardView` for its own board rendering; converts live DTOs into recorded-replay events before export; **hosts `BattleBoardSnapshot`/`BattleBoardSlotSnapshot`/`ReplayBoardPresentationAdapter` (F0, this plan)** | `AbstractBoardView.bind(BattleBoardSnapshot)`; `ReplayBoardPresentationAdapter.build_snapshot(BoardModel) -> BattleBoardSnapshot`; `LiveRecordingSink`/`ReplayExportGateway` (M3) | Direct dependency (default); direct consumer of `CanonicalProtocolEventStream` (M3a) | F0 (board-presentation-contract refactor), M3a–M3c | Reinterpret or recompute recorded evidence; assemble canonical bundle bytes itself; hold or import `HumanBattleCommandGateway` |
| Workspace | `godot/src/workspace/` | `StudioRoot`, `WorkspaceRouter`, `OfflineViewerWorkspace` (wraps the existing `AppShell` unchanged), `LiveClientWorkspace` (Connection, Spectator, Matchmaking, HumanBattle areas, from M1d/M2d) | `WorkspaceRouter.register_workspace()/show_workspace()/get_active_workspace_id()`; `StudioRoot.get_router()` | Direct dependency (default); composes other modules, holds no domain state itself | F0 (scaffold), M1d (Connection + Spectator), M2d (Matchmaking + HumanBattle) | Own battle or credential state; duplicate board/team/replay logic; hold `HumanBattleCommandGateway` outside the HumanBattle area's controller |

## Communication-path legend

Exactly three paths exist (spec section 4.2); a design that reaches for a fourth informal path is
wrong by construction:

- **Direct dependency (default, section 4.2.1).** A small, explicit, typed interface wired by
  composition-root/constructor injection, with locally scoped typed signals where a callback shape
  fits better than a return value.
- **`ObservationEventBus` (section 4.2.2).** A typed, versioned, read-only bus carrying only its
  fixed list: connection status changed, battle state published, battle completed, chat received,
  diagnostic event. Never carries battle commands, login/credential data, a mutable session
  object, or the raw `CanonicalProtocolEventStream`.
- **Privileged command gateway (section 4.2.3).** `HumanBattleCommandGateway` and its narrowly
  scoped siblings (room join/leave, chat send, challenge/ladder, timer/forfeit/undo). Injected only
  into the intended UI component; never registered on or discoverable through the bus; never
  imported by `replay/`, `battle/`, or an analysis module.
