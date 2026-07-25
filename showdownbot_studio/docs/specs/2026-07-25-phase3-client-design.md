# ShowdownBot Studio — Phase 3 Full Showdown Protocol Client Design

**Status:** APPROVED (owner review, 2026-07-25) — implementation planning allowed, starting with
F0; implementation gated per §9
**Date:** 2026-07-25
**Platform:** desktop, inside the existing Godot 4.5.2 application (`showdownbot_studio/godot/`)
**UI technology:** typed GDScript, extending the Phase-0 shell; see
[`../decisions/ADR-001-godot-ui-technology.md`](../decisions/ADR-001-godot-ui-technology.md)
**Domain technology:** Python remains authoritative for team validation, packing, and bundle
canonicalization; this phase adds no second implementation of either
**Master spec:** [`../MASTER_SPEC.md`](../MASTER_SPEC.md) §4 (Phase 3), §5, §11
**Boundaries:** [`../architecture/PROJECT_BOUNDARIES.md`](../architecture/PROJECT_BOUNDARIES.md) §2,
§4, §8
**Agent rules:** [`../../AGENTS.md`](../../AGENTS.md) — the Studio-specific maintainer rules this
design depends on; §10 states which parts of it apply here and does not restate its full text
**Style precedent:** [`viewer-v0-design.md`](viewer-v0-design.md)

## 1. Purpose and context

Phase 0 (offline Replay + DecisionTrace Viewer) is closed. The product roadmap in
`MASTER_SPEC.md` §0 lists five further phases in order: Live Spectator, Team/Matchup Analyzer, full
Showdown protocol client, mods/add-ons, external bot adapters. This document authorizes **Phase 3,
the full Showdown protocol client, ahead of Phases 1 and 2**, and defines its v1 scope, milestones,
architecture, and gates.

**Why Phase 3 first.** A full client needs a WebSocket connection, a protocol parser, a
battle-state model, and a battle board before it can do anything else. That connection/protocol
layer is a strict superset of what Phase 1 (read-only Live Spectator) needs: watching a public
battle without controlling it is a subset of watching *and* controlling one's own battle. Building
the superset first and taking the read-only subset as its first milestone avoids building the same
protocol client twice. Phase 2 (Team/Matchup Analyzer) has no such relationship to Phase 3 — it
needs team-import, usage-stat, and matchup-calculation adapters that a battle client does not
require — so Phase 2 is **not** absorbed by this document. It is genuinely skipped and stays
exactly as unauthorized as every other later phase (§11).

**Primary user.** The project owner, playing **himself**, live, against the **official** Pokémon
Showdown servers. This is a human-operated client, not a bot deployment surface. Every requirement
in this document that touches move selection exists to enforce that distinction; see §5, §7, and
§11 for the binding no-automation rule.

**Relationship to Phase 0.** The abstract, sprite-independent battle board, the DTO/event
discipline, and the typed-GDScript module convention from Phase 0 are reused, not re-derived. Where
this document is silent on a UX convention already fixed by Phase 0 (scaling, density, keyboard
focus, state-banner semantics), MASTER_SPEC §5 continues to apply unchanged.

**A foundation slice comes first.** Phase 3 begins with F0 (§3.3), an architecture-and-documentation
slice with no WebSocket code, before Milestone M1. F0 exists because three of this document's
binding decisions — the derived-state rule (§4.7), the communication-path separation (§4.2), and
the state-machine contracts (§4.8) — are markedly cheaper to get right before live code exists than
to retrofit onto it afterward.

## 2. Governance and authorization

`showdownbot_studio/README.md` currently records the written master spec as **non-binding context**
for Phase 0, with "separate review later" promised before later phases. This document is that
separate review for Phase 3 only.

**Binding for this phase, effective on approval of this document:**

- `MASTER_SPEC.md` §4, the "Phase 3 — Full Showdown protocol client" subsection, including its
  candidate-capability list and its five required separate gates;
- `PROJECT_BOUNDARIES.md` §4, "Later live boundary" (protocol adapter emits typed DTOs; no raw
  WebSocket text parsed outside `protocol/`; remote sprite assets stay out of scope; abstract board
  is the required fallback);
- `MASTER_SPEC.md` §5 (cross-phase UX requirements) and §6 (cross-phase observability and
  provenance), which already apply to every implemented phase and therefore apply to Phase 3
  without modification;
- `PROJECT_BOUNDARIES.md` §2, the dependency-direction table, unchanged and unextended by this
  document;
- `showdownbot_studio/AGENTS.md`, the operational enforcement document for the maintainer rules this
  design applies to Phase 3 (§10).

**Not authorized by this document:** Phase 1 as an independent product slice (it is subsumed as
Milestone M1, §3.3), Phase 2 (untouched, unauthorized, no shared module is implied or pre-built for
it), Phase 4, Phase 5, or any capability in `MASTER_SPEC.md` §4's candidate list beyond what §3
below selects into v1.

**Relationship to `PROJECT_BOUNDARIES.md` §8.** This document does not change any boundary; it
declares an existing one (§4) binding for a phase that §4 already anticipated, so no new
architecture decision record is required to adopt it. A future document that wants to *change* §4
itself still needs a reviewed ADR under `docs/decisions/`.

**Relationship to `MASTER_SPEC.md` §11.** §11 restricts implementation planning to Phase 0. This
document is the "own design" §11 requires before a later phase becomes eligible, and it updates that
eligibility for Phase 3 alone; Phases 1 (as an independent slice), 2, 4, and 5 remain excluded
exactly as §11 already states.

## 3. Scope

### 3.1 v1 in scope

A minimal battle client:

- login against the official Showdown authentication flow;
- server-authoritative format selection, including random-team formats (§3.4, §6.3);
- team selection from an offline, Python-validated team bundle;
- challenge and ladder battle play;
- in-battle chat (the battle-room chat line, not lobby chat);
- replay saving, in the existing Phase-0 viewer bundle format.

### 3.2 v1 out of scope

- lobby chat, chat rooms, and private messages;
- notifications;
- a teambuilder UI (teams are prepared and validated offline, outside this client, by the existing
  Python team-import/validation path referenced in `MASTER_SPEC.md` §4/Phase 2 and
  `PROJECT_BOUNDARIES.md` §2; Phase 3 consumes an already-validated team bundle, it does not build
  the editor that produces one);
- sprites or any other remote/official asset; the abstract Phase-0 board style is reused unchanged;
- any plugin or mod loader;
- any bot adapter or automated move-selection pathway;
- a lobby, room list, or battle browser (M1 spectating uses direct room-ID/URL entry only, §3.3).

Any of the above appearing in a later plan requires its own approved design; none is implied by this
document.

### 3.3 Milestones and sub-slices

Phase 3 ships as one foundation slice (F0), followed by two milestone groups — M1 (Connect +
Spectate) and M2 (Login + Play) — plus a replay milestone (M3), each decomposed into small,
independently mergeable sub-slices with their own gate evidence (§9). A sub-slice does not start
until the previous one in its own milestone is merged and gated, and **no M1 sub-slice starts before
F0 is merged and gated** (§9 gate 1). The sequence is **F0 → M1a…M1e → M2a…M2f → M3a…M3c**. This
replaces a flatter grain that both made M2 too large to gate as one unit and let live-code sub-slices
start before the architecture decisions they depend on were settled.

**F0 — Phase-3 Architecture Foundation.** No WebSocket code; pure architecture and documentation
work, gated on its own (§9 gate 1):

- specify the `StudioRoot`/`WorkspaceRouter` shell boundary (§4.6);
- extract the neutral `BattleBoardSnapshot`/`bind()` board-presentation contract out of the existing
  Phase-0 abstract board view (§4.7), keeping existing Phase-0 tests green and protecting the
  refactor itself with targeted fail-checks;
- separate the direct-dependency default, the `ObservationEventBus`, and the privileged command
  gateways (§4.2), so no later sub-slice can casually reach for "put it on the bus";
- fix the four state machines and their states (§4.8); publish their full transition tables at
  `showdownbot_studio/docs/architecture/LIVE_STATE_MACHINES.md`;
