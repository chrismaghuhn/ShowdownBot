# Phase 3 M1 (Connect + Spectate) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Status:** APPROVED (owner, 2026-07-25, after two integration-review passes) — binding companion:
[`2026-07-25-phase3-m1-implementation-watchlist.md`](2026-07-25-phase3-m1-implementation-watchlist.md)
(mandatory implementation-review checks; on conflict, later revision notes and their acceptance
tests win over earlier code samples). Approval of this plan authorizes *planning-level*
detail only; the code itself additionally requires a separate implementation go-ahead per
`MASTER_SPEC.md` §11 and this design's own gating discipline.

> **Revision note (2026-07-25, first pass):** the owner reviewed the first draft of this plan. The
> three sign-off decisions below stand as recorded (`ObservationEventBus` placement, the
> `--print-room-id` CLI addition, the deferred official-server capture, the deferred §6.2
> team-preview/forced-switch scenarios). Seven implementation errors were found and fixed: (1) the
> M1a heartbeat design and a TDD-ordering violation; (2) room join/leave bypassing a privileged
> command gateway, contradicting spec §4.2.3; (3) the fixture format losing multi-line frame
> boundaries, a "contains at least" fixture assertion instead of a golden comparison, no distinction
> between a deliberately-ignored protocol line and a genuinely unrecognized one, and a real parser
> bug in `_parse_hp_status()`; (4) `LiveBattleSnapshot` being only conventionally immutable, and the
> workspace incorrectly holding derived battle state itself; (5) missing room isolation, a
> `win`/`tie`-closes-the-room conflation, and no reachable UI path to the live workspace at all;
> (6) two bugs in the E2E provisioning script; (7) M1e touching a module outside its normative list
> and using a snapshot-based dedup approach that does not actually prove a full rebuild.
>
> **Revision note (2026-07-25, second pass — integration re-review):** the owner re-reviewed the
> first revision and found six new cross-task integration bugs the individual-task fixes above did
> not catch, plus two small fixes. All are corrected in this pass: (A) the reconnect timer opened a
> new peer on every single frame once backoff elapsed instead of once per attempt (`WebSocketTransport`
> never actually reached `CONNECTED` again) — fixed with an explicit attempt-in-flight condition,
> Task 7. (B) `LiveClientWorkspace` never forwarded a decoded `init` event to `LiveBattleProjection`
> at all, so the M1e repeat-`init` reset could never fire in real wiring, and Task 38's own test
> poisoned a projection that had never seen a first `init`, so even a correct implementation would
> not have reset — fixed by forwarding every confirmed battle-`init` to the projection (Task 29) and
> rewriting Task 38's test to the correct five-step sequence. (C) the automatic reconnect-rejoin
> recreated a second outbound send path directly from `RoomStateMachine` through the encoder to the
> transport, bypassing `SpectatorRoomGateway` and ignoring send failures — fixed with a
> `RoomStateMachine.automatic_rejoin_requested` signal that `SpectatorRoomGateway` subscribes to and
> handles through the same send-and-check-failure path as a human join; the subscription itself is
> wired in Task 28 (M1d), which M1e's Task 37 activates by emitting the signal — resolved honestly
> below without leaving M1e's "no `workspace/`/`ui/panels/` changes" claim self-contradictory, since
> `ui/panels/spectator_room_gateway.gd` is not touched again in M1e at all. (D) a `deinit` arriving
> while `RoomState` was `LEAVING` (a leave already in flight) called `server_closed_room()`, which is
> invalid from `LEAVING` and silently did nothing, leaving the room permanently stuck — fixed with
> state-aware `deinit` dispatch (Task 29) and a new `RoomState` `LEAVING`→`ACTIVE` local-leave-
> send-failure edge (Task 1, owner-approved), keeping `leave()` in scope rather than removing it,
> since it was already small and already built. (E) protocol fixtures arrived after the parser tasks
> instead of before them, violating spec §8's binding fixture-before-parser rule — M1b's Tasks
> 12–16 are reordered so the JSONL transcript, hand-written golden sequence, and a genuinely red
> contract test all exist before any decoder vocabulary is implemented. (F) the planned E2E seeding
> path either exited before Godot could join or ran to completion before Godot could observe
> anything real — fixed by running the seeder as a background process that keeps the battle alive
> past the marker line, waiting for a real battle event before asserting, and terminating the seeder
> in an `always()` cleanup (Tasks 33–34). Two small fixes: `configure_transport_for_test()` no
> longer re-runs the one-time domain/UI wiring (Task 29); `RoomEntryPanel.configure()` now accepts a
> `SpectatorRoomGatewayPort` interface so a `RefCounted` test fake satisfies it (Tasks 27–28). The
> heartbeat liveness claim is also softened to what Godot's own documentation actually guarantees
> (M1a design note, Task 3). Task numbering is otherwise unchanged from the first revision except
> within M1b's Tasks 12–16 (reordered, same count) and two new tests added to Task 11.

**Authorizing spec:** [`../specs/2026-07-25-phase3-client-design.md`](../specs/2026-07-25-phase3-client-design.md)
(APPROVED 2026-07-25), §3.3 Milestone M1 (the M1a–M1e bullet list), §4.4 (the milestone-to-module
mapping table, normative), §9 gates 2, 4, 5 (reviewed plan; protocol/battle-state/reconnect/choice
tests green in `studio-protocol-contract`; E2E tests green in `studio-live-local-e2e`). Also binding:
`showdownbot_studio/AGENTS.md` (rules 1–10, the amended rule 9), `docs/architecture/LIVE_STATE_MACHINES.md`
(the `ConnectionState` and `RoomState` transition tables this plan implements — **amended by Task 1
below**, owner-approved via this 2026-07-25 M1-plan review), `docs/architecture/MODULE_CATALOG.md`,
`docs/security/UNTRUSTED_SERVER_CONTENT.md`, `docs/security/LOGGING_AND_REDACTION.md`.

**Preconditions verified before writing this plan:** F0 is merged — `godot/src/workspace/studio_root.gd`,
`workspace_router.gd`, `offline_viewer_workspace.gd`; `godot/src/replay/battle_board_snapshot.gd`,
`battle_board_slot_snapshot.gd`, `replay_board_presentation_adapter.gd`; the three
`@pytest.mark.architecture` guard files under `showdownbot_studio/tests/python/`
(`test_f0_gateway_import_guard.py`, `test_f0_untyped_boundary_guard.py`,
`test_f0_live_dto_bundle_guard.py`) and their three allowlists under
`tests/python/architecture_allowlists/` (`untyped_boundary_allowlist.txt`,
`named_value_object_allowlist.txt`, `live_dto_bundle_path_allowlist.txt`) — all read directly from
the current tree, not from the F0 plan document. `net/`, `protocol/`, `session/`, `battle/`, `ui/` do
not exist yet under `godot/src/`. `.github/workflows/studio-windows.yml` and
`studio-security-invariants.yml` exist; `studio-protocol-contract.yml` and `studio-live-local-e2e.yml`
do not exist yet.

## Goal

Land Phase 3's M1 milestone — WebSocket connection to the official Showdown server, decoding into
typed protocol events, a deterministic battle-state reducer, direct room-ID spectating with a
visible connection status and a read-only battle board/timeline reachable through real navigation
UI, and full reconnect/rebuild — across five independently gated sub-slices (M1a–M1e), with **no**
`/choose` path, **no** `session/` module code, and **no** login of any kind. Every sub-slice merges
only after its own tests are green in the CI lane spec §8.2 assigns it, `git diff --check` is clean,
and its own PR is reviewed.

## Architecture

M1 touches exactly the modules spec §4.4 assigns to each sub-slice, and no others:

| Sub-slice | Modules with new production code (per spec §4.4, normative) |
|---|---|
| M1a | `net/` (`WebSocketTransport`) |
| M1b | `protocol/` (decoder, general command encoder, room join/leave, `protocol/dto/`) |
| M1c | `battle/` (`LiveBattleReducer`, `battle/dto/`) |
| M1d | `workspace/` (`LiveClientWorkspace` Connection + Spectator areas), `ui/panels/` (board, timeline, connection status) |
| M1e | `net/`, `protocol/`, `battle/` (reconnect/rebuild, §6.2) |

Two placement questions spec §4.4's table leaves unresolved on its own text are decided in "Plan
decisions requiring owner sign-off" below (`ObservationEventBus`) and in M1b's rationale
(`RoomStateMachine`). This revision adds a third, non-owner-facing architectural decision — where
derived battle state is *owned* — driven directly by the review: **`battle/`'s new
`LiveBattleProjection` (M1c) is the single owner of "current" derived state and its parallel
timeline**, never `workspace/`. This is also what keeps M1e's reconnect-rebuild work entirely inside
`net/`, `protocol/`, `battle/` without touching `workspace/` (see M1e's section header).

Live data flow this milestone builds (spec §4.3, §4.7):

```text
Server --(WebSocket, net/)--> WebSocketTransport.raw_text_received
    --(protocol/)--> ProtocolDecoder --> ProtocolEventDTO stream (protocol/dto/)
    --(battle/)--> LiveBattleProjection.apply_event() --> LiveBattleReducer.apply() --> LiveBattleSnapshot
    --(battle/, published)--> ObservationEventBus.battle_state_published
    --(ui/panels/, subscriber)--> LiveBoardPresentationAdapter --> BattleBoardSnapshot (replay/, F0 contract)
    --> AbstractBoardView.bind() (replay/, F0 contract, reused unchanged)
Connection status: WebSocketTransport.connection_state_changed (M1a, direct signal)
    --(M1d, workspace/)--> ObservationEventBus.connection_state_changed --> ui/panels/ConnectionStatusPanel
Outbound room join/leave (the ONLY outbound path M1 has — no /choose exists until M2d):
    ui/panels/RoomEntryPanel --> ui/panels/SpectatorRoomGateway.join(RoomJoinIntent)/leave()
        --> protocol/ProtocolCommandEncoder --> net/WebSocketTransport.send_raw_text() --> Server
Automatic reconnect rejoin (M1e, system-triggered, never through the human-facing gateway above):
    protocol/RoomStateMachine (already holds a WebSocketTransport reference, spec section 4.1's
    protocol/-depends-on-net/ dependency) --> ProtocolCommandEncoder --> net/WebSocketTransport
```

`ui/panels/SpectatorRoomGateway` exists because spec §4.2.3 already requires it: "Room join/leave,
chat send, challenge/ladder, and timer/forfeit/undo commands each go through their own narrowly
scoped gateway instance following the identical four bans." The first draft of this plan wired
`RoomEntryPanel` straight to the encoder and transport, which is exactly the "the UI can just call
across" fourth path spec §4.2 calls "wrong by construction." Fixed throughout M1d below.

## Tech stack

Godot 4.5.2 typed GDScript + gdUnit4 (pinned, `showdownbot_studio/godot/tools/`), Python 3.12 pytest
(`showdownbot_studio/python`, `showdownbot_studio/tests/python/`). Same tool pins as F0; no new
dependency is introduced. M1d's E2E lane additionally needs Node.js (for the pinned
`pokemon-showdown` checkout) — new to Studio's own CI, not new to the repository.

## Plan decisions requiring owner sign-off

> **Owner decisions recorded 2026-07-25, reaffirmed unchanged at this revision's review:**
> `ObservationEventBus` placement — **option (b) selected** (direct typed signal in M1a, bus class
> in M1d inside `workspace/`). The small `showdown_bot` CLI addition for the E2E lane
> (`--print-room-id`, now its own Task 33) is **approved**. The optional official-server transcript
> capture stays **unapproved** for M1. The §6.2 team-preview/forced-switch reconnect scenarios
> remain deferred to M2.
>
> **New in this revision, owner-approved via this same 2026-07-25 M1-plan review (not a fresh
> sign-off request — the reviewer directed these fixes explicitly):** two `LIVE_STATE_MACHINES.md`
> table edges this plan's first draft needed and did not have (Task 1); introducing
> `ui/panels/SpectatorRoomGateway` as the room join/leave privileged gateway spec §4.2.3 already
> requires; moving derived-state ownership into `battle/`'s new `LiveBattleProjection`.

### `ObservationEventBus` placement (spec §3.3 M1a vs. §4.4's table)

Spec §3.3's M1a bullet says `net/`'s `WebSocketTransport` reports `ConnectionState` "onto the
`ObservationEventBus` (§4.2.2)." But §4.2.2 never assigns the bus a directory, §4.1's module table
never lists a class named `ObservationEventBus` anywhere, and §4.4's own table lists M1a's only
touched module as `net/` — not `workspace/`.

**Recommendation (selected): (b) — defer the `ObservationEventBus` class itself to M1d; M1a reports
`ConnectionState` via a direct typed signal only.**

- M1a's `WebSocketTransport` gets a plain, locally-typed signal,
  `connection_state_changed(old_state: ConnectionStateMachine.State, new_state: ConnectionStateMachine.State)`
  — the §4.2.1 "direct dependency (default)" path, already how Phase 0's `AppShell` is built.
- The `ObservationEventBus` class itself is created in M1d, inside `workspace/`, where §4.4's table
  already permits new `workspace/` code and where genuine multiple subscribers first exist
  (`ConnectionStatusPanel` and the spectator board/log panels, all `ui/panels/`, all introduced in
  M1d).
- M1e's reconnect work publishes onto the same path M1d already established; M1e adds no new
  placement question.

Alternative (a) (build the bus in `workspace/` already during M1a) remains not recommended for the
reasons the first draft gave: it would widen M1a's table cell, and a bus with one publisher and zero
subscribers does not yet meet §4.2.2's own justification. Not selected.

### `RoomStateMachine` module placement (a corollary the spec text leaves implicit)

Unchanged from the first draft: `RoomStateMachine` is built in `protocol/` (M1b, Task 11), mirroring
`net/`'s `ConnectionStateMachine` (M1a, Task 2) — a pure state object owned by the module whose
events drive it. **New in this revision:** `RoomStateMachine`'s constructor takes a
`WebSocketTransport` reference from the start (M1b), but only to *observe* its
`connection_state_changed` signal — never to send anything (owner re-review, 2026-07-25, second
pass, item C; see "Automatic rejoin routing" in M1e's own section header for the full resolution).
This observation-only reference is what lets M1e (Task 37) add the *emission* of
`automatic_rejoin_requested` by editing only `protocol/room_state_machine.gd`, with zero change to
how `workspace/` constructs or wires it — the actual send, for both a human join and this signal,
happens in `ui/panels/SpectatorRoomGateway` (Task 28, M1d).

## Ordering rationale

Sub-slices run in the fixed order spec §3.3 states: **M1a → M1b → M1c → M1d → M1e**, each blocked on
the previous one's merge and gate. Within each sub-slice, tasks are ordered: binding-document
amendments first (when a task needs one), then pure, dependency-free state/value objects (fully
gdUnit-testable with no engine I/O), then the class that drives them against real or faked I/O, then
CI/fixture work, then that sub-slice's gate-evidence task.

**TDD-ordering fix (this revision).** The first draft's M1a Task 3 implemented connect/disconnect,
reconnect, backoff, `EXHAUSTED`, and `connection_epoch` all at once, and Task 4 then added tests that
passed immediately with no production change — tests-after-the-fact, not TDD. `WebSocketTransport` is
now built across five small tasks (Tasks 4–8), each introducing exactly one behavior with its own
failing test shown first: connect/disconnect basics; `connection_epoch` on initial connect; the
`CONNECTING` timeout/cancel path; reconnect backoff/`EXHAUSTED`/epoch-on-reopen; heartbeat
configuration. A task that cannot show its own red step before its own implementation is not a valid
task under spec §8, exactly as the F0 plan already states.

## Baseline (recorded before this plan's first task)

```
cd showdownbot_studio/python
python -m pytest -q --collect-only
```

Record the reported count before Task 1 and compare it against this plan's running total at each
sub-slice's gate-evidence task. Do not assume this plan's own arithmetic is correct without checking
it against the actual files landed by each task.

```
./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/"
./showdownbot_studio/godot/tools/check_gdunit_truncation.ps1
```

Record the reported gdUnit total the same way.

---

## Task 1 — Amend `LIVE_STATE_MACHINES.md`: three missing edges (owner-approved 2026-07-25)

**Files:**
- Modify: `showdownbot_studio/docs/architecture/LIVE_STATE_MACHINES.md`
- Modify: `showdownbot_studio/tests/python/test_f0_binding_docs.py`

This document is a binding F0 deliverable; amending it after F0 has merged is exactly the kind of
change that needs an explicit, recorded approval rather than a silent edit — the reviewer supplied
that approval directly, across two review passes, for exactly these three edges, because Tasks
2/6, 11/28/37, and 29 below need them and the current table has none of them:

1. **`ConnectionState`: `CONNECTING` needs an exit other than success/initial-failure.** The current
   11-row table has no way to leave `CONNECTING` for a user-initiated cancel or an automatic connect
   timeout — a peer could otherwise sit in `CONNECTING` forever if the server never completes the
   handshake and never actively refuses it.
2. **`RoomState`: `JOINING` needs an exit for a *local* send failure**, distinct from the existing
   "unknown or private room ID rejected by **server**" row — a `/join` that never reaches the server
   at all (e.g. the connection dropped between pressing "Watch" and the command being sent) must not
   leave `RoomState` stuck in `JOINING`.
3. **`RoomState`: `LEAVING` needs an exit for a *local* leave-send failure** (added at the 2026-07-25
   second review pass) — symmetric with edge 2: a `/leave` that never reaches the server must not
   leave `RoomState` stuck in `LEAVING` forever. It returns to `ACTIVE` (the room the user was still
   in when the send failed), not to `NOT_JOINED` — the leave simply didn't happen. `leave()` stays in
   scope rather than being removed: it is already small, already built (`SpectatorRoomGateway`,
   `ui/panels/`), and completing its failure-edge coverage costs one table row and one method, cheaper
   than special-casing an already-implemented path back out of scope.

- [ ] Edit `showdownbot_studio/docs/architecture/LIVE_STATE_MACHINES.md`. In the `## ConnectionState
  transitions` table, add one row directly after the existing `CONNECTING --initial connection
  attempt fails, retries remain--> RECONNECTING` row:

  ```markdown
  | `CONNECTING` | user cancels the connection attempt, or a connect timeout elapses (owner-approved via 2026-07-25 M1-plan review) | `DISCONNECTED` | "Disconnected" status shown; the pending socket is discarded |
  ```

  In the `## RoomState transitions` table, add one row directly after the existing `JOINING --
  unknown or private room ID rejected by server--> NOT_JOINED` row:

  ```markdown
  | `JOINING` | local send failure -- the join command could not be sent (e.g. connection lost before it was sent) (owner-approved via 2026-07-25 M1-plan review) | `NOT_JOINED` | clear error shown; no fallback room (section 6.1) |
  ```

  And one more row directly after the existing `ACTIVE --user leaves the room / sends /leave-->
  LEAVING` row:

  ```markdown
  | `LEAVING` | local send failure -- the leave command could not be sent (owner-approved via 2026-07-25 M1-plan review, second pass) | `ACTIVE` | clear error shown; the room is still joined, the leave did not happen |
  ```

  Neither new edge creates a new *invalid* pair worth calling out beyond what the existing
  `## Invalid transitions (explicitly rejected)` section already lists, so no change is needed there.

- [ ] Update the row-count guard. Edit `showdownbot_studio/tests/python/test_f0_binding_docs.py`,
  changing:

  ```python
      assert _table_row_count(
          text, "## ConnectionState transitions", "## SessionState transitions"
      ) == 11
      assert _table_row_count(
          text, "## SessionState transitions", "## RoomState transitions"
      ) == 6
      assert _table_row_count(
          text, "## RoomState transitions", "## ChoiceRequestState transitions"
      ) == 9
  ```

  to:

  ```python
      assert _table_row_count(
          text, "## ConnectionState transitions", "## SessionState transitions"
      ) == 12
      assert _table_row_count(
          text, "## SessionState transitions", "## RoomState transitions"
      ) == 6
      assert _table_row_count(
          text, "## RoomState transitions", "## ChoiceRequestState transitions"
      ) == 11
  ```

- [ ] Run and confirm the doc-structure test still passes with the new counts:

  ```
  cd showdownbot_studio/python
  python -m pytest -q -k test_live_state_machines_doc_has_full_transition_tables
  ```

  Expected: `1 passed`.

- [ ] Run the full Python suite to confirm nothing else regressed:

  ```
  python -m pytest -q
  ```

- [ ] Commit:

  ```
  git add showdownbot_studio/docs/architecture/LIVE_STATE_MACHINES.md showdownbot_studio/tests/python/test_f0_binding_docs.py
  git commit -m "docs(studio): add ConnectionState cancel/timeout and RoomState send-failure edges (owner-approved 2026-07-25)"
  ```

---

# M1a — WebSocket transport and connection state

Blocked on Task 1 (this plan) and F0 (merged). New production code lands only in `godot/src/net/`
(spec §4.4). No protocol decoding, no room concept, no battle state.

**Design note carried into every M1a task:** Godot's built-in `WebSocketPeer` is a native engine
class; a GDScript file cannot subclass it and override its native methods to fake their behavior for
a unit test. Testing `WebSocketTransport`'s logic without a live socket requires a seam:
`SocketPeerPort` (Task 3) is a plain GDScript `RefCounted` base class mirroring the exact subset of
`WebSocketPeer`'s API `WebSocketTransport` calls; production code gets a real socket through
`GodotSocketPeerAdapter` (Task 3), and tests inject a `FakeSocketPeerPort` test double (Task 4) that
GDScript scripts *can* override, because it is script-defined, not native.

**Heartbeat design fix (this revision).** The first draft used a 40-second "no inbound frames"
idle timer as its only liveness check — wrong, because a quiet battle (no events for a while) is a
completely legitimate state, not a dead connection; that design would have force-reconnected a
perfectly healthy spectate session. Godot 4.5's `WebSocketPeer` exposes a `heartbeat_interval`
property; the engine's own documentation for it guarantees only that a ping control frame is sent
automatically at that interval. **It does not document that a missing pong closes the connection to
`STATE_CLOSED` within any defined window** — that would be a stronger claim than the engine's own
docs make, and this plan does not repeat it. M1a configures `heartbeat_interval` through the
`SocketPeerPort` seam (Task 3) because sending a periodic ping is still real, documented, useful
behavior (a well-behaved peer or intermediary is more likely to notice and close a genuinely dead
link when pings go unanswered than when the connection sits silent) — but this plan's actual
liveness *proof* is Tasks 7/36's reconnect tests observing `get_ready_state()` return `CLOSED` via
the normal poll loop, not a specific claim about when or whether the ping mechanism itself causes
that closure. The removed idle-timeout heuristic is not silently repurposed — it is recorded below
as a **deferred, deliberately conservative stale-connection heuristic candidate**, a post-M1 owner
decision, in case the engine's own ping/pong ever proves insufficient in practice.

## Task 2 — `net/README.md` + `ConnectionStateMachine`

**Files:**
- Create: `showdownbot_studio/godot/src/net/README.md`
- Create: `showdownbot_studio/godot/src/net/connection_state_machine.gd`
- Create: `showdownbot_studio/godot/tests/net/test_connection_state_machine.gd`

Implements the full 12-row `ConnectionState` table from Task 1 (11 original rows + the new
`CONNECTING`→`DISCONNECTED` cancel/timeout edge). One method per named trigger; a call from a
disallowed source state returns `false` and emits nothing.

- [ ] Write the failing test. Create `showdownbot_studio/godot/tests/net/test_connection_state_machine.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func test_initial_state_is_disconnected() -> void:
  	var m := ConnectionStateMachine.new()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


  func test_request_connect_from_disconnected_moves_to_connecting() -> void:
  	var m := ConnectionStateMachine.new()
  	assert_bool(m.request_connect()).is_true()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.CONNECTING)


  func test_handshake_succeeded_from_connecting_moves_to_connected() -> void:
  	var m := ConnectionStateMachine.new()
  	m.request_connect()
  	assert_bool(m.handshake_succeeded()).is_true()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)


  func test_initial_attempt_failed_retries_remain_from_connecting_moves_to_reconnecting() -> void:
  	var m := ConnectionStateMachine.new()
  	m.request_connect()
  	assert_bool(m.initial_attempt_failed_retries_remain()).is_true()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)


  func test_cancel_connect_from_connecting_moves_to_disconnected() -> void:
  	var m := ConnectionStateMachine.new()
  	m.request_connect()
  	assert_bool(m.cancel_connect()).is_true()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


  func test_connection_lost_retries_remain_from_connected_moves_to_reconnecting() -> void:
  	var m := ConnectionStateMachine.new()
  	m.request_connect()
  	m.handshake_succeeded()
  	assert_bool(m.connection_lost_retries_remain()).is_true()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)


  func test_request_disconnect_from_connected_moves_to_disconnected() -> void:
  	var m := ConnectionStateMachine.new()
  	m.request_connect()
  	m.handshake_succeeded()
  	assert_bool(m.request_disconnect()).is_true()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


  func test_reconnect_succeeded_from_reconnecting_moves_to_connected() -> void:
  	var m := ConnectionStateMachine.new()
  	m.request_connect()
  	m.initial_attempt_failed_retries_remain()  # CONNECTING -> RECONNECTING (only valid path here)
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)
  	assert_bool(m.reconnect_succeeded()).is_true()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)


  func test_reconnect_failed_retries_remain_is_a_self_transition_and_still_emits() -> void:
  	var m := ConnectionStateMachine.new()
  	m.request_connect()
  	m.initial_attempt_failed_retries_remain()
  	var emitted := []
  	m.state_changed.connect(func(old_state, new_state): emitted.append([old_state, new_state]))
  	assert_bool(m.reconnect_failed_retries_remain()).is_true()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)
  	assert_int(emitted.size()).is_equal(1)
  	assert_int(emitted[0][1]).is_equal(ConnectionStateMachine.State.RECONNECTING)


  func test_backoff_exhausted_from_reconnecting_moves_to_exhausted() -> void:
  	var m := ConnectionStateMachine.new()
  	m.request_connect()
  	m.initial_attempt_failed_retries_remain()
  	assert_bool(m.backoff_exhausted()).is_true()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.EXHAUSTED)


  func test_request_disconnect_from_reconnecting_moves_to_disconnected() -> void:
  	var m := ConnectionStateMachine.new()
  	m.request_connect()
  	m.initial_attempt_failed_retries_remain()
  	assert_bool(m.request_disconnect()).is_true()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


  func test_request_connect_from_exhausted_moves_to_connecting() -> void:
  	var m := ConnectionStateMachine.new()
  	m.request_connect()
  	m.initial_attempt_failed_retries_remain()
  	m.backoff_exhausted()
  	assert_bool(m.request_connect()).is_true()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.CONNECTING)


  func test_request_disconnect_from_exhausted_moves_to_disconnected() -> void:
  	var m := ConnectionStateMachine.new()
  	m.request_connect()
  	m.initial_attempt_failed_retries_remain()
  	m.backoff_exhausted()
  	assert_bool(m.request_disconnect()).is_true()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


  # -- Invalid transitions --


  func test_handshake_succeeded_from_disconnected_is_rejected() -> void:
  	var m := ConnectionStateMachine.new()
  	assert_bool(m.handshake_succeeded()).is_false()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


  func test_reconnect_succeeded_from_disconnected_is_rejected() -> void:
  	var m := ConnectionStateMachine.new()
  	assert_bool(m.reconnect_succeeded()).is_false()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


  func test_request_connect_from_connecting_is_rejected_not_queued() -> void:
  	var m := ConnectionStateMachine.new()
  	m.request_connect()
  	assert_bool(m.request_connect()).is_false()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.CONNECTING)


  func test_request_disconnect_from_connecting_is_rejected() -> void:
  	# request_disconnect() is valid only from CONNECTED/RECONNECTING/EXHAUSTED; CONNECTING's own
  	# exit is cancel_connect(), a distinct method (see test above).
  	var m := ConnectionStateMachine.new()
  	m.request_connect()
  	assert_bool(m.request_disconnect()).is_false()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.CONNECTING)


  func test_cancel_connect_from_connected_is_rejected() -> void:
  	var m := ConnectionStateMachine.new()
  	m.request_connect()
  	m.handshake_succeeded()
  	assert_bool(m.cancel_connect()).is_false()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)


  func test_backoff_exhausted_from_connected_is_rejected() -> void:
  	var m := ConnectionStateMachine.new()
  	m.request_connect()
  	m.handshake_succeeded()
  	assert_bool(m.backoff_exhausted()).is_false()
  	assert_int(m.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)
  ```

- [ ] Run and confirm it fails (`ConnectionStateMachine` does not exist yet):

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/net/test_connection_state_machine.gd"
  ```

- [ ] Write the implementation. Create `showdownbot_studio/godot/src/net/connection_state_machine.gd`:

  ```gdscript
  class_name ConnectionStateMachine
  extends RefCounted

  ## Pure, dependency-free implementation of the ConnectionState transition table
  ## (docs/architecture/LIVE_STATE_MACHINES.md, 12 rows including the CONNECTING -> DISCONNECTED
  ## cancel/timeout edge added by this plan's Task 1, owner-approved 2026-07-25). One public
  ## method per named trigger; a call from a disallowed source state returns false and emits
  ## nothing.

  enum State { DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING, EXHAUSTED }

  signal state_changed(old_state: State, new_state: State)

  var _state: State = State.DISCONNECTED


  func get_state() -> State:
  	return _state


  ## DISCONNECTED --user/app connect--> CONNECTING; EXHAUSTED --user manually retries--> CONNECTING.
  func request_connect() -> bool:
  	if _state != State.DISCONNECTED and _state != State.EXHAUSTED:
  		return false
  	_transition(State.CONNECTING)
  	return true


  ## CONNECTING --WebSocket handshake succeeds--> CONNECTED.
  func handshake_succeeded() -> bool:
  	if _state != State.CONNECTING:
  		return false
  	_transition(State.CONNECTED)
  	return true


  ## CONNECTING --initial connection attempt fails, retries remain--> RECONNECTING.
  func initial_attempt_failed_retries_remain() -> bool:
  	if _state != State.CONNECTING:
  		return false
  	_transition(State.RECONNECTING)
  	return true


  ## CONNECTING --user cancels, or a connect timeout elapses--> DISCONNECTED (Task 1's added edge).
  func cancel_connect() -> bool:
  	if _state != State.CONNECTING:
  		return false
  	_transition(State.DISCONNECTED)
  	return true


  ## CONNECTED --socket closes unexpectedly--> RECONNECTING (the engine's own ping/pong, Task 5,
  ## is what surfaces "unexpectedly" as a closed ready-state; this class has no timer of its own).
  func connection_lost_retries_remain() -> bool:
  	if _state != State.CONNECTED:
  		return false
  	_transition(State.RECONNECTING)
  	return true


  ## CONNECTED / RECONNECTING / EXHAUSTED --user explicit disconnect--> DISCONNECTED.
  func request_disconnect() -> bool:
  	if _state != State.CONNECTED and _state != State.RECONNECTING and _state != State.EXHAUSTED:
  		return false
  	_transition(State.DISCONNECTED)
  	return true


  ## RECONNECTING --a reconnect attempt succeeds--> CONNECTED.
  func reconnect_succeeded() -> bool:
  	if _state != State.RECONNECTING:
  		return false
  	_transition(State.CONNECTED)
  	return true


  ## RECONNECTING --a reconnect attempt fails, retries remain--> RECONNECTING (self-transition;
  ## still emits so a listening UI can refresh its backoff countdown).
  func reconnect_failed_retries_remain() -> bool:
  	if _state != State.RECONNECTING:
  		return false
  	_transition(State.RECONNECTING)
  	return true


  ## RECONNECTING --backoff attempts exhausted--> EXHAUSTED.
  func backoff_exhausted() -> bool:
  	if _state != State.RECONNECTING:
  		return false
  	_transition(State.EXHAUSTED)
  	return true


  func _transition(new_state: State) -> void:
  	var old_state := _state
  	_state = new_state
  	state_changed.emit(old_state, new_state)


  static func describe(state: State) -> String:
  	match state:
  		State.DISCONNECTED:
  			return "Disconnected"
  		State.CONNECTING:
  			return "Connecting..."
  		State.CONNECTED:
  			return "Connected"
  		State.RECONNECTING:
  			return "Reconnecting..."
  		State.EXHAUSTED:
  			return "Disconnected"
  		_:
  			return "Unknown"
  ```

- [ ] Run again and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/net/test_connection_state_machine.gd"
  ```

  Expected: `18` tests passed, `0` failed.

- [ ] Write `net/README.md`. Create `showdownbot_studio/godot/src/net/README.md`:

  ```markdown
  # Net (`godot/src/net/`)

  ## Purpose

  Owns the WebSocket connection to the Showdown server and its connection-lifetime state. Never
  parses or encodes protocol text, never holds battle state, never holds `CredentialProvider` state.

  ## Public interface

  New (M1a):

  - `ConnectionStateMachine` — pure implementation of the `ConnectionState` transition table
    (`docs/architecture/LIVE_STATE_MACHINES.md`, 12 rows). `signal state_changed(old_state, new_state)`.
  - `SocketPeerPort` / `GodotSocketPeerAdapter` — the seam between `WebSocketTransport` and the real
    socket, including heartbeat configuration (`configure_heartbeat_interval`).
  - `WebSocketTransport` — connects, disconnects, cancels a pending connect, reconnects with
    backoff, configures the engine's own ping/pong heartbeat. `signal connection_state_changed`;
    `signal raw_text_received(text: String)`.

  ## Dependencies

  Depends on nothing outside this module. `protocol/` depends on `net/` directly (receives raw
  text, sends encoded commands); `net/` never depends on `protocol/`.

  ## Rule for future producers

  `net/` never gains knowledge of protocol message shapes, room state, or battle state.
  ```

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/net/README.md showdownbot_studio/godot/src/net/connection_state_machine.gd showdownbot_studio/godot/tests/net/test_connection_state_machine.gd
  git commit -m "feat(studio): add net/ConnectionStateMachine (12-row ConnectionState incl. cancel/timeout)"
  ```

## Task 3 — `SocketPeerPort` seam + `GodotSocketPeerAdapter` (incl. heartbeat configuration)

**Files:**
- Create: `showdownbot_studio/godot/src/net/socket_peer_port.gd`
- Create: `showdownbot_studio/godot/src/net/godot_socket_peer_adapter.gd`
- Create: `showdownbot_studio/godot/tests/net/test_godot_socket_peer_adapter.gd`

- [ ] Write the failing test. Create `showdownbot_studio/godot/tests/net/test_godot_socket_peer_adapter.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func test_fresh_adapter_reports_closed_ready_state() -> void:
  	var adapter := GodotSocketPeerAdapter.new()
  	assert_int(adapter.get_ready_state()).is_equal(SocketPeerPort.ReadyState.CLOSED)


  func test_fresh_adapter_reports_zero_available_packets() -> void:
  	var adapter := GodotSocketPeerAdapter.new()
  	assert_int(adapter.get_available_packet_count()).is_equal(0)


  func test_adapter_is_a_socket_peer_port() -> void:
  	assert_bool(GodotSocketPeerAdapter.new() is SocketPeerPort).is_true()


  func test_configure_heartbeat_interval_does_not_error() -> void:
  	var adapter := GodotSocketPeerAdapter.new()
  	adapter.configure_heartbeat_interval(20.0)  # forwards to the real WebSocketPeer.heartbeat_interval
  ```

- [ ] Run and confirm it fails; then write the implementation. Create
  `showdownbot_studio/godot/src/net/socket_peer_port.gd`:

  ```gdscript
  class_name SocketPeerPort
  extends RefCounted

  ## Thin seam between WebSocketTransport and the actual socket implementation, so
  ## WebSocketTransport's logic is unit-testable without a live socket (a GDScript file cannot
  ## subclass the engine's native WebSocketPeer and override its native methods).
  ## GodotSocketPeerAdapter wraps the real WebSocketPeer for production; gdUnit test doubles
  ## extend this class directly (a plain script class, fully overridable).

  enum ReadyState { CONNECTING, OPEN, CLOSING, CLOSED }


  func connect_to_url(_url: String) -> int:
  	push_error("SocketPeerPort.connect_to_url is abstract")
  	return ERR_UNAVAILABLE


  func poll() -> void:
  	pass


  func get_ready_state() -> ReadyState:
  	return ReadyState.CLOSED


  func get_available_packet_count() -> int:
  	return 0


  func get_packet_string() -> String:
  	return ""


  func send_text(_text: String) -> int:
  	push_error("SocketPeerPort.send_text is abstract")
  	return ERR_UNAVAILABLE


  func close(_code: int, _reason: String) -> void:
  	pass


  ## Configures the engine's periodic WebSocket ping (Godot 4.5's WebSocketPeer.heartbeat_interval).
  ## Godot's own documentation guarantees only that a ping control frame is sent automatically at
  ## this interval -- NOT that a missing pong closes the connection within any defined window; this
  ## plan does not claim more than the engine documents. See this plan's M1a design note for why the
  ## earlier idle-timeout heuristic was wrong (a quiet battle is not a dead one) and for what this
  ## plan actually relies on to prove liveness (Tasks 7/36's reconnect tests).
  func configure_heartbeat_interval(_seconds: float) -> void:
  	pass
  ```

  Create `showdownbot_studio/godot/src/net/godot_socket_peer_adapter.gd`:

  ```gdscript
  class_name GodotSocketPeerAdapter
  extends SocketPeerPort

  var _peer := WebSocketPeer.new()


  func connect_to_url(url: String) -> int:
  	return _peer.connect_to_url(url)


  func poll() -> void:
  	_peer.poll()


  func get_ready_state() -> SocketPeerPort.ReadyState:
  	match _peer.get_ready_state():
  		WebSocketPeer.STATE_CONNECTING:
  			return SocketPeerPort.ReadyState.CONNECTING
  		WebSocketPeer.STATE_OPEN:
  			return SocketPeerPort.ReadyState.OPEN
  		WebSocketPeer.STATE_CLOSING:
  			return SocketPeerPort.ReadyState.CLOSING
  		_:
  			return SocketPeerPort.ReadyState.CLOSED


  func get_available_packet_count() -> int:
  	return _peer.get_available_packet_count()


  func get_packet_string() -> String:
  	return _peer.get_packet().get_string_from_utf8()


  func send_text(text: String) -> int:
  	return _peer.send_text(text)


  func close(code: int, reason: String) -> void:
  	_peer.close(code, reason)


  func configure_heartbeat_interval(seconds: float) -> void:
  	_peer.heartbeat_interval = seconds
  ```

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/net/test_godot_socket_peer_adapter.gd"
  ```

  Expected: `4` tests passed, `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/net/socket_peer_port.gd showdownbot_studio/godot/src/net/godot_socket_peer_adapter.gd showdownbot_studio/godot/tests/net/test_godot_socket_peer_adapter.gd
  git commit -m "feat(studio): add SocketPeerPort seam + heartbeat_interval configuration"
  ```

## Task 4 — `WebSocketTransport`: connect/disconnect basics + raw text passthrough

**Files:**
- Create: `showdownbot_studio/godot/src/net/web_socket_transport.gd`
- Create: `showdownbot_studio/godot/tests/net/fake_socket_peer_port.gd`
- Create: `showdownbot_studio/godot/tests/net/test_web_socket_transport_connect.gd`

Minimal on purpose: connect/disconnect, raw text passthrough, `send_raw_text`. No reconnect, no
backoff, no epoch, no connect-timeout — those are Tasks 5–8, each with its own red step, per this
plan's TDD-ordering fix.

- [ ] Write the shared fake test double. Create `showdownbot_studio/godot/tests/net/fake_socket_peer_port.gd`:

  ```gdscript
  class_name FakeSocketPeerPort
  extends SocketPeerPort

  var connect_result: int = OK
  var ready_state: SocketPeerPort.ReadyState = SocketPeerPort.ReadyState.CONNECTING
  var queued_packets: Array[String] = []
  var sent_texts: Array[String] = []
  var connect_urls: Array[String] = []
  var close_called: bool = false
  var configured_heartbeat_intervals: Array[float] = []


  func connect_to_url(url: String) -> int:
  	connect_urls.append(url)
  	return connect_result


  func poll() -> void:
  	pass


  func get_ready_state() -> SocketPeerPort.ReadyState:
  	return ready_state


  func get_available_packet_count() -> int:
  	return queued_packets.size()


  func get_packet_string() -> String:
  	return queued_packets.pop_front()


  func send_text(text: String) -> int:
  	sent_texts.append(text)
  	return OK


  func close(_code: int, _reason: String) -> void:
  	close_called = true
  	ready_state = SocketPeerPort.ReadyState.CLOSED


  func configure_heartbeat_interval(seconds: float) -> void:
  	configured_heartbeat_intervals.append(seconds)
  ```

- [ ] Write the failing test. Create `showdownbot_studio/godot/tests/net/test_web_socket_transport_connect.gd`:

  ```gdscript
  extends GdUnitTestSuite

  var _fake: FakeSocketPeerPort
  var _transport: WebSocketTransport


  func before_test() -> void:
  	_fake = FakeSocketPeerPort.new()
  	_transport = WebSocketTransport.new(func(): return _fake)
  	add_child(_transport)


  func after_test() -> void:
  	remove_child(_transport)
  	_transport.free()


  func test_initial_state_is_disconnected() -> void:
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


  func test_connect_to_server_moves_to_connecting_and_calls_peer() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTING)
  	assert_int(_fake.connect_urls.size()).is_equal(1)
  	assert_str(_fake.connect_urls[0]).is_equal("ws://localhost:8000/showdown/websocket")


  func test_poll_detects_open_and_moves_to_connected() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(0.016)
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)


  func test_inbound_packets_are_emitted_in_order() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_fake.queued_packets = ["|turn|1", "|turn|2"]
  	var received: Array[String] = []
  	_transport.raw_text_received.connect(func(text: String): received.append(text))
  	_transport._process(0.016)
  	assert_int(received.size()).is_equal(2)
  	assert_str(received[0]).is_equal("|turn|1")
  	assert_str(received[1]).is_equal("|turn|2")


  func test_disconnect_from_connected_calls_peer_close() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(0.016)
  	_transport.disconnect_from_server()
  	assert_bool(_fake.close_called).is_true()
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


  func test_send_raw_text_while_connected_forwards_to_peer() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(0.016)
  	assert_int(_transport.send_raw_text("|/join lobby")).is_equal(OK)
  	assert_int(_fake.sent_texts.size()).is_equal(1)
  	assert_str(_fake.sent_texts[0]).is_equal("|/join lobby")


  func test_send_raw_text_while_disconnected_is_rejected() -> void:
  	assert_int(_transport.send_raw_text("|/join lobby")).is_not_equal(OK)
  	assert_int(_fake.sent_texts.size()).is_equal(0)
  ```

- [ ] Run and confirm it fails (`WebSocketTransport` does not exist yet):

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/net/test_web_socket_transport_connect.gd"
  ```

- [ ] Write the minimal implementation. Create `showdownbot_studio/godot/src/net/web_socket_transport.gd`:

  ```gdscript
  class_name WebSocketTransport
  extends Node

  ## Connects to the Showdown server, tracks ConnectionState, and passes inbound frames through
  ## unmodified for protocol/ (M1b) to decode. This task is deliberately minimal: connect/
  ## disconnect/passthrough only. Tasks 5-8 add connection_epoch, connect-timeout/cancel, reconnect
  ## backoff, and heartbeat configuration, each with its own failing test first.

  signal connection_state_changed(old_state: ConnectionStateMachine.State, new_state: ConnectionStateMachine.State)
  signal raw_text_received(text: String)

  var _peer: SocketPeerPort
  var _state_machine := ConnectionStateMachine.new()
  var _peer_factory: Callable
  var _url: String = ""


  func _init(peer_factory: Callable = Callable()) -> void:
  	_peer_factory = peer_factory if peer_factory.is_valid() else Callable(self, "_make_default_peer")
  	_state_machine.state_changed.connect(_on_state_changed)


  func _make_default_peer() -> SocketPeerPort:
  	return GodotSocketPeerAdapter.new()


  func get_state() -> ConnectionStateMachine.State:
  	return _state_machine.get_state()


  func connect_to_server(url: String) -> void:
  	if not _state_machine.request_connect():
  		return
  	_url = url
  	_open_socket()


  func disconnect_from_server() -> void:
  	if not _state_machine.request_disconnect():
  		return
  	if _peer != null:
  		_peer.close(1000, "client disconnect")
  	_peer = null


  func send_raw_text(text: String) -> int:
  	if _peer == null or _state_machine.get_state() != ConnectionStateMachine.State.CONNECTED:
  		return ERR_UNCONFIGURED
  	return _peer.send_text(text)


  func _open_socket() -> void:
  	_peer = _peer_factory.call()
  	_peer.connect_to_url(_url)


  func _process(_delta: float) -> void:
  	if _peer == null:
  		return
  	_peer.poll()
  	var ready := _peer.get_ready_state()
  	if ready == SocketPeerPort.ReadyState.OPEN:
  		_on_peer_open()


  func _on_peer_open() -> void:
  	if _state_machine.get_state() == ConnectionStateMachine.State.CONNECTING:
  		_state_machine.handshake_succeeded()
  	while _peer.get_available_packet_count() > 0:
  		raw_text_received.emit(_peer.get_packet_string())


  func _on_state_changed(old_state: ConnectionStateMachine.State, new_state: ConnectionStateMachine.State) -> void:
  	connection_state_changed.emit(old_state, new_state)
  ```

- [ ] Run again and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/net/test_web_socket_transport_connect.gd"
  ```

  Expected: `7` tests passed, `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/net/web_socket_transport.gd showdownbot_studio/godot/tests/net/fake_socket_peer_port.gd showdownbot_studio/godot/tests/net/test_web_socket_transport_connect.gd
  git commit -m "feat(studio): add minimal WebSocketTransport (connect/disconnect/passthrough only)"
  ```

## Task 5 — `WebSocketTransport`: `connection_epoch` on initial connect

**Files:**
- Modify: `showdownbot_studio/godot/src/net/web_socket_transport.gd`
- Create: `showdownbot_studio/godot/tests/net/test_web_socket_transport_epoch.gd`

- [ ] Write the failing test. Create `showdownbot_studio/godot/tests/net/test_web_socket_transport_epoch.gd`:

  ```gdscript
  extends GdUnitTestSuite

  var _fake: FakeSocketPeerPort
  var _transport: WebSocketTransport


  func before_test() -> void:
  	_fake = FakeSocketPeerPort.new()
  	_transport = WebSocketTransport.new(func(): return _fake)
  	add_child(_transport)


  func after_test() -> void:
  	remove_child(_transport)
  	_transport.free()


  func test_epoch_starts_at_zero() -> void:
  	assert_int(_transport.get_connection_epoch()).is_equal(0)


  func test_epoch_increments_to_one_on_first_connect() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	assert_int(_transport.get_connection_epoch()).is_equal(1)


  func test_epoch_does_not_change_while_staying_connected() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(0.016)
  	var epoch_before := _transport.get_connection_epoch()
  	_fake.queued_packets = ["|turn|1"]
  	_transport._process(0.016)
  	assert_int(_transport.get_connection_epoch()).is_equal(epoch_before)
  ```

- [ ] Run and confirm it fails (`get_connection_epoch` does not exist yet); then extend the
  implementation. Edit `showdownbot_studio/godot/src/net/web_socket_transport.gd`, adding a field
  and a getter, and incrementing it in `connect_to_server`:

  ```gdscript
  var _connection_epoch: int = 0
  ```

  ```gdscript
  ## Incremented on every connect_to_server() and every successful reconnect (Task 7). Spec
  ## section 6.2/section 7 binds every outbound battle action to this counter; M1 sends no
  ## /choose, so nothing besides this class's own tests reads it yet, but net/ is the only module
  ## that can correctly own it.
  func get_connection_epoch() -> int:
  	return _connection_epoch
  ```

  ```gdscript
  func connect_to_server(url: String) -> void:
  	if not _state_machine.request_connect():
  		return
  	_url = url
  	_connection_epoch += 1
  	_open_socket()
  ```

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/net/test_web_socket_transport_epoch.gd"
  ```

  Expected: `3` tests passed, `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/net/web_socket_transport.gd showdownbot_studio/godot/tests/net/test_web_socket_transport_epoch.gd
  git commit -m "feat(studio): add connection_epoch, incremented on initial connect"
  ```

## Task 6 — `WebSocketTransport`: `CONNECTING` timeout + explicit cancel

**Files:**
- Modify: `showdownbot_studio/godot/src/net/web_socket_transport.gd`
- Create: `showdownbot_studio/godot/tests/net/test_web_socket_transport_connect_timeout.gd`

Uses Task 1's new `ConnectionStateMachine.cancel_connect()` edge for both the explicit user-cancel
path and the automatic connect-timeout path — the same underlying transition, two different
triggers, exactly as `LIVE_STATE_MACHINES.md`'s new row states.

- [ ] Write the failing test. Create
  `showdownbot_studio/godot/tests/net/test_web_socket_transport_connect_timeout.gd`:

  ```gdscript
  extends GdUnitTestSuite

  var _fake: FakeSocketPeerPort
  var _transport: WebSocketTransport


  func before_test() -> void:
  	_fake = FakeSocketPeerPort.new()
  	_transport = WebSocketTransport.new(func(): return _fake)
  	add_child(_transport)


  func after_test() -> void:
  	remove_child(_transport)
  	_transport.free()


  func test_cancel_connect_attempt_while_connecting_moves_to_disconnected_and_closes_peer() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_transport.cancel_connect_attempt()
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)
  	assert_bool(_fake.close_called).is_true()


  func test_cancel_connect_attempt_while_not_connecting_is_a_no_op() -> void:
  	_transport.cancel_connect_attempt()
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


  func test_connect_timeout_elapsing_moves_to_disconnected() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.CONNECTING  # handshake never completes
  	_transport._process(WebSocketTransport.CONNECT_TIMEOUT_S + 0.1)
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.DISCONNECTED)


  func test_handshake_succeeding_just_before_timeout_does_not_cancel() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(WebSocketTransport.CONNECT_TIMEOUT_S - 1.0)
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)
  ```

- [ ] Run and confirm it fails; then extend the implementation. Edit
  `showdownbot_studio/godot/src/net/web_socket_transport.gd`:

  ```gdscript
  const CONNECT_TIMEOUT_S := 15.0

  var _connecting_elapsed_s: float = 0.0
  ```

  ```gdscript
  ## Explicit user-initiated cancel of a pending connection attempt (LIVE_STATE_MACHINES.md's
  ## CONNECTING -> DISCONNECTED edge, Task 1). A no-op outside CONNECTING.
  func cancel_connect_attempt() -> void:
  	if not _state_machine.cancel_connect():
  		return
  	if _peer != null:
  		_peer.close(1000, "connect attempt cancelled")
  	_peer = null
  ```

  Update `connect_to_server` and `_process`:

  ```gdscript
  func connect_to_server(url: String) -> void:
  	if not _state_machine.request_connect():
  		return
  	_url = url
  	_connection_epoch += 1
  	_connecting_elapsed_s = 0.0
  	_open_socket()
  ```

  ```gdscript
  func _process(delta: float) -> void:
  	if _state_machine.get_state() == ConnectionStateMachine.State.CONNECTING:
  		_connecting_elapsed_s += delta
  		if _connecting_elapsed_s >= CONNECT_TIMEOUT_S and _peer.get_ready_state() != SocketPeerPort.ReadyState.OPEN:
  			cancel_connect_attempt()
  			return
  	if _peer == null:
  		return
  	_peer.poll()
  	var ready := _peer.get_ready_state()
  	if ready == SocketPeerPort.ReadyState.OPEN:
  		_on_peer_open()
  ```

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/net/test_web_socket_transport_connect_timeout.gd"
  ```

  Expected: `4` tests passed, `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/net/web_socket_transport.gd showdownbot_studio/godot/tests/net/test_web_socket_transport_connect_timeout.gd
  git commit -m "feat(studio): add CONNECTING timeout + explicit cancel_connect_attempt()"
  ```

