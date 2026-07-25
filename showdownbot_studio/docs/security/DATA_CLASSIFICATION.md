# Phase 3 Data Classification

**Status:** binding F0 deliverable (spec `2026-07-25-phase3-client-design.md` section 3.3)

## Purpose

Classifies every category of data Phase 3 handles so a later reviewer can answer
`AGENTS.md`'s acceptance question 5 ("which user data can leave this process?") without
re-deriving it from source.

## Classification levels

- **Secret, never stored.** Never written to disk, log, crash report, event payload, or export
  (spec section 5.1).
- **Sensitive, session-lifetime only.** Held only for the duration of a login session; released on
  logout or app exit; never intentionally persisted.
- **Untrusted input.** Received from the server or another player; rendered defensively, never
  trusted as source code or markup (spec section 5.2).
- **Portable evidence.** Data that may leave the process only through an explicit user action (a
  saved replay), and only in the fields the design allows (spec section 4.5).

## Data categories

| Category | Level | Leaves this process? | Reference |
|---|---|---|---|
| Login credential value | Secret, never stored | Never | section 5.1 |
| `SessionState` metadata (non-secret) | Sensitive, session-lifetime | Never | section 4.8, section 5.1 |
| `LiveBattleSnapshot` (derived battle state) | Sensitive, session-lifetime | Only via an explicit "save replay" action, converted first | section 4.7, section 4.5 |
| Chat content | Untrusted input | Never by default (diagnostic mode only, opt-in); excluded from replay by default | section 5.2 |
| Player names | Untrusted input | Only as already-seat-pseudonymized in a saved replay, matching Phase-0's `portable-pseudonymous-v1` profile | section 5.2, `PROJECT_BOUNDARIES.md` section 3 |
| `TeamBundleV1` contents | Portable evidence (already offline, pre-validated) | Read-only; never re-packed, re-validated, or re-exported by this client | section 3.4 |
| Saved replay bundle | Portable evidence | Yes, deliberately, via `ReplayExportGateway` | section 4.5, section 4.5.1 |
| Diagnostic/log output | Derived from the above; must not re-introduce a Secret or unredacted Untrusted-input value | See `LOGGING_AND_REDACTION.md` | section 5.1 (search list) |

## Cross-references

- Credential-specific lifecycle detail: `CREDENTIAL_LIFECYCLE.md`.
- Logging/redaction rules for every category above: `LOGGING_AND_REDACTION.md`.
- Untrusted-input handling detail for chat/server content: `UNTRUSTED_SERVER_CONTENT.md`.