- create the binding pre-M1 documents this design requires as F0 deliverables (listed here as
  required artifacts, not authored by this spec): `showdownbot_studio/docs/security/THREAT_MODEL.md`,
  `DATA_CLASSIFICATION.md`, `CREDENTIAL_LIFECYCLE.md`, `LOGGING_AND_REDACTION.md`,
  `UNTRUSTED_SERVER_CONTENT.md`, and `HUMAN_COMMAND_INVARIANTS.md`; plus
  `showdownbot_studio/docs/architecture/LIVE_STATE_MACHINES.md` and `MODULE_CATALOG.md`.
  `HUMAN_COMMAND_INVARIANTS.md` carries the machine-checkable command-origin rules: only the gateway
  may request choice commands; only the protocol encoder may build command strings; only `net/` may
  write to the socket; no replay/analyzer/mod/bot module imports the gateway; every choice command
  carries room ID, connection epoch, and current `rqid`; no request is sent twice; superseded
  requests are never re-sent; there is no automatic selection on timeout or error;
- define the forbidden-dependency architecture tests (gateway imports from `replay/`/`battle/`/an
  analysis module, untyped public interfaces, live-DTO reuse inside a bundle path) that the new
  `studio-security-invariants` CI lane (§8.2) runs from this slice onward;
- keep every existing Phase-0 test green throughout.

**M1 — Connect + Spectate.** WebSocket connection to the official server; watch one public battle
live, read-only, without logging in; visible connection status; reconnect with backoff. The
Phase-1-equivalent slice: it validates the entire net/protocol layer before any credential or
move-selection code exists.

- **M1a — WebSocket transport and connection state.** `net/`'s `WebSocketTransport`: connect,
  disconnect, heartbeat, `ConnectionState` (§4.8) reporting onto the `ObservationEventBus` (§4.2.2).
  No protocol decoding yet. Blocked on F0.
- **M1b — Protocol decoding and typed room events.** `protocol/`'s decoder (raw server text to
  typed, versioned DTOs under `protocol/dto/`, §4.1.2) plus its general outbound command encoder and
  the room join/leave commands specifically — M1d cannot spectate without sending `/join` (§4.1,
  §4.1.1). Introduces the `studio-protocol-contract` CI lane (§8.2).
- **M1c — Deterministic battle reducer.** `battle/`'s `LiveBattleReducer` (`battle/dto/`, §4.1.2)
  producing immutable `LiveBattleSnapshot` values from typed events, tested against frozen fixtures
  (§8); see §4.7 for the full live state model and the derived-state rule. This precedes spectating
  (M1d) because the spectator UI renders through `battle/`'s output — it cannot exist before that
  output does.
- **M1d — Direct room-ID spectating.** `workspace/`'s `LiveClientWorkspace` gains its Connection and
  Spectator areas (§4.6); UI to enter a known battle-room ID or full battle URL and watch that room's
  events render through `battle/` and `ui/panels/`, read-only, without login. Direct ID/URL entry
  only; an unknown or private ID produces a clear error (§6.1), never a fallback room or a room
  browser. Introduces the `studio-live-local-e2e` CI lane (§8.2).
- **M1e — Reconnect, full rebuild, and deduplication.** The reconnect/resync model in §6.2: on
  reconnect, `battle/` rebuilds completely from re-received room history, never incrementally.

No battle-choice command (`/choose`) can be issued in M1: the general encoder from M1b only knows
room join/leave here, and `HumanBattleCommandGateway` (§4.2.3) does not exist until M2d.

**M2 — Login + Play.** Login; a team chosen from an offline Python-validated team bundle; challenge
and ladder play; move selection. Legal actions are read exclusively from the server's `|request|`
JSON; Godot computes no game mechanics, legality, or damage in this milestone or any other.

- **M2a — Login session and credential lifecycle.** `session/`'s `CredentialProvider` (memory-only),
  `LoginCoordinator`, `SessionState` (the state machine in §4.8, plus non-secret session metadata);
  `net/`'s `LoginHttpTransport` (§4.1, §5.1); `session/dto/` (§4.1.2).
- **M2b — Format catalog and TeamBundleV1 acquisition.** A typed `FormatCatalogDTO`
  (`protocol/dto/`, §4.1.2) built from the server-authoritative `|formats|` event, carrying one
  `FormatDescriptor` per format: `format_id`, `display_name`, `section`, `team_mode` (`USER_TEAM` |
  `RANDOM_TEAM`), `supports_ladder`, `supports_challenge`, `required_capabilities`. Format-selection
  UI lists formats from this catalog only, never from a hardcoded list. Loading and validating an
  offline team bundle (§3.4) is required only when the selected format's `team_mode` is
  `USER_TEAM`; a `RANDOM_TEAM` format needs no team bundle (§6.3).
- **M2c — Challenge and ladder acquisition.** Challenge send/accept and ladder search start/cancel,
  through the M1b encoder; `RoomState` (§4.8) tracks the resulting room.
- **M2d — Human-only choice gateway.** `HumanBattleCommandGateway` (§4.2.3) wired to the
  move-choice UI; `workspace/`'s `LiveClientWorkspace` gains its Matchmaking and HumanBattle areas
  (§4.6); nothing else can send `/choose` after this lands.
- **M2e — Team preview, doubles choices, targets, switches.** The full VGC/doubles choice surface
  and its lifecycle (§7, §7.1), tracked through `ChoiceRequestState` (§4.8).
- **M2f — Timer, chat, undo, forfeit, reconnect while playing.** Remaining battle-room commands, the
  chat trust boundary (§5.2), and reconnect while a battle is in progress (§6.2).

**M3 — Replays.** Save a finished battle in the existing Phase-0 viewer bundle format, so a battle
played through this client opens in the existing, unmodified Phase-0 viewer.

- **M3a — Canonical live recording stream.** `replay/`'s `LiveRecordingSink` (§4.5) consumes
  `protocol/`'s `CanonicalProtocolEventStream` directly (§4.2.1) — the same stream `battle/`'s
  reducer consumes — and converts it (§4.1.2) into recorded-replay event types distinct from the
  live DTOs.
- **M3b — Phase-0 bundle writer.** `replay/`'s writer hands the recorded stream to
  `ReplayExportGateway` (§4.5.1), which invokes the existing, pinned Python exporter out of process
  for canonicalization, only after an explicit user "save replay" action; Godot never assembles
  bundle bytes itself.
- **M3c — Replay compatibility and privacy verification.** The written bundle opens unmodified in
  the existing Phase-0 viewer, and the chat/credential exclusions in §5.1–§5.2 hold under inspection.

Only finished battles are saved; a battle abandoned by disconnect or forfeit before completion is
not silently packaged as a normal replay (an explicit incomplete/aborted marker, if recorded at all,
is a later design's concern, not this one's).

### 3.4 TeamBundleV1 contract

A team bundle is a **canonical directory** (`team-bundle/`), matching the existing Phase-0
canonical-directory bundle convention (`viewer-v0-design.md` §5.2) rather than a single self-hashing
file — a hash cannot cover the JSON document that also contains it. `team-bundle/` contains:

- `manifest.json`;
- `packed-team.txt` — the already-canonical packed Showdown team string.

It is produced offline by the existing Python team-validation/packing path (`MASTER_SPEC.md`
§4/Phase 2, `PROJECT_BOUNDARIES.md` §2). **Team-bundle loading never invokes Python at runtime**:
Godot contains zero team-packing or team-validation logic; it only loads and re-checks an
already-produced directory. Replay export is a separate boundary with a different rule — it *may*
invoke Python out of process, under strict conditions; see §4.5.1.

`manifest.json` fields:

| Field | Meaning |
|---|---|
| `schema_version` | `major`/`minor` pair, following the discipline in `MASTER_SPEC.md` §3.3 |
| `bundle_id` | Stable identifier for this team bundle |
| `format_id` | The Showdown format this team is valid for |
| `display_name` | Human-readable label shown in the team-selection UI |
| `team_summary` | Species/role summary for display, derived from the packed team, not a second source of truth |
| `validation_provenance` | Validator version and source hash |
| `required_capabilities` | Capabilities a reader must recognize before trusting the bundle (same fail-closed discipline as §4.2.2) |
| `files` | One entry per bundle file, keyed by relative path, each carrying a `sha256` |

`files["packed-team.txt"].sha256` is the hash a reader checks against the actual file bytes on disk —
the hash lives in `manifest.json`, over a *different* file, so it is never self-referential.

**Deviation from an earlier draft, already approved by the owner:** the bundle carries **no
`created_at`** inside its hashed canonical content. `PROJECT_BOUNDARIES.md` §3 forbids export-time
metadata (timestamps, host names) inside canonical bundles; `validation_provenance` carries the
traceability this phase needs instead, exactly as the Phase-0 bundle manifest already omits a
creation timestamp (`viewer-v0-design.md` §5.2.1, §8).