## Task 7 — `WebSocketTransport`: reconnect backoff + `EXHAUSTED` + epoch-on-reopen

**Files:**
- Modify: `showdownbot_studio/godot/src/net/web_socket_transport.gd`
- Create: `showdownbot_studio/godot/tests/net/test_web_socket_transport_reconnect.gd`

**Integration bug fixed in this revision (owner re-review, 2026-07-25, second pass).** The version of
`_process()` originally drafted for this task has a real defect: once the backoff timer elapses, it
calls `_open_socket()` and `return`s **without marking that an attempt is now in flight**. On the
*next* frame, `_state_machine.get_state()` is still `RECONNECTING` (nothing transitioned it), so the
same branch fires again — `_reconnect_timer_s` is now some large negative number, so the `<= 0.0`
check is still true, and `_open_socket()` runs **again**, discarding the previous peer and creating a
brand-new one, every single frame, forever. The peer that was actually opening (or had already
opened) is thrown away before its `ready_state` is ever polled, so `RECONNECTING` → `CONNECTED` can
never be reached by a real socket, and Task 37/38's rejoin logic (which fires only on that
transition) could never run in practice. Fixed here with an explicit `_reconnect_attempt_in_flight`
flag: the backoff branch only calls `_open_socket()` once per attempt, then falls through to the
normal poll loop on every subsequent frame until that attempt resolves (open or closed) or a new one
is scheduled.

- [ ] Write the failing tests — four in total, each isolating one part of the bug above. Create
  `showdownbot_studio/godot/tests/net/test_web_socket_transport_reconnect.gd`:

  ```gdscript
  extends GdUnitTestSuite

  var _fake: FakeSocketPeerPort
  var _transport: WebSocketTransport


  func before_test() -> void:
  	_fake = FakeSocketPeerPort.new()
  	_transport = WebSocketTransport.new(func(): return _fake)
  	add_child(_transport)


  func after_test() -> void:
  	remove_child(_transport)
  	_transport.free()


  func test_unexpected_close_while_connected_moves_to_reconnecting() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(0.016)
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)
  	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
  	_transport._process(0.016)
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)


  func test_reconnect_reopens_socket_after_backoff_elapses() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
  	_transport._process(0.016)  # CONNECTING -> RECONNECTING (initial attempt failed)
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)
  	var urls_before := _fake.connect_urls.size()
  	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)
  	assert_int(_fake.connect_urls.size()).is_equal(urls_before + 1)


  func test_repeated_failures_exhaust_backoff_schedule() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.connect_result = ERR_CANT_CONNECT
  	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
  	_transport._process(0.016)  # attempt 1 fails -> RECONNECTING
  	for backoff_s in WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S:
  		assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)
  		_transport._process(backoff_s + 0.1)
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.EXHAUSTED)


  func test_manual_retry_from_exhausted_moves_to_connecting() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.connect_result = ERR_CANT_CONNECT
  	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
  	_transport._process(0.016)
  	for backoff_s in WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S:
  		_transport._process(backoff_s + 0.1)
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.EXHAUSTED)
  	_fake.connect_result = OK
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTING)


  func test_epoch_increments_exactly_once_per_reconnect_reopen() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	var epoch_after_initial := _transport.get_connection_epoch()
  	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
  	_transport._process(0.016)  # -> RECONNECTING
  	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # reopens
  	assert_int(_transport.get_connection_epoch()).is_equal(epoch_after_initial + 1)


  # -- Reconnect attempt-in-flight coverage (owner re-review, 2026-07-25, second pass) --


  func test_backoff_elapsed_opens_exactly_one_new_peer() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
  	_transport._process(0.016)  # -> RECONNECTING
  	var urls_before := _fake.connect_urls.size()
  	_fake.ready_state = SocketPeerPort.ReadyState.CONNECTING  # the new peer hasn't opened yet
  	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)
  	assert_int(_fake.connect_urls.size()).is_equal(urls_before + 1)


  func test_peer_still_connecting_on_subsequent_frames_opens_no_second_peer() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
  	_transport._process(0.016)  # -> RECONNECTING
  	_fake.ready_state = SocketPeerPort.ReadyState.CONNECTING
  	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # attempt opens
  	var urls_after_first_attempt := _fake.connect_urls.size()
  	# Several more frames pass with the SAME attempt still connecting -- without the
  	# attempt-in-flight guard, each of these would discard the peer and open a new one.
  	_transport._process(0.016)
  	_transport._process(0.016)
  	_transport._process(0.016)
  	assert_int(_fake.connect_urls.size()).is_equal(urls_after_first_attempt)
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)


  func test_peer_opening_after_backoff_reaches_connected() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
  	_transport._process(0.016)  # -> RECONNECTING
  	_fake.ready_state = SocketPeerPort.ReadyState.CONNECTING
  	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # attempt opens
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)
  	# The attempt's peer now finishes opening, observed on a later frame.
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(0.016)
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)


  func test_immediate_connect_failure_schedules_the_next_backoff_without_a_busy_loop() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
  	_transport._process(0.016)  # attempt 1 fails synchronously -> RECONNECTING, backoff[0] scheduled
  	_fake.connect_result = ERR_CANT_CONNECT  # attempt 2's connect_to_url will fail synchronously too
  	var urls_before := _fake.connect_urls.size()
  	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # attempt 2 fires and fails
  	assert_int(_fake.connect_urls.size()).is_equal(urls_before + 1)  # exactly one new attempt, not a loop
  	assert_int(_transport.get_state()).is_equal(ConnectionStateMachine.State.RECONNECTING)
  	# Processing less than backoff[1] must NOT trigger another attempt (no busy loop): the failed
  	# synchronous attempt must have scheduled backoff[1], not left the timer at <= 0.
  	var urls_after_attempt_2 := _fake.connect_urls.size()
  	_transport._process(0.1)
  	assert_int(_fake.connect_urls.size()).is_equal(urls_after_attempt_2)
  ```

