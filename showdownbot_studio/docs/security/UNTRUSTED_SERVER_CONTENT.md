# Phase 3 Untrusted Server Content

**Status:** binding F0 deliverable (spec `2026-07-25-phase3-client-design.md` section 3.3, section 5.2, section 6.1)

## Purpose

Fixes the chat/server-content trust boundary before `protocol/`'s decoder (M1b) or any chat UI
(M2f) exists, so both are built against a written contract instead of an ad hoc one.

## What counts as untrusted

Server-delivered chat lines, player names, and raw protocol text in general are untrusted input,
exactly like an imported bundle or team file is untrusted input in Phase 0
(`PROJECT_BOUNDARIES.md` section 3; spec section 5.2). This includes room names, battle titles,
and any other server-supplied string surfaced in the UI.

## Handling rules

- No rendering of server-delivered HTML.
- No BBCode interpretation; v1 renders all chat content as safe plaintext.
- URLs inside chat are never clickable without a deliberate, separate user action — no
  auto-linkification that becomes a default click target.
- Control characters are escaped before display.
- Message length is capped.
- Chat content does not appear in logs unless a diagnostic mode is explicitly enabled by the user
  for that session (see `LOGGING_AND_REDACTION.md`).
- Chat is excluded from replay bundles by default, at the recording stream itself — not as a later
  filter on an already-recorded stream (spec section 4.5, section 5.2).

(Verbatim from spec section 5.2, restated here as the binding pre-implementation contract for M2f's
chat UI and M1b's decoder.)

## Protocol parsing boundary

`protocol/` is the only module in the whole application, across every phase, allowed to see or
produce raw protocol text (spec section 4.1, `PROJECT_BOUNDARIES.md` section 4). No UI component
ever parses raw WebSocket text; every other module receives only typed, decoded DTOs.

## Unknown protocol line handling

An unknown or unrecognized protocol line is logged and surfaced as "not understood." The client
never crashes on it and never guesses an interpretation (spec section 6.1's fail-closed error
table). The module that classifies an event decides what is recoverable — `protocol/` for
parse-level conditions, `net/` for connection-level conditions — and a downstream module never
invents its own recovery logic (spec section 6.1).
