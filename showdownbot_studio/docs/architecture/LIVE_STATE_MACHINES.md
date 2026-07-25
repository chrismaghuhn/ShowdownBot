# Phase 3 Live State Machines

**Status:** binding F0 deliverable (spec `2026-07-25-phase3-client-design.md` section 3.3, section 4.8)

## Purpose

Fixes the full transition table for each of the four binding state machines spec section 4.8
names, so M1–M2 sub-slices implement against a written contract instead of inventing transitions
ad hoc. Every transition specifies its source state(s), triggering event, resulting state, and
user-visible behavior, per spec section 4.8's own requirement. An untested or unspecified
transition is treated the same as an untested branch anywhere else in this design (spec section 8):
not done.

## ConnectionState transitions

| Source state | Triggering event | Resulting state | Visible user behavior |
|---|---|---|---|
| `DISCONNECTED` | user or app initiates connect | `CONNECTING` | "Connecting..." status shown |
| `CONNECTING` | WebSocket handshake succeeds | `CONNECTED` | "Connected" status shown |
| `CONNECTING` | initial connection attempt fails, retries remain | `RECONNECTING` | "Reconnecting..." status with backoff countdown shown |
| `CONNECTED` | socket closes unexpectedly or heartbeat times out | `RECONNECTING` | "Disconnected, reconnecting..." status with backoff countdown shown |
| `CONNECTED` | user explicit disconnect | `DISCONNECTED` | "Disconnected" status shown |
| `RECONNECTING` | a reconnect attempt succeeds | `CONNECTED` | "Connected" status shown; triggers full battle-state rebuild (section 6.2) |
| `RECONNECTING` | a reconnect attempt fails, retries remain | `RECONNECTING` | updated backoff countdown shown (self-transition) |
| `RECONNECTING` | backoff attempts exhausted | `EXHAUSTED` | "Disconnected" status shown and stays visibly disconnected; no silent fallback |
| `RECONNECTING` | user explicit disconnect/cancel during reconnect | `DISCONNECTED` | "Disconnected" status shown |
| `EXHAUSTED` | user manually retries connect | `CONNECTING` | "Connecting..." status shown |
| `EXHAUSTED` | user dismisses / explicit disconnect | `DISCONNECTED` | "Disconnected" status shown |

## SessionState transitions

| Source state | Triggering event | Resulting state | Visible user behavior |
|---|---|---|---|
| `ANONYMOUS` | user submits login credentials | `AUTHENTICATING` | "Logging in..." shown |
| `AUTHENTICATING` | server returns a valid login assertion | `AUTHENTICATED` | "Logged in as \<username\>" shown |
| `AUTHENTICATING` | server rejects credentials, HTTP error, or timeout | `LOGIN_FAILED` | clear failure message shown (section 6.1) |
| `LOGIN_FAILED` | user explicitly submits login credentials again | `AUTHENTICATING` | "Logging in..." shown; never automatic (section 6.1) |
| `LOGIN_FAILED` | user cancels / navigates away from login | `ANONYMOUS` | "Not logged in" shown |
| `AUTHENTICATED` | user explicit logout, or `ConnectionState` reaches `EXHAUSTED` and the session is invalidated | `ANONYMOUS` | "Logged out" / "Session ended" shown |

## RoomState transitions

| Source state | Triggering event | Resulting state | Visible user behavior |
|---|---|---|---|
| `NOT_JOINED` | user enters a room ID/URL, or client sends `/join` | `JOINING` | "Joining room..." shown |
| `JOINING` | server confirms the join (room init event received) | `ACTIVE` | room content renders |
| `JOINING` | unknown or private room ID rejected by server | `NOT_JOINED` | clear error shown; no fallback room, no room browser (section 6.1) |
| `ACTIVE` | user leaves the room / sends `/leave` | `LEAVING` | "Leaving..." shown |
| `ACTIVE` | server closes the room (e.g. battle ended and room expired) | `CLOSED` | "Room closed" shown |
| `ACTIVE` | connection reconnects while this room was `ACTIVE` | `JOINING` | "Rejoining..." shown; pending unconfirmed choices discarded (section 6.2) |
| `JOINING` | rejoin confirmed and room history resent | `ACTIVE` | full battle-state rebuild from resent history (section 6.2) |
| `LEAVING` | server confirms the leave | `NOT_JOINED` | UI resets to pre-join state |
| `CLOSED` | user dismisses the closed room / returns to matchmaking | `NOT_JOINED` | UI resets to pre-join state |

