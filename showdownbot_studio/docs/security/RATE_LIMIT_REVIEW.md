# Phase 3 Rate-Limit Behavior Review

**Status:** binding phase-closure gate (spec `2026-07-25-phase3-client-design.md` section 9 gate
11). Written for **M1** (spectator, read-only) as scoped by section 3.3 of that spec.

## Gate text (quoted verbatim, section 9 item 11)

> 11. rate-limit behavior review: login-attempt and message-frequency behavior checked against
>     observed official-server limits before the live gate is attempted, so the live gate itself
>     cannot trip a rate limit by surprise;

## Sequence fact for the owner to rule on

This review was written on 2026-07-26, **after** the manual live gate (gate 6) had already been
run against the official server (`docs/plans/evidence/phase3-m1-milestone-evidence.md` section 6,
run recorded 2026-07-26). Gate 11 requires the opposite order: this review before the live gate is
attempted, precisely so the live run cannot trip a limit by surprise. That precondition did not
hold for the run that already happened. This is recorded here as a fact, not excused or smoothed
over; the milestone evidence document's own section 6 and section 7 already flag the same
sequence problem and leave the remedy (re-run, or an explicit recorded owner deviation) to the
owner. This document does not decide that question — it supplies the review gate 11 requires so
the owner has the missing input to decide with.

## 1. Every outbound message path in M1

Grep confirms exactly two call sites of `WebSocketTransport.send_raw_text()` in
`showdownbot_studio/godot/src`, both in one file:
`godot/src/ui/panels/spectator_room_gateway.gd:41` and `:54`. No other module in `src/` calls
`send_raw_text()`, and `WebSocketTransport._process()` (`godot/src/net/web_socket_transport.gd:134-184`)
only polls and reads the socket — it contains no send call and no looping/automatic sender of its
own. `ProtocolCommandEncoder` (`godot/src/protocol/protocol_command_encoder.gd`) exposes exactly
two encoders, `encode_join_room` (line 7) and `encode_leave_room` (line 11); there is no encoder
for any other outbound command in this tree, consistent with M1's read-only scope.

### Room join command

- **Code path:** `RoomEntryPanel._on_join_pressed()` (`godot/src/ui/panels/room_entry_panel.gd:74-80`)
  calls `SpectatorRoomGatewayPort.join()`, which in the production implementation
  (`godot/src/ui/panels/spectator_room_gateway.gd:31-34`) calls
  `RoomStateMachine.request_join()` and, if it returns true, sends
  `ProtocolCommandEncoder.encode_join_room(room_id)` (`"|/join %s"`,
  `protocol_command_encoder.gd:7-8`) via `_transport.send_raw_text()` (`spectator_room_gateway.gd:53-56`).
- **Trigger:** human click only — the `JoinButton.pressed` signal
  (`room_entry_panel.gd:45`, wired in `_ready()`).
- **Rate gating:** `RoomStateMachine.request_join()` only succeeds from `State.NOT_JOINED`
  (`godot/src/protocol/room_state_machine.gd:45-50`); every other state returns `false` and sends
  nothing. The `Join` button itself is disabled unless the room state is `NOT_JOINED`
  (`room_entry_panel.gd:98`, `_on_room_state_changed`). Because Godot signal handlers run
  synchronously on the same call stack as the `pressed` emission, `request_join()`'s state
  transition (and the `state_changed` signal that disables the button) completes before
  `_on_join_pressed()` returns and before another input event can be dispatched — a human cannot
  get two `/join` sends past the gateway from a double-click on the same room-entry session.
  **Maximum achievable rate: effectively one `/join` per full join round trip** (state must return
  to `NOT_JOINED` via rejection, send-failure, or an explicit leave+dismiss before a second join
  can be requested); no client-side numeric cap or cooldown timer exists beyond this state gate.

### Leave command

- **Code path:** `RoomEntryPanel._on_leave_pressed()` (`room_entry_panel.gd:83-84`) calls
  `SpectatorRoomGatewayPort.leave()`, which calls `RoomStateMachine.request_leave()` and, if it
  returns true, sends `ProtocolCommandEncoder.encode_leave_room(room_id)` (`"|/leave %s"`,
  `protocol_command_encoder.gd:11-12`) via `send_raw_text()` (`spectator_room_gateway.gd:37-43`).