On load, Godot runs these checks in order:

1. `manifest.json`'s `schema_version` against the versions it supports (an unsupported major fails
   closed, matching the Phase-0 rule in `viewer-v0-design.md` §7);
2. every entry in `required_capabilities` is known to this client (else fail closed);
3. `sha256` of `packed-team.txt` matches `files["packed-team.txt"].sha256`;
4. `format_id` is compatible with the format currently selected for challenge/ladder play — for a
   `RANDOM_TEAM` format (§3.1, §4.1.1, §6.3) this check, and the team bundle itself, is not required
   at all;
5. the packed team is consumed **as-is** — canonical, never re-packed or re-validated in GDScript.

Any mismatch in checks 1–4 is a visible, fail-closed error ("prepare teams offline via the Python
path"), never a silent fallback to a different team or format. A missing or invalid bundle for a
`USER_TEAM` format is the same visible error state, never a silent skip of team selection — the
concrete instance of the block-list entry in §6.3 ("incomplete or invalid `TeamBundleV1` → no
matchmaking," which §6.3 scopes to `USER_TEAM` formats only).

## 4. Architecture

### 4.1 Module map

One module is one directory and one job. Cross-module communication follows §4.2: direct typed
dependencies by default, the `ObservationEventBus` for a fixed, short list of broadcast events, and a
privileged command gateway for outbound commands. No module reaches into another module's internals
outside those three paths.

| Module | Directory | Job | Introduced in | Must not do |
|---|---|---|---|---|
| Net | `godot/src/net/` | `WebSocketTransport` (connection, reconnect, heartbeat, `ConnectionState` §4.8); `LoginHttpTransport` (the single HTTPS request to Showdown's login/action endpoint) | M1a (WebSocket), M1e (reconnect), M2a (login transport) | Parse or encode protocol text; hold battle state; hold `CredentialProvider` state |
| Protocol | `godot/src/protocol/` | THE only module permitted to encode any outbound Showdown protocol command, and the only module permitted to decode any inbound Showdown protocol text, into/from typed versioned DTOs under `protocol/dto/` (§4.1.2), including the `CanonicalProtocolEventStream` (§4.5) | M1b (decoder, general encoder, room join/leave), M1e (reconnect), M2b (`FormatCatalogDTO`), M2c/M2e/M2f (remaining command families, §4.1.1) | Render UI; hold connection sockets; decide whether a human is allowed to send a given command (that is the gateway's job, §4.2.3) |
| Session | `godot/src/session/` | `CredentialProvider`, `LoginCoordinator`, `SessionState` (holds the `SessionState` state machine, §4.8, plus non-secret metadata); team-bundle loading (§3.4); `session/dto/` (§4.1.2) | M2a–M2b | Touch raw protocol text; render UI |
| Battle | `godot/src/battle/` | Pure, deterministic, idempotent `LiveBattleReducer` producing immutable `LiveBattleSnapshot` values from `battle/dto/` DTOs (§4.7), consuming `CanonicalProtocolEventStream` directly (§4.2.1) | M1c, M1e (reconnect rebuild) | Contain UI nodes; recompute mechanics/damage/legality; hold or import `HumanBattleCommandGateway` (§4.2.3) |
| UI panels | `godot/src/ui/panels/` | Board, timeline, move choice, battle chat, connection status; renders via `BoardPresentationAdapter` (§4.7) | M1d (board, timeline, connection status), M2d–M2f (move choice, chat) | Produce protocol text directly; decide legality |
| Replay | `godot/src/replay/` | Record a finished live battle into a Phase-0 bundle via `LiveRecordingSink` and `ReplayExportGateway` (§4.5, §4.5.1); reuses `BoardPresentationAdapter` for its own board rendering (§4.7); converts live DTOs into recorded-replay events before export (§4.1.2, §4.5) | F0 (board-presentation-contract refactor, §4.7), M3a–M3c | Reinterpret or recompute recorded evidence; assemble canonical bundle bytes itself (§4.5); hold or import `HumanBattleCommandGateway` (§4.2.3) |
| Workspace | `godot/src/workspace/` | `StudioRoot`, `WorkspaceRouter`, `OfflineViewerWorkspace` (wraps the existing `AppShell` unchanged), `LiveClientWorkspace` (Connection, Spectator, Matchmaking, HumanBattle areas, §4.6) | F0 (scaffold), M1d (Connection + Spectator), M2d (Matchmaking + HumanBattle) | Own battle or credential state; duplicate board/team/replay logic; hold `HumanBattleCommandGateway` outside the HumanBattle area's controller (§4.2.3) |

`protocol/` is the single module in the whole application, across every phase, allowed to see or
produce raw protocol text. This restates `PROJECT_BOUNDARIES.md` §4 precisely: the UI must not
parse raw WebSocket text throughout arbitrary nodes, and no later module addition may weaken that.

The existing Phase-0 `replay/` directory (`abstract_board_view.gd`, `board_model.gd`,
`replay_presenter.gd`, `replay_workspace.gd`) is reused for its **view** and visual language, not for
its state object: `board_model.gd`'s mutable, replay-coupled `BoardModel` is not promoted to live
state (§4.7). M1d's live board panel in `ui/panels/` renders through the shared
`BoardPresentationAdapter` and the neutralized `AbstractBoardView` (post-F0 refactor, §4.7), and M3's
bundle writer lands as new files inside `replay/`. No second board *view* renderer exists anywhere in
Phase 3 — only a second, live-specific state source feeding the same view.

#### 4.1.1 Outbound command families

`protocol/`'s general command encoder grows to cover, across M1b and M2:

- login/name confirmation;
- room join/leave;
- team setting (`/utm`; sends the null-team form, `/utm null`, whenever the selected format's
  `team_mode` is `RANDOM_TEAM`, §3.4, §6.3);
- ladder search start/cancel;
- challenge send/accept;
- chat send;
- timer toggle;
- forfeit;
- undo/request-replacement;
- `/choose` (battle move, switch, and Terastallization actions).

Every family in this list is encoded exclusively by `protocol/`; no UI component ever assembles a
command string itself. Which sub-slice introduces which family is fixed by §3.3 and §4.4.

#### 4.1.2 DTO placement

Live protocol/session/battle DTOs do **not** live under `godot/src/bundle/`: that directory holds
`battle_event_dto.gd` and the rest of the existing Phase-0 sealed-replay-evidence DTOs, and reusing
it for live data would quietly couple a live transport shape to a frozen bundle contract. Live DTOs
get their own homes, one per owning module:

- `godot/src/protocol/dto/` — decoded protocol-level DTOs;
- `godot/src/session/dto/` — login/session DTOs;
- `godot/src/battle/dto/` — battle-domain DTOs consumed by `LiveBattleReducer`.

DTO families to name across these directories, introduced as their owning sub-slice lands (§4.4):
room lifecycle; user update; challstr/login; request JSON (`|request|`); error; inactive/timer;
chat; player and team preview; battle completion; reconnect epoch; request replacement; format
catalog (`|formats|`, §3.3 M2b).

Together, the decoded events form `protocol/`'s **`CanonicalProtocolEventStream`** — the single
ordered, provenance-carrying feed that `battle/` and `replay/` each consume directly (§4.2.1, §4.5).

`replay/`'s `LiveRecordingSink` (§4.5) deliberately **converts** this stream into separate canonical
recorded-replay event types before anything reaches the Python exporter; a live transport object
never becomes, by omission, a long-term bundle contract. An architecture test in the
`studio-security-invariants` CI lane (§8.2, from F0) checks this boundary directly: no live DTO type
may be serialized straight into a bundle file.

### 4.2 Communication paths

Phase 3 uses three structurally distinct ways for one module to affect another — only three. A
design or review that reaches for "publish it on the bus" or "the UI can just call across" as an
informal fourth path is wrong by construction.

#### 4.2.1 Direct dependencies (the default)

Most cross-module calls are ordinary: a small, explicit, typed interface, wired by
composition-root/constructor injection, with locally scoped typed signals where a callback shape
fits better than a return value. This is not a fallback — it is the **default** path for anything
that is not a broadcast observation (§4.2.2) or a privileged command (§4.2.3).

This already matches how Phase 0 is built: the existing `AppShell` (`godot/src/workspace/app_shell.gd`,
scene `godot/src/workspace/app_shell.tscn`) wires its loader, workspaces, and controllers through
explicit references and typed signals — there is no global bus anywhere in Phase 0. Phase 3 continues
that pattern rather than introducing a bus-first style the existing code does not use. `protocol/`'s
`CanonicalProtocolEventStream` (§4.1.2, §4.5) is the clearest live example: both of its consumers
reach it this way, never through the bus.

#### 4.2.2 ObservationEventBus

A typed, versioned, **read-only** bus carrying only a short, fixed list of broadcast events, because
a broadcast is the right shape only when more than one otherwise-unrelated module needs the same
notification: connection status changed, battle state published, battle completed, chat received,
diagnostic event. Anything narrower belongs on a direct dependency (§4.2.1), not the bus.

The bus **never** carries battle commands, login/credential data, a mutable session object, or the
raw `CanonicalProtocolEventStream` (§4.5) — only the fixed event list above, and only
already-published, read-only values. Event names and payload shapes are documented in
`showdownbot_studio/schemas/`, following the same `major`/`minor` discipline `MASTER_SPEC.md` §3.3
already defines. `ui/panels/` subscribes to render; nothing that only subscribes to it can cause an
outbound command.

This bus — and only this bus — is the potential future Phase-4 mod observation surface: a selected,
read-only subset of its events, once Phase 4 exists as its own approved design (§11). No plugin
loader, manifest system, or third-party registration path exists in Phase 3. Keeping the raw
protocol-event stream off the bus (§4.5) is what makes that future mod surface safe to build at all:
a mod could see "battle state published," never the event-by-event stream a replay recording needs.

#### 4.2.3 Privileged command gateways (HumanBattleCommandGateway and siblings)

Every outbound command reaches `protocol/` through exactly one explicit object reference, injected
only into the UI component responsible for that action. This pattern is called a **privileged
command gateway**, and it is never a variant of the bus: it is not registered on it, not discoverable
through it, and carries no observation traffic.

The battle-choice instance, `HumanBattleCommandGateway`, is named explicitly because §11's
no-automation guarantee depends on it directly. It carries four bans, binding together:

1. never registered on, or discoverable through, the `ObservationEventBus` (§4.2.2);
2. never part of any mod attachment surface in any later phase;
3. never imported by `replay/`, `battle/`, or any future analysis/matchup module — a module that only
   reads or records state has no legitimate reason to hold a reference that can send a server
   command;
4. injected only into the active human battle controller in `ui/panels/` (from M2d onward); nothing
   else in the application holds a reference to it.

Room join/leave, chat send, challenge/ladder, and timer/forfeit/undo commands each go through their
own narrowly scoped gateway instance following the identical four bans; naming each instance is
implementation-plan detail, the bans themselves are not negotiable for any of them.

**Honesty note.** GDScript has no language-level access control — there is no engine-enforced
`private` keyword that could technically prevent another node from acquiring a gateway reference.
The guarantee is therefore **structural**, not runtime-enforced: upheld by injection discipline, by
code review (a review that finds any other holder of a gateway reference, or an import of one from
`replay/`, `battle/`, or an analysis module, treats it as a defect — the same seriousness
`MASTER_SPEC.md` §6 gives an unrecorded aggregation mode), and by the forbidden-dependency
architecture tests introduced in F0 (§3.3, §8.2). This mirrors the honest framing this document
already uses for credentials (§5.1).

### 4.3 Data flow

```text
Inbound:  Server --> net/ --> protocol/ --> CanonicalProtocolEventStream (§4.5)
              --> battle/'s LiveBattleReducer --> LiveBattleSnapshot --> BoardPresentationAdapter --> ui/panels/
              --> replay/'s LiveRecordingSink --> ReplayExportGateway --> Phase-0 bundle (on explicit save, §4.5.1)
              --> ObservationEventBus (fixed allowlist only, §4.2.2) --> other subscribers
Outbound: user click --> human battle controller --> HumanBattleCommandGateway --> protocol/ --> net/ --> Server
```

Most of the inbound path is a direct, typed dependency (§4.2.1): `protocol/` hands its
`CanonicalProtocolEventStream` directly to both `battle/`'s `LiveBattleReducer` and `replay/`'s
`LiveRecordingSink` (§4.5) — two independent direct consumers of the same ordered stream, neither
reached via the bus. `battle/` then hands a fresh `LiveBattleSnapshot` to `BoardPresentationAdapter`,
again a direct call. Only the fixed, short list of events in §4.2.2 goes over the
`ObservationEventBus`. The outbound path stays exactly as strict as before: `protocol/` remains the
only module that forms outbound protocol text and the only module that parses inbound protocol
text; there is no shortcut from `ui/panels/` to `net/`, and no shortcut from `net/` to `battle/`.

### 4.4 Milestone-to-module mapping

| Sub-slice | Modules with new production code |
|---|---|
| F0 | `workspace/` (`StudioRoot`/`WorkspaceRouter`/`OfflineViewerWorkspace` scaffold, §4.6); board-presentation-contract refactor in `replay/` (`BattleBoardSnapshot` extraction, §4.7); architecture-test scaffolding (no runtime protocol/battle module code) |
| M1a | `net/` (`WebSocketTransport`) |
| M1b | `protocol/` (decoder, general command encoder, room join/leave, `protocol/dto/`) |
| M1c | `battle/` (`LiveBattleReducer`, `battle/dto/`) |
| M1d | `workspace/` (`LiveClientWorkspace` Connection + Spectator areas), `ui/panels/` (board, timeline, connection status) |
| M1e | `net/`, `protocol/`, `battle/` (reconnect/rebuild/dedup, §6.2) |
| M2a | `session/` (`session/dto/`), `net/` (`LoginHttpTransport`) |
| M2b | `protocol/` (`FormatCatalogDTO`, §4.1.2), `session/` (team-bundle loading, §3.4) |
| M2c | `protocol/` (challenge/ladder command families) |
| M2d | `ui/panels/` (`HumanBattleCommandGateway` wiring), `workspace/` (`LiveClientWorkspace` Matchmaking + HumanBattle areas) |
| M2e | `protocol/`, `ui/panels/` (doubles choice surface, §7.1) |
| M2f | `protocol/`, `ui/panels/` (timer, chat, undo, forfeit, §5.2, §6.2) |
| M3a | `replay/` (`LiveRecordingSink`, §4.5) |
| M3b | `replay/` (bundle writer, `ReplayExportGateway`, §4.5.1) |
| M3c | `replay/` |

Whether `TeamBundleV1` loading (M2b) lives directly inside `session/` or a small dedicated
submodule of it is an implementation-plan detail, not a design ambiguity: either choice keeps
team-bundle loading out of `protocol/`, `battle/`, and `ui/panels/`, which is the binding constraint.
No sub-slice adds code to a module outside this table without amending this document.

### 4.5 Replay data source

`protocol/`'s decoder emits a **`CanonicalProtocolEventStream`**: the ordered, normalized,
provenance-carrying sequence of typed events (`protocol/dto/`, §4.1.2) that everything else in the
live chain is built from. It has exactly two consumers, both reached through direct typed
dependencies (§4.2.1), never the bus:

- `battle/`'s `LiveBattleReducer` (§4.7), which folds it into `LiveBattleSnapshot` values;
- `replay/`'s `LiveRecordingSink` (M3a), which converts it into recorded-replay event types for
  export (§4.1.2).

The `ObservationEventBus` (§4.2.2) keeps **only** its fixed allowlist — published read-only states
and diagnostics. The raw `CanonicalProtocolEventStream` is never placed on it and is never part of
any mod surface: a future Phase-4 mod could see "battle state published," never the raw
event-by-event stream a replay recording needs. Putting the stream on the bus would both violate the
bus's fixed-allowlist rule (§4.2.2) and expose exactly the granularity a future mod boundary must
keep away from mods.

This direct-dependency shape, rather than a bus subscription, also buys strict event ordering and no
lost events: a broadcast bus makes no ordering promise across independent subscribers, but
`LiveRecordingSink` needs the exact order `protocol/` produced, and `LiveBattleReducer` needs the
same guarantee for determinism (§6.2). Recorder ownership is unambiguous as a result: `replay/` is
the only module that ever turns the stream into bundle-bound data (§4.1.2).

Replays are never reconstructed backwards from the final `LiveBattleSnapshot`; reconstructing from a
terminal state would lose exactly the intermediate detail (event timing, degraded/warning markers)
that makes a replay useful.

```text
protocol/ decoder --> CanonicalProtocolEventStream --> replay/'s LiveRecordingSink (M3a) --> replay/ bundle writer (M3b) --> ReplayExportGateway (§4.5.1) --> Phase-0 bundle
                                                    \--> battle/'s LiveBattleReducer --> LiveBattleSnapshot --> ui/panels/
```

`replay/`'s bundle writer hands the recorded stream to `ReplayExportGateway` (§4.5.1), which invokes
the existing Python exporter out of process for canonicalization: Godot never assembles canonical
bundle bytes itself, keeping bundle-creation ownership with Python per `MASTER_SPEC.md` §3.2 and
`PROJECT_BOUNDARIES.md` §1. This is the same DTO-conversion boundary named in §4.1.2: the stream
`LiveRecordingSink` produces never carries a live DTO type directly into the exporter — it carries
the converted recorded-replay event types instead.

Credentials (§5.1) and, by default, chat content (§5.2) never reach `LiveRecordingSink`. A field the
recorder is not allowed to carry is never written into the canonical stream in the first place; it
is not filtered out later at the bundle-writer stage, so no Python-side redaction step is trusted to
catch a credential or chat leak that Godot already recorded.

#### 4.5.1 ReplayExportGateway: the Python process boundary

§3.4 restated precisely: **team-bundle loading never invokes Python** — that rule is scoped to team
bundles specifically (loading, hashing, and format-compatibility checks are pure Godot). Replay
export is a different boundary: it **may** invoke a dedicated, pinned, out-of-process Python
exporter, and only after an explicit user action ("save replay"), exclusively through
`ReplayExportGateway`. Its binding contract:

- runs the pinned repository exporter — never a bare Python interpreter or a package resolved via
  PATH/ambient environment;
- writes to a temporary, app-owned working directory;
- receives no credential or chat content in its input (restates §4.5, §5.2);
- fixed, versioned input and output schemas (the same `major`/`minor` discipline as every other
  schema family, `MASTER_SPEC.md` §3.3);
- enforces a timeout, and supports user-controllable cancellation;
- captures stderr and redacts it before any surfacing to the user or a log;
- publishes the finished bundle **atomically** — a failed or cancelled export never leaves a
  partially-written, apparently-valid replay behind;
- any failure is a visible, fail-closed error (§6.3), never a silent partial save.

This is the same out-of-process, versioned-boundary pattern `MASTER_SPEC.md` §3.2 already requires
for bundle creation; `ReplayExportGateway` is Phase 3's concrete instance of it, reached only from
`replay/`'s bundle writer (M3b).

### 4.6 Shell architecture: StudioRoot and WorkspaceRouter

Phase 3 does **not** grow the existing `AppShell` (`godot/src/workspace/app_shell.gd`, main scene
`godot/src/workspace/app_shell.tscn`) into a live client. `AppShell` is the Viewer-v0 shell: it holds
the bundle path, the replay/decision workspaces, and the diagnostics dock, and that is a complete,
closed job (Phase 0, §1).

Phase 3 introduces one level of routing above it, inside the existing `workspace/` module:

- **`StudioRoot`** — the new application entry point. It owns only navigation, global safe settings
  (scale, density, theme — the cross-phase UX requirements already binding via `MASTER_SPEC.md` §5),
  window/theme management, and workspace lifecycle. It never owns battle or credential state; those
  stay inside `battle/` and `session/`, reached only through the paths in §4.2.
- **`WorkspaceRouter`** — switches between the two top-level workspaces below. It holds no domain
  state of its own.
- **`OfflineViewerWorkspace`** — wraps the existing `AppShell` content **unchanged**. Phase 0's
  viewer keeps working exactly as it does today; Phase 3 adds a router above it, not a rewrite
  inside it.
- **`LiveClientWorkspace`** — the new live surface, organized into four areas: Connection (status,
  reconnect), Spectator (M1d board/timeline), Matchmaking (M2b–M2c format/team/challenge/ladder), and
  HumanBattle (M2d–M2f choice UI, chat, timer). Each area is composed from `ui/panels/` components;
  `LiveClientWorkspace` itself holds no battle or credential state, matching `StudioRoot`'s rule one
  level up.

This boundary is specified in F0 (§3.3) before any WebSocket code exists, precisely so the live
surface is designed as an addition beside the closed Phase-0 shell, never as a modification of it.

### 4.7 Live state model, board presentation contract, and the derived-state rule

**Live chain:**

```text
raw protocol text --> protocol/ decoder --> CanonicalProtocolEventStream (protocol/dto/, §4.5)
    --> battle/'s LiveBattleReducer --> immutable LiveBattleSnapshot --> BoardPresentationAdapter --> AbstractBoardView
```

**Replay chain (parallel, existing Phase-0 path):**

```text
replay DTOs (godot/src/bundle/) --> replay/'s ReplayPresenter --> BoardPresentationAdapter --> AbstractBoardView
```

The existing Phase-0 `BoardModel` (`godot/src/replay/board_model.gd`) is mutable,
`Variant`/`Dictionary`-based, hardcoded to the `p1`/`p2` × `a`/`b` slot shape, and semantically
coupled to `has_replay`. It is **not** promoted to authoritative live state: `battle/`'s
`LiveBattleReducer` produces its own `LiveBattleSnapshot`, a typed, immutable value object
independent of `BoardModel`. What Phase 3 reuses from Phase 0 is the **view** (`AbstractBoardView`)
and its visual language, not the replay state object.

Both chains converge on a shared `BoardPresentationAdapter`, mapping either a `LiveBattleSnapshot` or
the existing replay presentation data into one neutral board-rendering contract,
`BattleBoardSnapshot` (`presentation_available`, `empty_state_reason`, `turn`, `weather`, `terrain`,
`slots`, `side_conditions`, `field_conditions`), and calling `AbstractBoardView.bind(snapshot)`. This
requires a characterization refactor of `abstract_board_view.gd` (F0, §3.3): today it hardcodes
`EMPTY_REPLAY_TEXT = "No replay evidence in this bundle"` and checks `board.has_replay` directly. F0
extracts the neutral `BattleBoardSnapshot`/`bind()` API first and moves replay-specific empty-state
wording into the replay adapter, with the existing Phase-0 test suite kept green throughout and the
refactor itself protected by targeted fail-checks (break the guard, confirm red) — the same practice
already used for the Phase-0 gate-coverage recheck.

**State is derived, never manually patched (binding).** `LiveBattleSnapshot` values exist only as
read-only output of the deterministic `LiveBattleReducer` (§6.2) applied to typed protocol events;
there is no other writer. A direct mutation from UI or any other module — `pokemon.hp = 0`,
`active_slot = 1`, `request_complete = true`, or equivalent — is a defect, not a valid shortcut,
exactly as `AGENTS.md` rule 5 already states. This extends unchanged from Phase 0's read-only DTO
discipline (`viewer-v0-design.md` §5.4); Phase 3 adds no second, mutable path to the same data.

### 4.8 State machines

Phase 0 already has a concrete lesson about loose booleans standing in for state: the
`BundleLoader`'s CI flake, where a deferred worker set a plain `is_loading()` to `false` while the
next operation had not actually begun (recorded in the Phase-0 gate-coverage-recheck evidence,
`docs/plans/evidence/viewer-v0-gate-coverage-recheck.md`). Phase 3 has more concurrency-sensitive
state than Phase 0, not less, so it uses explicit, enumerated state machines wherever a boolean
would otherwise stand in for "one of several mutually exclusive conditions."

Four state machines are binding:

| State machine | States |
|---|---|
| `ConnectionState` | `DISCONNECTED`, `CONNECTING`, `CONNECTED`, `RECONNECTING`, `EXHAUSTED` |
| `SessionState` | `ANONYMOUS`, `AUTHENTICATING`, `AUTHENTICATED`, `LOGIN_FAILED` |
| `RoomState` | `NOT_JOINED`, `JOINING`, `ACTIVE`, `LEAVING`, `CLOSED` |
| `ChoiceRequestState` | `NONE`, `OPEN`, `SUBMITTING`, `SUBMITTED`, `REJECTED`, `SUPERSEDED` |

`session/`'s `SessionState` object (§5.1) *is* this state machine, plus whatever non-secret session
metadata that state requires; it never holds the credential value itself, which stays inside
`CredentialProvider`/`LoginCoordinator` for the duration of a single login exchange (§5.1).
`ChoiceRequestState.SUPERSEDED` is the enumerated form of the "stale `rqid`" condition already
required in §6.2 and §7; `ConnectionState.EXHAUSTED` is the enumerated form of the "reconnect
exhausts backoff" row in §6.1.

Every transition in every one of these machines must specify, and be tested against: the allowed
source state(s), the triggering event, the resulting state, and the user-visible behavior at that
transition. An untested or unspecified transition is treated the same as an untested branch anywhere
else in this design (§8): not done.

The full transition tables are a binding F0 deliverable, not written by this design document:
`showdownbot_studio/docs/architecture/LIVE_STATE_MACHINES.md` (§3.3). This spec fixes the four
machines and their states; the tables fix every edge between them.

## 5. Credentials and security

### 5.1 Credential handling

- v1 stores **nothing**. There is no credential file, no cached token, and no keyring write in this
  phase's default configuration.
- The application releases all references to credential values immediately after the authentication
  exchange and never intentionally persists, logs, exports, or reuses them. **Secure memory
  zeroization is not claimed** for the GDScript runtime: GDScript strings are garbage-collected, not
  wiped on demand, so this document claims release-of-reference and no intentional retention, not
  that the password's bytes are erased from process memory at a specific instant.
- Authentication sits entirely behind a `CredentialProvider` interface (`session/`). v1 ships
  exactly one implementation, a memory-only provider. A second implementation backed by the Windows
  Credential Manager may be added later without changing `session/`'s consumers of
  `CredentialProvider`, because nothing outside `session/` may depend on which implementation is
  active.
- The single HTTPS request that exchanges credentials for a login assertion is made by `net/`'s
  `LoginHttpTransport` (§4.1): it receives a credential value for exactly that one request, returns
  a typed login result, and stores nothing afterward. `session/`'s `LoginCoordinator` orchestrates
  the exchange and, together with `SessionState` (the state machine in §4.8), is the only place that
  holds session-lifetime state; `CredentialProvider` itself is likewise owned only by `session/`.
- No credential may ever be written to disk, to a log line, to a crash report, or into any Studio
  export (viewer bundle, diagnostic summary, or otherwise).
- No bot automation of any kind exists in this phase. There is no code path by which a `/choose`
  command, or any other outbound battle command, originates from anything but an explicit human UI
  interaction through the `HumanBattleCommandGateway` (§4.2.3, §7).

The credential-handling review gate (§9) explicitly searches every place a value could leak
sideways, not only the obvious storage path:

- Godot debug output;
- exception and error texts;
- HTTP request dumps (the `LoginHttpTransport` call itself);
- `ObservationEventBus` event payloads and Godot signals;
- crash reports;
- diagnostic exports;
- screenshot or UI-state restore/session-persistence features;
- clipboard usage.

### 5.2 Chat trust boundary

Server-delivered chat lines and player names are **untrusted input**, exactly like an imported
bundle or team file is untrusted input in Phase 0 (`PROJECT_BOUNDARIES.md` §3). Binding rules:

- no rendering of server-delivered HTML;
- no BBCode interpretation; v1 renders all chat content as safe plaintext;
- URLs inside chat are never clickable without a deliberate, separate user action (no
  auto-linkification that becomes a click target by default);
- control characters are escaped before display;
- message length is capped;
- chat content does not appear in logs unless a diagnostic mode is explicitly enabled by the user
  for that session;
- chat is **excluded from replay bundles by default**, consistent with the existing
  `portable-pseudonymous-v1` rule in `PROJECT_BOUNDARIES.md` §3 that already excludes chat and
  private messages from Phase-0 portable bundles. Per §4.5, this exclusion happens at the recording
  stream itself (`LiveRecordingSink` never carries the field), not as a later filter on an
  already-recorded stream.

## 6. Error handling and reconnection

### 6.1 Fail-closed error table

Phase 3 keeps the Phase-0 rule that unknown or invalid state is surfaced, never guessed or silently
recovered.

| Condition | Required behavior |
|---|---|
| Connection lost | Visible status (connected / disconnected / reconnecting); auto-reconnect with backoff; full state rebuild after reconnect (§6.2); never silently frozen |
| Unknown protocol line | Logged and surfaced as "not understood"; never crash; never guess-interpreted |
| Server rejects/declares a move illegal | Server error surfaced to the user; choice UI reopens; no auto-retry (§7) |
| Login fails | Clear failure message; credential reference released immediately (§5.1); no automatic second attempt |
| Battle timer running out | Server-authoritative countdown displayed; the client never auto-picks a move on timeout; if the *server* applies its own format-dependent default choice, that turn is labeled `SERVER_DEFAULT_ON_TIMEOUT` (§7) — never displayed or recorded as a human selection or client automation |
| Reconnect exhausts backoff | Status shows disconnected and stays visibly disconnected; no silent fallback to an offline or frozen view |
| Action bound to a stale epoch/rqid | Dropped before send, with a surfaced notice (§6.2, §7); never sent to the server |
| Unknown or private battle-room ID entered (M1d) | Clear error shown; no fallback room and no room browser offered instead |

As in Phase 0, the module that classifies an event decides what is recoverable; a downstream module
never invents its own recovery logic. Here that classifying module is `protocol/` for parse-level
conditions and `net/` for connection-level conditions.

### 6.2 Reconnect and resync model

After **any** reconnect, `battle/`'s state is rebuilt **completely** from the re-received
authoritative room history that the server resends on rejoin. There is no incremental patching of a
possibly-stale local state: the `LiveBattleReducer` (M1c) is deterministic and idempotent, so
replaying the same room history — whether received the first time or after a reconnect — yields the
same `LiveBattleSnapshot`. This determinism is what makes "rebuild completely" tractable rather than
merely safe-sounding.

Binding rules:

- a locally selected but **unconfirmed** choice is discarded on reconnect and is **never**
  automatically re-sent; the human sees the current (possibly team-preview or force-switch) request
  again and chooses again;
- every outbound battle action is bound, at the moment the human battle controller hands it to the
  `HumanBattleCommandGateway`, to the current `battle_room_id`, the current `connection_epoch` (a
  counter incremented on every connect and reconnect), and the latest known server request id
  (`rqid`, §7); an action bound to an older epoch or an older `rqid` is dropped with a surfaced
  notice, not sent;
- received protocol lines are deduplicated across reconnects, including chat and timeline lines —
  the server's resent room history is expected to overlap with what the client already has, and that
  overlap must not appear twice in the timeline or the chat panel;
- a stale `|request|` payload (one superseded by a newer `rqid`) is discarded, not merged with the
  newer one.

Required test scenarios (§8) include, at minimum: reconnect during team preview; reconnect during a
forced switch; reconnect after the battle has already ended. Each must resolve to a single,
consistent, rebuilt state — never a partially-patched one — and none may re-send a choice the human
made before the disconnect.

### 6.3 Fail-closed action block list

The following conditions are binding blocks, not suggestions — each is a defined "no" that the
relevant module enforces before anything is sent, submitted, or saved:

| Condition | Blocked action |
|---|---|
| Unknown request type | No selection is offered |
| Inconsistent slots (a request that does not match the expected active-slot count) | No selection is offered |
| Missing target information | No selection is offered |
| Unknown required capability (schema, §4.2.2) | No selection is offered |
| Stale `rqid` (§6.2, §7, `ChoiceRequestState.SUPERSEDED`, §4.8) | No selection is offered |
| Incomplete or invalid `TeamBundleV1` for a `USER_TEAM` format (§3.4, §4.1.1) | No matchmaking (challenge/ladder stays unavailable) |
| Incompatible replay schema | The battle is not saved |

A `RANDOM_TEAM` format (§3.4, §4.1.1) is never blocked by this table's `TeamBundleV1` row: it
requires no team bundle at all, and the encoder sends the null-team form (`/utm null`) instead of a
packed team. None of these conditions degrade to a best-effort guess anywhere in the client; each
maps to a specific module's existing fail-closed responsibility from §6.1, §3.4, or §4.5.

## 7. Choice and request lifecycle

Every human choice intent — everything that ultimately becomes a `/choose` command — carries a
fixed set of fields from the moment it leaves the human battle controller:

- `battle_room_id`;
- `connection_epoch` (§6.2);
- `request_id` (`rqid`);
- `request_revision`;
- `selected_actions`;
- `human_interaction_provenance` (evidence that this intent originated from the human-facing side of
  the `HumanBattleCommandGateway`, not a synthesized call).

Before `protocol/` encodes the command and `net/` sends it, all of the following checks run, in
order, and any failure stops the send — each corresponds to a `ChoiceRequestState` transition (§4.8):

1. the room is still active (`RoomState.ACTIVE`, §4.8);
2. `rqid` is the latest one known to the client (§6.2; otherwise `ChoiceRequestState.SUPERSEDED`);
3. nothing has already been submitted for this `rqid` (otherwise already `SUBMITTED`);
4. the UI selection is complete for the current request (team preview, doubles targeting, switches,
   etc. all resolved; otherwise the request stays `OPEN`);
5. the command arrived through the privileged `HumanBattleCommandGateway` (§4.2.3), not any other
   path.

Checks 1–4 run in the human battle controller and its gateway before `protocol/` ever sees the
intent; check 5 is structural, guaranteed by the injection discipline in §4.2.3 rather than a
runtime check `protocol/` performs.

After sending, the request is marked locally `SUBMITTING` then `SUBMITTED`. A server error reopens
the choice UI in a controlled way (`REJECTED` → `OPEN` again), per §6.1; there is no auto-retry.

**Choice provenance.** Every resolved turn's choice carries a `ChoiceProvenance` enum value, distinct
from the field-5 gateway-origin check above: `HUMAN_SUBMITTED` (an intent that passed all five
checks and was sent), `SERVER_DEFAULT_ON_TIMEOUT` (the **server** — never the client — applied its
own format-dependent default choice after the timer expired; §6.1 already forbids the client from
ever doing this itself), `SERVER_REJECTED` (the server declined the submitted choice; §6.1), and
`NOT_SUBMITTED` (no choice reached the server before the turn resolved some other way, e.g. a
battle-ending event). `SERVER_DEFAULT_ON_TIMEOUT` is surfaced in the UI and, when the choice is later
saved into a replay (§4.5), recorded with that exact label. A server-applied default must never be
displayable or recordable as a human selection or as client automation — misrepresenting it that way
would quietly undercut §11's no-automation guarantee even though no client code chose anything.

### 7.1 Required VGC/doubles fixture cases

The encoder and lifecycle tests (§8) must cover, at minimum, these cases — chosen because VGC
doubles has meaningfully more choice shapes than a singles turn:

- team preview;
- two moves with targets (both active slots choosing a move and a target);
- move + switch (one slot moves, the other switches);
- double switch;
- forced switch (after a faint);
- pass (a slot with nothing legal to do this turn);
- a trapped Pokémon (no switch option legally available);
- disabled moves (a move made illegal mid-battle, e.g. Torment/Disable/Encore);
- Terastallization as part of a choice;
- a fainted slot;
- a target that faints or otherwise vanishes before the choice is submitted;
- undo/request-replacement (the server issues a new `rqid` for the same turn);
- reconnect with a new `rqid` mid-choice (§6.2);
- a turn resolved by the server's own default choice on timeout (`SERVER_DEFAULT_ON_TIMEOUT`, §7),
  confirming the client never originates that choice and never mislabels it as `HUMAN_SUBMITTED`.

## 8. Testing and TDD discipline

TDD remains mandatory for every milestone and sub-slice in this phase (§3.3). The rule is stated
precisely, because "mandatory TDD" is easy to claim and easy to hollow out in practice:

- test and production code land together, in the same small PR or commit pair;
- the PR's evidence shows the test failing before the implementation that makes it pass (a
  screenshot, CI run, or commit-by-commit history is acceptable evidence — the point is that the
  failure is shown, not merely asserted);
- protocol fixtures and their expected DTOs (§8.1), and `/choose`-family encoder expectations
  (§7.1), are reviewed **before** the parser or encoder diff that satisfies them;
- every bugfix requires a reproducing regression test landing with the fix;
- a pure refactoring — no behavior change, existing tests pass unmodified — does not require an
  artificially reddened test; TDD governs new and changed behavior, not mechanical reshuffling.

No production module in `net/`, `protocol/`, `session/`, `battle/`, `ui/panels/`, `replay/`, or
`workspace/` lands without this test-before-implementation evidence in its PR. The later
implementation plan is structured task-by-task around this discipline; a task whose PR cannot show
the red-then-green pair for its behavior is not a valid task under this design.

### 8.1 Test layers

- **Protocol contract tests.** Frozen real server transcripts are fixtures. `protocol/` must
  translate each fixture into exactly the expected DTOs. A new Showdown protocol version means a new
  fixture is captured and reviewed, never that the parser guesses a compatible shape.
- **Battle state tests.** `LiveBattleSnapshot` values built from fixture logs are compared against
  expected snapshots in `battle/`. Determinism and idempotency (§6.2) are tested directly: replaying
  an identical fixture log twice, or replaying it with a simulated mid-stream reconnect, must produce
  an identical `LiveBattleSnapshot`.
- **State-machine tests.** Every transition in `ConnectionState`, `SessionState`, `RoomState`, and
  `ChoiceRequestState` (§4.8) is tested against its allowed source states, triggering event,
  resulting state, and visible behavior; an invalid transition is tested as an explicit rejection,
  not merely left unexercised.
- **Choice-lifecycle and `/choose`-family encoder tests.** Every case in §7.1's required fixture
  list is tested against the exact expected command string and against the lifecycle checks in §7
  (stale `rqid`, already-submitted, wrong epoch, incomplete selection, wrong-path origin); choice
  provenance (§7) is tested so a server-applied timeout default is never recorded or displayed as
  `HUMAN_SUBMITTED`.
- **Reconnect/resync tests.** The three required scenarios in §6.2 — team preview, forced switch,
  post-battle-end — are each exercised as their own fixture-driven case.
- **Recording and export tests.** `LiveRecordingSink` (§4.5) is tested against the same fixture logs
  as `LiveBattleReducer`, confirming it never carries a credential or chat field (§5.1, §5.2) and
  converts the stream deterministically; `ReplayExportGateway` (§4.5.1) is tested for atomic publish
  (a killed or cancelled export leaves no bundle behind), captured-stderr redaction, and rejection of
  any live DTO type at its input boundary.
- **Architecture/dependency tests.** Forbidden-dependency checks (§4.2.3, §9 gate 1): no import of
  `HumanBattleCommandGateway` from `replay/`, `battle/`, or an analysis module; no untyped container
  crossing a module's public interface (§10); no live DTO type serialized directly into a bundle
  file (§4.1.2).
- **End-to-end tests.** Run against the repository's pinned local `pokemon-showdown` checkout
  (seeded local server), referenced in `PROJECT_BOUNDARIES.md` §7 as the first simulation
  distribution already audited for this project's formats, and including at least one reconnect
  exercised during a live E2E battle. E2E tests never run against the live official server.
- **Manual live gate.** One real battle on the official server, before phase closure, with filed
  evidence following this project's existing gate-evidence conventions (as used for Phase 0's PR
  #81 closure evidence).

### 8.2 CI

CI is organized into four lanes, each introduced with the slice that first needs it — not one lane
that silently grows to cover everything Phase 3 adds:

| Lane | Covers | Introduced with |
|---|---|---|
| `studio-windows` | The existing Phase-0 regression suite (gdUnit4 + Python), unchanged | Already exists (Phase 0) |
| `studio-security-invariants` | Dependency-boundary checks, forbidden imports (e.g. `HumanBattleCommandGateway` imported from `replay/`/`battle/`), credential/logging checks, command-origin checks | F0 |
| `studio-protocol-contract` | Frozen transcript fixtures, parser/encoder tests, schema checks | M1b |
| `studio-live-local-e2e` | Pinned local Showdown server: spectate, play, reconnect; never touches the official production server | M1d |

Every lane runs on `windows-latest`, pins the same gdUnit4 release verified against Godot 4.5.2 that
Phase 0 already uses, and emits JUnit-compatible results, matching the standard already established
for `studio-windows`.

## 9. Gates before phase closure

Each sub-slice in §3.3 — including F0 — merges only once its own scoped tests are green in the
relevant CI lane (§8.2); this section lists the gates required before the **whole phase** is
considered closed, mirroring the general phase gate list in `MASTER_SPEC.md` §11 and Phase 0's own
closure practice.

1. **F0 gate.** The architecture-foundation slice (§3.3) is merged: the `StudioRoot`/
   `WorkspaceRouter` boundary is specified (§4.6); the `BattleBoardSnapshot`/`bind()` presentation
   contract is extracted with existing Phase-0 tests green and the refactor protected by targeted
   fail-checks (§4.7); the communication-path separation is documented (§4.2); the four state
   machines are fixed (§4.8) and their full transition tables are published at
   `docs/architecture/LIVE_STATE_MACHINES.md`; the security/architecture docs listed in §3.3 are
   created; forbidden-dependency architecture tests are green in the `studio-security-invariants` CI
   lane. **No M1 sub-slice may start until this gate passes.**
2. reviewed implementation plan for this design, split at minimum along F0 / M1a–M1e / M2a–M2f /
   M3a–M3c, each with its own PR and gate evidence;
3. isolated branch or worktree per the project's existing workflow;
4. protocol contract tests, battle-state tests, reconnect/resync tests (§6.2), and
   choice-lifecycle/`/choose`-family encoder tests (§7, §7.1) green in the `studio-protocol-contract`
   CI lane;
5. E2E tests green in the `studio-live-local-e2e` CI lane, covering the required reconnect scenarios
   (§6.2) and the required VGC/doubles fixture cases (§7.1);
6. one manual live gate battle against the official server, with filed evidence following this
   project's existing gate-evidence conventions;
7. credential-handling review (§5.1), using the explicit search list in §5.1, confirming no
   credential path reaches disk, logs, crash reports, event payloads, or exports;
8. chat-trust-boundary review (§5.2): confirmed no server-delivered HTML/BBCode is rendered
   unescaped, and chat is absent from a saved replay bundle by default;
9. `TeamBundleV1` review (§3.4): confirmed Godot performs no team packing/validation, verifies the
   `manifest.json`/`packed-team.txt` sha256 envelope and `required_capabilities` before trusting a
   bundle, and fails closed on schema, capability, hash, or format mismatch; confirmed a
   `RANDOM_TEAM` format (§3.4, §6.3) requires no team bundle and is never blocked by a missing or
   invalid one;
10. `ReplayExportGateway` review (§4.5.1): confirmed the exporter subprocess is the pinned
    repository exporter — never a bare interpreter or a PATH-resolved package — runs in a temporary
    app-owned working directory, receives no credential or chat content, enforces a timeout and
    user-controllable cancellation, redacts captured stderr before any surfacing, and publishes the
    finished bundle atomically, so a failed or cancelled export never leaves a partially-written
    replay behind;
11. rate-limit behavior review: login-attempt and message-frequency behavior checked against
    observed official-server limits before the live gate is attempted, so the live gate itself
    cannot trip a rate limit by surprise;
12. licensing review: client code is self-written; using the public, documented protocol is
    permitted per `MASTER_SPEC.md` §2.3 and §8; no sprite or other official/community asset is
    introduced (the abstract board is kept); any reused open-source snippet carries its required
    notice per §8;
13. human/bot separation review: confirmed by code inspection and by the `studio-security-invariants`
    architecture tests that the `HumanBattleCommandGateway` (§4.2.3) is the only path to an outbound
    battle command, that it is injected only into the intended UI component, and that none of its
    four bans (§4.2.3) is violated;
14. accessibility and layout checks proportional to the new UI surface (move-choice panel, chat
    panel, connection-status indicator), per `MASTER_SPEC.md` §5;
15. **maintainer acceptance-question gate.** For every module and data flow this phase touches, a
    maintainer can answer all five questions in `AGENTS.md`'s Acceptance questions section
    unambiguously: (1) which module owns this data? (2) which module may change it? (3) where does
    every outbound server action originate? (4) what happens on invalid or stale data? (5) which
    user data can leave this process? An answer of "somewhere via the event bus" or "the UI decides"
    fails this gate outright — it means the structure, not the wording, needs fixing;
16. explicit owner review and approval before merge, and before any later phase (Phase 4 or 5) may
    be proposed against this codebase.

Gate 6 (the manual live gate) is evidence of correct client behavior in a single real session. Per
`MASTER_SPEC.md` §6, it must never be reported or read as a bot-strength or bot-safety claim; there
is no bot in this phase to make a claim about.

## 10. Maintainer rules

The owner has asked that this phase be built "super structured, super readable for maintainers,
prepared for later modding." `showdownbot_studio/AGENTS.md` is the operational enforcement document
for these rules — it is what a maintainer or reviewer reads before touching this module tree, and
this section does not restate its full text. What follows is the subset this specific design depends
on, cross-referenced to `AGENTS.md`'s numbered rules:

- one module is one directory and one job (`AGENTS.md` rule 1), per the table in §4.1; a module that
  starts doing two jobs is split, not overloaded;
- every module ships a short README stating its purpose, its public interface, and its dependencies
  (`AGENTS.md` rule 2), added alongside that module's first production file;
- events and DTOs are versioned and documented under `showdownbot_studio/schemas/`, following the
  existing `major`/`minor` compatibility rule (`MASTER_SPEC.md` §3.3): unknown required capabilities
  fail closed, optional additions may be ignored by an older reader;
- no cross-module access bypasses the three paths in §4.2 (`AGENTS.md` rule 4); a review that finds
  one module reaching into another's internals treats it as a defect, not a style preference;
- typed GDScript, precisely stated (this refines `AGENTS.md` rule 9 for this phase's boundaries):
  `Variant`, untyped `Array`, and untyped `Dictionary` are permitted **only** inside audited parsing
  and serialization boundaries — `protocol/`'s decoder/encoder, DTO (de)serialization, and the
  replay bundle writer, where the whole point of the code is turning untyped bytes into typed values.
  No cross-module **public** interface may expose an untyped container; a value leaving a module
  boundary must be a named typed DTO, enum, or value object. This is architecture-testable, and the
  `studio-security-invariants` CI lane (§8.2) tests it, not just documents it.

`AGENTS.md` rules 5, 6, 7, and 10 (state is derived and never patched; protocol/state/UI separation;
no duplicate board/team/replay/validation logic; fail closed by default) are already load-bearing
throughout this design; §4.7, §4.1, §3.4/§4.5, and §6/§6.3 respectively are where this document
applies them to Phase 3 specifically, rather than repeating them here.

These rules exist so that Phase 4's eventual mod attachment point — built only against the
`ObservationEventBus` (§4.2.2), never against `HumanBattleCommandGateway` or any other privileged
command gateway (§4.2.3), and never against the raw `CanonicalProtocolEventStream` (§4.5) — has a
clean, well-bounded surface to attach to, without this phase pre-building any part of Phase 4 itself.

## 11. Non-goals and stop line

Phase 3, as scoped by this document, never becomes a bot deployment surface and never grows silently
into a later phase:

- **No bot automation pathway.** No code, module, or configuration in this phase can cause a
  `/choose` command, or any other outbound battle command, to originate from anything other than a
  direct human UI interaction through the `HumanBattleCommandGateway` (§4.2.3, §7). This is the
  single property every other requirement in this document is written to protect, and it is not
  satisfied by a default setting that a later change could flip — it must remain structurally true
  (§4.2.3, §5.1, §9 gate 13).
- **Phase 2 (Team/Matchup Analyzer) remains unauthorized and untouched.** Nothing in the module map
  (§4.1) or the offline team bundle consumed by M2b (§3.4) constitutes Team Analyzer functionality,
  and no shared module is pre-built for it here.
- **Phase 4 (mods and add-ons) remains unauthorized.** Phase 3 builds clean internal events only
  (§4.2.2); it does not define a public mod API. The intended shape of a *future*, separately
  approved Phase 4 is recorded here as stop-line precision, not as work this document authorizes:
  Phase 4 would define its own public mod API, distinct from the internal `ObservationEventBus`;
  only an explicit, allowlisted subset of read-only events would ever be exposed to a mod; write
  rights would require explicit, per-capability grants, never a default; battle commands would stay
  inaccessible to mods by default, with no path to `HumanBattleCommandGateway` (§4.2.3) short of a
  new approved design; and mods would run isolated and never receive credentials. None of this is
  built, wired, or scaffolded in Phase 3.
- **Phase 5 (external bot adapters) remains unauthorized.** Nothing in this document's protocol or
  battle-state layer may be reused as justification for wiring an external bot into this client
  without that phase's own approved design and its own out-of-process isolation review.
- Lobby chat, rooms, private messages, notifications, a teambuilder UI, remote/official sprite
  assets, and any plugin/mod loader remain out of v1 scope (§3.2) and are not implied by anything in
  §4's architecture.
- Growing this spec's scope toward any of the above — inside this document or through an
  implementation plan — requires a new approved design, exactly as `MASTER_SPEC.md` §9.1 and §11
  already require for the rest of the product family.