## ChoiceRequestState transitions

| Source state | Triggering event | Resulting state | Visible user behavior |
|---|---|---|---|
| `NONE` | server sends a new `\|request\|` | `OPEN` | choice UI populated with legal actions from the request JSON |
| `OPEN` | human completes selection and all five section-7 checks pass | `SUBMITTING` | UI locks, "Submitting..." shown |
| `SUBMITTING` | protocol/net hands the command to the socket successfully | `SUBMITTED` | "Waiting for opponent" / turn resolving shown |
| `SUBMITTING` | local transport/send failure (socket handoff fails) | `OPEN` | send failure surfaced (section 6.1); prior selection kept in the UI; no auto-retry |
| `SUBMITTED` | server declines the submitted choice | `REJECTED` | server error surfaced (section 6.1) |
| `REJECTED` | choice UI reopens after a rejection | `OPEN` | choice UI re-populated; no auto-retry (section 6.1, section 7) |
| `OPEN` | a newer `rqid` arrives before submission | `SUPERSEDED` | surfaced notice; stale request dropped, never sent (section 6.2, section 6.3) |
| `SUBMITTED` | a newer `rqid` arrives after submission (e.g. request-replacement/undo) | `SUPERSEDED` | surfaced notice; prior submission superseded |
| `SUPERSEDED` | the newer `\|request\|` that superseded the prior one is itself opened for choice | `OPEN` | fresh choice UI for the new `rqid` |
| `SUBMITTED` | the turn resolves normally and no new request is yet open | `NONE` | battle continues; ready for the next `\|request\|` |
| `OPEN`, `SUBMITTING`, `SUBMITTED`, `REJECTED`, or `SUPERSEDED` | reconnect triggers a full rebuild (section 6.2) and the rebuilt history has no outstanding request | `NONE` | local unconfirmed choice discarded, never auto-resent |
| `OPEN`, `SUBMITTING`, `SUBMITTED`, `REJECTED`, or `SUPERSEDED` | reconnect triggers a full rebuild (section 6.2) and the rebuilt history's latest state is still an outstanding request | `OPEN` | choice UI re-populated from the rebuilt request; never auto-resent |

## Invalid transitions (explicitly rejected)

Per spec section 4.8/section 8, an invalid transition must be tested as an explicit rejection, not
merely left unexercised. At minimum, the following are invalid and must have a rejection test:

- `ConnectionState`: `DISCONNECTED` → `CONNECTED` directly (must pass through `CONNECTING`);
  `DISCONNECTED` → `RECONNECTING` (no prior connection attempt to reconnect from); `EXHAUSTED` →
  `CONNECTED` directly (must pass through `CONNECTING`).
- `SessionState`: `ANONYMOUS` → `AUTHENTICATED` directly (must pass through `AUTHENTICATING`);
  `AUTHENTICATING` → `AUTHENTICATING` (a repeated submit while authenticating is blocked, not
  queued).
- `RoomState`: `NOT_JOINED` → `ACTIVE` directly (must pass through `JOINING`); `CLOSED` → `ACTIVE`
  (a closed room never reopens; a new join creates a new `RoomState` instance).
- `ChoiceRequestState`: `NONE` → `SUBMITTING` directly (must pass through `OPEN`); `SUBMITTED` →
  `SUBMITTING` automatically on timeout (explicitly forbidden — spec section 6.1, "the client
  never auto-picks a move on timeout"); `SUPERSEDED` → `SUBMITTED` (a superseded request can never
  be submitted); `SUBMITTING` → `REJECTED` directly (a server decline can only arrive after the
  socket handoff completes, i.e. from `SUBMITTED`; a `SUBMITTING`-state send failure resolves to
  `OPEN`, never `REJECTED`).

## Cross-machine interactions

`RoomState`'s reconnect transitions (`ACTIVE` → `JOINING` → `ACTIVE`) and `ChoiceRequestState`'s
reconnect-triggered transitions both fire from the same underlying event: `ConnectionState`
reaching `RECONNECTING` then `CONNECTED` again (spec section 6.2). `ChoiceRequestState.SUPERSEDED`
is the enumerated form of the "stale `rqid`" condition (spec section 6.2, section 7);
`ConnectionState.EXHAUSTED` is the enumerated form of the "reconnect exhausts backoff" row in spec
section 6.1. `SessionState` is unaffected by a `RoomState` or `ChoiceRequestState` transition in
either direction — logging out does not, by itself, leave or close a room; leaving a room does
not, by itself, end a session.