- **Trigger:** human click only — the `LeaveButton.pressed` signal (`room_entry_panel.gd:46`).
- **Rate gating:** `request_leave()` only succeeds from `State.ACTIVE`
  (`room_state_machine.gd:86-90`); the `Leave` button is disabled unless the state is `ACTIVE`
  (`room_entry_panel.gd:99`). Same synchronous-disable argument as join applies. **Maximum
  achievable rate: one `/leave` per active room membership** — a second leave requires a fresh
  successful join first.

### Automatic reconnect rejoin

- **Code path:** `SpectatorRoomGateway._on_automatic_rejoin_requested()`
  (`spectator_room_gateway.gd:49-51`) sends the identical `encode_join_room()` /
  `send_raw_text()` pair used by a human join — there is no separate, faster send path for this
  case (documented explicitly in the file's class comment, lines 13-19).
- **Trigger:** system-triggered, not human. `RoomStateMachine._on_connection_state_changed()`
  (`room_state_machine.gd:147-160`) emits `automatic_rejoin_requested` exactly once per successful
  reconnect: when the connection transitions to `CONNECTED` while the room's local state is still
  `JOINING` (line 159-160) — either because a reconnect was in progress (`connection_reconnecting()`,
  lines 127-131, 148-150) or because a first join was interrupted by a drop before the server
  answered (the deliberate broader guard documented at lines 151-158). This signal is never emitted
  more than once per successful reconnect; it does not loop.
- **Maximum achievable rate:** bounded by how often a *successful* reconnect can occur — see the
  reconnect worst case below, since that is what actually paces this path.

### WebSocket-level pings (heartbeat)

- **Configured value:** `WebSocketTransport.HEARTBEAT_INTERVAL_S := 20.0`
  (`godot/src/net/web_socket_transport.gd:14`), applied to every newly opened peer in
  `_open_socket()` via `_peer.configure_heartbeat_interval(HEARTBEAT_INTERVAL_S)`
  (`web_socket_transport.gd:126-128`). The production adapter
  (`godot/src/net/godot_socket_peer_adapter.gd:43-44`) sets this directly on the engine's
  `WebSocketPeer.heartbeat_interval` property.
- **What it actually does (Godot's own documentation):** Godot's `WebSocketPeer.heartbeat_interval`
  reference states: *"The interval (in seconds) at which the peer will automatically send WebSocket
  'ping' control frames. When set to `0`, no 'ping' control frames will be sent."* Godot's
  documentation does not specify any behavior for a missing pong (no documented timeout or
  auto-close on a missed reply). `godot/src/net/socket_peer_port.gd:43-48`'s own comment already
  states this precisely and disclaims relying on anything beyond it. This is an **engine-managed
  WebSocket protocol control frame**, not a chat/command message and not something any of this
  project's own code sends through `send_raw_text()` or `ProtocolCommandEncoder` — it is not part
  of the two `send_raw_text()` call sites enumerated above.
- **Rate:** fixed at one automatic ping every 20 seconds per open connection (3 per minute), not
  user- or state-influenced.

## 2. Reconnect worst case

Constants, both in `godot/src/net/web_socket_transport.gd`:

- `RECONNECT_BACKOFF_SCHEDULE_S: Array[float] = [1.0, 2.0, 5.0, 10.0, 20.0]` (line 13) — 5 entries.
- `CONNECT_TIMEOUT_S := 15.0` (line 12), applied identically to a first connect and to an in-flight
  reconnect attempt (lines 159-177).
- `_schedule_next_attempt()` (lines 107-113): once `_reconnect_attempt >= RECONNECT_BACKOFF_SCHEDULE_S.size()`
  (i.e. after the 5th scheduled attempt), `_state_machine.backoff_exhausted()` fires and no further
  automatic attempt is made until a human calls `connect_to_server()` again (line 57-71, which also
  resets `_reconnect_attempt` to 0, line 68).
- Critically, `_on_peer_open()` resets `_reconnect_attempt` to 0 on **every** successful reconnect
  (line 192), not only on a manual connect. The backoff schedule therefore restarts from its first,
  1.0 s step after any success — it does not accumulate across a long session of intermittent
  drops.

Two worst-case numbers follow from this:

- **A single unbroken failing streak** (every attempt fails, never reconnects): up to **5**
  connection attempts before `EXHAUSTED` halts all automatic retries, over a window of roughly
  38 s (backoff waits only, if failures are near-instant: 1+2+5+10+20) up to about 113 s (if every
  attempt uses its full 15 s connect timeout: 5 x 15 + 38). **Zero** automatic rejoin commands are
  sent in this scenario, since `automatic_rejoin_requested` only fires after a *successful*
  reconnect (section 1 above). After the 5th failure, the client requires a human action to try
  again at all.
- **A repeatedly flapping connection** (each reconnect succeeds just long enough to trigger a
  rejoin, then drops again before the next poll): because every success resets the attempt counter
  to 0, the schedule never advances past its first 1.0 s step. The client can therefore cycle
  connect -> automatic rejoin -> drop -> wait 1.0 s -> reconnect indefinitely, with **no
  session-wide cap** on the number of these cycles (the 5-attempt cap in `_schedule_next_attempt()`
  only bounds one unbroken *failing* streak, not a sequence of successes interrupted by drops).
  Concretely, **in a worst-case 5-minute (300 s) window of continuous 1 Hz flapping, up to
  approximately 300 fresh WebSocket connection attempts and up to approximately 300 automatic
  `/join` rejoin commands could be sent** — bounded only by however long the underlying network
  keeps flapping, not by anything in this client.

## 3. Server-side limits found in the pinned source

Pin verified: `git -C ~/.cache/showdownbot/pokemon-showdown rev-parse HEAD` returns
`f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5`, matching the required pin.

### (a) Connections per IP

`Monitor.countConnection(ip)` (`server/monitor.ts:187-206`) increments a 30-minute rolling counter
per IP (`this.connections.increment(ip, 30 * 60 * 1000)`, line 189). At exactly 500 connections in
that window it logs a "cflooding" admin notice and returns `true`; every count above 500 also
returns `true` (lines 190-203). `Punishments.checkIpBanned()` (`server/punishments.ts:1777-1782`)
calls this on every new raw connection and, once tripped, adds the IP to `Punishments.cfloods` so
every later connection from that IP is refused outright: the connection receives
`|popup||modal|PS is under heavy load and cannot accommodate your connection right now.` and is
destroyed (`server/users.ts:1629-1643`, `socketConnect()`, which calls `checkIpBanned()` for
**every** new socket before any user or login object exists, line 1640). Both checks are
short-circuited entirely if `Config.noipchecks` or `Config.nothrottle` is set
(`monitor.ts:188`, `punishments.ts` gate is implicit through `countConnection`'s own guard).

**Limit found: 500 new connections from one IP within a rolling 30-minute window trips a
connection ban (`#cflood`) for the remainder of that window**, in this pinned source's defaults.

### (b) Messages/commands per connection

`server/users.ts:33-42` defines:

```
const THROTTLE_DELAY = 600;
const THROTTLE_DELAY_TRUSTED = 100;
const THROTTLE_DELAY_PUBLIC_BOT = 25;
const THROTTLE_BUFFER_LIMIT = 6;
```

`User.chat()` (`server/users.ts:1429-1465`) is the single entry point every inbound socket line is
routed through: `socketReceive()` (`server/users.ts:1685-1741`) splits each `ROOMID|MESSAGE` frame
into lines and calls `user.chat(line, room, connection)` for each one (line 1739) — there is no
separate path for `/join` or `/leave`; they are ordinary chat-queue messages like any other slash
command. `chat()` applies `throttleDelay` (600 ms default, 100 ms if `this.trusted`, 25 ms if
`this.isPublicBot`, line 1442-1443): a message sent before the previous one's delay has elapsed is
queued (`this.chatQueue`, lines 1445-1458) rather than processed immediately, and once the queue
reaches `THROTTLE_BUFFER_LIMIT - 1` (5) queued messages, further messages are dropped outright with
the reply *"Your message was not sent because you've been typing too quickly."* (lines 1447-1452).
`Config.nothrottle` or sysop access bypasses this entirely (line 1431, 1438).

**Limit found: an untrusted/unauthenticated connection (M1's spectator has no login, so it is
never `trusted` or `isPublicBot`) is throttled to one processed message per 600 ms, with up to 5
messages queued before the 6th is dropped with a "typing too quickly" notice**, in this pinned
source's defaults.

### (c) Room join/leave specific limits

No room-join- or room-leave-specific throttle was found. `server/rooms.ts` contains no
`throttle`/`rate limit` logic scoped to joining or leaving a room (its only throttle constants,
`CRASH_REPORT_THROTTLE` at line 25 and `LAST_BATTLE_WRITE_THROTTLE` at line 27, are unrelated to
room membership). `/join` and `/leave` are ordinary chat-queue messages and are governed entirely
by the general per-connection message throttle in (b); there is no additional or separate limit for
them.

### Login-attempt limits: not found in this repository

`server/loginserver.ts` is only an HTTP client abstraction that talks to a separate login-server
process (`LoginServerInstance`, lines 34+) — it defines request timeouts and batching
(`LOGIN_SERVER_TIMEOUT`, `LOGIN_SERVER_BATCH_TIME`, lines 10-11) but no login-attempt throttling of
its own. No `throttle`/`rate limit`/`attempt` logic was found in this file. The actual account/
password verification backend (`play.pokemonshowdown.com`'s login server) is a separate, closed
service not included in this pinned repository, so any login-attempt rate limit it applies cannot
be verified from this source at all. This is stated explicitly rather than inferring or assuming a
number.

### Production-config caveat

All of the above are the **pinned source's own defaults**. Every one of them (`Config.nothrottle`,
`Config.noipchecks`, the numeric constants themselves) is configuration the operator of
`play.pokemonshowdown.com` could set differently in their deployed `config.js`, which is not part of
this repository and was not inspected — this review cannot and does not claim these are the exact
numbers enforced on the official server today, only that they are what this pinned version of the
open-source server applies by default.

## 4. Assessment

- **Human join/leave clicks:** structurally cannot exceed roughly one command per full state
  round trip (section 1), because the UI button that would send a second command is disabled by
  the same synchronous call that sends the first. This is comfortably under both the 600 ms
  per-message throttle and the 6-message buffer limit found in section 3(b). **Low risk.**
- **Heartbeat pings:** a fixed, engine-managed WebSocket protocol control frame every 20 s, not a
  chat/command message, and not routed through `User.chat()`'s message throttle (section 3(b)
  throttles inbound *text frames* dispatched to `socketReceive()`; a WS-protocol ping control frame
  is handled below that layer). This review did not read the pinned server's WebSocket transport
  library itself to confirm ping control frames are never counted by `countConnection()` or
  `chat()` — that is stated as an assumption based on the protocol-layer/application-layer
  separation visible in `server/users.ts` and `server/sockets.ts`, not as something directly
  verified line-by-line in a socket library file. **Low risk, with that one explicit gap.**
- **Reconnect/automatic rejoin — the one real risk found.** A single unbroken failing streak is
  safely bounded at 5 attempts and 0 rejoins (section 2) — no risk. But the flapping scenario in
  section 2 (~1 new connection and ~1 automatic `/join` per second, indefinitely, no session-wide
  cap) is well below the 600 ms message throttle per individual message (1000 ms > 600 ms, so no
  single rejoin message would be queued or dropped by section 3(b)) but **each cycle is also a
  brand-new WebSocket connection**, and every new connection counts toward the 500-connections-
  per-30-minutes-per-IP limit found in section 3(a). At roughly 1 new connection per second, that
  threshold is reached in a little over **8 minutes** of continuous flapping — well within a
  plausible length for a flaky-network live-spectating session. **This is the one plausible way M1
  could trip a found server-side limit**, and it would not require malice or a bug in this client:
  ordinary unstable Wi-Fi sustained for several minutes could do it, because nothing in
  `WebSocketTransport` caps the number of successful-then-dropped reconnect cycles across a whole
  session (only a single unbroken *failing* streak is capped, at 5).
- **Uncertainty, stated plainly:** every number above comes from reading code, not from measuring
  against the official server. No stress test, flapping simulation, or rapid-click test was run
  against `play.pokemonshowdown.com` or any other live instance for this review (doing so was out
  of scope and not performed). The production deployment's actual configuration may differ from
  this pinned source's defaults (section 3's caveat). The single manual live gate already performed
  (`docs/plans/evidence/phase3-m1-milestone-evidence.md` section 6) exercised only one join, no
  leave, and no reconnect against the official server, so it provides no evidence either way on the
  reconnect-flapping risk identified here.

## 5. Login attempts: not applicable to M1

M1 has no login path of any kind. Verified directly: there is no `session/` directory anywhere
under `godot/src` (confirmed by directory search), and the only occurrence of the word "login" in
`godot/src` is a doc comment in `godot/src/workspace/observation_event_bus.gd:5` stating that
"login/credential data" is explicitly excluded from what the event bus may ever carry — not any
actual login code. `ProtocolCommandEncoder` (`godot/src/protocol/protocol_command_encoder.gd`)
encodes only `/join` and `/leave`; there is no `/trn`, no `challstr`/`assertion` handling, and no
credential code anywhere in this tree. This matches the milestone evidence document's own
independent finding (`phase3-m1-milestone-evidence.md` section 7: "No login exists (`session/`
does not exist as a directory)").

Consequently, half of gate 11 — the login-attempt half — is **not applicable until M2a**, when a
login path is first introduced. **This review must be redone for M2**, once login, chat sending,
and `/choose` exist. At minimum, the M2 redo needs to check:

- what the actual login/authentication flow sends and how often it can retry (M2a);
- whether the login-server abstraction in `server/loginserver.ts` — or the real, separate login
  backend it talks to — enforces any attempt-frequency limit, and whether that can be observed or
  must be treated as unknown;
- outbound chat message sending (M2f), which will exercise the section 3(b) per-message throttle
  and 6-message buffer for real, unlike M1's `/join`/`/leave`-only traffic;
- `/choose` command frequency once `HumanBattleCommandGateway` exists (M2), including whether rapid
  legal re-choices (e.g. changing a selection before submission) could approach the same
  per-message throttle;
- whether M2's own reconnect/resubscribe behavior (challenge/ladder, active battle rejoin) changes
  the reconnect-worst-case analysis in section 2 of this document, since M2 adds send paths beyond
  room join/leave that may also fire on reconnect.

## 6. Operational guidance for anyone running this client against the official server

- **Do not rely on rapid repeated Watch/Leave clicking as a way to "test" anything against the
  official server.** It is not useful even as a stress test: the `Join`/`Leave` buttons are
  disabled synchronously by the same click that sends the command (section 1), so rapid clicking
  does not actually produce rapid sends — the state machine blocks it structurally, not merely by
  convention or by debounce timing in the UI code.
- **Do not deliberately induce repeated connection drops (e.g. toggling network access on and off)
  over several minutes while this client is pointed at the official server.** Section 4 identifies
  this as the one plausible way M1's traffic could trip the pinned server's 500-connections-per-
  30-minutes-per-IP limit, at roughly 8 minutes of continuous 1 Hz flapping in the worst case.
  Ordinary brief network blips (a few seconds) are what the reconnect design targets and are not a
  concern; sustained, repeated flapping over many minutes is.
- **Do not run an extended unattended spectating session over a known-unstable network connection**
  against the official server without being aware of the same risk — a long session on flaky
  Wi-Fi is the realistic way this could happen by accident rather than by deliberate testing.
- **A single, brief connection drop and automatic recovery is expected and safe** — it produces at
  most one new connection and one automatic rejoin, nowhere near either found server-side limit.

## Residual risk and non-goals

This review does not claim to know the official production server's actual deployed configuration
(section 3's caveat) and does not claim any number here was verified by measurement against a live
instance. It does not cover login-attempt behavior at all (section 5) — that is explicitly deferred
to a required M2 redo. It does not claim completeness of the pinned server's throttling logic
outside `server/users.ts`, `server/monitor.ts`, `server/punishments.ts`, and `server/rooms.ts` — a
targeted search (`throttle`/`rate limit`/`THROTTLE`) was run across `server/`, but a search is not a
proof of absence for every possible mechanism elsewhere in the pinned tree.
