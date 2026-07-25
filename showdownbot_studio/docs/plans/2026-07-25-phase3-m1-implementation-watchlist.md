# M1 Implementation Watchlist

**Status:** BINDING — owner-authored implementation-review checklist, 2026-07-25
**Scope:** every M1 sub-slice PR (M1a–M1e) of
[`2026-07-25-phase3-m1-connect-spectate.md`](2026-07-25-phase3-m1-connect-spectate.md)
**Rule of precedence:** the approved M1 plan is authoritative, but it is large and has undergone
two integration-review passes. The checks below are mandatory implementation-review checks in
addition to the individual task instructions. If a code sample in the plan conflicts with a later
revision note, the later revision note and its corresponding acceptance test win.

## General execution rule

Do not copy a later task's final code prematurely into an earlier task.

For every task:

1. create or modify the test first;
2. run it and preserve evidence that it fails for the intended reason;
3. implement only the behavior authorized by that task;
4. run the targeted tests;
5. run all previously introduced tests for that sub-slice;
6. inspect the actual diff against the task's declared file list.

## M1a — transport

- A reconnect attempt may open exactly one peer after each backoff period.
- While that peer remains `CONNECTING`, subsequent frames must poll the same peer and must not
  create another one.
- `RECONNECTING → CONNECTED` requires observing that in-flight peer as `OPEN` on a later poll.
- A synchronous connection failure must schedule the next backoff and must not cause a busy loop.
- Initial connect, reconnect attempt, successful reconnect, cancel, timeout, manual disconnect,
  and exhaustion must each change `connection_epoch` and state only as explicitly specified.
- Do not reintroduce an inbound-traffic idle timeout.
- `heartbeat_interval` means periodic WebSocket ping configuration only; do not claim a guaranteed
  missing-pong closure deadline that Godot does not document.
- Always check `_peer != null` before querying its state in timeout and polling paths.

## M1b — protocol

- Preserve complete WebSocket frame boundaries. A single frame may contain a room header and
  multiple protocol lines.
- Fixtures are JSONL with one raw multi-line WebSocket frame per record.
- The hand-written golden DTO sequence must exist and be reviewed before decoder implementation.
- Compare the entire decoded sequence field by field and in order.
- Maintain three distinct classifications: decoded state event; known but deliberately ignored
  event; genuinely unknown event.
- Known ignored lines must not generate "not understood" warnings.
- Keep the explicit `0 fnt` regression test.
- Never split or parse raw Showdown protocol text outside `protocol/`.
- Room IDs must be inherited from the current `>roomid` frame header and must not leak between
  frames.

## Room lifecycle and commands

- Human join, human leave, and automatic reconnect rejoin all use `SpectatorRoomGateway`.
- `RoomStateMachine` may observe transport state and emit `automatic_rejoin_requested(room_id)`,
  but it must never encode or send room commands itself.
- The gateway must inspect the send result.
- Failed join send: `JOINING → NOT_JOINED`.
- Failed leave send: `LEAVING → ACTIVE`.
- `deinit` while `LEAVING` means `leave_confirmed() → NOT_JOINED`.
- `deinit` while `ACTIVE` means `server_closed_room() → CLOSED`.
- `win` and `tie` end the battle, not the room.
- Do not add a second direct encoder/transport path from UI, workspace, protocol state machine,
  or tests.

## M1c — derived state

- `LiveBattleProjection` is the sole owner of the current derived battle snapshot and timeline.
- `workspace/` must not own or patch authoritative battle state.
- Snapshots and slot snapshots must have no public mutation path.
- Getters must not expose mutable internal objects that can alter an existing snapshot.
- Reducer operations return new values and never modify their input snapshot.
- Unknown or inconsistent state events fail closed and remain diagnostically visible.

## M1d — composition and UI

- Forward every confirmed battle-room `init` to `LiveBattleProjection.apply_event()`.
- Do not return from the workspace's `init` handling before the projection receives it.
- Filter all room-scoped events by the currently joined room ID before they reach battle state or
  visible panels.
- Only `|init|battle` activates the spectator battle surface.
- Keep transport wiring separate from one-time domain/UI wiring.
- `configure_transport_for_test()` must not reconnect decoder, bus, projection, or UI signals a
  second time.
- `RoomEntryPanel` depends on `SpectatorRoomGatewayPort`, not the concrete production gateway.
- Publish battle state through one intended path; do not also update the same UI through an
  independent duplicate path.
- The live workspace must remain reachable through real navigation, not only registered in the
  router.

## Local E2E

- Use only the pinned local Showdown server.
- Do not capture official-server fixtures.
- Use `../../..` for the repository root from `showdownbot_studio/godot/tools/`.
- Use `npm ci`.
- Poll server readiness before seeding.
- Start the battle seeder in the background.
- Parse only the exact `SHOWDOWN_ROOM_ID=` marker line.
- Keep the seeded battle alive while Godot joins and observes it.
- Assert at least one real battle-state or timeline event, not only `RoomState.ACTIVE`.
- Stop both the seeder and local server in unconditional cleanup.
- Do not print unrelated stdout in the machine-readable marker path.

## M1e — reconnect and rebuild

A successful reconnect is not complete merely because the socket is open. Required sequence:

1. transport reaches `RECONNECTING`;
2. one reconnect peer is opened after backoff;
3. that same peer is polled until `OPEN`;
4. transport reaches `CONNECTED`;
5. `RoomStateMachine` emits `automatic_rejoin_requested(room_id)`;
6. `SpectatorRoomGateway` sends the rejoin command;
7. the server resends authoritative room history;
8. the second battle `init` resets `LiveBattleProjection`;
9. snapshot and timeline are rebuilt solely from the resent history;
10. new live events continue afterward.

The poisoned-state test must follow this exact order: first battle `init`; poison the state with
`FakeMon`, turn 99, and `OLD_ONLY_EVENT`; second battle `init`; confirm reset; fold the resent
authoritative history.

The timeline assertions are the load-bearing proof. Snapshot assertions alone are insufficient
because later events could overwrite poisoned values while stale timeline entries remain.

Do not introduce content-based protocol-line deduplication. Full reset and authoritative refolding
are the intended model.

## Slice-boundary checks

Before completing each PR:

- compare the actual changed files against the sub-slice's normative module list;
- fail the gate if an undeclared production module was modified;
- run `git diff --check`;
- run the full existing Studio suites and the sub-slice-specific lane;
- confirm no `/choose`, login, `session/`, credential, mod, or bot pathway entered M1.

For M1e specifically:

```text
git diff --stat <M1d-merge-sha>..HEAD -- \
  showdownbot_studio/godot/src/workspace/ \
  showdownbot_studio/godot/src/ui/
```

Expected output: none.

When implementation reality differs from a code block in the plan, do not silently improvise. Stop
that task, document the discrepancy, and request owner review before changing architecture or
module ownership.
