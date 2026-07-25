# Phase 3 Credential Lifecycle

**Status:** binding F0 deliverable (spec `2026-07-25-phase3-client-design.md` section 3.3, section 5.1)

## Purpose

Fixes the exact stages a credential value passes through during login, so `session/`'s
`CredentialProvider`/`LoginCoordinator` (introduced M2a) have a written contract to implement
against before any of that code exists.

## Lifecycle stages

1. **Acquisition.** The user types a password into a login UI control in `ui/panels/`. The value
   exists only in that control's own buffer until submitted.
2. **Hand-off.** On submit, the value is handed to `session/`'s `CredentialProvider` for exactly
   one login attempt. `SessionState` (spec section 4.8) transitions `ANONYMOUS` → `AUTHENTICATING`.
3. **Single-use exchange.** `session/`'s `LoginCoordinator` passes the value to `net/`'s
   `LoginHttpTransport`, which makes the single HTTPS request to Showdown's login/action endpoint
   and returns a typed login result. `LoginHttpTransport` stores nothing afterward (spec section 5.1).
4. **Release.** Every reference to the credential value is released immediately after the exchange
   completes, success or failure. No intentional retention exists past this point.
5. **Resulting state.** `SessionState` transitions to `AUTHENTICATED` (success) or `LOGIN_FAILED`
   (failure); non-secret session metadata persists in `SessionState` for the session's lifetime,
   but the credential value itself does not.

## Storage

v1 ships exactly one `CredentialProvider` implementation: memory-only, holding a value only for
the duration of stage 3 above. There is no credential file, cached token, or keyring write in this
phase's default configuration (spec section 5.1).

## Never-do list

A credential value must never reach: Godot debug output; exception or error text; an HTTP request
dump beyond the single login exchange itself; an `ObservationEventBus` payload or Godot signal; a
crash report; a diagnostic export; a screenshot or UI-state restore/session-persistence feature;
the clipboard (spec section 5.1's explicit review-gate search list, restated here as the
authoring-time checklist).

## Future extension

A second `CredentialProvider` implementation backed by the Windows Credential Manager may be added
later without changing anything outside `session/` that depends on `CredentialProvider` — nothing
outside `session/` may depend on which implementation is active (spec section 5.1). This is a
documented extension point, not work this F0 slice performs.
