# Phase 3 Logging and Redaction

**Status:** binding F0 deliverable (spec `2026-07-25-phase3-client-design.md` section 3.3, section 5.1, section 5.2)

## Purpose

Fixes what may and may not appear in any Studio log, diagnostic export, or crash report Phase 3
produces, and where redaction must happen before a value is captured at all.

## Never-log list

- Any credential value, at any stage of `CREDENTIAL_LIFECYCLE.md` (spec section 5.1).
- Chat content, unless a diagnostic mode is explicitly enabled by the user for that session (spec
  section 5.2).
- Full player identities beyond the seat-pseudonym scheme already used for Phase-0 portable bundles
  (`PROJECT_BOUNDARIES.md` section 3).
- Raw HTTP request/response bodies of the single login exchange beyond what is needed to classify
  success/failure (spec section 5.1).

## Diagnostic mode

Chat content may be captured in a diagnostic log only when the user has explicitly enabled a
diagnostic mode for that session (spec section 5.2). It is off by default. Enabling it never
changes whether chat is included in a saved replay bundle — that stays excluded by default
regardless of diagnostic mode (spec section 5.2, section 4.5).

## Redaction points

A field this document forbids is never captured into the canonical stream or a log sink in the
first place — it is not filtered out later, so no downstream redaction step is trusted to catch a
leak that already happened upstream (spec section 4.5). Concretely:

- `net/`'s `LoginHttpTransport` never logs the outbound request body's credential field.
- The `ObservationEventBus` (spec section 4.2.2) never carries a credential or raw chat payload —
  only its fixed allowlist of already-published, read-only events.
- `replay/`'s `LiveRecordingSink` never carries a credential or chat field into the canonical
  recording stream (spec section 4.5).
- `ReplayExportGateway` (spec section 4.5.1) captures the exporter subprocess's stderr and redacts
  it before any surfacing to the user or a log.

## Review checklist

The credential-handling review gate (spec section 9 gate 7) walks this exact list before phase
closure: Godot debug output; exception and error texts; HTTP request dumps; `ObservationEventBus`
payloads and Godot signals; crash reports; diagnostic exports; screenshot or UI-state
restore/session-persistence features; clipboard usage. This document exists so that list has a
home before any of the code it constrains is written.
