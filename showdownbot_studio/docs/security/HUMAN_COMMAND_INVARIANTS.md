# Phase 3 Human Command Invariants

**Status:** binding F0 deliverable (spec `2026-07-25-phase3-client-design.md` section 3.3, section 4.2.3, section 11)

## Purpose

Carries the machine-checkable command-origin rules spec section 3.3 requires as an F0 deliverable,
so the `studio-security-invariants` CI lane and every later gate can point at one canonical,
reviewable list instead of re-deriving it from the design document's prose each time.

## Binding command-origin invariants

- only the gateway may request choice commands
- only the protocol encoder may build command strings
- only `net/` may write to the socket
- no replay/analyzer/mod/bot module imports the gateway
- every choice command carries room ID, connection epoch, and current `rqid`
- no request is sent twice
- superseded requests are never re-sent
- there is no automatic selection on timeout or error

## Enforcement mapping

| Invariant | Enforced by |
|---|---|
| only the gateway may request choice commands | `HumanBattleCommandGateway` injection discipline (spec section 4.2.3); code review |
| only the protocol encoder may build command strings | `protocol/` module boundary (spec section 4.1); no other module assembles a command string |
| only `net/` may write to the socket | `net/` module boundary (spec section 4.1) |
| no replay/analyzer/mod/bot module imports the gateway | `test_no_module_outside_ui_panels_imports_the_human_battle_command_gateway` (Task 9), running in the `studio-security-invariants` CI lane |
| every choice command carries room ID, connection epoch, and current `rqid` | The choice-lifecycle field list and check sequence (spec section 7), tested in M2's choice-lifecycle tests |
| no request is sent twice | `ChoiceRequestState.SUBMITTED`/`SUPERSEDED` transitions (spec section 4.8, `LIVE_STATE_MACHINES.md`) |
| superseded requests are never re-sent | Same as above; spec section 6.2, section 6.3 |
| there is no automatic selection on timeout or error | Spec section 6.1's fail-closed error table; `ChoiceProvenance.SERVER_DEFAULT_ON_TIMEOUT` is the server's action, never the client's (spec section 7) |

## Gateway bans

Restated from spec section 4.2.3, binding for `HumanBattleCommandGateway` and every narrowly scoped
sibling gateway (room join/leave, chat send, challenge/ladder, timer/forfeit/undo):

1. never registered on, or discoverable through, the `ObservationEventBus`;
2. never part of any mod attachment surface in any later phase;
3. never imported by `replay/`, `battle/`, or any future analysis/matchup module;
4. injected only into the active human battle controller in `ui/panels/` (from M2d onward);
   nothing else in the application holds a reference to it.

This is a **structural** guarantee, not a runtime-enforced one — GDScript has no engine-level
`private` keyword (spec section 4.2.3's honesty note). It is upheld by injection discipline, by
code review, and by the architecture test in the enforcement mapping above.
