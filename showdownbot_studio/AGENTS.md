# ShowdownBot Studio — Agent Rules

Read this before touching anything under `showdownbot_studio/`. The repository-root
`AGENTS.md` still applies; this file adds the Studio-specific rules. The binding design
for the active phase is
[`docs/specs/2026-07-25-phase3-client-design.md`](docs/specs/2026-07-25-phase3-client-design.md);
boundaries are in
[`docs/architecture/PROJECT_BOUNDARIES.md`](docs/architecture/PROJECT_BOUNDARIES.md).

## Non-negotiable maintainer rules

These are review-enforced architecture rules, not recommendations. A violation is a
defect, not a style preference.

1. Every module has exactly one responsibility (one module = one directory = one job).
2. Public interfaces are small, typed, and documented; every module ships a short README
   (purpose, interface, dependencies).
3. No module reaches into another module's internals.
4. No global event bus as an invisible substitute for clean dependencies. The default is
   direct dependency: small explicit typed interfaces, composition-root injection, and
   locally typed signals (as Phase-0 `AppShell` already does). The ObservationEventBus
   carries only selected read-only events; privileged commands never travel on it (see
   below), and it never carries login data or mutable session objects.
5. Every state change has a traceable source. Battle state is **derived, never manually
   patched**: it is built only by the deterministic reducer from typed protocol events
   into read-only snapshots. UI code that writes state directly (`pokemon.hp = 0`,
   `active_slot = 1`, …) is a defect.
6. Protocol, state reducer, and UI stay strictly separated.
7. No duplicate board, team, replay, or validation logic — reuse the existing
   implementation behind its interface (Phase-0 board, Python team validation/packing,
   Python bundle canonicalization).
8. Every new capability needs a clear owner module, tests, and a documented data flow.
9. Typed GDScript everywhere. Bare `Array` and untyped `Dictionary` are restricted to
   audited parsing/serialization boundaries. `Variant` is permitted only for documented
   nullable scalar fields in named typed DTOs/value objects — never for containers, and
   never as a parameter or return type on a cross-module public interface. Values leaving
   a module boundary are named typed DTOs, enums, or value objects.
10. Fail closed by default: on unknown, stale, inconsistent, or incomplete data, block
    the action and surface the condition — never guess, never "best effort".

## The two pipelines

All data moves through exactly these two chains. There are no shortcuts.

```text
Inbound (observation):
Server data → protocol decoder → typed domain events
    → deterministic battle reducer → read-only battle state → UI

Outbound (privileged commands):
Human UI interaction → HumanBattleCommandGateway → request validation
    → protocol command encoder → network transport
```

`protocol/` is the only module that ever sees raw protocol text (inbound) or encodes
protocol commands (outbound). The `HumanBattleCommandGateway` is the only path by which
a human input becomes a server command: it is injected only into the active human battle
controller, is never registered on or discoverable through the event bus, is never part
of any mod surface, and is never imported by replay, battle-state, or analysis modules.
GDScript cannot enforce this at the language level — reviews and tests must.

## User safety defaults

- Server data (including chat and names) is untrusted input; chat renders as plaintext.
- No credentials in logs, exports, crash reports, event payloads, or diagnostics.
- No automatic retry of logins or battle choices; no auto-pick on timer expiry.
- After a reconnect, pending local choices are discarded and never auto-resent; state is
  rebuilt fully from the re-received room history.
- Every outbound action is bound to battle room ID, connection epoch, and current
  `rqid`; stale or duplicate requests are blocked.
- Replays contain only deliberately released data (no chat, no credentials).
- No remote assets; live-server tests are controlled gates, never a substitute for
  local E2E tests.

## Acceptance questions

Work is not merge-ready unless a maintainer can answer all five unambiguously:

1. Which module owns this data?
2. Which module may change it?
3. Where does every outbound server action originate?
4. What happens on invalid or stale data?
5. Which user data can leave this process?

If an answer is "somewhere via the event bus" or "the UI decides", the architecture is
not strict enough yet — fix the structure, not the wording.