- [ ] Run and confirm the four new tests fail against the naive implementation shown above this
  task's own draft (no attempt-in-flight guard): `test_peer_still_connecting_on_subsequent_frames_opens_no_second_peer`
  fails because every frame opens a fresh peer; `test_peer_opening_after_backoff_reaches_connected`
  fails because the peer that was about to report `OPEN` is discarded before that frame's poll ever
  observes it, so `RECONNECTING` never becomes `CONNECTED`. Then write the corrected implementation.
  Edit `showdownbot_studio/godot/src/net/web_socket_transport.gd`:

  ```gdscript
  const RECONNECT_BACKOFF_SCHEDULE_S: Array[float] = [1.0, 2.0, 5.0, 10.0, 20.0]

  var _reconnect_attempt: int = 0
  var _reconnect_timer_s: float = 0.0
  ## True from the moment a reconnect attempt's _open_socket() call returns until that attempt
  ## resolves (peer opens or closes) or a new attempt is scheduled. Without this flag, the
  ## RECONNECTING branch of _process() re-fires every frame once the backoff timer is <= 0.0,
  ## discarding the in-flight peer and opening a brand-new one forever -- the bug this task fixes.
  var _reconnect_attempt_in_flight: bool = false
  ```

  ```gdscript
  func _advance_after_failed_attempt() -> void:
  	_reconnect_attempt_in_flight = false
  	if _state_machine.get_state() == ConnectionStateMachine.State.CONNECTING:
  		_state_machine.initial_attempt_failed_retries_remain()
  	else:
  		_state_machine.reconnect_failed_retries_remain()
  	_schedule_next_attempt()


  func _schedule_next_attempt() -> void:
  	if _reconnect_attempt >= RECONNECT_BACKOFF_SCHEDULE_S.size():
  		_state_machine.backoff_exhausted()
  		return
  	_reconnect_timer_s = RECONNECT_BACKOFF_SCHEDULE_S[_reconnect_attempt]
  	_reconnect_attempt += 1
  ```

  Replace `_process` and `_on_peer_open`:

  ```gdscript
  func _process(delta: float) -> void:
  	if _state_machine.get_state() == ConnectionStateMachine.State.RECONNECTING:
  		if not _reconnect_attempt_in_flight:
  			_reconnect_timer_s -= delta
  			if _reconnect_timer_s <= 0.0:
  				_reconnect_attempt_in_flight = true
  				_connection_epoch += 1
  				_open_socket()
  			return
  		# An attempt is already in flight for this backoff period: fall through to poll it,
  		# exactly like the CONNECTING branch below -- never open a second peer for it.
  	elif _state_machine.get_state() == ConnectionStateMachine.State.CONNECTING:
  		_connecting_elapsed_s += delta
  		if _connecting_elapsed_s >= CONNECT_TIMEOUT_S and _peer.get_ready_state() != SocketPeerPort.ReadyState.OPEN:
  			cancel_connect_attempt()
  			return
  	if _peer == null:
  		return
  	_peer.poll()
  	var ready := _peer.get_ready_state()
  	if ready == SocketPeerPort.ReadyState.OPEN:
  		_reconnect_attempt_in_flight = false
  		_on_peer_open()
  	elif ready == SocketPeerPort.ReadyState.CLOSED:
  		_reconnect_attempt_in_flight = false
  		_on_peer_closed()


  func _on_peer_open() -> void:
  	if _state_machine.get_state() == ConnectionStateMachine.State.CONNECTING:
  		_state_machine.handshake_succeeded()
  		_reconnect_attempt = 0
  	elif _state_machine.get_state() == ConnectionStateMachine.State.RECONNECTING:
  		_state_machine.reconnect_succeeded()
  		_reconnect_attempt = 0
  	while _peer.get_available_packet_count() > 0:
  		raw_text_received.emit(_peer.get_packet_string())


  func _on_peer_closed() -> void:
  	if _state_machine.get_state() == ConnectionStateMachine.State.CONNECTED:
  		_state_machine.connection_lost_retries_remain()
  		_schedule_next_attempt()
  	elif _state_machine.get_state() == ConnectionStateMachine.State.CONNECTING:
  		_advance_after_failed_attempt()
  	elif _state_machine.get_state() == ConnectionStateMachine.State.RECONNECTING:
  		_advance_after_failed_attempt()
  ```

  Update `_open_socket` to route a failed `connect_to_url` through the same failure path:

  ```gdscript
  func _open_socket() -> void:
  	_peer = _peer_factory.call()
  	var err: int = _peer.connect_to_url(_url)
  	if err != OK:
  		_advance_after_failed_attempt()
  ```

  (Task 8 later adds a `configure_heartbeat_interval()` call to this same method — not part of this
  task's own scope.)

- [ ] Run and confirm all nine tests pass:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/net/test_web_socket_transport_reconnect.gd"
  ```

  Expected: `9` tests passed, `0` failed. Re-run Tasks 4–6's suites too to confirm no regression:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/net/"
  ```

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/net/web_socket_transport.gd showdownbot_studio/godot/tests/net/test_web_socket_transport_reconnect.gd
  git commit -m "feat(studio): add WebSocketTransport reconnect backoff, EXHAUSTED, epoch-on-reopen"
  ```

## Task 8 — `WebSocketTransport`: heartbeat configuration on connect

**Files:**
- Modify: `showdownbot_studio/godot/src/net/web_socket_transport.gd`
- Create: `showdownbot_studio/godot/tests/net/test_web_socket_transport_heartbeat.gd`

- [ ] Write the failing test. Create `showdownbot_studio/godot/tests/net/test_web_socket_transport_heartbeat.gd`:

  ```gdscript
  extends GdUnitTestSuite

  var _fake: FakeSocketPeerPort
  var _transport: WebSocketTransport


  func before_test() -> void:
  	_fake = FakeSocketPeerPort.new()
  	_transport = WebSocketTransport.new(func(): return _fake)
  	add_child(_transport)


  func after_test() -> void:
  	remove_child(_transport)
  	_transport.free()


  func test_heartbeat_interval_is_configured_on_every_new_peer() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	assert_int(_fake.configured_heartbeat_intervals.size()).is_equal(1)
  	assert_float(_fake.configured_heartbeat_intervals[0]).is_equal(WebSocketTransport.HEARTBEAT_INTERVAL_S)


  func test_heartbeat_interval_is_reconfigured_on_reconnect_reopen() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
  	_transport._process(0.016)  # -> RECONNECTING
  	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # reopens
  	assert_int(_fake.configured_heartbeat_intervals.size()).is_equal(2)
  ```

- [ ] Run and confirm it fails; then extend the implementation. Edit
  `showdownbot_studio/godot/src/net/web_socket_transport.gd`:

  ```gdscript
  const HEARTBEAT_INTERVAL_S := 20.0
  ```

  ```gdscript
  func _open_socket() -> void:
  	_peer = _peer_factory.call()
  	_peer.configure_heartbeat_interval(HEARTBEAT_INTERVAL_S)
  	var err: int = _peer.connect_to_url(_url)
  	if err != OK:
  		_advance_after_failed_attempt()
  ```

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/net/test_web_socket_transport_heartbeat.gd"
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/net/"
  ```

  Expected: `2` new tests passed; the full `net/` suite `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/net/web_socket_transport.gd showdownbot_studio/godot/tests/net/test_web_socket_transport_heartbeat.gd
  git commit -m "feat(studio): configure the engine's WebSocket heartbeat_interval on every new peer"
  ```

## Task 9 — M1a gate evidence

**Files:** none (verification only).

- [ ] Full Python suite; full gdUnit suite + truncation check; architecture lane — the same
  commands as every gate-evidence task in this plan.

- [ ] Confirm the deferred idle-timeout note (this plan's M1a design note) is recorded, not silently
  dropped: no production file reintroduces an application-level "no inbound frames" timer.

- [ ] `git status --porcelain` clean; `git diff --check main` clean.

- [ ] Open the M1a PR, citing Task 1's doc amendment and this section as prerequisites. Do not merge
  until reviewed.

---

# M1b — Protocol decoding and typed room events

Blocked on M1a merged and gated. New production code lands only in `godot/src/protocol/`, including
`protocol/dto/` (spec §4.4).

**Bounded decode vocabulary with three-way classification (revised).** The first draft only had two
outcomes for a decoded line: a recognized `ProtocolEventDTO`, or `line_not_understood` (the §6.1
fail-closed "not understood" signal). That conflated two very different situations: a line M1's
bounded vocabulary genuinely cannot classify at all, versus a line that is a perfectly well-known,
valid Showdown protocol message that M1 simply has no state to build from yet (`player`, `teamsize`,
`gametype`, `gen`, `tier`, `rule`, `clearpoke`, `poke`, `teampreview`, `start`, `rated`, `j`/`join`,
`l`/`leave`, `c`/`c:`/`chat`, `t:`). Emitting `line_not_understood` for those would misrepresent a
deliberate, documented scope boundary as parser confusion. `ProtocolDecoder` now classifies every
line into exactly one of three outcomes:

- **`DECODED_STATE_EVENT`** — `init`, `title`, `error`, `deinit`, `turn`, `switch`, `drag`,
  `-damage`, `-heal`, `-status`, `-curestatus`, `faint`, `-weather`, `-fieldstart`, `-fieldend`,
  `-sidestart`, `-sideend`, `move`, `win`, `tie` — emitted as a `ProtocolEventDTO` via
  `event_decoded`.
- **`KNOWN_IGNORED_EVENT`** — the list above, emitted via `known_ignored_event(raw_line,
  message_type)` for diagnostic visibility only; never affects battle state; never a fail-closed
  warning. Each is a candidate for later, deliberate promotion into `DECODED_STATE_EVENT` by a
  future sub-slice, not a silent gap.
- **`UNKNOWN_EVENT`** — anything not in either list above — emitted via `line_not_understood`, the
  real §6.1 "not understood" signal.

`deinit` is new to this revision too: real Showdown room closure is signaled by `|deinit|`, not by
`win`/`tie` (which end the battle but leave the room joinable for a while, e.g. to review the log) —
see M1d's room-isolation fixes for why this distinction matters.

## Task 10 — `protocol/README.md` + `protocol/dto/protocol_event_dto.gd`

**Files:**
- Create: `showdownbot_studio/godot/src/protocol/README.md`
- Create: `showdownbot_studio/godot/src/protocol/dto/protocol_event_dto.gd`
- Modify: `showdownbot_studio/tests/python/architecture_allowlists/named_value_object_allowlist.txt`
- Create: `showdownbot_studio/godot/tests/protocol/test_protocol_event_dto.gd`

Unchanged in shape from the first draft except one addition: `condition_label` is documented as also
carrying `|init|`'s room-type argument (`"battle"` vs `"chat"`, etc.) — reusing the existing generic
label field rather than growing the DTO further, since it already serves the same "one label,
several event families" role for weather/terrain/field/side conditions.

- [ ] Write the failing test. Create `showdownbot_studio/godot/tests/protocol/test_protocol_event_dto.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func test_defaults_are_null_or_empty() -> void:
  	var e := ProtocolEventDTO.new()
  	assert_int(e.protocol_index).is_equal(0)
  	assert_str(e.room_id).is_equal("")
  	assert_str(e.event_type).is_equal("")
  	assert_object(e.pokemon_species).is_null()
  	assert_object(e.hp_current).is_null()


  func test_fields_are_settable_before_seal() -> void:
  	var e := ProtocolEventDTO.new()
  	e.protocol_index = 3
  	e.event_type = "switch"
  	e.pokemon_side = "p1"
  	e.pokemon_slot = "a"
  	e.pokemon_species = "Pikachu"
  	e.hp_current = 100
  	e.hp_maximum = 100
  	e.hp_fainted = false
  	assert_int(e.protocol_index).is_equal(3)
  	assert_str(str(e.pokemon_species)).is_equal("Pikachu")
  	assert_int(e.hp_current).is_equal(100)


  func test_condition_label_carries_init_room_type() -> void:
  	var e := ProtocolEventDTO.new()
  	e.event_type = "init"
  	e.condition_label = "battle"
  	assert_str(str(e.condition_label)).is_equal("battle")


  func test_seal_freezes_further_writes() -> void:
  	var e := ProtocolEventDTO.new()
  	e.event_type = "turn"
  	e.turn_number = 1
  	e.seal()
  	e.turn_number = 99
  	assert_int(e.turn_number).is_equal(1)
  ```

- [ ] Run and confirm it fails; then write the implementation. Create
  `showdownbot_studio/godot/src/protocol/dto/protocol_event_dto.gd`:

  ```gdscript
  class_name ProtocolEventDTO
  extends RefCounted

  ## One decoded, DECODED_STATE_EVENT-classified Showdown protocol line (this plan's M1b section
  ## header). Flat and generic like bundle/battle_event_dto.gd's proven shape, but a distinct
  ## class under protocol/dto/, never a live/bundle DTO reuse (spec section 4.1.2). Sealed after
  ## construction by the decoder.

  var _sealed: bool = false
  var _protocol_index: int = 0
  var _room_id: String = ""
  var _event_type: String = ""
  var _pokemon_side: Variant = null
  var _pokemon_slot: Variant = null
  var _pokemon_species: Variant = null
  var _hp_current: Variant = null
  var _hp_maximum: Variant = null
  var _hp_fainted: Variant = null
  var _hp_status: Variant = null
  ## Weather/terrain/field-condition/side-condition name, OR |init|'s room-type argument
  ## ("battle"/"chat"/...) -- one shared field across several event families.
  var _condition_label: Variant = null
  var _side: Variant = null
  var _turn_number: Variant = null
  var _error_reason: Variant = null

  var protocol_index: int:
  	get: return _protocol_index
  	set(value):
  		if _sealed: return
  		_protocol_index = value

  var room_id: String:
  	get: return _room_id
  	set(value):
  		if _sealed: return
  		_room_id = value

  var event_type: String:
  	get: return _event_type
  	set(value):
  		if _sealed: return
  		_event_type = value

  var pokemon_side: Variant:
  	get: return _pokemon_side
  	set(value):
  		if _sealed: return
  		_pokemon_side = value

  var pokemon_slot: Variant:
  	get: return _pokemon_slot
  	set(value):
  		if _sealed: return
  		_pokemon_slot = value

  var pokemon_species: Variant:
  	get: return _pokemon_species
  	set(value):
  		if _sealed: return
  		_pokemon_species = value

  var hp_current: Variant:
  	get: return _hp_current
  	set(value):
  		if _sealed: return
  		_hp_current = value

  var hp_maximum: Variant:
  	get: return _hp_maximum
  	set(value):
  		if _sealed: return
  		_hp_maximum = value

  var hp_fainted: Variant:
  	get: return _hp_fainted
  	set(value):
  		if _sealed: return
  		_hp_fainted = value

  var hp_status: Variant:
  	get: return _hp_status
  	set(value):
  		if _sealed: return
  		_hp_status = value

  var condition_label: Variant:
  	get: return _condition_label
  	set(value):
  		if _sealed: return
  		_condition_label = value

  var side: Variant:
  	get: return _side
  	set(value):
  		if _sealed: return
  		_side = value

  var turn_number: Variant:
  	get: return _turn_number
  	set(value):
  		if _sealed: return
  		_turn_number = value

  var error_reason: Variant:
  	get: return _error_reason
  	set(value):
  		if _sealed: return
  		_error_reason = value


  func seal() -> void:
  	_sealed = true
  ```

- [ ] Add the allowlist entry. Edit
  `showdownbot_studio/tests/python/architecture_allowlists/named_value_object_allowlist.txt`,
  appending:

  ```

  # protocol_index/room_id/event_type are typed (int/String), not Variant. The remaining ten
  # fields are documented nullable display/state scalars decoded from Showdown protocol text
  # (spec section 4.1.2); never containers, never a cross-module function parameter/return type.
  protocol/dto/protocol_event_dto.gd
  ```

- [ ] Run and confirm the DTO test passes and no architecture test regresses:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/protocol/test_protocol_event_dto.gd"
  cd showdownbot_studio/python
  python -m pytest -q -m architecture
  ```

  Expected: `4` gdUnit tests passed; all architecture tests pass.

- [ ] Write `protocol/README.md`. Create `showdownbot_studio/godot/src/protocol/README.md`:

  ```markdown
  # Protocol (`godot/src/protocol/`)

  ## Purpose

  The only module permitted to decode inbound Showdown protocol text or encode outbound Showdown
  protocol commands (spec section 4.1, `PROJECT_BOUNDARIES.md` section 4).

  ## Public interface

  New (M1b):

  - `protocol/dto/ProtocolEventDTO` — one decoded, `DECODED_STATE_EVENT`-classified protocol line.
  - `RoomStateMachine` — pure-transition implementation of the `RoomState` table
    (`docs/architecture/LIVE_STATE_MACHINES.md`, 10 rows including the local-send-failure edge),
    holding a `net/WebSocketTransport` reference from construction (this module already depends on
    `net/` for sending encoded commands) so M1e can add automatic-reconnect-rejoin behavior without
    changing how any composition root constructs or wires it.
  - `ProtocolDecoder` — three-way classification: `signal event_decoded(event: ProtocolEventDTO)`,
    `signal known_ignored_event(raw_line: String, message_type: String)`,
    `signal line_not_understood(raw_line: String)`; `decode_frame(raw_frame: String) -> void`.
  - `ProtocolCommandEncoder` — `static func encode_join_room(room_id: String) -> String`,
    `static func encode_leave_room(room_id: String) -> String`.

  ## Dependencies

  Depends on `net/` as a direct dependency (receives raw text via composition-root wiring, sends
  encoded commands via a held `WebSocketTransport` reference in `RoomStateMachine`). Never depends
  on `battle/`, `replay/`, `workspace/`, or `ui/panels/`.

  ## Rule for future producers

  Every new outbound command family (spec section 4.1.1) is encoded here, in
  `ProtocolCommandEncoder` or a narrowly-scoped sibling — never assembled as a raw string anywhere
  else. Every human-initiated command additionally reaches this encoder only through a privileged
  command gateway living in `ui/panels/` (e.g. `SpectatorRoomGateway`, M1d) — `protocol/` itself
  never decides whether a human is allowed to send a given command.
  ```

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/protocol/README.md showdownbot_studio/godot/src/protocol/dto/protocol_event_dto.gd showdownbot_studio/tests/python/architecture_allowlists/named_value_object_allowlist.txt showdownbot_studio/godot/tests/protocol/test_protocol_event_dto.gd
  git commit -m "feat(studio): add protocol/dto/ProtocolEventDTO"
  ```

## Task 11 — `RoomStateMachine` (transport-aware from the start)

**Files:**
- Create: `showdownbot_studio/godot/src/protocol/room_state_machine.gd`
- Create: `showdownbot_studio/godot/tests/protocol/test_room_state_machine.gd`

Implements the 11-row `RoomState` table from Task 1 (9 original rows + the two new local-send-
failure edges, `JOINING`→`NOT_JOINED` and `LEAVING`→`ACTIVE`). Constructor takes a `WebSocketTransport`
and subscribes to its `connection_state_changed` immediately — but **only to observe it**; this class
never calls `send_raw_text()` or references `ProtocolCommandEncoder` (owner re-review, 2026-07-25,
second pass, item C). `_on_connection_state_changed`'s body is intentionally minimal here (M1e, Task
37, extends it to *emit* `automatic_rejoin_requested` — never to send anything itself — so M1e's own
change stays a pure `protocol/` file edit). `SpectatorRoomGateway` (`ui/panels/`, Task 28) is the only
object that ever calls `send_raw_text()` for a room command, whether the trigger was a human "Watch"
click or this class's own reconnect signal — resolving the review's item C exactly as it prescribed:
"the gateway handles human join AND system rejoin; `RoomStateMachine` never touches encoder or
transport" for sending, while still legitimately holding the transport reference to *observe*
`connection_state_changed`, a role it has had since this task, unchanged.

- [ ] Write the failing test. Create `showdownbot_studio/godot/tests/protocol/test_room_state_machine.gd`:

  ```gdscript
  extends GdUnitTestSuite

  var _fake: FakeSocketPeerPort
  var _transport: WebSocketTransport


  func before_test() -> void:
  	_fake = FakeSocketPeerPort.new()
  	_transport = WebSocketTransport.new(func(): return _fake)
  	add_child(_transport)


  func after_test() -> void:
  	remove_child(_transport)
  	_transport.free()


  func test_initial_state_is_not_joined() -> void:
  	var m := RoomStateMachine.new(_transport)
  	assert_int(m.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)


  func test_request_join_moves_to_joining_and_records_room_id() -> void:
  	var m := RoomStateMachine.new(_transport)
  	assert_bool(m.request_join("battle-1")).is_true()
  	assert_int(m.get_state()).is_equal(RoomStateMachine.State.JOINING)
  	assert_str(m.get_room_id()).is_equal("battle-1")


  func test_join_confirmed_moves_to_active() -> void:
  	var m := RoomStateMachine.new(_transport)
  	m.request_join("battle-1")
  	assert_bool(m.join_confirmed()).is_true()
  	assert_int(m.get_state()).is_equal(RoomStateMachine.State.ACTIVE)


  func test_join_rejected_moves_back_to_not_joined_and_records_reason() -> void:
  	var m := RoomStateMachine.new(_transport)
  	m.request_join("battle-1")
  	assert_bool(m.join_rejected("[Room not found]")).is_true()
  	assert_int(m.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)
  	assert_str(m.get_last_error_reason()).is_equal("[Room not found]")
  	assert_str(m.get_room_id()).is_equal("")


  func test_join_send_failed_moves_back_to_not_joined_with_a_surfaced_reason() -> void:
  	var m := RoomStateMachine.new(_transport)
  	m.request_join("battle-1")
  	assert_bool(m.join_send_failed()).is_true()
  	assert_int(m.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)
  	assert_bool(m.get_last_error_reason().length() > 0).is_true()


  func test_request_leave_from_active_moves_to_leaving() -> void:
  	var m := RoomStateMachine.new(_transport)
  	m.request_join("battle-1")
  	m.join_confirmed()
  	assert_bool(m.request_leave()).is_true()
  	assert_int(m.get_state()).is_equal(RoomStateMachine.State.LEAVING)


  func test_leave_send_failed_returns_to_active_with_a_surfaced_reason_and_keeps_room_id() -> void:
  	var m := RoomStateMachine.new(_transport)
  	m.request_join("battle-1")
  	m.join_confirmed()
  	m.request_leave()
  	assert_bool(m.leave_send_failed()).is_true()
  	assert_int(m.get_state()).is_equal(RoomStateMachine.State.ACTIVE)
  	assert_bool(m.get_last_error_reason().length() > 0).is_true()
  	assert_str(m.get_room_id()).is_equal("battle-1")  # the room is still joined -- leave didn't happen


  func test_leave_send_failed_outside_leaving_is_rejected() -> void:
  	var m := RoomStateMachine.new(_transport)
  	m.request_join("battle-1")
  	m.join_confirmed()
  	assert_bool(m.leave_send_failed()).is_false()
  	assert_int(m.get_state()).is_equal(RoomStateMachine.State.ACTIVE)


  func test_leave_confirmed_moves_to_not_joined() -> void:
  	var m := RoomStateMachine.new(_transport)
  	m.request_join("battle-1")
  	m.join_confirmed()
  	m.request_leave()
  	assert_bool(m.leave_confirmed()).is_true()
  	assert_int(m.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)


  func test_server_closed_room_from_active_moves_to_closed() -> void:
  	var m := RoomStateMachine.new(_transport)
  	m.request_join("battle-1")
  	m.join_confirmed()
  	assert_bool(m.server_closed_room()).is_true()
  	assert_int(m.get_state()).is_equal(RoomStateMachine.State.CLOSED)


  func test_dismiss_closed_room_moves_to_not_joined() -> void:
  	var m := RoomStateMachine.new(_transport)
  	m.request_join("battle-1")
  	m.join_confirmed()
  	m.server_closed_room()
  	assert_bool(m.dismiss_closed_room()).is_true()
  	assert_int(m.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)


  func test_connection_reconnecting_while_active_moves_to_joining() -> void:
  	var m := RoomStateMachine.new(_transport)
  	m.request_join("battle-1")
  	m.join_confirmed()
  	assert_bool(m.connection_reconnecting()).is_true()
  	assert_int(m.get_state()).is_equal(RoomStateMachine.State.JOINING)


  func test_not_joined_to_active_directly_is_rejected() -> void:
  	var m := RoomStateMachine.new(_transport)
  	assert_bool(m.join_confirmed()).is_false()
  	assert_int(m.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)


  func test_closed_to_active_directly_is_rejected() -> void:
  	var m := RoomStateMachine.new(_transport)
  	m.request_join("battle-1")
  	m.join_confirmed()
  	m.server_closed_room()
  	assert_bool(m.join_confirmed()).is_false()
  	assert_int(m.get_state()).is_equal(RoomStateMachine.State.CLOSED)
  ```

- [ ] Run and confirm it fails; then write the implementation. Create
  `showdownbot_studio/godot/src/protocol/room_state_machine.gd`:

  ```gdscript
  class_name RoomStateMachine
  extends RefCounted

  ## Pure-transition implementation of the RoomState table (docs/architecture/LIVE_STATE_MACHINES.md,
  ## 11 rows including the two local-send-failure edges, this plan's Task 1). Holds a
  ## WebSocketTransport reference from construction ONLY to observe its connection_state_changed
  ## signal -- this class never calls send_raw_text() or references ProtocolCommandEncoder
  ## (owner re-review, 2026-07-25, second pass, item C). M1e (Task 37) extends
  ## _on_connection_state_changed to EMIT automatic_rejoin_requested, never to send anything
  ## itself, so that task stays a pure protocol/ file edit with zero change to how any
  ## composition root constructs or wires this class.

  enum State { NOT_JOINED, JOINING, ACTIVE, LEAVING, CLOSED }

  signal state_changed(old_state: State, new_state: State)
  ## Emitted by M1e's extension of _on_connection_state_changed (Task 37) when a reconnect
  ## succeeds while this room was mid-rejoin. protocol/ never sends anything itself in reaction
  ## to this signal; ui/panels/SpectatorRoomGateway (Task 28) is the sole subscriber and the sole
  ## sender, for both a human-initiated join and this system-initiated one.
  signal automatic_rejoin_requested(room_id: String)

  var _state: State = State.NOT_JOINED
  var _room_id: String = ""
  var _last_error_reason: String = ""
  var _transport: WebSocketTransport


  func _init(transport: WebSocketTransport) -> void:
  	_transport = transport
  	_transport.connection_state_changed.connect(_on_connection_state_changed)


  func get_state() -> State:
  	return _state


  func get_room_id() -> String:
  	return _room_id


  func get_last_error_reason() -> String:
  	return _last_error_reason


  func request_join(room_id: String) -> bool:
  	if _state != State.NOT_JOINED:
  		return false
  	_room_id = room_id
  	_transition(State.JOINING)
  	return true


  func join_confirmed() -> bool:
  	if _state != State.JOINING:
  		return false
  	_transition(State.ACTIVE)
  	return true


  ## Alias of join_confirmed(), same precondition and destination -- named separately so a caller's
  ## own code distinguishes "first join" from "rejoin after reconnect" even though both are valid
  ## only from JOINING and land on ACTIVE identically.
  func rejoin_confirmed() -> bool:
  	return join_confirmed()


  func join_rejected(reason: String = "") -> bool:
  	if _state != State.JOINING:
  		return false
  	_last_error_reason = reason
  	_transition(State.NOT_JOINED)
  	return true


  ## New edge (Task 1, owner-approved 2026-07-25): the /join command itself could not be sent (e.g.
  ## the connection dropped between "Watch" being pressed and the command reaching the socket) --
  ## distinct from the server actively rejecting a join it received.
  func join_send_failed() -> bool:
  	if _state != State.JOINING:
  		return false
  	_last_error_reason = "Could not send the join request (not connected)"
  	_transition(State.NOT_JOINED)
  	return true


  func request_leave() -> bool:
  	if _state != State.ACTIVE:
  		return false
  	_transition(State.LEAVING)
  	return true


  func leave_confirmed() -> bool:
  	if _state != State.LEAVING:
  		return false
  	_transition(State.NOT_JOINED)
  	return true


  ## New edge (Task 1, owner-approved 2026-07-25, second pass): the /leave command itself could
  ## not be sent. Returns to ACTIVE, not NOT_JOINED -- the room is still joined; the leave simply
  ## didn't happen. Symmetric with join_send_failed().
  func leave_send_failed() -> bool:
  	if _state != State.LEAVING:
  		return false
  	_last_error_reason = "Could not send the leave request (not connected)"
  	_transition(State.ACTIVE)
  	return true


  ## Real room closure only -- driven by a decoded `deinit` event, never by win/tie (spec section
  ## 6.1's fail-closed table; win/tie end the BATTLE, not the room -- see this plan's M1d fixes).
  func server_closed_room() -> bool:
  	if _state != State.ACTIVE:
  		return false
  	_transition(State.CLOSED)
  	return true


  func dismiss_closed_room() -> bool:
  	if _state != State.CLOSED:
  		return false
  	_transition(State.NOT_JOINED)
  	return true


  func connection_reconnecting() -> bool:
  	if _state != State.ACTIVE:
  		return false
  	_transition(State.JOINING)
  	return true


  func _transition(new_state: State) -> void:
  	var old_state := _state
  	_state = new_state
  	if new_state == State.NOT_JOINED:
  		_room_id = ""
  	state_changed.emit(old_state, new_state)


  ## M1b: intentionally minimal. M1e (Task 37) extends this SAME method (protocol/ is a normative
  ## M1e module) to EMIT automatic_rejoin_requested -- no other file changes when that lands, and
  ## this class still never sends anything itself (owner re-review, 2026-07-25, second pass).
  func _on_connection_state_changed(_old_state: ConnectionStateMachine.State, _new_state: ConnectionStateMachine.State) -> void:
  	pass
  ```

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/protocol/test_room_state_machine.gd"
  ```

  Expected: `14` tests passed, `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/protocol/room_state_machine.gd showdownbot_studio/godot/tests/protocol/test_room_state_machine.gd
  git commit -m "feat(studio): add protocol/RoomStateMachine (transport-aware, 10-row RoomState)"
  ```

## Task 12 — Capture the JSONL transcript, hand-write the golden DTO sequence, and show the contract test red

**Files:**
- Create: `showdownbot_studio/fixtures/live-protocol-v0/SOURCES.md`
- Create: `showdownbot_studio/fixtures/live-protocol-v0/local-spectate-01/transcript.jsonl`
- Create: `showdownbot_studio/fixtures/live-protocol-v0/local-spectate-01/golden_events.jsonl`
- Create: `showdownbot_studio/tests/python/test_protocol_contract_fixtures.py`
- Create: `showdownbot_studio/godot/tests/protocol/test_protocol_decoder_local_transcript.gd`

**Reordered in this revision (owner re-review, 2026-07-25, second pass, item E).** Spec §8 is
explicit and binding: "protocol fixtures and their expected DTOs... are reviewed **before** the
parser or encoder diff that satisfies them." The first revision's plan captured the transcript and
golden file in what was then Task 16, *after* the three decoder tasks — backwards relative to
spec's own ordering rule. This task now runs first in M1b's fixture/decoder work: the transcript is
captured, the golden sequence is hand-written and reviewed, and the contract test exists and is
shown **red** (because `ProtocolDecoder` does not exist at all yet) before Tasks 13–15 write a
single line of decoder code. Tasks 13–15 then implement the decoder's vocabulary in groups; the
contract test stays red across all three (each group only ever satisfies part of the golden
sequence) until Task 16 confirms it green.

**Fixture-format fix (carried from the first revision).** A single Showdown server frame is
multi-line — `">battle-room\n|init|battle\n|title|A vs B\n|turn|1"` arrives as **one** WebSocket
message with several `|`-delimited lines inside it. Fixtures are JSONL: one JSON object per
**frame**, `{"sequence": N, "raw_frame": "...the exact multi-line frame, newlines included as JSON
string escapes..."}` — never one line of decoder-level text per file line, which would destroy real
frame boundaries.

**Golden-comparison fix (carried from the first revision).** The contract test compares the
decoder's full output against a golden file naming the exact expected `DECODED_STATE_EVENT`
sequence, field by field, in order — not "contains at least a turn/switch/completion event."

- [ ] **Capture the local-server transcript as JSONL** (manual step, run once). Using the recipe at
  `showdown_bot/tools/localserver/README.md` (pinned commit
  `f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5`), capture the raw WebSocket **messages** (not
  post-split lines) the client receives for one full battle, and write each as one JSON object per
  line to `showdownbot_studio/fixtures/live-protocol-v0/local-spectate-01/transcript.jsonl`:

  ```jsonl
  {"sequence": 0, "raw_frame": ">battle-gen9vgc2025regg-1\n|init|battle\n|title|Alice vs Bob\n|j|Alice\n|j|Bob"}
  {"sequence": 1, "raw_frame": ">battle-gen9vgc2025regg-1\n|player|p1|Alice|1\n|player|p2|Bob|2\n|teamsize|p1|4\n|teamsize|p2|4\n|gametype|doubles\n|gen|9"}
  {"sequence": 2, "raw_frame": ">battle-gen9vgc2025regg-1\n|start\n|turn|1\n|switch|p1a: Pikachu|Pikachu, L50, M|100/100\n|switch|p2a: Ditto|Ditto, L50|100/100"}
  {"sequence": 3, "raw_frame": ">battle-gen9vgc2025regg-1\n|move|p1a: Pikachu|Thunderbolt|p2a: Ditto\n|-damage|p2a: Ditto|40/100\n|turn|2"}
  {"sequence": 4, "raw_frame": ">battle-gen9vgc2025regg-1\n|faint|p2a: Ditto\n|win|Alice"}
  ```

  (This shown content is a realistic **placeholder** matching the exact JSONL shape and the decoded
  vocabulary Tasks 13–15 will implement; when this task is actually executed, replace it with the
  real captured transcript from a real local-server battle — do not commit the placeholder text
  above as if it were a real capture.)

- [ ] Write the golden file recording the exact expected `DECODED_STATE_EVENT` sequence for the
  transcript above, hand-verified line by line against the raw frames (`KNOWN_IGNORED_EVENT`/
  `UNKNOWN_EVENT` lines are deliberately absent — this file records only what `event_decoded` should
  fire, in order). Create `showdownbot_studio/fixtures/live-protocol-v0/local-spectate-01/golden_events.jsonl`:

  ```jsonl
  {"event_type": "init", "room_id": "battle-gen9vgc2025regg-1", "condition_label": "battle"}
  {"event_type": "title", "room_id": "battle-gen9vgc2025regg-1"}
  {"event_type": "turn", "room_id": "battle-gen9vgc2025regg-1", "turn_number": 1}
  {"event_type": "switch", "room_id": "battle-gen9vgc2025regg-1", "pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": "Pikachu", "hp_current": 100, "hp_maximum": 100}
  {"event_type": "switch", "room_id": "battle-gen9vgc2025regg-1", "pokemon_side": "p2", "pokemon_slot": "a", "pokemon_species": "Ditto", "hp_current": 100, "hp_maximum": 100}
  {"event_type": "move", "room_id": "battle-gen9vgc2025regg-1", "pokemon_side": "p1", "pokemon_slot": "a"}
  {"event_type": "-damage", "room_id": "battle-gen9vgc2025regg-1", "pokemon_side": "p2", "pokemon_slot": "a", "hp_current": 40, "hp_maximum": 100}
  {"event_type": "turn", "room_id": "battle-gen9vgc2025regg-1", "turn_number": 2}
  {"event_type": "faint", "room_id": "battle-gen9vgc2025regg-1", "pokemon_side": "p2", "pokemon_slot": "a"}
  {"event_type": "win", "room_id": "battle-gen9vgc2025regg-1"}
  ```

  (Same placeholder-content caveat — regenerate from the real transcript when this task actually
  executes, by hand-verifying each expected event against the raw frames before freezing it as
  golden, per spec §8.1's fixture-review discipline.)

- [ ] Write `SOURCES.md`. Create `showdownbot_studio/fixtures/live-protocol-v0/SOURCES.md`:

  ```markdown
  # Live protocol fixtures — sources

  ## `local-spectate-01/transcript.jsonl` + `local-spectate-01/golden_events.jsonl`

  - Captured from the repository's pinned local `pokemon-showdown` checkout
    (`~/.cache/showdownbot/pokemon-showdown`, commit `f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5`,
    `--no-security`, port 8000).
  - `transcript.jsonl`: one JSON object per **frame** (`{"sequence", "raw_frame"}`), raw and
    unmodified, exact multi-line frame boundaries preserved as JSON string escapes. No chat content,
    no credentials.
  - `golden_events.jsonl`: the exact expected `DECODED_STATE_EVENT` sequence, hand-verified against
    the raw frames before being frozen, and captured/reviewed *before* `protocol/protocol_decoder.gd`
    existed at all (spec section 8.1; Tasks 13–15 implement against this file, not the reverse).
  - Captured for M1b (`docs/plans/2026-07-25-phase3-m1-connect-spectate.md`); replace this line with
    the real capture date (`YYYY-MM-DD`) when this task is actually executed.

  ## Official-server capture — NOT included in this fixture set

  Requires separate owner approval under `AGENTS.md`'s controlled-live-test rule; not performed for
  M1 (owner decision recorded 2026-07-25, reaffirmed at both review passes).
  ```

- [ ] Write the pytest-side fixture-presence guard. Create
  `showdownbot_studio/tests/python/test_protocol_contract_fixtures.py`:

  ```python
  """Protocol contract fixture guard (spec section 8.1, studio-protocol-contract lane). Confirms
  the JSONL transcript and golden-event fixtures exist with real content -- the gdUnit-side test
  that actually replays the transcript and compares it against the golden file lives at
  godot/tests/protocol/test_protocol_decoder_local_transcript.gd.
  """
  from __future__ import annotations

  import json

  from conftest import STUDIO_ROOT  # type: ignore[import-not-found]

  _FIXTURE_DIR = STUDIO_ROOT / "fixtures" / "live-protocol-v0" / "local-spectate-01"


  def test_transcript_jsonl_exists_and_has_valid_frame_objects():
      path = _FIXTURE_DIR / "transcript.jsonl"
      assert path.is_file(), f"missing frozen protocol transcript fixture: {path}"
      lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
      assert lines, f"transcript fixture is empty: {path}"
      for line in lines:
          obj = json.loads(line)
          assert "sequence" in obj and "raw_frame" in obj


  def test_golden_events_jsonl_exists_and_has_valid_event_objects():
      path = _FIXTURE_DIR / "golden_events.jsonl"
      assert path.is_file(), f"missing golden-event fixture: {path}"
      lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
      assert lines, f"golden-event fixture is empty: {path}"
      for line in lines:
          obj = json.loads(line)
          assert "event_type" in obj


  def test_sources_md_documents_both_fixtures():
      path = _FIXTURE_DIR.parent / "SOURCES.md"
      text = path.read_text(encoding="utf-8")
      assert "transcript.jsonl" in text and "golden_events.jsonl" in text
  ```

- [ ] Run and confirm the fixture-presence guard already passes (it only checks the files exist,
  which they now do):

  ```
  cd showdownbot_studio/python
  python -m pytest -q -k test_protocol_contract_fixtures
  ```

- [ ] Write the gdUnit golden-comparison contract test — the one that stays red until Task 16.
  Create `showdownbot_studio/godot/tests/protocol/test_protocol_decoder_local_transcript.gd`:

  ```gdscript
  extends GdUnitTestSuite

  const _TRANSCRIPT_PATH := "res://../fixtures/live-protocol-v0/local-spectate-01/transcript.jsonl"
  const _GOLDEN_PATH := "res://../fixtures/live-protocol-v0/local-spectate-01/golden_events.jsonl"


  func _decode_transcript() -> Array[ProtocolEventDTO]:
  	var file := FileAccess.open(_TRANSCRIPT_PATH, FileAccess.READ)
  	var decoder := ProtocolDecoder.new()
  	var events: Array[ProtocolEventDTO] = []
  	var unrecognized: Array[String] = []
  	decoder.event_decoded.connect(func(e: ProtocolEventDTO): events.append(e))
  	decoder.line_not_understood.connect(func(line: String): unrecognized.append(line))
  	while not file.eof_reached():
  		var raw_line := file.get_line()
  		if raw_line.is_empty():
  			continue
  		var frame_obj: Dictionary = JSON.parse_string(raw_line)
  		decoder.decode_frame(str(frame_obj["raw_frame"]))
  	file.close()
  	# Every line in this bounded-vocabulary fixture is expected to be either decoded or a
  	# documented KNOWN_IGNORED type -- a real transcript tripping line_not_understood is a real
  	# gap in this plan's bounded vocabulary (Tasks 13-15), never silently ignored.
  	assert_int(unrecognized.size()).is_equal(0)
  	return events


  func _load_golden() -> Array[Dictionary]:
  	var file := FileAccess.open(_GOLDEN_PATH, FileAccess.READ)
  	var golden: Array[Dictionary] = []
  	while not file.eof_reached():
  		var raw_line := file.get_line()
  		if not raw_line.is_empty():
  			golden.append(JSON.parse_string(raw_line))
  	file.close()
  	return golden


  func test_decoded_events_match_the_golden_sequence_exactly() -> void:
  	var events := _decode_transcript()
  	var golden := _load_golden()
  	assert_int(events.size()).is_equal(golden.size())
  	for i in range(golden.size()):
  		var expected: Dictionary = golden[i]
  		var actual := events[i]
  		for key in expected:
  			assert_object(actual.get(key)).is_equal(expected[key])
  ```

- [ ] Run and confirm it fails, for the correct reason (`ProtocolDecoder` does not exist yet — a
  parse/load error, not an assertion failure):

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/protocol/test_protocol_decoder_local_transcript.gd"
  ```

  This red result is the state Tasks 13–15 work against; do not write any `protocol/` decoder code
  before this commit lands.

- [ ] Commit:

  ```
  git add showdownbot_studio/fixtures/live-protocol-v0 showdownbot_studio/tests/python/test_protocol_contract_fixtures.py showdownbot_studio/godot/tests/protocol/test_protocol_decoder_local_transcript.gd
  git commit -m "test(studio): capture JSONL transcript + hand-written golden DTO sequence (red, no decoder yet)"
  ```

## Task 13 — `ProtocolDecoder`: three-way classification + room-lifecycle frames

**Files:**
- Create: `showdownbot_studio/godot/src/protocol/protocol_decoder.gd`
- Create: `showdownbot_studio/godot/tests/protocol/test_protocol_decoder_room_lifecycle.gd`

Covers `init` (with its room-type argument), `title`, `error`, `deinit`, plus the
`KNOWN_IGNORED_EVENT`/`UNKNOWN_EVENT` split. This is the first decoder code in the whole plan — Task
12's golden-comparison contract test is still red after this task (it does not yet decode `turn`,
`switch`, `move`, `-damage`, `faint`, or `win`), and that is expected; only this task's own unit
tests below need to be green to land it.

- [ ] Write the failing test. Create
  `showdownbot_studio/godot/tests/protocol/test_protocol_decoder_room_lifecycle.gd`:

  ```gdscript
  extends GdUnitTestSuite

  var _decoder: ProtocolDecoder
  var _events: Array[ProtocolEventDTO]
  var _known_ignored: Array[String]
  var _unrecognized: Array[String]


  func before_test() -> void:
  	_decoder = ProtocolDecoder.new()
  	_events = []
  	_known_ignored = []
  	_unrecognized = []
  	_decoder.event_decoded.connect(func(e: ProtocolEventDTO): _events.append(e))
  	_decoder.known_ignored_event.connect(func(_line: String, message_type: String): _known_ignored.append(message_type))
  	_decoder.line_not_understood.connect(func(line: String): _unrecognized.append(line))


  func test_room_prefix_is_attached_to_every_event_in_the_frame() -> void:
  	_decoder.decode_frame(">battle-1\n|init|battle\n|title|A vs B")
  	assert_int(_events.size()).is_equal(2)
  	assert_str(_events[0].room_id).is_equal("battle-1")
  	assert_str(_events[1].room_id).is_equal("battle-1")


  func test_init_battle_line_decodes_room_type() -> void:
  	_decoder.decode_frame(">battle-1\n|init|battle")
  	assert_str(_events[0].event_type).is_equal("init")
  	assert_str(str(_events[0].condition_label)).is_equal("battle")


  func test_init_chat_line_decodes_a_different_room_type() -> void:
  	_decoder.decode_frame(">some-room\n|init|chat")
  	assert_str(str(_events[0].condition_label)).is_equal("chat")


  func test_error_line_decodes_with_reason() -> void:
  	_decoder.decode_frame(">battle-1\n|error|[Room not found]")
  	assert_str(_events[0].event_type).is_equal("error")
  	assert_str(str(_events[0].error_reason)).is_equal("[Room not found]")


  func test_deinit_line_decodes_as_its_own_event_type() -> void:
  	_decoder.decode_frame(">battle-1\n|deinit")
  	assert_str(_events[0].event_type).is_equal("deinit")


  func test_protocol_index_increments_monotonically_across_frames() -> void:
  	_decoder.decode_frame(">battle-1\n|init|battle")
  	_decoder.decode_frame(">battle-1\n|title|A vs B")
  	assert_int(_events[0].protocol_index).is_equal(0)
  	assert_int(_events[1].protocol_index).is_equal(1)


  func test_known_ignored_line_is_reported_but_never_as_not_understood() -> void:
  	_decoder.decode_frame(">battle-1\n|player|p1|Alice|1")
  	assert_int(_events.size()).is_equal(0)
  	assert_int(_unrecognized.size()).is_equal(0)
  	assert_int(_known_ignored.size()).is_equal(1)
  	assert_str(_known_ignored[0]).is_equal("player")


  func test_chat_and_timestamp_lines_are_known_ignored() -> void:
  	_decoder.decode_frame(">battle-1\n|c|Alice|hi\n|t:|1234567890")
  	assert_int(_known_ignored.size()).is_equal(2)


  func test_genuinely_unrecognized_line_is_reported_not_understood() -> void:
  	_decoder.decode_frame(">battle-1\n|totallyunknowntype|foo|bar")
  	assert_int(_events.size()).is_equal(0)
  	assert_int(_known_ignored.size()).is_equal(0)
  	assert_int(_unrecognized.size()).is_equal(1)
  	assert_str(_unrecognized[0]).is_equal("|totallyunknowntype|foo|bar")


  func test_frame_without_room_prefix_decodes_with_empty_room_id() -> void:
  	_decoder.decode_frame("|init|battle")
  	assert_str(_events[0].room_id).is_equal("")
  ```

- [ ] Run and confirm it fails; then write the implementation. Create
  `showdownbot_studio/godot/src/protocol/protocol_decoder.gd`:

  ```gdscript
  class_name ProtocolDecoder
  extends RefCounted

  ## The only place raw Showdown protocol text is parsed (spec section 4.1). Three-way
  ## classification (this plan's M1b section header): DECODED_STATE_EVENT (event_decoded),
  ## KNOWN_IGNORED_EVENT (known_ignored_event -- a deliberately out-of-scope but recognized line,
  ## never a fail-closed warning), UNKNOWN_EVENT (line_not_understood -- the real spec section 6.1
  ## "not understood" signal).

  signal event_decoded(event: ProtocolEventDTO)
  signal known_ignored_event(raw_line: String, message_type: String)
  signal line_not_understood(raw_line: String)

  ## Real, valid Showdown protocol lines M1's bounded vocabulary deliberately does not model yet.
  ## Each is a candidate for later, deliberate promotion to DECODED_STATE_EVENT -- never silently
  ## dropped, never mistaken for a genuinely unrecognized line.
  const _KNOWN_IGNORED_TYPES: PackedStringArray = [
  	"player", "teamsize", "gametype", "gen", "tier", "rule", "clearpoke", "poke", "teampreview",
  	"start", "rated", "j", "join", "l", "leave", "c", "c:", "chat", "t:",
  ]

  var _next_protocol_index: int = 0


  func decode_frame(raw_frame: String) -> void:
  	var room_id := ""
  	var body := raw_frame
  	if raw_frame.begins_with(">"):
  		var newline_index := raw_frame.find("\n")
  		if newline_index == -1:
  			room_id = raw_frame.substr(1)
  			body = ""
  		else:
  			room_id = raw_frame.substr(1, newline_index - 1)
  			body = raw_frame.substr(newline_index + 1)
  	for line in body.split("\n"):
  		if line.is_empty():
  			continue
  		_decode_line(room_id, line)


  func _decode_line(room_id: String, line: String) -> void:
  	var parts := line.split("|")
  	if parts.size() < 2:
  		line_not_understood.emit(line)
  		return
  	var msg_type := parts[1]
  	if msg_type in _KNOWN_IGNORED_TYPES:
  		known_ignored_event.emit(line, msg_type)
  		return
  	match msg_type:
  		"init":
  			_emit(room_id, "init", {"condition_label": _arg(parts, 2)})
  		"title":
  			_emit(room_id, "title", {})
  		"error":
  			_emit(room_id, "error", {"error_reason": _arg(parts, 2)})
  		"deinit":
  			_emit(room_id, "deinit", {})
  		_:
  			line_not_understood.emit(line)


  func _arg(parts: PackedStringArray, index: int) -> String:
  	return parts[index] if index < parts.size() else ""


  func _emit(room_id: String, event_type: String, fields: Dictionary) -> void:
  	var e := ProtocolEventDTO.new()
  	e.protocol_index = _next_protocol_index
  	_next_protocol_index += 1
  	e.room_id = room_id
  	e.event_type = event_type
  	for key in fields:
  		e.set(key, fields[key])
  	e.seal()
  	event_decoded.emit(e)
  ```

  (`_emit`'s bare `Dictionary fields` parameter is an internal dispatch helper, covered by
  `protocol/`'s existing directory-prefix entry in `untyped_boundary_allowlist.txt` — no new
  allowlist edit needed.)

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/protocol/test_protocol_decoder_room_lifecycle.gd"
  ```

  Expected: `10` tests passed, `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/protocol/protocol_decoder.gd showdownbot_studio/godot/tests/protocol/test_protocol_decoder_room_lifecycle.gd
  git commit -m "feat(studio): add ProtocolDecoder three-way classification + room-lifecycle frames"
  ```

## Task 14 — `ProtocolDecoder`: battle-state frames (with the `_parse_hp_status` fix)

**Files:**
- Modify: `showdownbot_studio/godot/src/protocol/protocol_decoder.gd`
- Create: `showdownbot_studio/godot/tests/protocol/test_protocol_decoder_battle_state.gd`

**Bug fixed in this revision, red-first.** `"0 fnt"` is a real, common HP/status string — the
opponent's side, hidden max HP, fainted — and it contains **no `/`** at all (the exact/percentage
fraction only appears when a maximum is known). A parser that requires a `/` before it will even
look at the status suffix returns all-null for this input, silently losing every opponent faint. The
test below is written and shown failing against that naive shape *first*.

- [ ] Write the failing test, including the `"0 fnt"` case. Create
  `showdownbot_studio/godot/tests/protocol/test_protocol_decoder_battle_state.gd`:

  ```gdscript
  extends GdUnitTestSuite

  var _decoder: ProtocolDecoder
  var _events: Array[ProtocolEventDTO]


  func before_test() -> void:
  	_decoder = ProtocolDecoder.new()
  	_events = []
  	_decoder.event_decoded.connect(func(e: ProtocolEventDTO): _events.append(e))


  func test_turn_line_decodes_turn_number() -> void:
  	_decoder.decode_frame(">battle-1\n|turn|4")
  	assert_int(_events[0].turn_number).is_equal(4)


  func test_switch_line_decodes_side_slot_species_and_hp() -> void:
  	_decoder.decode_frame(">battle-1\n|switch|p1a: Pikachu|Pikachu, L50, M|100/100")
  	var e := _events[0]
  	assert_str(str(e.pokemon_side)).is_equal("p1")
  	assert_str(str(e.pokemon_slot)).is_equal("a")
  	assert_str(str(e.pokemon_species)).is_equal("Pikachu")
  	assert_int(e.hp_current).is_equal(100)
  	assert_int(e.hp_maximum).is_equal(100)
  	assert_bool(e.hp_fainted).is_false()


  func test_drag_line_decodes_same_as_switch() -> void:
  	_decoder.decode_frame(">battle-1\n|drag|p2b: Ditto|Ditto, shiny|50/50")
  	assert_str(_events[0].event_type).is_equal("drag")
  	assert_str(str(_events[0].pokemon_species)).is_equal("Ditto")


  func test_damage_line_decodes_hp_and_status() -> void:
  	_decoder.decode_frame(">battle-1\n|-damage|p1a: Pikachu|50/100 brn")
  	var e := _events[0]
  	assert_int(e.hp_current).is_equal(50)
  	assert_int(e.hp_maximum).is_equal(100)
  	assert_str(str(e.hp_status)).is_equal("brn")


  func test_heal_line_decodes_hp() -> void:
  	_decoder.decode_frame(">battle-1\n|-heal|p1a: Pikachu|75/100")
  	assert_int(_events[0].hp_current).is_equal(75)


  func test_hidden_max_hp_fainted_with_no_slash_decodes_zero_hp_and_fainted_true() -> void:
  	# The real, common "0 fnt" shape (opponent side, hidden max HP, no "/" at all) -- the bug this
  	# task fixes.
  	_decoder.decode_frame(">battle-1\n|-damage|p2a: Ditto|0 fnt")
  	var e := _events[0]
  	assert_int(e.hp_current).is_equal(0)
  	assert_object(e.hp_maximum).is_null()
  	assert_bool(e.hp_fainted).is_true()
  	assert_object(e.hp_status).is_null()


  func test_exact_zero_over_max_also_sets_fainted_true() -> void:
  	_decoder.decode_frame(">battle-1\n|-damage|p1a: Pikachu|0/100")
  	assert_bool(_events[0].hp_fainted).is_true()


  func test_status_line_decodes_status_label() -> void:
  	_decoder.decode_frame(">battle-1\n|-status|p1a: Pikachu|par")
  	assert_str(str(_events[0].hp_status)).is_equal("par")


  func test_curestatus_line_clears_status() -> void:
  	_decoder.decode_frame(">battle-1\n|-curestatus|p1a: Pikachu|par")
  	assert_object(_events[0].hp_status).is_null()


  func test_faint_line_decodes_side_and_slot() -> void:
  	_decoder.decode_frame(">battle-1\n|faint|p2a: Ditto")
  	var e := _events[0]
  	assert_str(str(e.pokemon_side)).is_equal("p2")
  	assert_str(str(e.pokemon_slot)).is_equal("a")
  ```

- [ ] Run and confirm it fails; then extend the implementation. Edit
  `showdownbot_studio/godot/src/protocol/protocol_decoder.gd`, adding to the `match` in
  `_decode_line` (before the `_:` fallback) and adding the parsing helpers:

  ```gdscript
  		"turn":
  			_emit(room_id, "turn", {"turn_number": _arg(parts, 2).to_int()})
  		"switch", "drag":
  			_emit_switch(room_id, msg_type, parts)
  		"-damage", "-heal":
  			_emit_hp_change(room_id, msg_type, parts)
  		"-status":
  			_emit_side_slot(room_id, "-status", parts, {"hp_status": _arg(parts, 3)})
  		"-curestatus":
  			_emit_side_slot(room_id, "-curestatus", parts, {"hp_status": null})
  		"faint":
  			_emit_faint(room_id, parts)
  ```

  ```gdscript
  static func _parse_pokemon_identifier(identifier: String) -> Dictionary:
  	var colon_index := identifier.find(":")
  	if colon_index < 3:
  		return {"side": null, "slot": null}
  	var side_slot := identifier.substr(0, colon_index)
  	return {"side": side_slot.substr(0, 2), "slot": side_slot.substr(2, 1)}


  ## "100/100" | "50/100 brn" | "0 fnt" (NO slash -- hidden max HP) -> hp_current/hp_maximum/
  ## hp_fainted/hp_status. Fixed bug: the slash-less case must not fall through to all-null.
  static func _parse_hp_status(hp_status_text: String) -> Dictionary:
  	var space_index := hp_status_text.find(" ")
  	var hp_part := hp_status_text if space_index == -1 else hp_status_text.substr(0, space_index)
  	var status_part := "" if space_index == -1 else hp_status_text.substr(space_index + 1)
  	var slash_index := hp_part.find("/")
  	var hp_current: int
  	var hp_maximum: Variant = null
  	if slash_index == -1:
  		if not hp_part.is_valid_int():
  			return {"hp_current": null, "hp_maximum": null, "hp_fainted": null, "hp_status": null}
  		hp_current = hp_part.to_int()
  	else:
  		hp_current = hp_part.substr(0, slash_index).to_int()
  		hp_maximum = hp_part.substr(slash_index + 1).to_int()
  	var fainted := status_part == "fnt" or hp_current == 0
  	var status: Variant = null if status_part.is_empty() or status_part == "fnt" else status_part
  	return {"hp_current": hp_current, "hp_maximum": hp_maximum, "hp_fainted": fainted, "hp_status": status}


  func _emit_switch(room_id: String, event_type: String, parts: PackedStringArray) -> void:
  	var identifier := _parse_pokemon_identifier(_arg(parts, 2))
  	var details := _arg(parts, 3)
  	var species: Variant = details.split(",")[0] if not details.is_empty() else null
  	var hp := _parse_hp_status(_arg(parts, 4))
  	var fields := {
  		"pokemon_side": identifier["side"], "pokemon_slot": identifier["slot"], "pokemon_species": species,
  	}
  	fields.merge(hp)
  	_emit(room_id, event_type, fields)


  func _emit_hp_change(room_id: String, event_type: String, parts: PackedStringArray) -> void:
  	var identifier := _parse_pokemon_identifier(_arg(parts, 2))
  	var hp := _parse_hp_status(_arg(parts, 3))
  	var fields := {"pokemon_side": identifier["side"], "pokemon_slot": identifier["slot"]}
  	fields.merge(hp)
  	_emit(room_id, event_type, fields)


  func _emit_side_slot(room_id: String, event_type: String, parts: PackedStringArray, extra: Dictionary) -> void:
  	var identifier := _parse_pokemon_identifier(_arg(parts, 2))
  	var fields := {"pokemon_side": identifier["side"], "pokemon_slot": identifier["slot"]}
  	fields.merge(extra)
  	_emit(room_id, event_type, fields)


  func _emit_faint(room_id: String, parts: PackedStringArray) -> void:
  	var identifier := _parse_pokemon_identifier(_arg(parts, 2))
  	_emit(room_id, "faint", {
  		"pokemon_side": identifier["side"], "pokemon_slot": identifier["slot"],
  		"hp_current": 0, "hp_fainted": true,
  	})
  ```

- [ ] Run and confirm it passes, with special attention to the two previously-buggy cases:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/protocol/test_protocol_decoder_battle_state.gd"
  ```

  Expected: `10` tests passed, `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/protocol/protocol_decoder.gd showdownbot_studio/godot/tests/protocol/test_protocol_decoder_battle_state.gd
  git commit -m "feat(studio): add ProtocolDecoder battle-state frames; fix slash-less HP/status parsing"
  ```

## Task 15 — `ProtocolDecoder`: field/side/weather/move/completion frames

**Files:**
- Modify: `showdownbot_studio/godot/src/protocol/protocol_decoder.gd`
- Create: `showdownbot_studio/godot/tests/protocol/test_protocol_decoder_field_and_completion.gd`

Unchanged in design from earlier revisions (`-weather`, `-fieldstart`/`-fieldend`,
`-sidestart`/`-sideend`, `move`, `win`/`tie`) — `win`/`tie` still only mark battle completion at the
decoder level; `RoomStateMachine`'s wiring (Task 29) is what no longer conflates that with room
closure. After this task, Task 12's golden-comparison contract test should decode every remaining
event in the golden sequence — confirmed explicitly in Task 16.

- [ ] Write the failing test. Create
  `showdownbot_studio/godot/tests/protocol/test_protocol_decoder_field_and_completion.gd`:

  ```gdscript
  extends GdUnitTestSuite

  var _decoder: ProtocolDecoder
  var _events: Array[ProtocolEventDTO]


  func before_test() -> void:
  	_decoder = ProtocolDecoder.new()
  	_events = []
  	_decoder.event_decoded.connect(func(e: ProtocolEventDTO): _events.append(e))


  func test_weather_line_decodes_condition_label() -> void:
  	_decoder.decode_frame(">battle-1\n|-weather|RainDance")
  	assert_str(str(_events[0].condition_label)).is_equal("RainDance")


  func test_weather_none_clears_weather() -> void:
  	_decoder.decode_frame(">battle-1\n|-weather|none")
  	assert_object(_events[0].condition_label).is_null()


  func test_fieldstart_strips_move_prefix() -> void:
  	_decoder.decode_frame(">battle-1\n|-fieldstart|move: Trick Room")
  	assert_str(str(_events[0].condition_label)).is_equal("Trick Room")


  func test_sidestart_decodes_side_and_condition() -> void:
  	_decoder.decode_frame(">battle-1\n|-sidestart|p1: Player1|move: Stealth Rock")
  	var e := _events[0]
  	assert_str(str(e.side)).is_equal("p1")
  	assert_str(str(e.condition_label)).is_equal("Stealth Rock")


  func test_move_line_decodes_species_side_slot() -> void:
  	_decoder.decode_frame(">battle-1\n|move|p1a: Pikachu|Thunderbolt|p2a: Ditto")
  	assert_str(str(_events[0].pokemon_side)).is_equal("p1")


  func test_win_line_decodes_battle_completion() -> void:
  	_decoder.decode_frame(">battle-1\n|win|Player1")
  	assert_str(_events[0].event_type).is_equal("win")


  func test_tie_line_decodes_battle_completion() -> void:
  	_decoder.decode_frame(">battle-1\n|tie")
  	assert_str(_events[0].event_type).is_equal("tie")
  ```

- [ ] Run and confirm it fails; then extend the implementation. Edit
  `showdownbot_studio/godot/src/protocol/protocol_decoder.gd`, adding to the `match`:

  ```gdscript
  		"-weather":
  			_emit(room_id, "-weather", {"condition_label": _clean_condition(_arg(parts, 2))})
  		"-fieldstart", "-fieldend":
  			_emit(room_id, msg_type, {"condition_label": _clean_condition(_arg(parts, 2))})
  		"-sidestart", "-sideend":
  			_emit(room_id, msg_type, {
  				"side": _arg(parts, 2).split(":")[0],
  				"condition_label": _clean_condition(_arg(parts, 3)),
  			})
  		"move":
  			_emit_side_slot(room_id, "move", parts, {})
  		"win", "tie":
  			_emit(room_id, msg_type, {})
  ```

  ```gdscript
  static func _clean_condition(raw: String) -> Variant:
  	if raw == "none":
  		return null
  	var colon_index := raw.find(": ")
  	return raw.substr(colon_index + 2) if colon_index != -1 else raw
  ```

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/protocol/"
  ```

  Expected: `7` new tests passed; full `protocol/` suite `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/protocol/protocol_decoder.gd showdownbot_studio/godot/tests/protocol/test_protocol_decoder_field_and_completion.gd
  git commit -m "feat(studio): add ProtocolDecoder field/side/weather/move/completion frames"
  ```

## Task 16 — Confirm the golden contract is green, add `ProtocolCommandEncoder`, add the `studio-protocol-contract` CI lane

**Files:**
- Create: `showdownbot_studio/godot/src/protocol/protocol_command_encoder.gd`
- Create: `showdownbot_studio/godot/tests/protocol/test_protocol_command_encoder.gd`
- Create: `.github/workflows/studio-protocol-contract.yml`

Two independent pieces of work land together in this task: (1) `ProtocolCommandEncoder`, which has
no dependency on the decoder vocabulary and could in principle land anywhere in M1b — kept last only
so the sub-slice's own commit order tells the story "decode, then encode, then wire CI"; (2)
confirming that Task 12's golden-comparison contract test — red since it was written, and
incrementally less red across Tasks 13–15 — is now fully green, which is the actual completion
signal for M1b's fixture-before-parser discipline (item E).

- [ ] Confirm Task 12's contract test now passes in full, with **no changes to the test or the
  fixtures** — only Tasks 13–15's decoder work should have been needed:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/protocol/test_protocol_decoder_local_transcript.gd"
  cd showdownbot_studio/python
  python -m pytest -q -k test_protocol_contract_fixtures
  ```

  Expected: both green. If the gdUnit test still fails here, that means the golden fixture names an
  event type or field Tasks 13–15 did not implement — extend the relevant decoder task with its own
  red-then-green step before treating this task as done; never loosen the golden file to match an
  incomplete decoder.

- [ ] Write the failing test. Create `showdownbot_studio/godot/tests/protocol/test_protocol_command_encoder.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func test_encode_join_room() -> void:
  	assert_str(ProtocolCommandEncoder.encode_join_room("battle-1")).is_equal("|/join battle-1")


  func test_encode_leave_room() -> void:
  	assert_str(ProtocolCommandEncoder.encode_leave_room("battle-1")).is_equal("|/leave battle-1")
  ```

- [ ] Run and confirm it fails; then write the implementation. Create
  `showdownbot_studio/godot/src/protocol/protocol_command_encoder.gd`:

  ```gdscript
  class_name ProtocolCommandEncoder
  extends RefCounted

  ## The only place an outbound Showdown command string is assembled (spec section 4.1, 4.1.1).


  static func encode_join_room(room_id: String) -> String:
  	return "|/join %s" % room_id


  static func encode_leave_room(room_id: String) -> String:
  	return "|/leave %s" % room_id
  ```

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/protocol/test_protocol_command_encoder.gd"
  ```

  Expected: `2` tests passed, `0` failed.

- [ ] Commit the encoder on its own:

  ```
  git add showdownbot_studio/godot/src/protocol/protocol_command_encoder.gd showdownbot_studio/godot/tests/protocol/test_protocol_command_encoder.gd
  git commit -m "feat(studio): add ProtocolCommandEncoder (room join/leave)"
  ```

- [ ] Add the `studio-protocol-contract` CI lane. Create `.github/workflows/studio-protocol-contract.yml`:

  ```yaml
  name: studio protocol contract lane

  # Spec section 8.2: introduced with M1b. Runs the frozen-transcript golden-comparison test
  # (godot/tests/protocol/) plus the fixture-presence pytest guard. Mirrors studio-windows.yml's
  # gdUnit steps exactly.

  on:
    push:
    pull_request:

  jobs:
    studio-protocol-contract:
      runs-on: windows-latest
      steps:
        - uses: actions/checkout@v4

        - uses: actions/setup-python@v5
          with:
            python-version: "3.12"

        - name: Install showdown_bot (Studio pytest imports its modules via tests/python/conftest.py)
          run: pip install -e ./showdown_bot

        - name: Install showdownbot_studio_exporter (+ pytest)
          run: pip install -e "./showdownbot_studio/python[dev]"

        - name: Run protocol contract fixture-presence guard
          working-directory: showdownbot_studio/python
          run: python -m pytest -q -k test_protocol_contract_fixtures

        - name: Cache pinned Godot engine
          id: cache-engine
          uses: actions/cache@v4
          with:
            path: showdownbot_studio/godot/tools/engine
            key: godot-engine-${{ hashFiles('showdownbot_studio/godot/tools/ENGINE_SHA256SUMS') }}

        - name: Download pinned Godot engine (cache miss only)
          if: steps.cache-engine.outputs.cache-hit != 'true'
          shell: pwsh
          run: |
            New-Item -ItemType Directory -Force -Path showdownbot_studio/godot/tools/engine | Out-Null
            Invoke-WebRequest `
              -Uri "https://github.com/godotengine/godot-builds/releases/download/4.5.2-stable/Godot_v4.5.2-stable_win64.exe.zip" `
              -OutFile "showdownbot_studio/godot/tools/engine/Godot_v4.5.2-stable_win64.exe.zip"

        - name: Install pinned Godot engine (cache miss only)
          if: steps.cache-engine.outputs.cache-hit != 'true'
          shell: pwsh
          run: ./showdownbot_studio/godot/tools/install_engine.ps1

        - name: Verify pinned Godot engine digest
          shell: pwsh
          run: ./showdownbot_studio/godot/tools/verify_engine_pin.ps1

        - name: Run protocol contract gdUnit suite
          shell: pwsh
          run: ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/protocol/"

        - name: Assert gdUnit results were not truncated
          shell: pwsh
          run: ./showdownbot_studio/godot/tools/check_gdunit_truncation.ps1
  ```

- [ ] Commit:

  ```
  git add showdownbot_studio/fixtures/live-protocol-v0 showdownbot_studio/tests/python/test_protocol_contract_fixtures.py showdownbot_studio/godot/tests/protocol/test_protocol_decoder_local_transcript.gd .github/workflows/studio-protocol-contract.yml
  git commit -m "test(studio): JSONL frame-preserving fixtures + golden-comparison protocol contract test"
  ```

## Task 17 — M1b gate evidence

**Files:** none (verification only).

- [ ] Full Python suite; full gdUnit suite + truncation check; architecture lane.

- [ ] `studio-protocol-contract` runs green in CI on the M1b PR.

- [ ] `git status --porcelain` clean; `git diff --check main` clean.

- [ ] Open the M1b PR. Do not merge until reviewed.

---

# M1c — Deterministic battle reducer

Blocked on M1b merged and gated. New production code lands only in `godot/src/battle/`, including
`battle/dto/` (spec §4.4).

**Immutability fix (this revision).** The first draft's `LiveBattleSnapshot`/`LiveBattleSlotSnapshot`
were *conventionally* immutable — public mutable fields that every caller was merely trusted not to
write to directly, plus `with_*` methods that duplicated internal dictionaries but still handed out
direct references from `get_slot()`. That is not what spec §4.7's derived-state rule ("state is
derived, never manually patched") or `AGENTS.md` rule 5 require — both call for something
**structurally** true, the same way GDScript's own read-only property syntax (`var x: T: get: ...`,
no `set:` block) makes external assignment a language-level error, not a code-review nicety. Both
value objects are rebuilt in this revision with **private backing fields and read-only-only
properties** (no `set:` block exists anywhere on either class); every value that "changes" is a
**new object built via the constructor**, and `get_slot()`/`get_side_conditions()`/
`get_field_conditions()` never return a container another module could mutate to affect this
snapshot's own future reads.

**State-ownership fix (this revision).** The first draft had `workspace/LiveClientWorkspace` hold
`_current_snapshot` directly — the composition root computing and owning derived state itself,
which is exactly the module-boundary violation the review flagged (and, mechanically, why M1e's
reconnect-rebuild work would otherwise have had to touch `workspace/`, violating M1e's own normative
module list). This sub-slice introduces `battle/LiveBattleProjection`, the single owner of "current"
derived snapshot **and** its parallel event timeline (both reset together — a reconnect rebuild that
cleared one but not the other would violate "state is rebuilt COMPLETELY," not just the board).
`workspace/`/`ui/panels/` only ever receive already-published `LiveBattleSnapshot` values from here on.

## Task 18 — `battle/README.md` + `battle/dto/` (structurally immutable)

**Files:**
- Create: `showdownbot_studio/godot/src/battle/README.md`
- Create: `showdownbot_studio/godot/src/battle/dto/live_battle_slot_snapshot.gd`
- Create: `showdownbot_studio/godot/src/battle/dto/live_battle_snapshot.gd`
- Modify: `showdownbot_studio/tests/python/architecture_allowlists/named_value_object_allowlist.txt`
- Create: `showdownbot_studio/godot/tests/battle/test_live_battle_snapshot.gd`

- [ ] Write the failing test, including a test that structural immutability actually holds (getting
  a slot and mutating the returned object, if it had setters, would be a compile error — this test
  instead proves `with_slot` never touches the original and that repeated `get_slot` calls observe
  no external tampering path). Create `showdownbot_studio/godot/tests/battle/test_live_battle_snapshot.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func test_default_snapshot_has_four_empty_slots() -> void:
  	var s := LiveBattleSnapshot.new()
  	assert_object(s.get_slot("p1", "a")).is_not_null()
  	assert_object(s.get_slot("p2", "b")).is_not_null()
  	assert_bool(s.battle_completed).is_false()


  func test_slot_snapshot_fields_default_to_null() -> void:
  	var slot := LiveBattleSlotSnapshot.new()
  	assert_object(slot.species).is_null()
  	assert_object(slot.hp_current).is_null()


  func test_slot_snapshot_fields_are_set_only_through_the_constructor() -> void:
  	var slot := LiveBattleSlotSnapshot.new("Pikachu", 100, 100, false, null)
  	assert_str(str(slot.species)).is_equal("Pikachu")
  	assert_int(slot.hp_current).is_equal(100)


  func test_with_slot_returns_a_new_snapshot_leaving_the_original_untouched() -> void:
  	var original := LiveBattleSnapshot.new()
  	var updated := original.with_slot("p1", "a", LiveBattleSlotSnapshot.new("Pikachu"))
  	assert_object(original.get_slot("p1", "a").species).is_null()
  	assert_str(str(updated.get_slot("p1", "a").species)).is_equal("Pikachu")


  func test_get_side_conditions_returns_an_independent_copy() -> void:
  	var s := LiveBattleSnapshot.new().with_side_condition_added("p1", "Stealth Rock")
  	var copy := s.get_side_conditions("p1")
  	copy.append("Spikes")  # mutate the RETURNED array only
  	assert_bool(s.get_side_conditions("p1").has("Spikes")).is_false()
  ```

- [ ] Run and confirm it fails; then write the implementation. Create
  `showdownbot_studio/godot/src/battle/dto/live_battle_slot_snapshot.gd`:

  ```gdscript
  class_name LiveBattleSlotSnapshot
  extends RefCounted

  ## One board slot's derived state (spec section 4.7's derived-state rule, made STRUCTURALLY
  ## true, not conventionally true): private backing fields, read-only-only properties (no
  ## `set:` block anywhere -- external assignment is a language-level error, not a review
  ## convention). Every field is set exactly once, at construction, by LiveBattleReducer.

  var _species: Variant
  var _hp_current: Variant
  var _hp_maximum: Variant
  var _hp_fainted: Variant
  var _hp_status: Variant


  func _init(
  	p_species: Variant = null, p_hp_current: Variant = null, p_hp_maximum: Variant = null,
  	p_hp_fainted: Variant = null, p_hp_status: Variant = null,
  ) -> void:
  	_species = p_species
  	_hp_current = p_hp_current
  	_hp_maximum = p_hp_maximum
  	_hp_fainted = p_hp_fainted
  	_hp_status = p_hp_status


  var species: Variant:
  	get: return _species

  var hp_current: Variant:
  	get: return _hp_current

  var hp_maximum: Variant:
  	get: return _hp_maximum

  var hp_fainted: Variant:
  	get: return _hp_fainted

  var hp_status: Variant:
  	get: return _hp_status
  ```

  Create `showdownbot_studio/godot/src/battle/dto/live_battle_snapshot.gd`:

  ```gdscript
  class_name LiveBattleSnapshot
  extends RefCounted

  ## battle/'s own structurally-immutable authoritative snapshot. Every `with_*` method returns a
  ## NEW LiveBattleSnapshot built via the constructor; there is no setter anywhere on this class,
  ## and no accessor ever hands out a container a caller could mutate to affect a FUTURE read of
  ## this same snapshot (get_side_conditions/get_field_conditions always return a duplicate).

  const SLOT_KEYS := ["p1a", "p1b", "p2a", "p2b"]

  var _turn: Variant
  var _weather: Variant
  var _terrain: Variant
  var _battle_completed: bool
  var _slots: Dictionary[String, LiveBattleSlotSnapshot] = {}
  var _side_conditions: Dictionary[String, PackedStringArray] = {}
  var _field_conditions: PackedStringArray = PackedStringArray()


  func _init(
  	p_turn: Variant = null, p_weather: Variant = null, p_terrain: Variant = null,
  	p_slots: Dictionary[String, LiveBattleSlotSnapshot] = {},
  	p_side_conditions: Dictionary[String, PackedStringArray] = {},
  	p_field_conditions: PackedStringArray = PackedStringArray(),
  	p_battle_completed: bool = false,
  ) -> void:
  	_turn = p_turn
  	_weather = p_weather
  	_terrain = p_terrain
  	_battle_completed = p_battle_completed
  	for key in SLOT_KEYS:
  		_slots[key] = p_slots.get(key, LiveBattleSlotSnapshot.new())
  	for side in ["p1", "p2"]:
  		_side_conditions[side] = p_side_conditions.get(side, PackedStringArray()).duplicate()
  	_field_conditions = p_field_conditions.duplicate()


  var turn: Variant:
  	get: return _turn

  var weather: Variant:
  	get: return _weather

  var terrain: Variant:
  	get: return _terrain

  var battle_completed: bool:
  	get: return _battle_completed


  static func slot_key(side: String, slot: String) -> String:
  	return "%s%s" % [side, slot]


  func get_slot(side: String, slot: String) -> LiveBattleSlotSnapshot:
  	return _slots[slot_key(side, slot)]


  func get_side_conditions(side: String) -> PackedStringArray:
  	return _side_conditions[side].duplicate()


  func get_field_conditions() -> PackedStringArray:
  	return _field_conditions.duplicate()


  func with_slot(side: String, slot: String, next_slot: LiveBattleSlotSnapshot) -> LiveBattleSnapshot:
  	var next_slots := _duplicate_slots()
  	next_slots[slot_key(side, slot)] = next_slot
  	return LiveBattleSnapshot.new(_turn, _weather, _terrain, next_slots, _duplicate_side_conditions(), _field_conditions, _battle_completed)


  func with_turn(next_turn: Variant) -> LiveBattleSnapshot:
  	return LiveBattleSnapshot.new(next_turn, _weather, _terrain, _duplicate_slots(), _duplicate_side_conditions(), _field_conditions, _battle_completed)


  func with_weather(next_weather: Variant) -> LiveBattleSnapshot:
  	return LiveBattleSnapshot.new(_turn, next_weather, _terrain, _duplicate_slots(), _duplicate_side_conditions(), _field_conditions, _battle_completed)


  func with_terrain(next_terrain: Variant) -> LiveBattleSnapshot:
  	return LiveBattleSnapshot.new(_turn, _weather, next_terrain, _duplicate_slots(), _duplicate_side_conditions(), _field_conditions, _battle_completed)


  func with_field_condition_added(label: String) -> LiveBattleSnapshot:
  	var next_fields := _field_conditions.duplicate()
  	if not label in next_fields:
  		next_fields.append(label)
  	return LiveBattleSnapshot.new(_turn, _weather, _terrain, _duplicate_slots(), _duplicate_side_conditions(), next_fields, _battle_completed)


  func with_field_condition_removed(label: String) -> LiveBattleSnapshot:
  	var next_fields := PackedStringArray()
  	for item in _field_conditions:
  		if item != label:
  			next_fields.append(item)
  	return LiveBattleSnapshot.new(_turn, _weather, _terrain, _duplicate_slots(), _duplicate_side_conditions(), next_fields, _battle_completed)


  func with_side_condition_added(side: String, label: String) -> LiveBattleSnapshot:
  	var next_conditions := _duplicate_side_conditions()
  	var arr: PackedStringArray = next_conditions[side]
  	if not label in arr:
  		arr.append(label)
  	next_conditions[side] = arr
  	return LiveBattleSnapshot.new(_turn, _weather, _terrain, _duplicate_slots(), next_conditions, _field_conditions, _battle_completed)


  func with_side_condition_removed(side: String, label: String) -> LiveBattleSnapshot:
  	var next_conditions := _duplicate_side_conditions()
  	var next_arr := PackedStringArray()
  	for item in next_conditions[side]:
  		if item != label:
  			next_arr.append(item)
  	next_conditions[side] = next_arr
  	return LiveBattleSnapshot.new(_turn, _weather, _terrain, _duplicate_slots(), next_conditions, _field_conditions, _battle_completed)


  func with_battle_completed() -> LiveBattleSnapshot:
  	return LiveBattleSnapshot.new(_turn, _weather, _terrain, _duplicate_slots(), _duplicate_side_conditions(), _field_conditions, true)


  func _duplicate_slots() -> Dictionary[String, LiveBattleSlotSnapshot]:
  	var copy: Dictionary[String, LiveBattleSlotSnapshot] = {}
  	for key in _slots:
  		copy[key] = _slots[key]  # slot values are themselves immutable; sharing the reference is safe
  	return copy


  func _duplicate_side_conditions() -> Dictionary[String, PackedStringArray]:
  	var copy: Dictionary[String, PackedStringArray] = {}
  	for side in _side_conditions:
  		copy[side] = _side_conditions[side].duplicate()
  	return copy
  ```

- [ ] Add the allowlist entries. Edit
  `showdownbot_studio/tests/python/architecture_allowlists/named_value_object_allowlist.txt`,
  appending:

  ```

  # turn/weather/terrain are documented nullable display scalars on battle/'s own structurally-
  # immutable snapshot (spec section 4.7) -- read-only-only properties, no setter anywhere.
  battle/dto/live_battle_snapshot.gd

  # species/hp_current/hp_maximum/hp_fainted/hp_status are documented nullable per-slot scalars
  # on the same structurally-immutable value object.
  battle/dto/live_battle_slot_snapshot.gd
  ```

- [ ] Run and confirm the test passes and no architecture test regresses:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/battle/test_live_battle_snapshot.gd"
  cd showdownbot_studio/python
  python -m pytest -q -m architecture
  ```

  Expected: `5` gdUnit tests passed; all architecture tests pass.

- [ ] Write `battle/README.md`. Create `showdownbot_studio/godot/src/battle/README.md`:

  ```markdown
  # Battle (`godot/src/battle/`)

  ## Purpose

  Pure, deterministic, idempotent `LiveBattleReducer` producing structurally-immutable
  `LiveBattleSnapshot` values from `protocol/`'s decoded event stream (spec section 4.7), and
  `LiveBattleProjection`, the single owner of "current" derived state and its parallel event
  timeline. Never contains UI nodes, never recomputes mechanics/damage/legality, never holds or
  imports `HumanBattleCommandGateway`.

  ## Public interface

  New (M1c):

  - `battle/dto/LiveBattleSnapshot` / `LiveBattleSlotSnapshot` — structurally immutable (private
    backing fields, read-only-only properties, no setter anywhere).
  - `LiveBattleReducer` — `static func apply(previous, event: ProtocolEventDTO) -> LiveBattleSnapshot`.
    Pure function.
  - `LiveBattleProjection` — owns the current `LiveBattleSnapshot` and its parallel event timeline;
    `apply_event(event)`, `get_current_snapshot()`, `get_timeline()`. `workspace/`/`ui/panels/`
    never hold or compute derived battle state themselves — they only receive what this class
    publishes.

  ## Dependencies

  Depends on `protocol/dto/ProtocolEventDTO` as a direct dependency. Never depends on `replay/`,
  `ui/panels/`, `workspace/`, or `net/`.

  ## Rule for future producers

  `LiveBattleSnapshot` has exactly one producer: `LiveBattleReducer.apply()`, called only from
  `LiveBattleProjection.apply_event()`. A direct mutation of derived state from any other code is a
  defect (`AGENTS.md` rule 5) — and, since M1c, is also a compile error, not just a review finding.
  ```

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/battle/README.md showdownbot_studio/godot/src/battle/dto showdownbot_studio/tests/python/architecture_allowlists/named_value_object_allowlist.txt showdownbot_studio/godot/tests/battle/test_live_battle_snapshot.gd
  git commit -m "feat(studio): add structurally-immutable battle/dto/LiveBattleSnapshot value objects"
  ```

## Task 19 — `LiveBattleReducer`: core folding + determinism

**Files:**
- Create: `showdownbot_studio/godot/src/battle/live_battle_reducer.gd`
- Create: `showdownbot_studio/godot/tests/battle/test_live_battle_reducer_core.gd`

- [ ] Write the failing test. Create `showdownbot_studio/godot/tests/battle/test_live_battle_reducer_core.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func _event(fields: Dictionary) -> ProtocolEventDTO:
  	var e := ProtocolEventDTO.new()
  	for key in fields:
  		e.set(key, fields[key])
  	e.seal()
  	return e


  func test_turn_event_updates_turn_number() -> void:
  	var s := LiveBattleReducer.apply(LiveBattleSnapshot.new(), _event({"event_type": "turn", "turn_number": 3}))
  	assert_int(s.turn).is_equal(3)


  func test_switch_event_sets_slot_species_and_hp() -> void:
  	var e := _event({
  		"event_type": "switch", "pokemon_side": "p1", "pokemon_slot": "a",
  		"pokemon_species": "Pikachu", "hp_current": 100, "hp_maximum": 100, "hp_fainted": false,
  	})
  	var s := LiveBattleReducer.apply(LiveBattleSnapshot.new(), e)
  	var slot := s.get_slot("p1", "a")
  	assert_str(str(slot.species)).is_equal("Pikachu")
  	assert_int(slot.hp_current).is_equal(100)


  func test_damage_event_updates_hp_without_clearing_species() -> void:
  	var initial := LiveBattleReducer.apply(LiveBattleSnapshot.new(), _event({
  		"event_type": "switch", "pokemon_side": "p1", "pokemon_slot": "a",
  		"pokemon_species": "Pikachu", "hp_current": 100, "hp_maximum": 100, "hp_fainted": false,
  	}))
  	var damaged := LiveBattleReducer.apply(initial, _event({
  		"event_type": "-damage", "pokemon_side": "p1", "pokemon_slot": "a",
  		"hp_current": 50, "hp_maximum": 100, "hp_fainted": false, "hp_status": "brn",
  	}))
  	var slot := damaged.get_slot("p1", "a")
  	assert_str(str(slot.species)).is_equal("Pikachu")
  	assert_int(slot.hp_current).is_equal(50)


  func test_faint_event_forces_zero_hp_and_fainted_true() -> void:
  	var initial := LiveBattleReducer.apply(LiveBattleSnapshot.new(), _event({
  		"event_type": "switch", "pokemon_side": "p2", "pokemon_slot": "a",
  		"pokemon_species": "Ditto", "hp_current": 10, "hp_maximum": 100, "hp_fainted": false,
  	}))
  	var fainted := LiveBattleReducer.apply(initial, _event({
  		"event_type": "faint", "pokemon_side": "p2", "pokemon_slot": "a",
  		"hp_current": 0, "hp_fainted": true,
  	}))
  	var slot := fainted.get_slot("p2", "a")
  	assert_int(slot.hp_current).is_equal(0)
  	assert_bool(slot.hp_fainted).is_true()


  func test_unhandled_event_type_returns_snapshot_unchanged() -> void:
  	var s := LiveBattleSnapshot.new()
  	var next := LiveBattleReducer.apply(s, _event({"event_type": "init"}))
  	assert_object(next.turn).is_equal(s.turn)


  func test_determinism_replaying_same_event_list_twice_yields_equal_by_value_snapshots() -> void:
  	var events := [
  		_event({"event_type": "turn", "turn_number": 1}),
  		_event({
  			"event_type": "switch", "pokemon_side": "p1", "pokemon_slot": "a",
  			"pokemon_species": "Pikachu", "hp_current": 100, "hp_maximum": 100, "hp_fainted": false,
  		}),
  	]
  	var first := LiveBattleSnapshot.new()
  	for e in events:
  		first = LiveBattleReducer.apply(first, e)
  	var second := LiveBattleSnapshot.new()
  	for e in events:
  		second = LiveBattleReducer.apply(second, e)
  	assert_int(first.turn).is_equal(second.turn)
  	assert_int(first.get_slot("p1", "a").hp_current).is_equal(second.get_slot("p1", "a").hp_current)
  ```

- [ ] Run and confirm it fails; then write the implementation. Create
  `showdownbot_studio/godot/src/battle/live_battle_reducer.gd`:

  ```gdscript
  class_name LiveBattleReducer
  extends RefCounted

  ## Pure, deterministic fold: apply(previous, event) -> next. Never mutates `previous`
  ## (LiveBattleSnapshot has no setter anywhere). An unmodeled event type returns `previous`
  ## unchanged (spec section 6.1).


  static func apply(previous: LiveBattleSnapshot, event: ProtocolEventDTO) -> LiveBattleSnapshot:
  	match event.event_type:
  		"turn":
  			return previous.with_turn(event.turn_number)
  		"switch", "drag":
  			return _apply_switch(previous, event)
  		"-damage", "-heal":
  			return _apply_hp_change(previous, event)
  		"-status", "-curestatus":
  			return _apply_status(previous, event)
  		"faint":
  			return _apply_faint(previous, event)
  		"-weather":
  			return previous.with_weather(event.condition_label)
  		"-fieldstart":
  			return previous.with_field_condition_added(str(event.condition_label))
  		"-fieldend":
  			return previous.with_field_condition_removed(str(event.condition_label))
  		"-sidestart":
  			return previous.with_side_condition_added(str(event.side), str(event.condition_label))
  		"-sideend":
  			return previous.with_side_condition_removed(str(event.side), str(event.condition_label))
  		"win", "tie":
  			return previous.with_battle_completed()
  		_:
  			return previous


  static func _apply_switch(previous: LiveBattleSnapshot, event: ProtocolEventDTO) -> LiveBattleSnapshot:
  	if event.pokemon_side == null or event.pokemon_slot == null:
  		return previous
  	var slot := LiveBattleSlotSnapshot.new(event.pokemon_species, event.hp_current, event.hp_maximum, event.hp_fainted, event.hp_status)
  	return previous.with_slot(str(event.pokemon_side), str(event.pokemon_slot), slot)


  static func _apply_hp_change(previous: LiveBattleSnapshot, event: ProtocolEventDTO) -> LiveBattleSnapshot:
  	if event.pokemon_side == null or event.pokemon_slot == null:
  		return previous
  	var existing := previous.get_slot(str(event.pokemon_side), str(event.pokemon_slot))
  	var slot := LiveBattleSlotSnapshot.new(
  		existing.species,
  		event.hp_current if event.hp_current != null else existing.hp_current,
  		event.hp_maximum if event.hp_maximum != null else existing.hp_maximum,
  		event.hp_fainted if event.hp_fainted != null else existing.hp_fainted,
  		event.hp_status if event.hp_status != null else existing.hp_status,
  	)
  	return previous.with_slot(str(event.pokemon_side), str(event.pokemon_slot), slot)


  static func _apply_status(previous: LiveBattleSnapshot, event: ProtocolEventDTO) -> LiveBattleSnapshot:
  	if event.pokemon_side == null or event.pokemon_slot == null:
  		return previous
  	var existing := previous.get_slot(str(event.pokemon_side), str(event.pokemon_slot))
  	var slot := LiveBattleSlotSnapshot.new(existing.species, existing.hp_current, existing.hp_maximum, existing.hp_fainted, event.hp_status)
  	return previous.with_slot(str(event.pokemon_side), str(event.pokemon_slot), slot)


  static func _apply_faint(previous: LiveBattleSnapshot, event: ProtocolEventDTO) -> LiveBattleSnapshot:
  	if event.pokemon_side == null or event.pokemon_slot == null:
  		return previous
  	var existing := previous.get_slot(str(event.pokemon_side), str(event.pokemon_slot))
  	var slot := LiveBattleSlotSnapshot.new(existing.species, 0, existing.hp_maximum, true, existing.hp_status)
  	return previous.with_slot(str(event.pokemon_side), str(event.pokemon_slot), slot)
  ```

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/battle/test_live_battle_reducer_core.gd"
  ```

  Expected: `6` tests passed, `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/battle/live_battle_reducer.gd showdownbot_studio/godot/tests/battle/test_live_battle_reducer_core.gd
  git commit -m "feat(studio): add LiveBattleReducer core folding (structurally-immutable snapshots)"
  ```

## Task 20 — `LiveBattleProjection` (single owner of current state + timeline; no reset logic yet)

**Files:**
- Create: `showdownbot_studio/godot/src/battle/live_battle_projection.gd`
- Create: `showdownbot_studio/godot/tests/battle/test_live_battle_projection.gd`

This is the class the review requires so derived state has exactly one owner, inside `battle/`, and
so M1e's reconnect-rebuild work (Task 39) can be done entirely by editing this file — no `workspace/`
change. This task builds `apply_event`/`get_current_snapshot`/`get_timeline` only; the
reset-on-repeat-`init` behavior is added in M1e (Task 39), which is a real, red-first behavior
change to this same file, not something invented here ahead of its own test.

- [ ] Write the failing test. Create `showdownbot_studio/godot/tests/battle/test_live_battle_projection.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func _event(fields: Dictionary) -> ProtocolEventDTO:
  	var e := ProtocolEventDTO.new()
  	for key in fields:
  		e.set(key, fields[key])
  	e.seal()
  	return e


  func test_initial_snapshot_is_empty_and_timeline_is_empty() -> void:
  	var p := LiveBattleProjection.new()
  	assert_int(p.get_timeline().size()).is_equal(0)
  	assert_object(p.get_current_snapshot().turn).is_null()


  func test_apply_event_updates_current_snapshot_and_appends_to_timeline() -> void:
  	var p := LiveBattleProjection.new()
  	p.apply_event(_event({"event_type": "turn", "turn_number": 1}))
  	assert_int(p.get_current_snapshot().turn).is_equal(1)
  	assert_int(p.get_timeline().size()).is_equal(1)


  func test_apply_event_emits_snapshot_published() -> void:
  	var p := LiveBattleProjection.new()
  	var received: Array[LiveBattleSnapshot] = []
  	p.snapshot_published.connect(func(s: LiveBattleSnapshot): received.append(s))
  	p.apply_event(_event({"event_type": "turn", "turn_number": 1}))
  	assert_int(received.size()).is_equal(1)
  	assert_int(received[0].turn).is_equal(1)


  func test_battle_completed_signal_fires_on_win() -> void:
  	var p := LiveBattleProjection.new()
  	var completed_rooms: Array[String] = []
  	p.battle_completed.connect(func(room_id: String): completed_rooms.append(room_id))
  	p.set_room_id("battle-1")
  	p.apply_event(_event({"event_type": "win"}))
  	assert_int(completed_rooms.size()).is_equal(1)
  	assert_str(completed_rooms[0]).is_equal("battle-1")


  func test_get_timeline_returns_an_independent_copy() -> void:
  	var p := LiveBattleProjection.new()
  	p.apply_event(_event({"event_type": "turn", "turn_number": 1}))
  	var timeline := p.get_timeline()
  	timeline.append(_event({"event_type": "turn", "turn_number": 2}))
  	assert_int(p.get_timeline().size()).is_equal(1)
  ```

- [ ] Run and confirm it fails; then write the implementation. Create
  `showdownbot_studio/godot/src/battle/live_battle_projection.gd`:

  ```gdscript
  class_name LiveBattleProjection
  extends RefCounted

  ## The single owner of "current" derived battle state (spec section 4.7's derived-state rule,
  ## applied structurally): workspace/ and ui/panels/ only ever RECEIVE a published
  ## LiveBattleSnapshot; they never hold or compute one themselves. Also owns the parallel
  ## timeline projection so a future reconnect reset (M1e, Task 39) clears both together -- a
  ## decoupled reset would violate "state is rebuilt COMPLETELY," not just board state.

  signal snapshot_published(snapshot: LiveBattleSnapshot)
  signal battle_completed(room_id: String)

  var _current: LiveBattleSnapshot = LiveBattleSnapshot.new()
  var _timeline: Array[ProtocolEventDTO] = []
  var _room_id: String = ""


  func get_current_snapshot() -> LiveBattleSnapshot:
  	return _current


  func get_timeline() -> Array[ProtocolEventDTO]:
  	return _timeline.duplicate()


  ## Set by whoever confirms the room join (M1d's composition root) -- purely for attributing
  ## battle_completed to the right room id; never used for room-membership filtering (that is
  ## the composition root's own job, applied before events reach this class at all, M1d Task 29).
  func set_room_id(room_id: String) -> void:
  	_room_id = room_id


  func apply_event(event: ProtocolEventDTO) -> void:
  	_timeline.append(event)
  	_current = LiveBattleReducer.apply(_current, event)
  	snapshot_published.emit(_current)
  	if _current.battle_completed:
  		battle_completed.emit(_room_id)
  ```

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/battle/test_live_battle_projection.gd"
  ```

  Expected: `5` tests passed, `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/battle/live_battle_projection.gd showdownbot_studio/godot/tests/battle/test_live_battle_projection.gd
  git commit -m "feat(studio): add LiveBattleProjection (single owner of current state + timeline)"
  ```

## Task 21 — `LiveBattleProjection` against the real M1b transcript fixture

**Files:**
- Create: `showdownbot_studio/godot/tests/battle/test_live_battle_projection_local_transcript.gd`

- [ ] Write the test (verification against already-existing production code from Task 16's JSONL
  fixture). Create `showdownbot_studio/godot/tests/battle/test_live_battle_projection_local_transcript.gd`:

  ```gdscript
  extends GdUnitTestSuite

  const _TRANSCRIPT_PATH := "res://../fixtures/live-protocol-v0/local-spectate-01/transcript.jsonl"


  func _fold_transcript() -> LiveBattleProjection:
  	var file := FileAccess.open(_TRANSCRIPT_PATH, FileAccess.READ)
  	var decoder := ProtocolDecoder.new()
  	var projection := LiveBattleProjection.new()
  	decoder.event_decoded.connect(projection.apply_event)
  	while not file.eof_reached():
  		var raw_line := file.get_line()
  		if raw_line.is_empty():
  			continue
  		var frame_obj: Dictionary = JSON.parse_string(raw_line)
  		decoder.decode_frame(str(frame_obj["raw_frame"]))
  	file.close()
  	return projection


  func test_folding_the_real_transcript_ends_with_a_completed_battle() -> void:
  	assert_bool(_fold_transcript().get_current_snapshot().battle_completed).is_true()


  func test_folding_the_real_transcript_twice_yields_equal_by_value_final_turn_numbers() -> void:
  	var first := _fold_transcript()
  	var second := _fold_transcript()
  	assert_object(first.get_current_snapshot().turn).is_equal(second.get_current_snapshot().turn)
  ```

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/battle/test_live_battle_projection_local_transcript.gd"
  ```

  Expected: `2` tests passed, `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/tests/battle/test_live_battle_projection_local_transcript.gd
  git commit -m "test(studio): fold the frozen local transcript through decoder+projection end to end"
  ```

## Task 22 — `LiveBattleReducer`: fail-closed handling of an inconsistent event

**Files:**
- Create: `showdownbot_studio/godot/tests/battle/test_live_battle_reducer_fail_closed.gd`

Unchanged in intent from the first draft — never crash, never invent a value not carried by the
event itself.

- [ ] Write the test. Create `showdownbot_studio/godot/tests/battle/test_live_battle_reducer_fail_closed.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func _event(fields: Dictionary) -> ProtocolEventDTO:
  	var e := ProtocolEventDTO.new()
  	for key in fields:
  		e.set(key, fields[key])
  	e.seal()
  	return e


  func test_damage_event_for_a_slot_never_switched_in_does_not_crash_and_only_sets_given_fields() -> void:
  	var s := LiveBattleReducer.apply(LiveBattleSnapshot.new(), _event({
  		"event_type": "-damage", "pokemon_side": "p2", "pokemon_slot": "b",
  		"hp_current": 40, "hp_maximum": 100,
  	}))
  	var slot := s.get_slot("p2", "b")
  	assert_int(slot.hp_current).is_equal(40)
  	assert_object(slot.species).is_null()


  func test_event_missing_side_or_slot_returns_snapshot_unchanged() -> void:
  	var s := LiveBattleSnapshot.new()
  	var next := LiveBattleReducer.apply(s, _event({"event_type": "-damage", "hp_current": 10}))
  	assert_object(next.get_slot("p1", "a").hp_current).is_equal(s.get_slot("p1", "a").hp_current)


  func test_error_event_never_mutates_battle_state() -> void:
  	var s := LiveBattleSnapshot.new()
  	var next := LiveBattleReducer.apply(s, _event({"event_type": "error", "error_reason": "[Room not found]"}))
  	assert_bool(next.battle_completed).is_equal(s.battle_completed)
  ```

- [ ] Run and confirm it passes without a production change; if it fails, that is a real Task 19
  defect to fix with its own red-then-green evidence:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/battle/test_live_battle_reducer_fail_closed.gd"
  ```

  Expected: `3` tests passed, `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/tests/battle/test_live_battle_reducer_fail_closed.gd
  git commit -m "test(studio): cover LiveBattleReducer fail-closed handling of inconsistent events"
  ```

## Task 23 — M1c gate evidence

**Files:** none (verification only).

- [ ] Full Python suite; full gdUnit suite + truncation check; architecture lane.

- [ ] `git status --porcelain` clean; `git diff --check main` clean.

- [ ] Open the M1c PR. Do not merge until reviewed.

---

# M1d — Direct room-ID spectating

Blocked on M1c merged and gated. New production code lands only in `godot/src/workspace/`
(`LiveClientWorkspace` Connection + Spectator areas) and `godot/src/ui/panels/` (spec §4.4's table
cell for M1d). This is also where the `ObservationEventBus` class is first built (per the recorded
decision above).

**Fixes applied in this revision (all detailed in their own tasks below):** room join/leave now goes
through a privileged `SpectatorRoomGateway`, not straight from the UI to the encoder/transport
(spec §4.2.3); every decoded event is filtered to the currently-joined room before it can affect
anything visible; `|init|battle` vs `|init|chat` is distinguished before a join is ever confirmed as
a battle; `win`/`tie` ends the battle but leaves `RoomState` at `ACTIVE` (only a decoded `deinit`
closes the room); a failed join *send* surfaces an error and returns to `NOT_JOINED` instead of
sticking in `JOINING`; there is exactly one render path (subscribe to the bus, never also call the
panel directly); server-delivered text is length-capped and control-character-sanitized before
display; and `StudioRoot` gets real, clickable navigation to `LiveClientWorkspace` plus a real
"Connect" action — the first draft registered the workspace but never made it reachable.

## Task 24 — `ObservationEventBus`

**Files:**
- Create: `showdownbot_studio/godot/src/workspace/observation_event_bus.gd`
- Create: `showdownbot_studio/schemas/observation-event-bus-v1.md`
- Create: `showdownbot_studio/godot/tests/workspace/test_observation_event_bus.gd`

Unchanged from the first draft.

- [ ] Write the schema doc. Create `showdownbot_studio/schemas/observation-event-bus-v1.md`:

  ```markdown
  # ObservationEventBus events — schema v1

  **Status:** binding (spec section 4.2.2). **Introduced:** M1d.
  `schema_version: {major: 1, minor: 0}`.

  | Event | Payload | Publisher | Subscribers (M1) |
  |---|---|---|---|
  | `connection_state_changed` | `old_state`, `new_state: ConnectionStateMachine.State` | `workspace/`'s composition root, republishing `net/WebSocketTransport.connection_state_changed` | `ui/panels/ConnectionStatusPanel` |
  | `battle_state_published` | `snapshot: LiveBattleSnapshot` | `workspace/`'s composition root, republishing `battle/LiveBattleProjection.snapshot_published` | `ui/panels/BattleBoardPanel`, `ui/panels/LiveBattleLogPanel` |
  | `battle_completed` | `room_id: String` | same composition root, republishing `battle/LiveBattleProjection.battle_completed` | reserved for a future replay-save prompt (M3, not built here) |
  | `chat_received` | not populated in M1 (no chat UI until M2f) | — | — |

  Never carries: battle commands, login/credential data, a mutable session object, or the raw
  `ProtocolEventDTO` stream.
  ```

- [ ] Write the failing test. Create `showdownbot_studio/godot/tests/workspace/test_observation_event_bus.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func test_publish_connection_state_changed_notifies_subscribers() -> void:
  	var bus := ObservationEventBus.new()
  	var received: Array = []
  	bus.connection_state_changed.connect(func(old_state, new_state): received.append([old_state, new_state]))
  	bus.publish_connection_state_changed(ConnectionStateMachine.State.DISCONNECTED, ConnectionStateMachine.State.CONNECTING)
  	assert_int(received.size()).is_equal(1)


  func test_publish_battle_state_published_notifies_subscribers() -> void:
  	var bus := ObservationEventBus.new()
  	var received: Array[LiveBattleSnapshot] = []
  	bus.battle_state_published.connect(func(snapshot: LiveBattleSnapshot): received.append(snapshot))
  	var snapshot := LiveBattleSnapshot.new()
  	bus.publish_battle_state_published(snapshot)
  	assert_int(received.size()).is_equal(1)
  	assert_object(received[0]).is_same(snapshot)


  func test_publish_battle_completed_notifies_subscribers() -> void:
  	var bus := ObservationEventBus.new()
  	var received: Array[String] = []
  	bus.battle_completed.connect(func(room_id: String): received.append(room_id))
  	bus.publish_battle_completed("battle-1")
  	assert_str(received[0]).is_equal("battle-1")
  ```

- [ ] Run and confirm it fails; then write the implementation. Create
  `showdownbot_studio/godot/src/workspace/observation_event_bus.gd`:

  ```gdscript
  class_name ObservationEventBus
  extends RefCounted

  signal connection_state_changed(old_state: ConnectionStateMachine.State, new_state: ConnectionStateMachine.State)
  signal battle_state_published(snapshot: LiveBattleSnapshot)
  signal battle_completed(room_id: String)


  func publish_connection_state_changed(old_state: ConnectionStateMachine.State, new_state: ConnectionStateMachine.State) -> void:
  	connection_state_changed.emit(old_state, new_state)


  func publish_battle_state_published(snapshot: LiveBattleSnapshot) -> void:
  	battle_state_published.emit(snapshot)


  func publish_battle_completed(room_id: String) -> void:
  	battle_completed.emit(room_id)
  ```

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/workspace/test_observation_event_bus.gd"
  ```

  Expected: `3` tests passed, `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/workspace/observation_event_bus.gd showdownbot_studio/schemas/observation-event-bus-v1.md showdownbot_studio/godot/tests/workspace/test_observation_event_bus.gd
  git commit -m "feat(studio): add ObservationEventBus"
  ```

## Task 25 — `LiveBoardPresentationAdapter` + `UntrustedTextSanitizer` (ui/panels/)

**Files:**
- Create: `showdownbot_studio/godot/src/ui/panels/live_board_presentation_adapter.gd`
- Create: `showdownbot_studio/godot/src/ui/panels/untrusted_text_sanitizer.gd`
- Create: `showdownbot_studio/godot/tests/ui/panels/test_live_board_presentation_adapter.gd`
- Create: `showdownbot_studio/godot/tests/ui/panels/test_untrusted_text_sanitizer.gd`

`UntrustedTextSanitizer` is new in this revision: `docs/security/UNTRUSTED_SERVER_CONTENT.md`
requires "control characters are escaped before display" and "message length is capped" — the first
draft never implemented either. Applied at render time (in `ui/panels/`, not decode time in
`protocol/`) because "before display" is literally what the doc says, and what counts as
display-safe is a UI concern, not a parsing one.

- [ ] Write the failing sanitizer test. Create `showdownbot_studio/godot/tests/ui/panels/test_untrusted_text_sanitizer.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func test_control_characters_are_stripped() -> void:
  	var sanitized := UntrustedTextSanitizer.sanitize("hello\x01\x02world")
  	assert_bool(sanitized.contains("\x01")).is_false()
  	assert_str(sanitized).is_equal("helloworld")


  func test_length_is_capped() -> void:
  	var long_text := "a".repeat(1000)
  	var sanitized := UntrustedTextSanitizer.sanitize(long_text)
  	assert_int(sanitized.length()).is_equal(UntrustedTextSanitizer.MAX_LENGTH)


  func test_normal_text_passes_through_unchanged() -> void:
  	assert_str(UntrustedTextSanitizer.sanitize("Alice vs Bob")).is_equal("Alice vs Bob")
  ```

- [ ] Run and confirm it fails; then write the implementation. Create
  `showdownbot_studio/godot/src/ui/panels/untrusted_text_sanitizer.gd`:

  ```gdscript
  class_name UntrustedTextSanitizer
  extends RefCounted

  ## docs/security/UNTRUSTED_SERVER_CONTENT.md: "control characters are escaped before display...
  ## message length is capped." Applied here, at render time, to every server-delivered string
  ## (room titles, player names, log lines) before it reaches a Label/RichTextLabel.

  const MAX_LENGTH := 300


  static func sanitize(raw: String) -> String:
  	var stripped := ""
  	for i in range(raw.length()):
  		var code := raw.unicode_at(i)
  		if code >= 0x20 and code != 0x7F:
  			stripped += raw[i]
  	if stripped.length() > MAX_LENGTH:
  		stripped = stripped.substr(0, MAX_LENGTH)
  	return stripped
  ```

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/ui/panels/test_untrusted_text_sanitizer.gd"
  ```

  Expected: `3` tests passed, `0` failed.

- [ ] Write the failing board-adapter test (mirrors `replay/ReplayBoardPresentationAdapter`'s
  pattern, F0). Create `showdownbot_studio/godot/tests/ui/panels/test_live_board_presentation_adapter.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func test_empty_live_snapshot_is_presentation_available() -> void:
  	var snapshot := LiveBoardPresentationAdapter.build_snapshot(LiveBattleSnapshot.new())
  	assert_bool(snapshot.presentation_available).is_true()


  func test_null_live_snapshot_is_unavailable_with_a_reason() -> void:
  	var snapshot := LiveBoardPresentationAdapter.build_snapshot(null)
  	assert_bool(snapshot.presentation_available).is_false()
  	assert_str(snapshot.empty_state_reason).is_equal("No battle state received yet")


  func test_slot_species_and_hp_carry_over() -> void:
  	var live := LiveBattleSnapshot.new().with_slot("p1", "a", LiveBattleSlotSnapshot.new("Pikachu", 20, 35))
  	var snapshot := LiveBoardPresentationAdapter.build_snapshot(live)
  	var out_slot := snapshot.get_slot("p1", "a")
  	assert_str(str(out_slot.species)).is_equal("Pikachu")
  	assert_int(out_slot.hp_current).is_equal(20)


  func test_turn_and_side_conditions_carry_over() -> void:
  	var live := LiveBattleSnapshot.new().with_turn(3).with_side_condition_added("p1", "Stealth Rock")
  	var snapshot := LiveBoardPresentationAdapter.build_snapshot(live)
  	assert_int(snapshot.turn).is_equal(3)
  	assert_bool(snapshot.side_conditions["p1"].has("Stealth Rock")).is_true()
  ```

- [ ] Run and confirm it fails; then write the implementation. Create
  `showdownbot_studio/godot/src/ui/panels/live_board_presentation_adapter.gd`:

  ```gdscript
  class_name LiveBoardPresentationAdapter
  extends RefCounted

  ## Converts battle/'s LiveBattleSnapshot into replay/'s neutral BattleBoardSnapshot contract
  ## (spec section 4.7), mirroring ReplayBoardPresentationAdapter's pattern (F0). Lives in
  ## ui/panels/ (not replay/, which spec section 4.4's table does not list for M1d).

  const NO_BATTLE_STATE_TEXT := "No battle state received yet"


  static func build_snapshot(live: LiveBattleSnapshot) -> BattleBoardSnapshot:
  	var snapshot := BattleBoardSnapshot.new()
  	if live == null:
  		snapshot.presentation_available = false
  		snapshot.empty_state_reason = NO_BATTLE_STATE_TEXT
  		return snapshot
  	snapshot.presentation_available = true
  	snapshot.empty_state_reason = ""
  	snapshot.turn = live.turn
  	snapshot.weather = live.weather
  	snapshot.terrain = live.terrain
  	snapshot.field_conditions = live.get_field_conditions()
  	for side in ["p1", "p2"]:
  		snapshot.side_conditions[side] = live.get_side_conditions(side)
  		for slot in ["a", "b"]:
  			var live_slot := live.get_slot(side, slot)
  			var out_slot := snapshot.get_slot(side, slot)
  			out_slot.species = live_slot.species
  			out_slot.hp_current = live_slot.hp_current
  			out_slot.hp_maximum = live_slot.hp_maximum
  			out_slot.hp_fainted = live_slot.hp_fainted
  			out_slot.hp_status = live_slot.hp_status
  	return snapshot
  ```

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/ui/panels/"
  ```

  Expected: `7` tests passed (this task's 3 sanitizer + 4 adapter), `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/ui/panels/live_board_presentation_adapter.gd showdownbot_studio/godot/src/ui/panels/untrusted_text_sanitizer.gd showdownbot_studio/godot/tests/ui/panels/test_live_board_presentation_adapter.gd showdownbot_studio/godot/tests/ui/panels/test_untrusted_text_sanitizer.gd
  git commit -m "feat(studio): add LiveBoardPresentationAdapter + UntrustedTextSanitizer"
  ```

## Task 26 — `ui/panels/` board, connection status, and log panels + `ui/README.md`

**Files:**
- Create: `showdownbot_studio/godot/src/ui/panels/README.md`
- Create: `showdownbot_studio/godot/src/ui/panels/battle_board_panel.gd` (+ `.tscn`)
- Create: `showdownbot_studio/godot/src/ui/panels/connection_status_panel.gd` (+ `.tscn`)
- Create: `showdownbot_studio/godot/src/ui/panels/live_battle_log_panel.gd` (+ `.tscn`)
- Create: `showdownbot_studio/godot/tests/ui/panels/test_battle_board_panel.gd`
- Create: `showdownbot_studio/godot/tests/ui/panels/test_connection_status_panel.gd`
- Create: `showdownbot_studio/godot/tests/ui/panels/test_live_battle_log_panel.gd`

**`LiveBattleLogPanel` redesigned in this revision.** The first draft appended one line per event
the panel itself observed directly — a second, independent accumulation of the same data
`LiveBattleProjection`'s timeline already owns, which would double-render after an M1e reconnect
reset (the projection's timeline clears; the panel's own separately-accumulated lines would not).
The panel now **rebuilds its full displayed text from `LiveBattleProjection.get_timeline()`** every
time it is notified (`rebuild_from_timeline`), so a projection reset is automatically reflected with
no second reset path to keep in sync. Server-delivered text (species/room text embedded in a
summary line) is sanitized via Task 25's `UntrustedTextSanitizer` before display.

- [ ] Write the three failing tests. Create `showdownbot_studio/godot/tests/ui/panels/test_battle_board_panel.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func test_bind_renders_through_the_shared_board_view() -> void:
  	var panel: BattleBoardPanel = preload("res://src/ui/panels/battle_board_panel.tscn").instantiate()
  	add_child(panel)
  	var live := LiveBattleSnapshot.new().with_slot("p1", "a", LiveBattleSlotSnapshot.new("Pikachu"))
  	panel.bind(live)
  	assert_str(panel.get_board_view().get_slot_species("p1", "a")).is_equal("Pikachu")
  	panel.free()


  func test_bind_null_shows_empty_state() -> void:
  	var panel: BattleBoardPanel = preload("res://src/ui/panels/battle_board_panel.tscn").instantiate()
  	add_child(panel)
  	panel.bind(null)
  	assert_bool(panel.get_board_view().get_empty_state_visible()).is_true()
  	panel.free()
  ```

  Create `showdownbot_studio/godot/tests/ui/panels/test_connection_status_panel.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func test_shows_connecting_text_on_state_change() -> void:
  	var panel: ConnectionStatusPanel = preload("res://src/ui/panels/connection_status_panel.tscn").instantiate()
  	add_child(panel)
  	panel.on_connection_state_changed(ConnectionStateMachine.State.DISCONNECTED, ConnectionStateMachine.State.CONNECTING)
  	assert_str(panel.get_status_text()).is_equal("Connecting...")
  	panel.free()
  ```

  Create `showdownbot_studio/godot/tests/ui/panels/test_live_battle_log_panel.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func _event(fields: Dictionary) -> ProtocolEventDTO:
  	var e := ProtocolEventDTO.new()
  	for key in fields:
  		e.set(key, fields[key])
  	e.seal()
  	return e


  func test_rebuild_from_timeline_shows_one_line_per_event_without_per_row_nodes() -> void:
  	var panel: LiveBattleLogPanel = preload("res://src/ui/panels/live_battle_log_panel.tscn").instantiate()
  	add_child(panel)
  	var timeline: Array[ProtocolEventDTO] = [_event({"event_type": "turn", "turn_number": 4})]
  	panel.rebuild_from_timeline(timeline)
  	assert_str(panel.get_log_text()).contains("turn 4")
  	assert_int(panel.get_child_count()).is_equal(1)  # the RichTextLabel itself, never one node/row
  	panel.free()


  func test_rebuild_from_timeline_replaces_prior_content_entirely() -> void:
  	var panel: LiveBattleLogPanel = preload("res://src/ui/panels/live_battle_log_panel.tscn").instantiate()
  	add_child(panel)
  	panel.rebuild_from_timeline([_event({"event_type": "turn", "turn_number": 99})])
  	panel.rebuild_from_timeline([_event({"event_type": "turn", "turn_number": 1})])
  	assert_bool(panel.get_log_text().contains("turn 99")).is_false()
  	assert_bool(panel.get_log_text().contains("turn 1")).is_true()
  	panel.free()
  ```

- [ ] Run and confirm all three fail; then write the implementations. Create
  `showdownbot_studio/godot/src/ui/panels/battle_board_panel.gd`:

  ```gdscript
  class_name BattleBoardPanel
  extends Control

  @onready var _board_view: AbstractBoardView = $AbstractBoardView


  func bind(live: LiveBattleSnapshot) -> void:
  	_board_view.bind(LiveBoardPresentationAdapter.build_snapshot(live))


  func get_board_view() -> AbstractBoardView:
  	return _board_view
  ```

  Create `showdownbot_studio/godot/src/ui/panels/battle_board_panel.tscn`:

  ```
  [gd_scene load_steps=3 format=3]

  [ext_resource type="Script" path="res://src/ui/panels/battle_board_panel.gd" id="1_panel"]
  [ext_resource type="PackedScene" path="res://src/replay/abstract_board_view.tscn" id="2_board"]

  [node name="BattleBoardPanel" type="Control"]
  layout_mode = 3
  script = ExtResource("1_panel")

  [node name="AbstractBoardView" parent="." instance=ExtResource("2_board")]
  layout_mode = 1
  ```

  Create `showdownbot_studio/godot/src/ui/panels/connection_status_panel.gd`:

  ```gdscript
  class_name ConnectionStatusPanel
  extends Control

  @onready var _label: Label = $StatusLabel


  func on_connection_state_changed(_old_state: ConnectionStateMachine.State, new_state: ConnectionStateMachine.State) -> void:
  	_label.text = ConnectionStateMachine.describe(new_state)


  func get_status_text() -> String:
  	return _label.text
  ```

  Create `showdownbot_studio/godot/src/ui/panels/connection_status_panel.tscn`:

  ```
  [gd_scene load_steps=2 format=3]

  [ext_resource type="Script" path="res://src/ui/panels/connection_status_panel.gd" id="1_panel"]

  [node name="ConnectionStatusPanel" type="Control"]
  layout_mode = 3
  script = ExtResource("1_panel")

  [node name="StatusLabel" type="Label" parent="."]
  layout_mode = 0
  text = "Disconnected"
  ```

  Create `showdownbot_studio/godot/src/ui/panels/live_battle_log_panel.gd`:

  ```gdscript
  class_name LiveBattleLogPanel
  extends Control

  ## Rebuilds its full displayed text from LiveBattleProjection.get_timeline() every time it is
  ## notified -- never a second, independently-accumulated copy of the same data (which would
  ## double-render after an M1e reconnect reset). Bounded, scrolling: one RichTextLabel, never one
  ## Control per row (ADR-001's "instantiating one Control per unbounded row is prohibited" rule).
  ## Server-delivered species/text is sanitized via UntrustedTextSanitizer before display.

  const MAX_DISPLAYED_LINES := 500

  @onready var _text: RichTextLabel = $LogText


  func rebuild_from_timeline(timeline: Array[ProtocolEventDTO]) -> void:
  	var lines: Array[String] = []
  	for event in timeline:
  		lines.append(_summarize(event))
  	if lines.size() > MAX_DISPLAYED_LINES:
  		lines = lines.slice(lines.size() - MAX_DISPLAYED_LINES, lines.size())
  	_text.text = "\n".join(lines)


  func get_log_text() -> String:
  	return _text.text


  func _summarize(event: ProtocolEventDTO) -> String:
  	match event.event_type:
  		"turn":
  			return "turn %s" % str(event.turn_number)
  		"switch", "drag":
  			var species := UntrustedTextSanitizer.sanitize(str(event.pokemon_species))
  			return "%s%s switched in: %s" % [str(event.pokemon_side), str(event.pokemon_slot), species]
  		"faint":
  			return "%s%s fainted" % [str(event.pokemon_side), str(event.pokemon_slot)]
  		"win", "tie":
  			return "battle ended (%s)" % event.event_type
  		_:
  			return event.event_type
  ```

  Create `showdownbot_studio/godot/src/ui/panels/live_battle_log_panel.tscn`:

  ```
  [gd_scene load_steps=2 format=3]

  [ext_resource type="Script" path="res://src/ui/panels/live_battle_log_panel.gd" id="1_panel"]

  [node name="LiveBattleLogPanel" type="Control"]
  layout_mode = 3
  script = ExtResource("1_panel")

  [node name="LogText" type="RichTextLabel" parent="."]
  layout_mode = 1
  anchor_right = 1.0
  anchor_bottom = 1.0
  scroll_following = true
  ```

- [ ] Run and confirm all pass:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/ui/panels/"
  ```

  Expected: `3` new tests pass (this task's own), `0` failed overall.

- [ ] Write `ui/panels/README.md`. Create `showdownbot_studio/godot/src/ui/panels/README.md`:

  ```markdown
  # UI panels (`godot/src/ui/panels/`)

  ## Purpose

  Board, log, move choice, battle chat, and connection status panels. Renders via
  `BoardPresentationAdapter`-style conversions; never produces protocol text directly, never
  decides legality.

  ## Public interface

  New (M1d):

  - `LiveBoardPresentationAdapter`, `UntrustedTextSanitizer`.
  - `BattleBoardPanel` — wraps `replay/AbstractBoardView` unchanged; `bind(live)`.
  - `ConnectionStatusPanel` — `on_connection_state_changed(old_state, new_state)`.
  - `LiveBattleLogPanel` — `rebuild_from_timeline(timeline: Array[ProtocolEventDTO])`; re-renders
    fully from the projection's timeline every time, never accumulates its own separate copy.
  - `RoomEntryPanel` (Task 27) — direct room-ID/URL entry, no room browser; sends nothing itself —
    it holds a `SpectatorRoomGateway` (Task 28), injected, and calls it.
  - `SpectatorRoomGateway` (Task 28) — the privileged command gateway for room join/leave (spec
    section 4.2.3).

  ## Dependencies

  Depends on `battle/dto/LiveBattleSnapshot`, `protocol/dto/ProtocolEventDTO`,
  `net/ConnectionStateMachine`, `protocol/ProtocolCommandEncoder`, `net/WebSocketTransport`, and
  `replay/`'s `BattleBoardSnapshot`/`AbstractBoardView` (F0 contract, reused unchanged) as direct
  dependencies; subscribes to `workspace/ObservationEventBus` for render-only notifications.

  ## Rule for future producers

  A panel never assembles protocol text itself. `SpectatorRoomGateway` is the only object that
  holds both an encoder call site and a transport reference for room commands, and it is injected
  only into `RoomEntryPanel` — the same four bans spec section 4.2.3 states for
  `HumanBattleCommandGateway` (never on the bus, never in a mod surface, never imported by
  `replay/`/`battle/`/an analysis module, injected only into its one intended UI component).
  ```

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/ui/panels/README.md showdownbot_studio/godot/src/ui/panels/battle_board_panel.gd showdownbot_studio/godot/src/ui/panels/battle_board_panel.tscn showdownbot_studio/godot/src/ui/panels/connection_status_panel.gd showdownbot_studio/godot/src/ui/panels/connection_status_panel.tscn showdownbot_studio/godot/src/ui/panels/live_battle_log_panel.gd showdownbot_studio/godot/src/ui/panels/live_battle_log_panel.tscn showdownbot_studio/godot/tests/ui/panels/test_battle_board_panel.gd showdownbot_studio/godot/tests/ui/panels/test_connection_status_panel.gd showdownbot_studio/godot/tests/ui/panels/test_live_battle_log_panel.gd
  git commit -m "feat(studio): add BattleBoardPanel, ConnectionStatusPanel, LiveBattleLogPanel (rebuild-from-timeline)"
  ```

## Task 27 — `RoomEntryPanel` (gateway-injected via a port interface, no direct encoder/transport access)

**Files:**
- Create: `showdownbot_studio/godot/src/ui/panels/spectator_room_gateway_port.gd`
- Create: `showdownbot_studio/godot/src/ui/panels/room_entry_panel.gd` (+ `.tscn`)
- Create: `showdownbot_studio/godot/tests/ui/panels/test_room_entry_panel.gd`

**Fixed in this revision (first pass).** The first draft had `RoomEntryPanel` emit a
`join_requested(room_id)` signal that the composition root caught and forwarded straight to
`_transport.send_raw_text(ProtocolCommandEncoder.encode_join_room(...))` — the UI reaching the
socket through the composition root, exactly the informal fourth path spec §4.2 forbids. This panel
now holds a gateway, injected via `configure()`, and calls it directly from its own button handler;
there is no `join_requested` signal anymore.

**Fixed in this revision (second pass, small fix #2).** `configure()` originally typed its parameter
as the concrete `SpectatorRoomGateway` class, which a `RefCounted` test fake cannot satisfy without
either subclassing the real gateway (dragging in its `WebSocketTransport`/`RoomStateMachine`
dependencies just to build a fake) or GDScript rejecting the type mismatch. `configure()` now takes
a small `SpectatorRoomGatewayPort` interface — mirroring this plan's existing `SocketPeerPort`
seam pattern (Task 3) exactly — that both the production gateway (Task 28) and any test fake extend.

- [ ] Write the port interface first (no test of its own — it is an abstract seam, exactly like
  `SocketPeerPort`). Create `showdownbot_studio/godot/src/ui/panels/spectator_room_gateway_port.gd`:

  ```gdscript
  class_name SpectatorRoomGatewayPort
  extends RefCounted

  ## Seam between RoomEntryPanel and the real SpectatorRoomGateway, mirroring net/SocketPeerPort's
  ## pattern: a plain, script-defined RefCounted base class that both the production gateway
  ## (Task 28) and a gdUnit test fake can extend, so RoomEntryPanel.configure() never has to name
  ## the concrete gateway type (which a fake cannot satisfy without dragging in its
  ## WebSocketTransport/RoomStateMachine dependencies).

  func join(_intent: RoomJoinIntent) -> void:
  	push_error("SpectatorRoomGatewayPort.join is abstract")


  func leave() -> void:
  	push_error("SpectatorRoomGatewayPort.leave is abstract")
  ```

- [ ] Write the failing test. Create `showdownbot_studio/godot/tests/ui/panels/test_room_entry_panel.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func test_extracts_room_id_from_bare_id() -> void:
  	assert_str(RoomEntryPanel.extract_room_id("battle-1")).is_equal("battle-1")


  func test_extracts_room_id_from_full_url() -> void:
  	assert_str(RoomEntryPanel.extract_room_id("https://play.pokemonshowdown.com/battle-1")).is_equal("battle-1")


  func test_blank_input_extracts_to_empty_string() -> void:
  	assert_str(RoomEntryPanel.extract_room_id("   ")).is_equal("")


  func test_pressing_watch_calls_the_gateways_join_with_a_room_join_intent() -> void:
  	var panel: RoomEntryPanel = preload("res://src/ui/panels/room_entry_panel.tscn").instantiate()
  	add_child(panel)
  	var fake_gateway := _FakeGatewayPort.new()
  	panel.configure(fake_gateway)
  	panel.set_input_text_for_test("battle-1")
  	panel.press_watch_for_test()
  	assert_int(fake_gateway.joined_room_ids.size()).is_equal(1)
  	assert_str(fake_gateway.joined_room_ids[0]).is_equal("battle-1")
  	panel.free()


  func test_on_join_rejected_shows_server_error_text_verbatim_as_plaintext() -> void:
  	var panel: RoomEntryPanel = preload("res://src/ui/panels/room_entry_panel.tscn").instantiate()
  	add_child(panel)
  	panel.on_join_rejected("[Room not found]")
  	assert_str(panel.get_error_text()).is_equal("[Room not found]")
  	panel.free()


  class _FakeGatewayPort:
  	extends SpectatorRoomGatewayPort
  	var joined_room_ids: Array[String] = []

  	func join(intent: RoomJoinIntent) -> void:
  		joined_room_ids.append(intent.room_id)
  ```

- [ ] Run and confirm it fails; then write the implementation. Create
  `showdownbot_studio/godot/src/ui/panels/room_entry_panel.gd`:

  ```gdscript
  class_name RoomEntryPanel
  extends Control

  ## Direct room-ID/URL entry, no fallback room, no room browser (spec section 6.1, section 3.2).
  ## Holds a SpectatorRoomGatewayPort (Task 27/28), injected via configure() -- never a direct
  ## reference to protocol/'s encoder or net/'s transport, and never the concrete SpectatorRoomGateway
  ## type either (so a test fake can satisfy this without the gateway's own dependencies). There is
  ## no join_requested signal: this panel calls the gateway directly from its own button handler.

  @onready var _input: LineEdit = $RoomIdInput
  @onready var _error_label: Label = $ErrorLabel
  @onready var _join_button: Button = $JoinButton

  var _gateway: SpectatorRoomGatewayPort


  func _ready() -> void:
  	_join_button.pressed.connect(_on_join_pressed)


  func configure(gateway: SpectatorRoomGatewayPort) -> void:
  	_gateway = gateway


  static func extract_room_id(raw_input: String) -> String:
  	var trimmed := raw_input.strip_edges()
  	if trimmed.is_empty():
  		return ""
  	if not (trimmed.begins_with("http://") or trimmed.begins_with("https://")):
  		return trimmed
  	var without_trailing_slash := trimmed.rstrip("/")
  	var segments := without_trailing_slash.split("/")
  	return segments[segments.size() - 1]


  func _on_join_pressed() -> void:
  	var room_id := extract_room_id(_input.text)
  	if room_id.is_empty():
  		_error_label.text = "Enter a battle room ID or URL"
  		return
  	_error_label.text = ""
  	_gateway.join(RoomJoinIntent.new(room_id))


  func on_join_rejected(server_error_text: String) -> void:
  	# Untrusted server content: rendered as plain Label text, sanitized before display.
  	_error_label.text = UntrustedTextSanitizer.sanitize(server_error_text)


  func get_error_text() -> String:
  	return _error_label.text


  func set_input_text_for_test(text: String) -> void:
  	_input.text = text


  func press_watch_for_test() -> void:
  	_on_join_pressed()
  ```

  Create `showdownbot_studio/godot/src/ui/panels/room_entry_panel.tscn`:

  ```
  [gd_scene load_steps=2 format=3]

  [ext_resource type="Script" path="res://src/ui/panels/room_entry_panel.gd" id="1_panel"]

  [node name="RoomEntryPanel" type="Control"]
  layout_mode = 3
  script = ExtResource("1_panel")

  [node name="RoomIdInput" type="LineEdit" parent="."]
  layout_mode = 0
  placeholder_text = "battle room ID or URL"

  [node name="JoinButton" type="Button" parent="."]
  layout_mode = 0
  text = "Watch"

  [node name="ErrorLabel" type="Label" parent="."]
  layout_mode = 0
  text = ""
  ```

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/ui/panels/test_room_entry_panel.gd"
  ```

  Expected: `5` tests passed, `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/ui/panels/spectator_room_gateway_port.gd showdownbot_studio/godot/src/ui/panels/room_entry_panel.gd showdownbot_studio/godot/src/ui/panels/room_entry_panel.tscn showdownbot_studio/godot/tests/ui/panels/test_room_entry_panel.gd
  git commit -m "feat(studio): add RoomEntryPanel (gateway-port-injected, no direct encoder/transport access)"
  ```

## Task 28 — `SpectatorRoomGateway` + `RoomJoinIntent` (handles human join AND system rejoin)

**Files:**
- Create: `showdownbot_studio/godot/src/ui/panels/spectator_room_gateway.gd`
- Create: `showdownbot_studio/godot/src/ui/panels/room_join_intent.gd`
- Create: `showdownbot_studio/godot/tests/ui/panels/test_spectator_room_gateway.gd`

Spec §4.2.3: "Room join/leave, chat send, challenge/ladder, and timer/forfeit/undo commands each go
through their own narrowly scoped gateway instance following the identical four bans" — this is that
gateway for room join/leave, the first one this codebase builds. `SpectatorRoomGateway` extends
`SpectatorRoomGatewayPort` (Task 27) and is the **only** object that holds both
`net/WebSocketTransport` (to send) and `protocol/RoomStateMachine` (to validate state before sending,
and to record a local send failure). It is injected only into `RoomEntryPanel`.

**Fixed in this revision (owner re-review, 2026-07-25, second pass, item C).** The first pass's
design had `RoomStateMachine` itself call `_transport.send_raw_text(ProtocolCommandEncoder...)`
directly on an automatic reconnect-rejoin, bypassing this gateway entirely — a second outbound send
path for the exact same command family spec §4.2.3 says has "their own narrowly scoped gateway
instance," and one that never checked or reacted to a send failure. Fixed here: this gateway now
**also** subscribes to `RoomStateMachine.automatic_rejoin_requested` (declared in Task 11, not
emitted until M1e's Task 37) and reacts to it through the exact same send-and-check-failure code
path `join()` already uses — `SpectatorRoomGateway` is now the sole sender for both a human-clicked
"Watch" and a system-triggered reconnect rejoin. Wiring this subscription here, in M1d, rather than
in M1e, is deliberate: M1e's own normative module list is `net/`, `protocol/`, `battle/` only (spec
§4.4); Task 37 only ever needs to *emit* a signal from a `protocol/` file, never to *touch*
`ui/panels/` again — this task's subscription is what makes that possible, exactly the "move the
subscription wiring into an M1d task that M1e activates" resolution the review asked for.

- [ ] Write the failing test — including the reaction to `automatic_rejoin_requested`, exercised
  directly by emitting it (this class's own test does not need `RoomStateMachine`'s M1e emission
  logic to exist yet; it only needs the signal itself, already declared in Task 11). Create
  `showdownbot_studio/godot/tests/ui/panels/test_spectator_room_gateway.gd`:

  ```gdscript
  extends GdUnitTestSuite

  var _fake: FakeSocketPeerPort
  var _transport: WebSocketTransport
  var _room_state_machine: RoomStateMachine
  var _gateway: SpectatorRoomGateway


  func before_test() -> void:
  	_fake = FakeSocketPeerPort.new()
  	_transport = WebSocketTransport.new(func(): return _fake)
  	add_child(_transport)
  	_room_state_machine = RoomStateMachine.new(_transport)
  	_gateway = SpectatorRoomGateway.new(_transport, _room_state_machine)


  func after_test() -> void:
  	remove_child(_transport)
  	_transport.free()


  func test_join_while_connected_sends_the_encoded_command_and_moves_to_joining() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(0.016)
  	_gateway.join(RoomJoinIntent.new("battle-1"))
  	assert_int(_fake.sent_texts.size()).is_equal(1)
  	assert_str(_fake.sent_texts[0]).is_equal("|/join battle-1")
  	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.JOINING)


  func test_join_while_disconnected_fails_the_send_and_returns_to_not_joined_with_an_error() -> void:
  	_gateway.join(RoomJoinIntent.new("battle-1"))
  	assert_int(_fake.sent_texts.size()).is_equal(0)
  	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)
  	assert_bool(_room_state_machine.get_last_error_reason().length() > 0).is_true()


  func test_leave_while_active_sends_the_encoded_command() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(0.016)
  	_gateway.join(RoomJoinIntent.new("battle-1"))
  	_room_state_machine.join_confirmed()
  	_gateway.leave()
  	assert_str(_fake.sent_texts[1]).is_equal("|/leave battle-1")


  func test_leave_send_failure_calls_leave_send_failed_on_the_room_state_machine() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(0.016)
  	_gateway.join(RoomJoinIntent.new("battle-1"))
  	_room_state_machine.join_confirmed()
  	_transport.disconnect_from_server()  # send_raw_text now fails (not CONNECTED)
  	_gateway.leave()
  	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.ACTIVE)
  	assert_bool(_room_state_machine.get_last_error_reason().length() > 0).is_true()


  func test_automatic_rejoin_requested_sends_the_same_join_command_as_a_human_join() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(0.016)
  	# Exercised directly, decoupled from RoomStateMachine actually emitting it on a real
  	# reconnect (that emission is Task 37's, M1e) -- this test only proves the gateway's own
  	# reaction, through the exact same send path join() uses.
  	_room_state_machine.automatic_rejoin_requested.emit("battle-1")
  	assert_int(_fake.sent_texts.size()).is_equal(1)
  	assert_str(_fake.sent_texts[0]).is_equal("|/join battle-1")


  func test_automatic_rejoin_send_failure_calls_join_send_failed() -> void:
  	# Not connected -- send_raw_text fails.
  	_room_state_machine.request_join("battle-1")  # pure transition only, mirrors a resend already in JOINING
  	_room_state_machine.automatic_rejoin_requested.emit("battle-1")
  	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)
  ```

- [ ] Run and confirm it fails; then write the implementation. Create
  `showdownbot_studio/godot/src/ui/panels/room_join_intent.gd`:

  ```gdscript
  class_name RoomJoinIntent
  extends RefCounted

  var room_id: String


  func _init(p_room_id: String) -> void:
  	room_id = p_room_id
  ```

  Create `showdownbot_studio/godot/src/ui/panels/spectator_room_gateway.gd`:

  ```gdscript
  class_name SpectatorRoomGateway
  extends SpectatorRoomGatewayPort

  ## Privileged command gateway for room join/leave (spec section 4.2.3's "narrowly scoped
  ## sibling" gateways). Holds both net/'s transport and protocol/'s RoomStateMachine -- the only
  ## object in the application that does. Injected only into RoomEntryPanel (ui/panels/). Four
  ## bans, identical to HumanBattleCommandGateway's own (spec section 4.2.3): never registered on
  ## or discoverable through the ObservationEventBus; never part of any mod attachment surface;
  ## never imported by replay/, battle/, or any future analysis module; injected only into the
  ## intended UI component.
  ##
  ## Handles BOTH a human-clicked "Watch"/"Leave" and a system-triggered automatic reconnect
  ## rejoin (RoomStateMachine.automatic_rejoin_requested, emitted by M1e's Task 37) through the
  ## SAME send-and-check-failure code path -- this is the only object anywhere that ever calls
  ## send_raw_text() for a room command, regardless of what triggered it (owner re-review,
  ## 2026-07-25, second pass, item C). GDScript cannot enforce this at the language level --
  ## upheld by injection discipline and review, the same honesty note spec section 4.2.3 states
  ## for HumanBattleCommandGateway.

  var _transport: WebSocketTransport
  var _room_state_machine: RoomStateMachine


  func _init(transport: WebSocketTransport, room_state_machine: RoomStateMachine) -> void:
  	_transport = transport
  	_room_state_machine = room_state_machine
  	_room_state_machine.automatic_rejoin_requested.connect(_on_automatic_rejoin_requested)


  func join(intent: RoomJoinIntent) -> void:
  	if not _room_state_machine.request_join(intent.room_id):
  		return
  	_send_join_command(intent.room_id)


  func leave() -> void:
  	var room_id := _room_state_machine.get_room_id()
  	if not _room_state_machine.request_leave():
  		return
  	var err := _transport.send_raw_text(ProtocolCommandEncoder.encode_leave_room(room_id))
  	if err != OK:
  		_room_state_machine.leave_send_failed()


  ## System-triggered rejoin: RoomStateMachine has already transitioned ACTIVE -> JOINING itself
  ## (connection_reconnecting()), so no request_join() call is needed or valid here -- only the
  ## send, through the identical path a human join uses.
  func _on_automatic_rejoin_requested(room_id: String) -> void:
  	_send_join_command(room_id)


  func _send_join_command(room_id: String) -> void:
  	var err := _transport.send_raw_text(ProtocolCommandEncoder.encode_join_room(room_id))
  	if err != OK:
  		_room_state_machine.join_send_failed()
  ```

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/ui/panels/test_spectator_room_gateway.gd"
  ```

  Expected: `6` tests passed, `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/ui/panels/spectator_room_gateway.gd showdownbot_studio/godot/src/ui/panels/room_join_intent.gd showdownbot_studio/godot/tests/ui/panels/test_spectator_room_gateway.gd
  git commit -m "feat(studio): add SpectatorRoomGateway (handles human join AND system rejoin, spec section 4.2.3)"
  ```

## Task 29 — `LiveClientWorkspace`: composition root with room isolation and a single render path

**Files:**
- Create: `showdownbot_studio/godot/src/workspace/live_client_workspace.gd` (+ `.tscn`)
- Create: `showdownbot_studio/godot/tests/workspace/test_live_client_workspace.gd`

**Fixes applied in this task (first pass):** the composition root never calls `send_raw_text`
itself — it constructs `SpectatorRoomGateway` and injects it into `RoomEntryPanel`; every decoded
event is filtered on `event.room_id` before it can reach the projection or the log panel;
`|init|battle` (not `|init|chat`) is what confirms a battle join; `win`/`tie` publish
`battle_completed` but do **not** close the room; a rejected/failed join calls
`RoomEntryPanel.on_join_rejected()` with the reason `RoomStateMachine` now records; there is exactly
one render path (panels subscribe to the bus; the composition root never also calls them directly).

**Fixed in this revision (second pass, item B).** The version originally drafted for this task
handled a confirmed battle `init` by calling `_room_state_machine.rejoin_confirmed()` and
`_projection.set_room_id(...)`, then `return`ed — **never calling `_projection.apply_event(event)`
at all**. `battle/LiveBattleProjection`'s M1e repeat-`init` reset (Task 38) can only ever fire if the
projection actually *sees* every `init` event, including the first one (to set `_has_seen_init`) and
every later one (to detect the repeat and reset). With the original wiring, the projection would
never observe an `init` at all in real use, and Task 38's own reset logic — however correct in
isolation — could never fire through the real wiring. Fixed: a confirmed battle `init` now also
calls `_projection.apply_event(event)`, exactly like every other in-room event.

**Fixed in this revision (second pass, item D).** `deinit` originally always called
`_room_state_machine.server_closed_room()` unconditionally, which is valid only from `ACTIVE`. If a
`deinit` arrives while a human-initiated `leave()` was already in flight (`RoomState.LEAVING`),
`server_closed_room()` silently does nothing (wrong precondition), leaving the room stuck in
`LEAVING` forever — the server closing the room and the user's own leave request racing each other,
with the loser wedging the state machine. Fixed with state-aware dispatch: `deinit` while `LEAVING`
calls `leave_confirmed()` (→ `NOT_JOINED`, the leave the user asked for, now confirmed by the room
actually going away); `deinit` while `ACTIVE` still calls `server_closed_room()` (→ `CLOSED`, the
server closed the room out from under a spectator who never asked to leave).

**Fixed in this revision (second pass, small fix #1).** `configure_transport_for_test()` called the
same `_wire()` used by `_ready()`, which re-ran the one-time domain/UI signal connections (bus →
panels, decoder → `_on_event_decoded`) a second time whenever a test swapped the transport — every
subsequent event would have been processed twice by those subscriptions. `_wire()` is split into
`_wire_transport()` (transport-dependent; re-run safely on every swap) and `_wire_domain_and_ui()`
(one-time; run only from `_ready()`).

- [ ] Write the failing test. Create `showdownbot_studio/godot/tests/workspace/test_live_client_workspace.gd`:

  ```gdscript
  extends GdUnitTestSuite

  var _fake: FakeSocketPeerPort
  var _workspace: LiveClientWorkspace


  func before_test() -> void:
  	_fake = FakeSocketPeerPort.new()
  	_workspace = preload("res://src/workspace/live_client_workspace.tscn").instantiate()
  	add_child(_workspace)
  	_workspace.configure_transport_for_test(func(): return _fake)


  func after_test() -> void:
  	remove_child(_workspace)
  	_workspace.free()


  func _connect_and_open() -> void:
  	_workspace.get_transport().connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_workspace.get_transport()._process(0.016)


  func test_watch_sends_the_join_command_through_the_gateway_not_directly() -> void:
  	_connect_and_open()
  	_workspace.get_room_entry_panel().set_input_text_for_test("battle-1")
  	_workspace.get_room_entry_panel().press_watch_for_test()
  	assert_int(_fake.sent_texts.size()).is_equal(1)
  	assert_str(_fake.sent_texts[0]).is_equal("|/join battle-1")


  func test_init_battle_confirms_join_and_battle_frames_render() -> void:
  	_connect_and_open()
  	_workspace.get_room_entry_panel().set_input_text_for_test("battle-1")
  	_workspace.get_room_entry_panel().press_watch_for_test()
  	_fake.queued_packets = [
  		">battle-1\n|init|battle",
  		">battle-1\n|switch|p1a: Pikachu|Pikachu, L50, M|100/100",
  	]
  	_workspace.get_transport()._process(0.016)
  	assert_int(_workspace.get_room_state_machine().get_state()).is_equal(RoomStateMachine.State.ACTIVE)
  	assert_str(_workspace.get_battle_board_panel().get_board_view().get_slot_species("p1", "a")).is_equal("Pikachu")


  func test_init_chat_does_not_confirm_a_battle_join() -> void:
  	_connect_and_open()
  	_workspace.get_room_entry_panel().set_input_text_for_test("some-room")
  	_workspace.get_room_entry_panel().press_watch_for_test()
  	_fake.queued_packets = [">some-room\n|init|chat"]
  	_workspace.get_transport()._process(0.016)
  	assert_int(_workspace.get_room_state_machine().get_state()).is_not_equal(RoomStateMachine.State.ACTIVE)


  func test_events_for_a_different_room_are_ignored() -> void:
  	_connect_and_open()
  	_workspace.get_room_entry_panel().set_input_text_for_test("battle-1")
  	_workspace.get_room_entry_panel().press_watch_for_test()
  	_fake.queued_packets = [">battle-1\n|init|battle"]
  	_workspace.get_transport()._process(0.016)
  	_fake.queued_packets = [">some-other-room\n|switch|p1a: Ditto|Ditto|50/50"]
  	_workspace.get_transport()._process(0.016)
  	assert_object(_workspace.get_battle_board_panel().get_board_view().get_slot_species("p1", "a")).is_not_equal("Ditto")


  func test_win_publishes_completion_but_does_not_close_the_room() -> void:
  	_connect_and_open()
  	_workspace.get_room_entry_panel().set_input_text_for_test("battle-1")
  	_workspace.get_room_entry_panel().press_watch_for_test()
  	_fake.queued_packets = [">battle-1\n|init|battle"]
  	_workspace.get_transport()._process(0.016)
  	_fake.queued_packets = [">battle-1\n|win|Alice"]
  	_workspace.get_transport()._process(0.016)
  	assert_int(_workspace.get_room_state_machine().get_state()).is_equal(RoomStateMachine.State.ACTIVE)


  func test_deinit_while_active_closes_the_room() -> void:
  	_connect_and_open()
  	_workspace.get_room_entry_panel().set_input_text_for_test("battle-1")
  	_workspace.get_room_entry_panel().press_watch_for_test()
  	_fake.queued_packets = [">battle-1\n|init|battle"]
  	_workspace.get_transport()._process(0.016)
  	_fake.queued_packets = [">battle-1\n|deinit"]
  	_workspace.get_transport()._process(0.016)
  	assert_int(_workspace.get_room_state_machine().get_state()).is_equal(RoomStateMachine.State.CLOSED)


  func test_deinit_while_leaving_confirms_the_leave_instead_of_closing() -> void:
  	# A deinit racing an already-in-flight human leave() must not try server_closed_room()
  	# (invalid from LEAVING, silently a no-op) and leave RoomState stuck in LEAVING forever.
  	_connect_and_open()
  	_workspace.get_room_entry_panel().set_input_text_for_test("battle-1")
  	_workspace.get_room_entry_panel().press_watch_for_test()
  	_fake.queued_packets = [">battle-1\n|init|battle"]
  	_workspace.get_transport()._process(0.016)
  	_workspace.get_room_state_machine().request_leave()  # simulate a leave already in flight
  	assert_int(_workspace.get_room_state_machine().get_state()).is_equal(RoomStateMachine.State.LEAVING)
  	_fake.queued_packets = [">battle-1\n|deinit"]
  	_workspace.get_transport()._process(0.016)
  	assert_int(_workspace.get_room_state_machine().get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)


  func test_confirmed_battle_init_is_forwarded_to_the_projection() -> void:
  	# Proves item B's fix directly: the confirmed `init` event itself must reach
  	# LiveBattleProjection.apply_event() (checked via the projection's own timeline), not just
  	# the events that follow it -- otherwise Task 38's (M1e) reset-on-repeat-init logic could
  	# never fire through this real wiring, no matter how correct it is in isolation.
  	_connect_and_open()
  	_workspace.get_room_entry_panel().set_input_text_for_test("battle-1")
  	_workspace.get_room_entry_panel().press_watch_for_test()
  	_fake.queued_packets = [">battle-1\n|init|battle"]
  	_workspace.get_transport()._process(0.016)
  	assert_int(_workspace.get_projection_for_test().get_timeline().size()).is_equal(1)
  	assert_str(_workspace.get_projection_for_test().get_timeline()[0].event_type).is_equal("init")


  func test_unknown_room_error_rejects_join_and_shows_error_text() -> void:
  	_connect_and_open()
  	_workspace.get_room_entry_panel().set_input_text_for_test("battle-missing")
  	_workspace.get_room_entry_panel().press_watch_for_test()
  	_fake.queued_packets = [">battle-missing\n|error|[Room not found]"]
  	_workspace.get_transport()._process(0.016)
  	assert_int(_workspace.get_room_state_machine().get_state()).is_equal(RoomStateMachine.State.NOT_JOINED)
  	assert_str(_workspace.get_room_entry_panel().get_error_text()).is_equal("[Room not found]")


  func test_connection_state_changes_reach_the_status_panel_via_the_bus() -> void:
  	_workspace.get_transport().connect_to_server("ws://localhost:8000/showdown/websocket")
  	assert_str(_workspace.get_connection_status_panel().get_status_text()).is_equal("Connecting...")
  ```

- [ ] Run and confirm it fails; then write the implementation. Create
  `showdownbot_studio/godot/src/workspace/live_client_workspace.gd`:

  ```gdscript
  class_name LiveClientWorkspace
  extends Control

  ## Connection + Spectator areas (spec section 4.6). Holds no derived battle state itself
  ## (battle/LiveBattleProjection owns that); composes modules and routes already-published values
  ## only. Room join/leave never reaches net/'s transport except through SpectatorRoomGateway.

  const SHOWDOWN_WEBSOCKET_URL := "wss://sim3.psim.us/showdown/websocket"

  @onready var _room_entry_panel: RoomEntryPanel = $RoomEntryPanel
  @onready var _connection_status_panel: ConnectionStatusPanel = $ConnectionStatusPanel
  @onready var _battle_board_panel: BattleBoardPanel = $BattleBoardPanel
  @onready var _live_battle_log_panel: LiveBattleLogPanel = $LiveBattleLogPanel

  var _transport: WebSocketTransport
  var _decoder := ProtocolDecoder.new()
  var _room_state_machine: RoomStateMachine
  var _gateway: SpectatorRoomGateway
  var _projection := LiveBattleProjection.new()
  var _bus := ObservationEventBus.new()


  func _ready() -> void:
  	_transport = WebSocketTransport.new()
  	add_child(_transport)
  	_wire_domain_and_ui()  # one-time only -- never re-run, see this task's small-fix-#1 note
  	_wire_transport()


  func configure_transport_for_test(peer_factory: Callable) -> void:
  	remove_child(_transport)
  	_transport.free()
  	_transport = WebSocketTransport.new(peer_factory)
  	add_child(_transport)
  	_wire_transport()  # transport-dependent only -- safe to re-run on every swap


  ## Depends on _transport, so it is re-run every time _transport is replaced
  ## (configure_transport_for_test). Constructs RoomStateMachine/SpectatorRoomGateway fresh each
  ## time, since both hold a reference to the specific transport instance.
  func _wire_transport() -> void:
  	_room_state_machine = RoomStateMachine.new(_transport)
  	_gateway = SpectatorRoomGateway.new(_transport, _room_state_machine)
  	_room_entry_panel.configure(_gateway)
  	_transport.connection_state_changed.connect(_on_connection_state_changed)
  	_transport.raw_text_received.connect(_decoder.decode_frame)


  ## One-time wiring only: connects _decoder (a fixed instance, never recreated) and _bus (ditto)
  ## to their subscribers. Fixed in this revision (small fix #1): this used to be part of the same
  ## _wire() that also ran on every configure_transport_for_test() call, which reconnected these
  ## signals a second time and processed every subsequent event twice.
  func _wire_domain_and_ui() -> void:
  	_decoder.event_decoded.connect(_on_event_decoded)
  	_bus.connection_state_changed.connect(_connection_status_panel.on_connection_state_changed)
  	_bus.battle_state_published.connect(_battle_board_panel.bind)
  	_bus.battle_state_published.connect(_on_battle_state_published_for_log)


  func _on_battle_state_published_for_log(_snapshot: LiveBattleSnapshot) -> void:
  	_live_battle_log_panel.rebuild_from_timeline(_projection.get_timeline())


  func connect_to_showdown() -> void:
  	_transport.connect_to_server(SHOWDOWN_WEBSOCKET_URL)


  func get_transport() -> WebSocketTransport:
  	return _transport


  func get_room_entry_panel() -> RoomEntryPanel:
  	return _room_entry_panel


  func get_connection_status_panel() -> ConnectionStatusPanel:
  	return _connection_status_panel


  func get_battle_board_panel() -> BattleBoardPanel:
  	return _battle_board_panel


  func get_room_state_machine() -> RoomStateMachine:
  	return _room_state_machine


  func get_projection_for_test() -> LiveBattleProjection:
  	return _projection


  func _on_connection_state_changed(old_state: ConnectionStateMachine.State, new_state: ConnectionStateMachine.State) -> void:
  	_bus.publish_connection_state_changed(old_state, new_state)


  func _on_event_decoded(event: ProtocolEventDTO) -> void:
  	if event.event_type == "error" and _room_state_machine.get_state() == RoomStateMachine.State.JOINING:
  		_room_state_machine.join_rejected(str(event.error_reason))
  		_room_entry_panel.on_join_rejected(str(event.error_reason))
  		return
  	# Room isolation: an event for any room other than the one this workspace joined never
  	# reaches the projection or the log -- the socket is shared across whatever rooms the server
  	# multiplexes over it, but this UI shows exactly one room.
  	if event.room_id != _room_state_machine.get_room_id():
  		return
  	if event.event_type == "init":
  		if str(event.condition_label) != "battle":
  			return  # a non-battle init (e.g. "chat") never confirms a battle join
  		_room_state_machine.rejoin_confirmed()
  		_projection.set_room_id(event.room_id)
  		# Fixed (item B): the init event itself must reach the projection too -- Task 38's (M1e)
  		# reset-on-repeat-init logic can only ever fire if the projection actually sees every
  		# init, including this one.
  		_projection.apply_event(event)
  		_bus.publish_battle_state_published(_projection.get_current_snapshot())
  		return
  	if event.event_type == "deinit":
  		# Fixed (item D): state-aware dispatch. A deinit while a human leave() is already in
  		# flight (LEAVING) confirms that leave, rather than calling server_closed_room() -- which
  		# is invalid from LEAVING and would silently no-op, wedging RoomState forever.
  		if _room_state_machine.get_state() == RoomStateMachine.State.LEAVING:
  			_room_state_machine.leave_confirmed()
  		elif _room_state_machine.get_state() == RoomStateMachine.State.ACTIVE:
  			_room_state_machine.server_closed_room()
  		return
  	_projection.apply_event(event)
  	_bus.publish_battle_state_published(_projection.get_current_snapshot())
  	if _projection.get_current_snapshot().battle_completed:
  		_bus.publish_battle_completed(event.room_id)
  ```

  Create `showdownbot_studio/godot/src/workspace/live_client_workspace.tscn`:

  ```
  [gd_scene load_steps=5 format=3]

  [ext_resource type="Script" path="res://src/workspace/live_client_workspace.gd" id="1_workspace"]
  [ext_resource type="PackedScene" path="res://src/ui/panels/room_entry_panel.tscn" id="2_entry"]
  [ext_resource type="PackedScene" path="res://src/ui/panels/connection_status_panel.tscn" id="3_status"]
  [ext_resource type="PackedScene" path="res://src/ui/panels/battle_board_panel.tscn" id="4_board"]
  [ext_resource type="PackedScene" path="res://src/ui/panels/live_battle_log_panel.tscn" id="5_log"]

  [node name="LiveClientWorkspace" type="Control"]
  layout_mode = 3
  anchors_preset = 15
  anchor_right = 1.0
  anchor_bottom = 1.0
  script = ExtResource("1_workspace")

  [node name="RoomEntryPanel" parent="." instance=ExtResource("2_entry")]
  layout_mode = 1

  [node name="ConnectionStatusPanel" parent="." instance=ExtResource("3_status")]
  layout_mode = 1

  [node name="BattleBoardPanel" parent="." instance=ExtResource("4_board")]
  layout_mode = 1

  [node name="LiveBattleLogPanel" parent="." instance=ExtResource("5_log")]
  layout_mode = 1
  ```

- [ ] Run and confirm everything passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/workspace/"
  ```

  Expected: `11` new tests pass, `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/workspace/live_client_workspace.gd showdownbot_studio/godot/src/workspace/live_client_workspace.tscn showdownbot_studio/godot/tests/workspace/test_live_client_workspace.gd
  git commit -m "feat(studio): add LiveClientWorkspace with room isolation, a single render path, and state-aware deinit dispatch"
  ```

## Task 30 — `StudioRoot`: reachable navigation + a real Connect action

**Files:**
- Modify: `showdownbot_studio/godot/src/workspace/studio_root.gd`
- Modify: `showdownbot_studio/godot/src/workspace/studio_root.tscn`
- Modify: `showdownbot_studio/godot/tests/workspace/test_studio_root.gd`
- Create: `showdownbot_studio/godot/tests/workspace/test_studio_root_live_client_navigation.gd`

**Fixed in this revision.** The first draft registered `LiveClientWorkspace` with `WorkspaceRouter`
but never gave a user any way to actually reach it or connect — `WorkspaceRouter.show_workspace()`
and `WebSocketTransport.connect_to_server()` were only ever called from tests. `StudioRoot` now has
two visible buttons: one that switches to `LiveClientWorkspace`, and (inside that workspace once
switched-to) a real "Connect" button wired to `connect_to_showdown()`.

- [ ] Write the failing test. Create
  `showdownbot_studio/godot/tests/workspace/test_studio_root_live_client_navigation.gd`:

  ```gdscript
  extends GdUnitTestSuite

  const _STUDIO_ROOT_SCENE := preload("res://src/workspace/studio_root.tscn")


  func after_test() -> void:
  	for child in get_children():
  		if child is StudioRoot:
  			remove_child(child)
  			child.free()


  func test_clicking_live_client_nav_button_switches_the_active_workspace() -> void:
  	var root: StudioRoot = _STUDIO_ROOT_SCENE.instantiate()
  	add_child(root)
  	await await_idle_frame()
  	root.get_live_client_nav_button().pressed.emit()
  	assert_str(root.get_router().get_active_workspace_id()).is_equal(StudioRoot.LIVE_CLIENT_WORKSPACE_ID)


  func test_connect_button_inside_live_client_workspace_calls_connect_to_showdown() -> void:
  	var root: StudioRoot = _STUDIO_ROOT_SCENE.instantiate()
  	add_child(root)
  	await await_idle_frame()
  	root.get_live_client_nav_button().pressed.emit()
  	root.get_live_client_workspace().get_connect_button_for_test().pressed.emit()
  	assert_int(root.get_live_client_workspace().get_transport().get_state()).is_equal(ConnectionStateMachine.State.CONNECTING)
  ```

- [ ] Run and confirm it fails; then edit `showdownbot_studio/godot/src/workspace/live_client_workspace.gd`
  to add a real Connect button and expose it for the test:

  ```gdscript
  @onready var _connect_button: Button = $ConnectButton
  ```

  ```gdscript
  func _ready() -> void:
  	_transport = WebSocketTransport.new()
  	add_child(_transport)
  	_wire_domain_and_ui()
  	_wire_transport()
  	_connect_button.pressed.connect(connect_to_showdown)
  ```

  ```gdscript
  func get_connect_button_for_test() -> Button:
  	return _connect_button
  ```

  Add the button node to `live_client_workspace.tscn` (append inside `[node name="LiveClientWorkspace" ...]`'s children):

  ```
  [node name="ConnectButton" type="Button" parent="."]
  layout_mode = 1
  text = "Connect"
  ```

- [ ] Edit `showdownbot_studio/godot/src/workspace/studio_root.gd`, adding a nav bar with two
  buttons and a getter for the test:

  ```gdscript
  const LIVE_CLIENT_WORKSPACE_ID := "live_client"

  @onready var _live_client: LiveClientWorkspace = $WorkspaceRouter/LiveClientWorkspace
  @onready var _offline_viewer_nav_button: Button = $NavBar/OfflineViewerButton
  @onready var _live_client_nav_button: Button = $NavBar/LiveClientButton
  ```

  ```gdscript
  func _ready() -> void:
  	_router.register_workspace(OFFLINE_VIEWER_WORKSPACE_ID, _offline_viewer)
  	_router.register_workspace(LIVE_CLIENT_WORKSPACE_ID, _live_client)
  	_router.show_workspace(OFFLINE_VIEWER_WORKSPACE_ID)
  	_offline_viewer_nav_button.pressed.connect(func(): _router.show_workspace(OFFLINE_VIEWER_WORKSPACE_ID))
  	_live_client_nav_button.pressed.connect(func(): _router.show_workspace(LIVE_CLIENT_WORKSPACE_ID))
  ```

  ```gdscript
  func get_live_client_workspace() -> LiveClientWorkspace:
  	return _live_client


  func get_live_client_nav_button() -> Button:
  	return _live_client_nav_button
  ```

  Edit `showdownbot_studio/godot/src/workspace/studio_root.tscn`, adding a `NavBar` node with two
  buttons above `WorkspaceRouter`, and the `LiveClientWorkspace` instance already planned:

  ```
  [node name="NavBar" type="HBoxContainer" parent="."]
  layout_mode = 1

  [node name="OfflineViewerButton" type="Button" parent="NavBar"]
  layout_mode = 2
  text = "Offline Viewer"

  [node name="LiveClientButton" type="Button" parent="NavBar"]
  layout_mode = 2
  text = "Live Client"

  [node name="LiveClientWorkspace" parent="WorkspaceRouter" instance=ExtResource("4_live_client")]
  layout_mode = 1
  ```

  (add the matching `ext_resource` line for `live_client_workspace.tscn` and bump `load_steps`.)

- [ ] Update `test_studio_root.gd`'s workspace-count assertion from `1` to `2` (F0's own
  `StudioRoot` docstring already anticipated this: "`LiveClientWorkspace` does not exist until
  M1d"). Edit `showdownbot_studio/godot/tests/workspace/test_studio_root.gd`:

  ```gdscript
  func test_studio_root_router_has_exactly_two_registered_workspaces() -> void:
  	var root := _spawn_root()
  	await await_idle_frame()
  	assert_int(root.get_router().get_registered_workspace_ids().size()).is_equal(2)
  ```

- [ ] Run and confirm everything passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/workspace/"
  ```

  Expected: `2` new navigation tests pass; the updated workspace-count test passes; no other
  `workspace/` test regresses.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/workspace/live_client_workspace.gd showdownbot_studio/godot/src/workspace/live_client_workspace.tscn showdownbot_studio/godot/src/workspace/studio_root.gd showdownbot_studio/godot/src/workspace/studio_root.tscn showdownbot_studio/godot/tests/workspace/test_studio_root.gd showdownbot_studio/godot/tests/workspace/test_studio_root_live_client_navigation.gd
  git commit -m "feat(studio): add reachable StudioRoot navigation + a real Connect button"
  ```

## Task 31 — Update `workspace/README.md` for `LiveClientWorkspace`

**Files:**
- Modify: `showdownbot_studio/godot/src/workspace/README.md`

- [ ] Add a "New (M1d)" subsection documenting `LiveClientWorkspace` and the nav-bar addition to
  `StudioRoot`, mirroring this plan's Task 24's ObservationEventBus entry and Task 30's navigation
  fix. (Content mirrors the first draft's version of this task, adjusted for the gateway/projection
  architecture: `LiveClientWorkspace` "composes `net/`, `protocol/`, `battle/LiveBattleProjection`,
  `ObservationEventBus`, and the `ui/panels/` spectate panels; holds no derived battle state itself
  and never calls `send_raw_text` directly — room commands go only through `SpectatorRoomGateway`.")

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/workspace/README.md
  git commit -m "docs(studio): update workspace/README.md for LiveClientWorkspace"
  ```

## Task 32 — `studio-live-local-e2e`: pinned local server provisioning (path + `npm ci` + readiness poll fixed)

**Files:**
- Create: `showdownbot_studio/godot/tools/start_local_showdown_server.ps1`
- Create: `showdownbot_studio/godot/tools/stop_local_showdown_server.ps1`

**Three bugs fixed in this revision:** (1) the repo-root computation from
`showdownbot_studio/godot/tools/` was `../../../..` (four levels up), one level too far — it escapes
the repository entirely. The correct path is **three** levels up (`tools` → `godot` →
`showdownbot_studio` → repo root). (2) `npm install` replaced with `npm ci` (reproducible install
from the lockfile, the correct choice for CI/pinned-environment provisioning). (3) the script now
polls the port for readiness with a timeout before returning, instead of assuming the server is
already listening the instant the process starts.

- [ ] Create `showdownbot_studio/godot/tools/start_local_showdown_server.ps1`:

  ```powershell
  # Starts the repository's pinned local pokemon-showdown server for the studio-live-local-e2e
  # CI lane. No prior automation for this exists in the repo -- built from the manual recipe at
  # showdown_bot/tools/localserver/README.md, reading the SAME pin the bot's own eval tooling uses
  # (config/eval/provenance.yaml's showdown_commit) rather than a second, driftable pin.
  param(
      [string]$CacheDir = (Join-Path $env:USERPROFILE ".cache/showdownbot/pokemon-showdown"),
      [int]$Port = 8000,
      [int]$ReadinessTimeoutSeconds = 60
  )

  $ErrorActionPreference = "Stop"
  # FIXED (2026-07-25 review): from showdownbot_studio/godot/tools/, the repo root is THREE levels
  # up (tools -> godot -> showdownbot_studio -> repo root), not four -- the previous "../../../.."
  # escaped the repository entirely.
  $RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "../../..")
  $ProvenancePath = Join-Path $RepoRoot "config/eval/provenance.yaml"
  $PatchPath = Join-Path $RepoRoot "tools/eval/patches/pokemon-showdown-seeded-battle.patch"

  $commitLine = Get-Content -LiteralPath $ProvenancePath | Where-Object { $_ -match '^showdown_commit:\s*(\S+)' }
  if (-not $commitLine) {
      Write-Host "ERROR: could not read showdown_commit from $ProvenancePath"
      exit 2
  }
  $commit = ($commitLine -split ':\s*')[1].Trim()

  if (-not (Test-Path -LiteralPath $CacheDir)) {
      git clone https://github.com/smogon/pokemon-showdown.git $CacheDir
      if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  }

  Push-Location $CacheDir
  try {
      git fetch origin $commit
      git checkout $commit
      if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

      $patchCheck = git apply --reverse --check $PatchPath 2>$null
      if ($LASTEXITCODE -ne 0) {
          git apply $PatchPath
          if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
      }

      if (-not (Test-Path "config/config.js")) {
          Copy-Item "config/config-example.js" "config/config.js"
      }

      # FIXED (2026-07-25 review): npm ci, not npm install -- reproducible install from the
      # committed lockfile, the correct choice for pinned CI provisioning.
      npm ci
      if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
      node build
      if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

      $proc = Start-Process -FilePath "node" -ArgumentList "pokemon-showdown", "start", "$Port", "--no-security" `
          -WorkingDirectory $CacheDir -PassThru -NoNewWindow
      $proc.Id | Out-File -FilePath (Join-Path $PSScriptRoot ".local_showdown_server.pid") -Encoding ascii

      # FIXED (2026-07-25 review): poll for readiness instead of assuming the port is open the
      # instant the process starts.
      $deadline = (Get-Date).AddSeconds($ReadinessTimeoutSeconds)
      $ready = $false
      while ((Get-Date) -lt $deadline) {
          $test = Test-NetConnection -ComputerName "localhost" -Port $Port -WarningAction SilentlyContinue
          if ($test.TcpTestSucceeded) {
              $ready = $true
              break
          }
          Start-Sleep -Seconds 1
      }
      if (-not $ready) {
          Write-Host "ERROR: pokemon-showdown did not become ready on port $Port within $ReadinessTimeoutSeconds s"
          exit 2
      }
      Write-Host "pokemon-showdown ready (pid $($proc.Id)) on port $Port, commit $commit"
  }
  finally {
      Pop-Location
  }
  ```

- [ ] Create `showdownbot_studio/godot/tools/stop_local_showdown_server.ps1` (unchanged from the
  first draft):

  ```powershell
  $ErrorActionPreference = "Stop"
  $PidFile = Join-Path $PSScriptRoot ".local_showdown_server.pid"
  if (-not (Test-Path -LiteralPath $PidFile)) {
      Write-Host "No .local_showdown_server.pid found -- nothing to stop"
      exit 0
  }
  $procId = Get-Content -LiteralPath $PidFile | Select-Object -First 1
  try {
      Stop-Process -Id $procId -Force -ErrorAction Stop
      Write-Host "Stopped pokemon-showdown (pid $procId)"
  }
  catch {
      Write-Host "Process $procId already stopped or not found"
  }
  Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
  ```

- [ ] **Manual verification**: run both scripts locally, confirm the readiness poll actually blocks
  until the server accepts a connection, and confirm the repo-root path resolves inside the actual
  repository (not above it) by printing `$RepoRoot` and checking it equals the real repo root.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/tools/start_local_showdown_server.ps1 showdownbot_studio/godot/tools/stop_local_showdown_server.ps1
  git commit -m "fix(studio): correct E2E provisioning repo-root path, use npm ci, poll for readiness"
  ```

## Task 33 — `showdown_bot` CLI addition: `--print-room-id` with a slow-paced keep-alive mode (owner-approved test-infrastructure exception)

**Files:**
- Modify: `showdown_bot/src/showdown_bot/cli.py`
- Modify: `showdown_bot/src/showdown_bot/client/gauntlet.py`
- Create: `showdown_bot/tests/test_gauntlet_print_room_id.py`

**This task is an owner-approved test-infrastructure exception (recorded 2026-07-25), separate from
this plan's own scope.** Spec §4.4's Godot module table governs `godot/src/*` only; it says nothing
about `showdown_bot/`, and this addition is not itself part of Phase 3's client — it is a small,
narrowly-scoped CLI addition the E2E lane needs so Godot can join and observe a real, still-running
battle, so `studio-live-local-e2e` (Task 34) has something real to spectate. Stating this explicitly
here so the table-conformance note above and this task cannot be read as contradictory: this task
touches `showdown_bot/`, which §4.4's table was never about in the first place.

**Fixed in this revision (owner re-review, 2026-07-25, second pass, item F).** The first pass's
design had `--print-room-id` print the marker line and then **exit** before running the actual
`--games` loop — meaning by the time Godot's E2E test could join the announced room, either the
battle process had already exited (the room gone, nothing to spectate) or, if the room somehow
persisted, no further battle events would ever arrive because nothing was still playing it. Fixed:
`--print-room-id` no longer exits early. It prints the marker as soon as the room exists, then
**keeps running the real battle** through to completion, paced by a new `--move-delay-seconds`
flag (a deliberate delay between the bot's own move submissions, used only for this E2E scenario)
so the battle stays open long enough for the CI lane to run the Godot test against a genuinely
active room before the process (and the battle) eventually ends.

- [ ] Write the failing test. Create `showdown_bot/tests/test_gauntlet_print_room_id.py`:

  ```python
  """--print-room-id emits exactly one unambiguous, machine-readable marker line to stdout as
  soon as the room exists, distinct from the gauntlet's normal human-readable summary output, and
  does NOT exit the process afterward -- the battle keeps running (owner-approved
  test-infrastructure exception, 2026-07-25 M1-plan review, second pass; see
  docs/plans/2026-07-25-phase3-m1-connect-spectate.md, Task 33/34).
  """
  from __future__ import annotations

  import re

  from showdown_bot.client import gauntlet

  _MARKER_RE = re.compile(r"^SHOWDOWN_ROOM_ID=(\S+)$", re.MULTILINE)


  def test_print_room_id_marker_line_format():
      line = gauntlet.format_room_id_marker("battle-gen9vgc2025regg-1")
      assert line == "SHOWDOWN_ROOM_ID=battle-gen9vgc2025regg-1"
      match = _MARKER_RE.search(line)
      assert match is not None
      assert match.group(1) == "battle-gen9vgc2025regg-1"


  def test_move_delay_seconds_defaults_to_zero_when_not_the_e2e_scenario():
      # The pacing delay is opt-in -- a normal gauntlet run (no --print-room-id/--move-delay-seconds)
      # must not slow down, only the E2E seeding path deliberately does.
      assert gauntlet.DEFAULT_MOVE_DELAY_SECONDS == 0.0
  ```

- [ ] Run and confirm it fails (`format_room_id_marker`/`DEFAULT_MOVE_DELAY_SECONDS` do not exist
  yet):

  ```
  cd showdown_bot
  python -m pytest -q tests/test_gauntlet_print_room_id.py
  ```

- [ ] Add `format_room_id_marker` and `DEFAULT_MOVE_DELAY_SECONDS` to
  `showdown_bot/src/showdown_bot/client/gauntlet.py` (small, pure additions near the existing
  room-naming/move-submission logic):

  ```python
  DEFAULT_MOVE_DELAY_SECONDS = 0.0


  def format_room_id_marker(room_id: str) -> str:
      """Exactly one machine-readable marker line for --print-room-id, parsed verbatim by the
      Studio E2E CI lane (docs/plans/2026-07-25-phase3-m1-connect-spectate.md, Task 34) -- never
      mixed into the gauntlet's normal human-readable summary output."""
      return f"SHOWDOWN_ROOM_ID={room_id}"
  ```

- [ ] Add `--print-room-id` and `--move-delay-seconds` flags to the `gauntlet` subcommand in
  `showdown_bot/src/showdown_bot/cli.py`:
  - `--print-room-id`: when set, print `format_room_id_marker(room_id)` to stdout via the normal
    `print()` path (not a logger, so CI can capture it from stdout directly) as soon as the first
    battle's room is created — and, unlike the first revision, **do not exit afterward**; continue
    running the battle normally through to completion.
  - `--move-delay-seconds` (default `gauntlet.DEFAULT_MOVE_DELAY_SECONDS`, i.e. `0.0`): an
    `await asyncio.sleep(move_delay_seconds)` inserted immediately before each of the hero bot's own
    move submissions, used only to keep an E2E-seeded battle observably active for longer than an
    instant; a normal gauntlet run never passes this flag and sees no change in pacing.

- [ ] Run and confirm the new tests pass, and the existing gauntlet CLI tests still pass:

  ```
  cd showdown_bot
  python -m pytest -q tests/test_gauntlet_print_room_id.py tests/test_profile_runner.py
  ```

- [ ] Commit:

  ```
  git add showdown_bot/src/showdown_bot/cli.py showdown_bot/src/showdown_bot/client/gauntlet.py showdown_bot/tests/test_gauntlet_print_room_id.py
  git commit -m "feat(bot): add gauntlet --print-room-id keep-alive mode + --move-delay-seconds (owner-approved Studio E2E test-infra exception, 2026-07-25, second pass)"
  ```

## Task 34 — `studio-live-local-e2e` gdUnit test + CI lane (waits for a real, still-running battle)

**Files:**
- Create: `showdownbot_studio/godot/tests/e2e/test_live_client_workspace_spectate_e2e.gd`
- Create: `.github/workflows/studio-live-local-e2e.yml`

**Fixed in this revision (first pass):** the CI step parses exactly the `SHOWDOWN_ROOM_ID=...`
marker line Task 33 defines, rather than capturing arbitrary stdout.

**Fixed in this revision (second pass, item F).** The first pass's design still had a fatal timing
problem even with correct marker parsing: `$output = python -m ...` **waits for the process to
exit** before the workflow step continues — meaning either the seeder had already finished the whole
battle and exited (nothing left running for Godot to join) or, with the exit-early
`--print-room-id` behavior from the first pass's Task 33, the room may not even have persisted long
enough. Fixed together with Task 33's keep-alive mode: the seeder now runs as a **background**
process (`Start-Process`, stdout redirected to a file), the marker line is read from that file while
the process keeps running the real battle, Godot joins the still-**active** room, and the gdUnit test
waits for and asserts on **real battle content** (the timeline growing, a real species or turn
value) rather than stopping at `RoomState.ACTIVE` — a joined room proves nothing was observed in it.
The seeder process is terminated in an `always()` cleanup step, alongside the pinned server itself.

- [ ] Write the E2E gdUnit test — still real `GodotSocketPeerAdapter`, no fake, but now waiting for
  real content, not just a state-machine value. Create
  `showdownbot_studio/godot/tests/e2e/test_live_client_workspace_spectate_e2e.gd`:

  ```gdscript
  extends GdUnitTestSuite

  const _LOCAL_SERVER_URL := "ws://localhost:8000/showdown/websocket"


  func test_spectating_a_real_local_battle_observes_real_content_not_just_room_state() -> void:
  	var workspace: LiveClientWorkspace = preload("res://src/workspace/live_client_workspace.tscn").instantiate()
  	add_child(workspace)
  	workspace.get_transport().connect_to_server(_LOCAL_SERVER_URL)
  	var frames := 0
  	while workspace.get_transport().get_state() != ConnectionStateMachine.State.CONNECTED and frames < 600:
  		await await_idle_frame()
  		frames += 1
  	assert_int(workspace.get_transport().get_state()).is_equal(ConnectionStateMachine.State.CONNECTED)
  	workspace.get_room_entry_panel().set_input_text_for_test(OS.get_environment("STUDIO_E2E_ROOM_ID"))
  	workspace.get_room_entry_panel().press_watch_for_test()
  	frames = 0
  	while workspace.get_room_state_machine().get_state() != RoomStateMachine.State.ACTIVE and frames < 600:
  		await await_idle_frame()
  		frames += 1
  	assert_int(workspace.get_room_state_machine().get_state()).is_equal(RoomStateMachine.State.ACTIVE)
  	# Fixed (item F): RoomState.ACTIVE alone only proves the room was joined, not that anything
  	# real was ever observed in it -- the seeder keeps the battle running past this point
  	# (Task 33's keep-alive mode), so wait for at least one real battle event (the timeline
  	# growing) and assert on real content, not merely a state-machine value.
  	frames = 0
  	while workspace.get_projection_for_test().get_timeline().size() == 0 and frames < 1200:
  		await await_idle_frame()
  		frames += 1
  	assert_bool(workspace.get_projection_for_test().get_timeline().size() > 0).is_true()
  	var snapshot := workspace.get_projection_for_test().get_current_snapshot()
  	var has_real_content := (
  		snapshot.turn != null
  		or str(snapshot.get_slot("p1", "a").species) != ""
  		or str(snapshot.get_slot("p2", "a").species) != ""
  	)
  	assert_bool(has_real_content).is_true()
  	workspace.free()
  ```

- [ ] Create `.github/workflows/studio-live-local-e2e.yml`. **Fixed in this revision (item F):** the
  seeder now runs as a background process, its stdout redirected to a file the workflow polls for
  the marker line while the process keeps running (rather than waiting for the process to exit and
  capturing its complete output, which is what the first pass's `$output = python -m ...` line
  actually did); the seeder is terminated in an `always()` cleanup step alongside the server itself.

  ```yaml
  name: studio live local e2e lane

  # Spec section 8.2: introduced with M1d. First CI lane in this repository to provision the
  # pinned local pokemon-showdown server. Never touches the official production server.

  on:
    push:
    pull_request:

  jobs:
    studio-live-local-e2e:
      runs-on: windows-latest
      steps:
        - uses: actions/checkout@v4

        - uses: actions/setup-python@v5
          with:
            python-version: "3.12"

        - uses: actions/setup-node@v4
          with:
            node-version: "20"

        - name: Install showdown_bot (needed to seed one gauntlet battle below)
          run: pip install -e ./showdown_bot

        - name: Cache pinned pokemon-showdown checkout
          id: cache-showdown
          uses: actions/cache@v4
          with:
            path: ~/.cache/showdownbot/pokemon-showdown
            key: pokemon-showdown-${{ hashFiles('config/eval/provenance.yaml', 'tools/eval/patches/pokemon-showdown-seeded-battle.patch') }}

        - name: Start pinned local pokemon-showdown server (polls for readiness)
          shell: pwsh
          run: ./showdownbot_studio/godot/tools/start_local_showdown_server.ps1

        - name: Seed a long-running battle in the background, parse the SHOWDOWN_ROOM_ID= marker
          shell: pwsh
          run: |
            $stdoutPath = Join-Path $env:RUNNER_TEMP "gauntlet_stdout.txt"
            $proc = Start-Process -FilePath "python" `
              -ArgumentList "-m", "showdown_bot.cli", "gauntlet", "--games", "1", "--villain", "max_damage", "--print-room-id", "--move-delay-seconds", "3" `
              -RedirectStandardOutput $stdoutPath -PassThru -NoNewWindow
            $proc.Id | Out-File -FilePath (Join-Path $env:RUNNER_TEMP "gauntlet.pid") -Encoding ascii

            # Poll the redirected stdout file for the marker line WHILE the process keeps running
            # (it does not exit after printing it -- Task 33's keep-alive mode) -- never wait for
            # the process to exit and read its complete output, which would defeat the point.
            $deadline = (Get-Date).AddSeconds(30)
            $roomId = $null
            while ((Get-Date) -lt $deadline) {
                if (Test-Path $stdoutPath) {
                    $match = Select-String -Path $stdoutPath -Pattern '^SHOWDOWN_ROOM_ID=(\S+)$' | Select-Object -First 1
                    if ($match) {
                        $roomId = $match.Matches[0].Groups[1].Value
                        break
                    }
                }
                Start-Sleep -Seconds 1
            }
            if (-not $roomId) {
                Write-Host "ERROR: no SHOWDOWN_ROOM_ID= marker found within 30s"
                exit 2
            }
            echo "STUDIO_E2E_ROOM_ID=$roomId" >> $env:GITHUB_ENV

        - name: Cache pinned Godot engine
          id: cache-engine
          uses: actions/cache@v4
          with:
            path: showdownbot_studio/godot/tools/engine
            key: godot-engine-${{ hashFiles('showdownbot_studio/godot/tools/ENGINE_SHA256SUMS') }}

        - name: Download pinned Godot engine (cache miss only)
          if: steps.cache-engine.outputs.cache-hit != 'true'
          shell: pwsh
          run: |
            New-Item -ItemType Directory -Force -Path showdownbot_studio/godot/tools/engine | Out-Null
            Invoke-WebRequest `
              -Uri "https://github.com/godotengine/godot-builds/releases/download/4.5.2-stable/Godot_v4.5.2-stable_win64.exe.zip" `
              -OutFile "showdownbot_studio/godot/tools/engine/Godot_v4.5.2-stable_win64.exe.zip"

        - name: Install pinned Godot engine (cache miss only)
          if: steps.cache-engine.outputs.cache-hit != 'true'
          shell: pwsh
          run: ./showdownbot_studio/godot/tools/install_engine.ps1

        - name: Verify pinned Godot engine digest
          shell: pwsh
          run: ./showdownbot_studio/godot/tools/verify_engine_pin.ps1

        - name: Run live-local-e2e gdUnit suite
          shell: pwsh
          run: ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/e2e/"

        - name: Assert gdUnit results were not truncated
          shell: pwsh
          run: ./showdownbot_studio/godot/tools/check_gdunit_truncation.ps1

        - name: Stop the background gauntlet seeder process
          if: always()
          shell: pwsh
          run: |
            $pidFile = Join-Path $env:RUNNER_TEMP "gauntlet.pid"
            if (Test-Path $pidFile) {
                $procId = Get-Content -LiteralPath $pidFile | Select-Object -First 1
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }

        - name: Stop pinned local pokemon-showdown server
          if: always()
          shell: pwsh
          run: ./showdownbot_studio/godot/tools/stop_local_showdown_server.ps1
  ```

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/tests/e2e/test_live_client_workspace_spectate_e2e.gd .github/workflows/studio-live-local-e2e.yml
  git commit -m "test(studio): E2E waits for real battle content from a background, kept-alive seeder"
  ```

## Task 35 — M1d gate evidence

**Files:** none (verification only).

- [ ] Full Python suite (including `showdown_bot/tests/test_gauntlet_print_room_id.py` from Task
  33); full gdUnit suite + truncation check; architecture lane.

- [ ] `studio-live-local-e2e` runs green in CI on the M1d PR.

- [ ] Accessibility/layout check proportional to the new UI surface: board/status/log/entry/nav
  panels are keyboard-reachable and scale with `WorkspaceLayout`'s existing presets.

- [ ] `git status --porcelain` clean; `git diff --check main` clean.

- [ ] Open the M1d PR, explicitly noting this is the first CI lane in the repository to provision
  the pinned local server. Do not merge until reviewed.

---

# M1e — Reconnect and full rebuild

Blocked on M1d merged and gated. New production code lands only in `godot/src/net/`,
`godot/src/protocol/`, `godot/src/battle/` (spec §4.4) — **this revision drops the first draft's
`ProtocolLineDeduplicator` (`protocol/`) entirely and touches no `workspace/` file whatsoever**, both
directly fixing the review's most serious finding.

**Why the first draft was wrong, precisely.** Two separate defects: (1) Task 29 of the first draft
edited `live_client_workspace.gd` to interpose a dedup step — a `workspace/` file change inside a
sub-slice whose normative module list is `net/`, `protocol/`, `battle/` only. (2) The dedup approach
itself — a per-`connection_epoch` "seen lines" set — does not actually implement spec §6.2's rule.
Spec §6.2 requires `battle/` to **rebuild completely from re-received room history, never
incrementally**; a "skip lines already seen this epoch" filter is the opposite of a full rebuild — it
tries to reuse the *existing* (potentially stale, potentially already-diverged) state and merely
avoid double-counting the overlap, which both fails to guarantee a correct rebuild (a line the
dedup set incorrectly treats as "already seen" from a slightly different pre-disconnect context is
silently dropped) and can swallow legitimately identical events that occur twice within one battle
for real game reasons (e.g. the same Pokémon fainting is decoded once; a genuinely repeated
identical-looking line later in the SAME session is not automatically a duplicate).

**What replaces it.** `battle/LiveBattleProjection` (M1c, Task 20) already owns the current snapshot
and timeline. This revision makes it **reset entirely and refold from scratch whenever it observes a
second `init` event** — real Showdown semantics: on rejoin, the server resends the room's full
history starting with `|init|battle` again. Detecting a repeat `init` from the event stream alone is
purely data-driven and needs no cross-module signal at all — `battle/` never has to know *why* the
history restarted, only that it did.

**Automatic rejoin routing (owner re-review, 2026-07-25, second pass, item C).** The **send** itself
still originates from a decision `protocol/`'s `RoomStateMachine` makes (Task 37 extends the same
`_on_connection_state_changed` stub M1b, Task 11 left empty for exactly this), but `RoomStateMachine`
never calls `send_raw_text()` or references `ProtocolCommandEncoder` itself — it only **emits**
`automatic_rejoin_requested(room_id)` (declared in Task 11). `ui/panels/SpectatorRoomGateway`
(subscribed since M1d's Task 28, specifically so this M1e task never has to touch `ui/panels/` again)
is the sole subscriber and the sole sender, reacting to this system-triggered signal through the
exact same send-and-check-failure path a human-clicked "Watch" uses. Task 37 itself is therefore a
pure `protocol/` file edit — it emits a signal, nothing more — keeping M1e's own module list exactly
`net/`, `protocol/`, `battle/` even though the *reaction* to that signal lives in a `ui/panels/` file
that was written and committed one sub-slice earlier.

**§6.2 scope note (unchanged from the first draft, restated here since it directly governs what this
sub-slice's tests can prove).** Team preview and forced switch require `|request|`/`ChoiceRequestState`,
which do not exist until M2 — M1 sends no `/choose` (spec §3.3's closing line). This sub-slice
implements and tests the two required §6.2 scenarios meaningful in a read-only spectate client
(**reconnect mid-battle**, **reconnect after the battle has already ended**); team preview and
forced switch remain deferred to M2's own plan.

## Task 36 — `connection_epoch` regression coverage across a reconnect cycle

**Files:**
- Create: `showdownbot_studio/godot/tests/net/test_web_socket_transport_connection_epoch_reconnect.gd`

Unchanged from the first draft — Tasks 5/7 already implement this; this task is the explicit,
named regression proof.

- [ ] Write the test. Create
  `showdownbot_studio/godot/tests/net/test_web_socket_transport_connection_epoch_reconnect.gd`:

  ```gdscript
  extends GdUnitTestSuite

  var _fake: FakeSocketPeerPort
  var _transport: WebSocketTransport


  func before_test() -> void:
  	_fake = FakeSocketPeerPort.new()
  	_transport = WebSocketTransport.new(func(): return _fake)
  	add_child(_transport)


  func after_test() -> void:
  	remove_child(_transport)
  	_transport.free()


  func test_epoch_does_not_change_while_staying_connected_and_receiving_traffic() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(0.016)
  	var epoch_before := _transport.get_connection_epoch()
  	_fake.queued_packets = ["|turn|1"]
  	_transport._process(0.016)
  	assert_int(_transport.get_connection_epoch()).is_equal(epoch_before)


  func test_epoch_increments_exactly_once_per_full_reconnect_cycle() -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	var epoch_after_initial := _transport.get_connection_epoch()
  	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
  	_transport._process(0.016)  # -> RECONNECTING
  	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # reopens
  	assert_int(_transport.get_connection_epoch()).is_equal(epoch_after_initial + 1)
  ```

- [ ] Run and confirm it passes without a production change; if it fails, that is a real Task 5/7
  defect to fix with its own red-then-green evidence:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/net/test_web_socket_transport_connection_epoch_reconnect.gd"
  ```

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/tests/net/test_web_socket_transport_connection_epoch_reconnect.gd
  git commit -m "test(studio): regression-cover connection_epoch across a full reconnect cycle"
  ```

## Task 37 — `protocol/RoomStateMachine`: emit `automatic_rejoin_requested` on reconnect (RED-first)

**Files:**
- Modify: `showdownbot_studio/godot/src/protocol/room_state_machine.gd`
- Create: `showdownbot_studio/godot/tests/protocol/test_room_state_machine_reconnect.gd`

Extends `_on_connection_state_changed` (M1b, Task 11 left it an empty stub specifically so this task
could fill it in without touching any other file) to: (1) call `connection_reconnecting()` the
moment the connection reaches `RECONNECTING` while `ACTIVE`; (2) **emit**
`automatic_rejoin_requested(_room_id)` once the connection reaches `CONNECTED` again while `JOINING`
from a reconnect. This class never calls `send_raw_text()` or references `ProtocolCommandEncoder`
(owner re-review, 2026-07-25, second pass, item C) — `ui/panels/SpectatorRoomGateway` (subscribed
since Task 28) is the sole sender, for both this system-triggered signal and a human-clicked
"Watch"; this task's own test therefore asserts on the **signal being emitted**, not on anything
being sent (`RoomStateMachine`'s own tests hold no gateway at all, by design — the send path is
`SpectatorRoomGateway`'s own tested behavior, Task 28).

- [ ] Write the failing test. Create `showdownbot_studio/godot/tests/protocol/test_room_state_machine_reconnect.gd`:

  ```gdscript
  extends GdUnitTestSuite

  var _fake: FakeSocketPeerPort
  var _transport: WebSocketTransport
  var _room_state_machine: RoomStateMachine


  func before_test() -> void:
  	_fake = FakeSocketPeerPort.new()
  	_transport = WebSocketTransport.new(func(): return _fake)
  	add_child(_transport)
  	_room_state_machine = RoomStateMachine.new(_transport)


  func after_test() -> void:
  	remove_child(_transport)
  	_transport.free()


  func _connect_join_and_activate(room_id: String) -> void:
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(0.016)
  	_room_state_machine.request_join(room_id)
  	_room_state_machine.join_confirmed()


  func test_reconnecting_while_active_moves_room_state_to_joining_automatically() -> void:
  	_connect_join_and_activate("battle-1")
  	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
  	_transport._process(0.016)  # transport -> RECONNECTING
  	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.JOINING)


  func test_reconnect_succeeding_emits_automatic_rejoin_requested_for_the_same_room() -> void:
  	_connect_join_and_activate("battle-1")
  	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
  	_transport._process(0.016)  # -> RECONNECTING, RoomState -> JOINING
  	var emitted_room_ids: Array[String] = []
  	_room_state_machine.automatic_rejoin_requested.connect(func(room_id: String): emitted_room_ids.append(room_id))
  	# Two _process() calls, matching Task 7's attempt-in-flight fix: the first opens the new
  	# peer (still RECONNECTING that same frame); the second observes it as OPEN -> CONNECTED.
  	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(0.016)
  	assert_int(emitted_room_ids.size()).is_equal(1)
  	assert_str(emitted_room_ids[0]).is_equal("battle-1")


  func test_no_automatic_rejoin_is_emitted_when_no_room_was_ever_joined() -> void:
  	var emitted_room_ids: Array[String] = []
  	_room_state_machine.automatic_rejoin_requested.connect(func(room_id: String): emitted_room_ids.append(room_id))
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
  	_transport._process(0.016)
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)
  	assert_int(emitted_room_ids.size()).is_equal(0)


  func test_room_state_machine_never_calls_send_raw_text_itself() -> void:
  	# Structural proof of item C's fix: even across a full reconnect-and-rejoin cycle, this
  	# class's own fake transport never records a sent text -- only SpectatorRoomGateway (Task 28)
  	# ever does, and it is not present in this test at all.
  	_connect_join_and_activate("battle-1")
  	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
  	_transport._process(0.016)
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)
  	assert_int(_fake.sent_texts.size()).is_equal(0)
  ```

- [ ] Run and confirm it fails (the M1b stub does nothing yet); then extend
  `_on_connection_state_changed` in `showdownbot_studio/godot/src/protocol/room_state_machine.gd`:

  ```gdscript
  ## M1e: emits automatic_rejoin_requested after a successful reconnect (spec section 6.2) --
  ## system-triggered, distinct from a human-initiated join. This class never sends anything
  ## itself; ui/panels/SpectatorRoomGateway (subscribed since M1d's Task 28) is the sole sender
  ## for both this signal and a human-clicked "Watch" (owner re-review, 2026-07-25, second pass,
  ## item C) -- so this task is a pure protocol/ file edit, never touching ui/panels/ again.
  func _on_connection_state_changed(_old_state: ConnectionStateMachine.State, new_state: ConnectionStateMachine.State) -> void:
  	if new_state == ConnectionStateMachine.State.RECONNECTING and _state == State.ACTIVE:
  		connection_reconnecting()
  		return
  	if new_state == ConnectionStateMachine.State.CONNECTED and _state == State.JOINING and not _room_id.is_empty():
  		automatic_rejoin_requested.emit(_room_id)
  ```

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/protocol/test_room_state_machine_reconnect.gd"
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/protocol/"
  ```

  Expected: `4` new tests pass; the full `protocol/` suite `0` failed.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/protocol/room_state_machine.gd showdownbot_studio/godot/tests/protocol/test_room_state_machine_reconnect.gd
  git commit -m "feat(studio): protocol/RoomStateMachine emits automatic_rejoin_requested (never sends itself)"
  ```

## Task 38 — `battle/LiveBattleProjection`: reset-on-repeat-`init`, proven against a poisoned pre-state (RED-first)

**Files:**
- Modify: `showdownbot_studio/godot/src/battle/live_battle_projection.gd`
- Create: `showdownbot_studio/godot/tests/battle/test_live_battle_projection_rebuild.gd`

This is the review's central demand: a **deliberately poisoned pre-state** — content that must not
survive a rebuild — proven gone after a simulated resend, written and shown red *against the M1c
implementation* (which has no reset logic at all) before the fix lands.

**Fixed in this revision (owner re-review, 2026-07-25, second pass, item B).** The test originally
drafted for this task poisoned a **fresh** `LiveBattleProjection` — one that had never seen an
`init` at all — and then sent what it called a "second" `init` as part of the resend. But
`_has_seen_init` starts `false` on a fresh projection, so that "second" `init` was actually the
*first* one the object ever observed: even a fully correct implementation would not reset there,
because nothing had happened yet to reset *from*. The test now follows the exact five-step sequence
the review specified: (1) send a genuine first battle `init` to the projection (mirroring Task 29's
fixed wiring, which now always forwards a confirmed battle `init`); (2) poison the state; (3) send a
**second** battle `init` — now a real repeat; (4) assert the poison is gone; (5) the resend history
that follows is folded normally. The timeline afterward includes that second, triggering `init`
event itself — the reset happens *before* the triggering event is appended, so it lands in the fresh
timeline, not the discarded one.

**Honesty note on what this test actually proves.** With this exact event sequence, the two
snapshot-content assertions (`snapshot.turn`, the species) would *coincidentally* still pass even
without the fix — the reducer's own last-write-wins semantics mean the final `turn`/`switch` events
overwrite the poisoned ones regardless of whether a reset happened in between. The load-bearing
assertions are the **timeline** ones: without the fix, `timeline.size()` would be `7` (all four
pre-reset events plus the three resent ones, none discarded) and `"OLD_ONLY_EVENT"` would still be
present — that is what actually distinguishes "reset and refold" from "just keep appending forever,"
and that is what genuinely fails red against the unfixed M1c implementation.

- [ ] Write the failing test. Create
  `showdownbot_studio/godot/tests/battle/test_live_battle_projection_rebuild.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func _event(fields: Dictionary) -> ProtocolEventDTO:
  	var e := ProtocolEventDTO.new()
  	for key in fields:
  		e.set(key, fields[key])
  	e.seal()
  	return e


  func test_repeat_init_discards_poisoned_pre_state_and_rebuilds_from_scratch() -> void:
  	var projection := LiveBattleProjection.new()

  	# 1. A genuine FIRST battle init reaches the projection -- mirrors Task 29's fixed wiring,
  	# which always forwards a confirmed battle init. Without this step, the "second" init below
  	# would actually be the projection's first, and the reset this test proves would never need
  	# to fire even in a correct implementation.
  	projection.apply_event(_event({"event_type": "init", "condition_label": "battle"}))

  	# 2. Poison the state: none of this must survive a rebuild.
  	projection.apply_event(_event({"event_type": "turn", "turn_number": 99}))
  	projection.apply_event(_event({
  		"event_type": "switch", "pokemon_side": "p1", "pokemon_slot": "a",
  		"pokemon_species": "FakeMon", "hp_current": 1, "hp_maximum": 1, "hp_fainted": false,
  	}))
  	projection.apply_event(_event({"event_type": "OLD_ONLY_EVENT"}))

  	# 3. The resent authoritative history arrives, starting with a genuine SECOND battle init --
  	# exactly as a real reconnect resend does.
  	var resend_history := [
  		_event({"event_type": "init", "condition_label": "battle"}),
  		_event({"event_type": "turn", "turn_number": 1}),
  		_event({
  			"event_type": "switch", "pokemon_side": "p1", "pokemon_slot": "a",
  			"pokemon_species": "Pikachu", "hp_current": 100, "hp_maximum": 100, "hp_fainted": false,
  		}),
  	]
  	for e in resend_history:
  		projection.apply_event(e)

  	# 4. Assert the poison is gone.
  	var snapshot := projection.get_current_snapshot()
  	assert_int(snapshot.turn).is_equal(1)  # not 99
  	assert_str(str(snapshot.get_slot("p1", "a").species)).is_equal("Pikachu")  # not FakeMon

  	# 5. The timeline is EXACTLY the resend history (including its own leading init) -- this is
  	# the load-bearing proof (see this task's "honesty note" above).
  	var timeline := projection.get_timeline()
  	assert_int(timeline.size()).is_equal(resend_history.size())
  	for e in timeline:
  		assert_str(e.event_type).is_not_equal("OLD_ONLY_EVENT")


  func test_first_init_never_triggers_a_reset() -> void:
  	var projection := LiveBattleProjection.new()
  	projection.apply_event(_event({"event_type": "init", "condition_label": "battle"}))
  	projection.apply_event(_event({"event_type": "turn", "turn_number": 1}))
  	assert_int(projection.get_timeline().size()).is_equal(2)  # not discarded by its own first init
  ```

- [ ] Run and confirm it fails **against the M1c implementation** (no reset logic exists yet — the
  timeline assertions fail: `timeline.size()` is `7`, not `3`, and `"OLD_ONLY_EVENT"` is still
  present; the two snapshot-content assertions may pass anyway per this task's honesty note above —
  that is expected and does not mean the test is meaningless, only that the timeline assertions are
  the ones actually carrying this test):

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/battle/test_live_battle_projection_rebuild.gd"
  ```

  Expected: `test_repeat_init_discards_poisoned_pre_state_and_rebuilds_from_scratch` fails.

- [ ] Fix it. Edit `showdownbot_studio/godot/src/battle/live_battle_projection.gd`:

  ```gdscript
  var _has_seen_init: bool = false
  ```

  ```gdscript
  func apply_event(event: ProtocolEventDTO) -> void:
  	if event.event_type == "init" and _has_seen_init:
  		# Spec section 6.2: rebuild COMPLETELY from re-received room history, never
  		# incrementally. A second `init` after the first is real Showdown's own signal that
  		# authoritative history is starting over (a reconnect resend) -- purely data-driven,
  		# battle/ never needs to know WHY the history restarted, only that it did.
  		_current = LiveBattleSnapshot.new()
  		_timeline = []
  	if event.event_type == "init":
  		_has_seen_init = true
  	_timeline.append(event)
  	_current = LiveBattleReducer.apply(_current, event)
  	snapshot_published.emit(_current)
  	if _current.battle_completed:
  		battle_completed.emit(_room_id)
  ```

- [ ] Run again and confirm both pass:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/battle/test_live_battle_projection_rebuild.gd"
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/battle/"
  ```

  Expected: `2` new tests pass; full `battle/` suite `0` failed (re-confirm Task 20's original
  tests, which never exercised a repeat `init`, are unaffected).

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/src/battle/live_battle_projection.gd showdownbot_studio/godot/tests/battle/test_live_battle_projection_rebuild.gd
  git commit -m "feat(studio): LiveBattleProjection resets and rebuilds from scratch on repeat init (proven against a poisoned pre-state)"
  ```

## Task 39 — End-to-end reconnect proof through the real decode path

**Files:**
- Create: `showdownbot_studio/godot/tests/e2e/test_reconnect_full_rebuild_real_decode_path.gd`

Proves Tasks 37–38 compose correctly, using `FakeSocketPeerPort` to feed **raw frame text** for both
the pre-disconnect and the resent history (never pre-decoded `ProtocolEventDTO` objects injected
directly) — the real decode path, exactly as the review requires. Wires `net/` + `protocol/` +
`battle/` directly in the test; **no `workspace/` class is instantiated or touched anywhere in this
task**, proving M1e's rebuild genuinely does not need it.

**Fixed in this revision (owner re-review, 2026-07-25, second pass, item B).** The wiring originally
drafted for this test mirrored the *original*, buggy `LiveClientWorkspace` wiring: it forwarded an
`init` event only to `_room_state_machine.rejoin_confirmed()`, never to `_projection.apply_event()`.
Fixed to match Task 29's corrected wiring — every event, `init` included, reaches
`_projection.apply_event()` — which also changes the expected timeline counts below (the timeline
now includes the triggering `init` events, not just the lines after them).

- [ ] Write the test. Create
  `showdownbot_studio/godot/tests/e2e/test_reconnect_full_rebuild_real_decode_path.gd`:

  ```gdscript
  extends GdUnitTestSuite

  var _fake: FakeSocketPeerPort
  var _transport: WebSocketTransport
  var _decoder: ProtocolDecoder
  var _room_state_machine: RoomStateMachine
  var _projection: LiveBattleProjection


  func before_test() -> void:
  	_fake = FakeSocketPeerPort.new()
  	_transport = WebSocketTransport.new(func(): return _fake)
  	add_child(_transport)
  	_decoder = ProtocolDecoder.new()
  	_room_state_machine = RoomStateMachine.new(_transport)
  	_projection = LiveBattleProjection.new()
  	_transport.raw_text_received.connect(_decoder.decode_frame)
  	_decoder.event_decoded.connect(func(e: ProtocolEventDTO):
  		if e.event_type == "init":
  			_room_state_machine.rejoin_confirmed()
  			_projection.set_room_id(e.room_id)
  		# Fixed (item B): every event, including init, reaches the projection -- mirrors Task
  		# 29's corrected LiveClientWorkspace wiring exactly.
  		_projection.apply_event(e)
  	)


  func after_test() -> void:
  	remove_child(_transport)
  	_transport.free()


  func test_full_reconnect_rebuild_through_the_real_decode_path_no_dedup_needed() -> void:
  	# 1. Connect, join, and receive the pre-disconnect history through the real decode path.
  	_transport.connect_to_server("ws://localhost:8000/showdown/websocket")
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(0.016)
  	_room_state_machine.request_join("battle-1")
  	_fake.queued_packets = [">battle-1\n|init|battle\n|turn|1\n|switch|p1a: Pikachu|Pikachu, L50, M|100/100"]
  	_transport._process(0.016)
  	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.ACTIVE)
  	assert_int(_projection.get_current_snapshot().turn).is_equal(1)
  	assert_int(_projection.get_timeline().size()).is_equal(3)  # init, turn, switch

  	# 2. Connection drops; automatic reconnect begins; RoomState reacts to ACTIVE -> RECONNECTING.
  	_fake.ready_state = SocketPeerPort.ReadyState.CLOSED
  	_transport._process(0.016)
  	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.JOINING)

  	# 3. Reconnect succeeds; RoomStateMachine emits automatic_rejoin_requested; there is no
  	# gateway in this test, so nothing actually sends /join here -- this test proves the
  	# rebuild, not the send (that is SpectatorRoomGateway's own tested behavior, Task 28). Two
  	# _process() calls are required here, matching Task 7's attempt-in-flight fix: the first
  	# opens the new peer (still RECONNECTING that same frame); the second observes it as OPEN.
  	var rejoin_requested_room_ids: Array[String] = []
  	_room_state_machine.automatic_rejoin_requested.connect(func(room_id: String): rejoin_requested_room_ids.append(room_id))
  	_transport._process(WebSocketTransport.RECONNECT_BACKOFF_SCHEDULE_S[0] + 0.1)  # opens the new peer
  	_fake.ready_state = SocketPeerPort.ReadyState.OPEN
  	_transport._process(0.016)  # observes OPEN -> CONNECTED
  	assert_int(rejoin_requested_room_ids.size()).is_equal(1)
  	assert_str(rejoin_requested_room_ids[0]).is_equal("battle-1")

  	# 4. Server resends the ENTIRE authoritative history from scratch (a second `init`), through
  	# the same real decode path, containing neither the pre-disconnect turn number nor species.
  	_fake.queued_packets = [">battle-1\n|init|battle\n|turn|1\n|switch|p1a: Ditto|Ditto|50/50"]
  	_transport._process(0.016)

  	# 5. Only now do new live events continue -- verified separately below.
  	assert_int(_room_state_machine.get_state()).is_equal(RoomStateMachine.State.ACTIVE)
  	var snapshot := _projection.get_current_snapshot()
  	assert_int(snapshot.turn).is_equal(1)
  	assert_str(str(snapshot.get_slot("p1", "a").species)).is_equal("Ditto")  # not "Pikachu"
  	# Timeline count equals exactly the rebuilt (resent) history's three lines (init, turn,
  	# switch) -- no leftover from before the reconnect, and no dedup-driven under- or over-count.
  	assert_int(_projection.get_timeline().size()).is_equal(3)

  	_fake.queued_packets = [">battle-1\n|turn|2"]
  	_transport._process(0.016)
  	assert_int(_projection.get_current_snapshot().turn).is_equal(2)
  	assert_int(_projection.get_timeline().size()).is_equal(4)
  ```

- [ ] Run and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/e2e/test_reconnect_full_rebuild_real_decode_path.gd"
  ```

  Expected: `1` test passed, `0` failed.

- [ ] Confirm no `workspace/` file was touched by this task (the constraint this whole restructure
  exists to satisfy):

  ```
  git diff --stat main -- showdownbot_studio/godot/src/workspace/
  ```

  Expected: no output.

- [ ] Commit:

  ```
  git add showdownbot_studio/godot/tests/e2e/test_reconnect_full_rebuild_real_decode_path.gd
  git commit -m "test(studio): prove full reconnect rebuild through the real decode path (net/+protocol/+battle/ only)"
  ```

## Task 40 — M1e (and M1 milestone) gate evidence

**Files:** none (verification only).

- [ ] Full Python suite; full gdUnit suite + truncation check; architecture lane.

- [ ] Confirm `studio-protocol-contract` and `studio-live-local-e2e` both still run green with
  M1e's changes.

- [ ] Confirm, across every M1e commit, that no file under `godot/src/workspace/` or
  `godot/src/ui/panels/` was created or modified — the module-table-conformance property this
  restructure exists to prove:

  ```
  git diff --stat <M1d-merge-sha>..HEAD -- showdownbot_studio/godot/src/workspace/ showdownbot_studio/godot/src/ui/
  ```

  Expected: no output.

- [ ] Re-run this plan's spec-coverage self-check before declaring M1 closed:
  - every §3.3 M1a–M1e bullet maps to a task above (M1a: Task 2–9; M1b: Task 10–17; M1c: Task
    18–23; M1d: Task 24–35; M1e: Task 36–40; Task 1 is a shared cross-cutting doc amendment
    preceding all of them);
  - every `ConnectionState` and `RoomState` transition in the amended `LIVE_STATE_MACHINES.md` has
    a passing test, including the three edges Task 1 added (`CONNECTING`→`DISCONNECTED`,
    `JOINING`→`NOT_JOINED` local send failure, `LEAVING`→`ACTIVE` local send failure);
  - no task added code to `session/`, no task added a `/choose` path, no task references
    `HumanBattleCommandGateway`;
  - room join/leave never bypasses `SpectatorRoomGateway` — including the automatic reconnect
    rejoin, which reaches it only via `RoomStateMachine.automatic_rejoin_requested` (item C);
  - `LiveBattleSnapshot`/`LiveBattleSlotSnapshot` have no setter anywhere in the codebase;
  - `LiveClientWorkspace.configure_transport_for_test()` never re-runs `_wire_domain_and_ui()`
    (small fix #1); `RoomEntryPanel.configure()` accepts `SpectatorRoomGatewayPort`, not the
    concrete gateway (small fix #2);
  - a `deinit` while `LEAVING` confirms the leave; a `deinit` while `ACTIVE` closes the room
    (item D);
  - the two §6.2 reconnect scenarios this milestone can contain (mid-battle, post-battle-end) are
    both tested (Task 38, Task 39); team preview and forced switch remain explicitly deferred to
    M2's own plan.

- [ ] `git status --porcelain` clean; `git diff --check main` clean.

- [ ] Open the M1e PR. On merge, M1 (Connect + Spectate) is closed per spec §3.3; M2 (Login + Play)
  requires its own separately-reviewed implementation plan before any `session/` code or `/choose`
  path may be authorized.
