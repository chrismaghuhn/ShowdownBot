# Phase 3 F0 â€” Architecture Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Status:** APPROVED (owner, 2026-07-25) â€” code additionally requires a separate implementation
go-ahead
**Authorizing spec:** [`../specs/2026-07-25-phase3-client-design.md`](../specs/2026-07-25-phase3-client-design.md)
(APPROVED 2026-07-25), Â§3.3 F0, Â§4.4 F0 row, Â§9 gate 1
**Goal:** Land Phase 3's F0 slice â€” the `StudioRoot`/`WorkspaceRouter`/`OfflineViewerWorkspace`
shell scaffold, the `BattleBoardSnapshot`/`bind()` board-presentation-contract refactor in
`replay/`, the eight binding pre-M1 documents, and the forbidden-dependency architecture tests plus
their dedicated CI lane â€” with zero WebSocket/protocol/session/battle runtime code and every
existing Phase-0 test still green.
**Architecture:** F0 touches exactly three areas named in spec Â§4.4: `godot/src/workspace/` (new
`StudioRoot`/`WorkspaceRouter`/`OfflineViewerWorkspace` scaffold wrapping the existing `AppShell`
unchanged), `godot/src/replay/` (the `BattleBoardSnapshot`/`BattleBoardSlotSnapshot` value objects
and a `ReplayBoardPresentationAdapter` that converts `BoardModel` into that neutral contract, with
`AbstractBoardView.bind()` retyped to consume it instead of `BoardModel` directly), and
`showdownbot_studio/tests/python/` plus a new `.github/workflows/studio-security-invariants.yml`
lane (three forbidden-dependency/typed-boundary architecture tests). Eight binding documents land
under `showdownbot_studio/docs/security/` and `showdownbot_studio/docs/architecture/`.
**Tech stack:** Godot 4.5.2 typed GDScript + gdUnit4 (pinned, `showdownbot_studio/godot/tools/`),
Python 3.12 pytest (`showdownbot_studio/python`, `showdownbot_studio/tests/python/`).

## Ordering rationale

Tasks run in this order: **binding documents (1â€“8) â†’ forbidden-dependency architecture tests + CI
lane (9â€“12) â†’ board-presentation-contract refactor in `replay/` (13â€“16) â†’ workspace scaffold
(17â€“18) â†’ full-suite verification (19)**.

Docs come first because every later task cites them (the architecture tests cite
`HUMAN_COMMAND_INVARIANTS.md`'s rules; the refactor and scaffold tasks are exactly what
`LIVE_STATE_MACHINES.md` and `MODULE_CATALOG.md` describe). The architecture tests come next, before
any production code changes, so the refactor and scaffold tasks are built and merged under the same
CI guardrail a later sub-slice will be held to â€” this also means the refactor's new typed
`BattleBoardSnapshot` contract lands under a live "no untyped container crosses a module boundary"
check instead of only being checked after the fact.

**Board-presentation refactor (13â€“16) is ordered before the workspace scaffold (17â€“18), and the plan
verified there is no dependency requiring the opposite order.** The actual scene wiring was read
before deciding this:

- `showdownbot_studio/godot/project.godot:12` sets `run/main_scene="res://src/workspace/app_shell.tscn"`.
  No other production file reads `run/main_scene`; nothing but the engine's own scene bootstrap
  consumes it.
- Every existing gdUnit test that needs `AppShell` (`test_app_shell_smoke.gd`,
  `test_app_shell_decision.gd`, `test_app_shell_replay.gd`, `test_app_shell_plan_e.gd`,
  `test_workspace_shortcuts.gd`, and every `decision/`/`timeline/`/`replay/` test that spawns a
  shell) does so with `preload("res://src/workspace/app_shell.tscn")` directly â€” none of them
  instantiate the project's main scene. Changing `run/main_scene` to `studio_root.tscn` (Task 18)
  therefore cannot break any existing test.
- `AbstractBoardView`, `BoardModel`, `ReplayPresenter`, and `ReplayWorkspace` (the refactor's targets,
  Tasks 13â€“16) live entirely under `godot/src/replay/` and are wired together inside
  `replay_workspace.tscn` and `app_shell.tscn`. Neither `StudioRoot` nor `WorkspaceRouter` nor
  `OfflineViewerWorkspace` (Tasks 17â€“18) reference any of those four types, and the refactor never
  touches `workspace/app_shell.gd` or `app_shell.tscn` at all (`AppShell` is wrapped **unchanged**,
  per spec Â§4.6).

With no real dependency either way, the refactor is sequenced first because it is the riskier,
higher-line-count change (a public API signature change plus a data-shape migration through three
existing files and their tests) and benefits from running under the Task 9â€“12 CI guardrail
immediately; the scaffold is sequenced last because it is purely additive, does not touch a single
existing production file's *content* (only `project.godot`'s one `run/main_scene` line), and has nothing
left to react to once the refactor is done.

## Baseline (recorded before this plan's first task)

```
cd showdownbot_studio/python
python -m pytest -q --collect-only
```

Real output tail, captured during planning:

```
114 tests collected in 0.07s
```

Task 19 re-runs this and the gdUnit suite and compares against this recorded baseline.

---

## Task 1 â€” `docs/security/THREAT_MODEL.md`

**Files:**
- Create: `showdownbot_studio/docs/security/THREAT_MODEL.md`
- Create: `showdownbot_studio/tests/python/test_f0_binding_docs.py`

- [x] Write the failing test. Create `showdownbot_studio/tests/python/test_f0_binding_docs.py`:

  ```python
  """F0 binding-document existence/structure guards (spec 2026-07-25-phase3-client-design.md
  section 3.3, section 9 gate 1). Each test asserts a required F0 deliverable doc exists and
  carries its required section structure -- not full prose review, which is a human gate-9
  review task, but enough that a doc silently regressed to an empty stub fails loudly.
  """
  from __future__ import annotations

  from pathlib import Path

  import pytest

  from conftest import STUDIO_ROOT  # type: ignore[import-not-found]

  _DOCS_SECURITY = STUDIO_ROOT / "docs" / "security"
  _DOCS_ARCHITECTURE = STUDIO_ROOT / "docs" / "architecture"


  def _assert_doc_has_headings(path: Path, required_headings: list[str]) -> None:
      assert path.is_file(), f"missing required F0 doc: {path}"
      text = path.read_text(encoding="utf-8")
      missing = [h for h in required_headings if h not in text]
      assert not missing, f"{path.name} missing required headings: {missing}"


  def test_threat_model_doc_exists_with_required_sections():
      _assert_doc_has_headings(
          _DOCS_SECURITY / "THREAT_MODEL.md",
          [
              "## Purpose and scope",
              "## Assets",
              "## Trust boundaries",
              "## Threat actors",
              "## Threats and mitigations",
              "## Residual risk and non-goals",
          ],
      )
  ```

- [x] Run it and confirm it fails for the right reason:

  ```
  cd showdownbot_studio/python
  python -m pytest -q -k test_threat_model_doc_exists_with_required_sections
  ```

  Expected failure: `AssertionError: missing required F0 doc: ...THREAT_MODEL.md`.

- [x] Write the doc. Create `showdownbot_studio/docs/security/THREAT_MODEL.md`:

  ```markdown
  # Phase 3 Threat Model

  **Status:** binding F0 deliverable (spec `2026-07-25-phase3-client-design.md` section 3.3)
  **Scope:** the full Showdown protocol client (Phase 3), v1 as scoped by section 3 of the spec.

  ## Purpose and scope

  This document enumerates the assets Phase 3 introduces, the trust boundaries between them, the
  threat actors positioned to attack them, and the mitigation each threat maps to in the approved
  design. It does not re-derive the design; every mitigation cited here is a cross-reference to a
  binding section of `2026-07-25-phase3-client-design.md`, not a new decision.

  ## Assets

  - The user's Showdown account credential, held only transiently during a login exchange (spec
    section 5.1).
  - Session-lifetime, non-secret metadata (`SessionState`, spec section 4.8).
  - The connection to the official Showdown server (spec section 4.1, `net/`).
  - Battle state derived during a live battle (`LiveBattleSnapshot`, spec section 4.7).
  - Chat content received in a battle room (spec section 5.2).
  - The offline, Python-validated `TeamBundleV1` a user loads for challenge/ladder play (spec
    section 3.4).
  - A saved replay bundle (spec section 4.5, section 4.5.1).
  - The outbound authority to send a `/choose` command (spec section 4.2.3, section 11).

  ## Trust boundaries

  - The Showdown server is untrusted input once its bytes cross the socket: only `protocol/` may
    parse it (spec section 4.1, `PROJECT_BOUNDARIES.md` section 4).
  - Chat lines and player names are untrusted input, handled exactly like an imported bundle or team
    file in Phase 0 (spec section 5.2).
  - The offline team bundle is a pre-validated, hash-checked artifact re-verified on load, never
    re-packed or re-validated in GDScript (spec section 3.4).
  - The `ReplayExportGateway`'s Python subprocess boundary is a separate, out-of-process trust
    boundary with its own contract (spec section 4.5.1).
  - Every module boundary inside the client is itself a trust boundary in the structural sense of
    spec section 4.2: a module may only reach another through a direct typed dependency, the
    read-only `ObservationEventBus`, or a privileged command gateway.

  ## Threat actors

  - A malicious or compromised official server, or a network attacker between the client and it
    (mitigated by TLS transport in `net/` and by `protocol/` treating all inbound text as untyped
    until decoded).
  - A malicious chat sender in the same battle room (spec section 5.2).
  - A local attacker with filesystem or process access on the user's own machine (mitigated by
    "v1 stores nothing" for credentials, spec section 5.1, and by the `ReplayExportGateway`'s pinned,
    non-PATH-resolved subprocess contract, spec section 4.5.1).
  - A supply-chain attacker substituting the replay-export subprocess (mitigated by "runs the pinned
    repository exporter â€” never a bare Python interpreter or a package resolved via PATH/ambient
    environment," spec section 4.5.1).
  - Any in-application code path attempting to originate a `/choose` command outside a human UI
    interaction (the single property spec section 11 exists to prevent; mitigated structurally by
    the `HumanBattleCommandGateway`'s four bans, spec section 4.2.3, and enforced by the
    `studio-security-invariants` CI lane, spec section 8.2).

  ## Threats and mitigations

  | Threat | Mitigation | Spec reference |
  |---|---|---|
  | Credential leaks to disk, logs, or exports | v1 stores nothing; explicit search list at every phase-closure gate | section 5.1, section 9 gate 7 |
  | Chat renders as executable content (HTML/BBCode) | Plaintext-only rendering, no auto-linkification, escaped control characters | section 5.2 |
  | A module bypasses the three communication paths | Structural discipline plus the forbidden-dependency architecture tests (this F0 slice) | section 4.2, section 8.2 |
  | An automated or non-human path sends a battle choice | `HumanBattleCommandGateway`'s four bans; gateway-import architecture test | section 4.2.3, section 11 |
  | A stale or duplicate choice reaches the server | Epoch/`rqid` binding and the checks in section 7 | section 6.2, section 7 |
  | A live DTO leaks into a portable replay bundle | `LiveRecordingSink` converts before export; architecture test forbids a live DTO type in a bundle-writer file | section 4.1.2, section 4.5 |
  | A compromised or substituted export subprocess | Pinned repository exporter only, temp app-owned working directory, timeout, atomic publish | section 4.5.1 |

  ## Residual risk and non-goals

  Secure memory zeroization is not claimed for the GDScript runtime (spec section 5.1): this
  document does not claim a credential's bytes are erased from process memory at a specific
  instant, only that no code path intentionally retains, logs, or exports it. This document does not
  cover a compromised operating system, a keylogger, or a compromised Showdown account outside this
  client's control â€” those remain out of scope exactly as they are for any client of a service the
  user does not operate.
  ```

- [x] Run the test again and confirm it passes:

  ```
  cd showdownbot_studio/python
  python -m pytest -q -k test_threat_model_doc_exists_with_required_sections
  ```

  Expected: `1 passed`.

- [x] Commit:

  ```
  git add showdownbot_studio/docs/security/THREAT_MODEL.md showdownbot_studio/tests/python/test_f0_binding_docs.py
  git commit -m "docs(studio): add Phase 3 F0 threat model"
  ```

---

## Task 2 â€” `docs/security/DATA_CLASSIFICATION.md`

**Files:**
- Create: `showdownbot_studio/docs/security/DATA_CLASSIFICATION.md`
- Modify: `showdownbot_studio/tests/python/test_f0_binding_docs.py`

- [x] Write the failing test. Append to `showdownbot_studio/tests/python/test_f0_binding_docs.py`:

  ```python
  def test_data_classification_doc_exists_with_required_sections():
      _assert_doc_has_headings(
          _DOCS_SECURITY / "DATA_CLASSIFICATION.md",
          [
              "## Purpose",
              "## Classification levels",
              "## Data categories",
              "## Cross-references",
          ],
      )
  ```

- [x] Run and confirm failure:

  ```
  cd showdownbot_studio/python
  python -m pytest -q -k test_data_classification_doc_exists_with_required_sections
  ```

  Expected: `AssertionError: missing required F0 doc: ...DATA_CLASSIFICATION.md`.

- [x] Write the doc. Create `showdownbot_studio/docs/security/DATA_CLASSIFICATION.md`:

  ```markdown
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
  ```

- [x] Run and confirm pass:

  ```
  cd showdownbot_studio/python
  python -m pytest -q -k test_data_classification_doc_exists_with_required_sections
  ```

- [x] Commit:

  ```
  git add showdownbot_studio/docs/security/DATA_CLASSIFICATION.md showdownbot_studio/tests/python/test_f0_binding_docs.py
  git commit -m "docs(studio): add Phase 3 F0 data classification"
  ```

---

## Task 3 â€” `docs/security/CREDENTIAL_LIFECYCLE.md`

**Files:**
- Create: `showdownbot_studio/docs/security/CREDENTIAL_LIFECYCLE.md`
- Modify: `showdownbot_studio/tests/python/test_f0_binding_docs.py`

- [x] Write the failing test. Append:

  ```python
  def test_credential_lifecycle_doc_exists_with_required_sections():
      _assert_doc_has_headings(
          _DOCS_SECURITY / "CREDENTIAL_LIFECYCLE.md",
          [
              "## Purpose",
              "## Lifecycle stages",
              "## Storage",
              "## Never-do list",
              "## Future extension",
          ],
      )
  ```

- [x] Run and confirm failure (same shape as Task 1/2, doc missing).

- [x] Write the doc. Create `showdownbot_studio/docs/security/CREDENTIAL_LIFECYCLE.md`:

  ```markdown
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
     one login attempt. `SessionState` (spec section 4.8) transitions `ANONYMOUS` â†’ `AUTHENTICATING`.
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
  later without changing anything outside `session/` that depends on `CredentialProvider` â€” nothing
  outside `session/` may depend on which implementation is active (spec section 5.1). This is a
  documented extension point, not work this F0 slice performs.
  ```

- [x] Run and confirm pass; commit:

  ```
  git add showdownbot_studio/docs/security/CREDENTIAL_LIFECYCLE.md showdownbot_studio/tests/python/test_f0_binding_docs.py
  git commit -m "docs(studio): add Phase 3 F0 credential lifecycle"
  ```

---

## Task 4 â€” `docs/security/LOGGING_AND_REDACTION.md`

**Files:**
- Create: `showdownbot_studio/docs/security/LOGGING_AND_REDACTION.md`
- Modify: `showdownbot_studio/tests/python/test_f0_binding_docs.py`

- [x] Write the failing test. Append:

  ```python
  def test_logging_and_redaction_doc_exists_with_required_sections():
      _assert_doc_has_headings(
          _DOCS_SECURITY / "LOGGING_AND_REDACTION.md",
          [
              "## Purpose",
              "## Never-log list",
              "## Diagnostic mode",
              "## Redaction points",
              "## Review checklist",
          ],
      )
  ```

- [x] Run, confirm failure.

- [x] Write the doc. Create `showdownbot_studio/docs/security/LOGGING_AND_REDACTION.md`:

  ```markdown
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
  changes whether chat is included in a saved replay bundle â€” that stays excluded by default
  regardless of diagnostic mode (spec section 5.2, section 4.5).

  ## Redaction points

  A field this document forbids is never captured into the canonical stream or a log sink in the
  first place â€” it is not filtered out later, so no downstream redaction step is trusted to catch a
  leak that already happened upstream (spec section 4.5). Concretely:

  - `net/`'s `LoginHttpTransport` never logs the outbound request body's credential field.
  - The `ObservationEventBus` (spec section 4.2.2) never carries a credential or raw chat payload â€”
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
  ```

- [x] Run, confirm pass; commit:

  ```
  git add showdownbot_studio/docs/security/LOGGING_AND_REDACTION.md showdownbot_studio/tests/python/test_f0_binding_docs.py
  git commit -m "docs(studio): add Phase 3 F0 logging and redaction rules"
  ```

---

## Task 5 â€” `docs/security/UNTRUSTED_SERVER_CONTENT.md`

**Files:**
- Create: `showdownbot_studio/docs/security/UNTRUSTED_SERVER_CONTENT.md`
- Modify: `showdownbot_studio/tests/python/test_f0_binding_docs.py`

- [x] Write the failing test. Append:

  ```python
  def test_untrusted_server_content_doc_exists_with_required_sections():
      _assert_doc_has_headings(
          _DOCS_SECURITY / "UNTRUSTED_SERVER_CONTENT.md",
          [
              "## Purpose",
              "## What counts as untrusted",
              "## Handling rules",
              "## Protocol parsing boundary",
              "## Unknown protocol line handling",
          ],
      )
  ```

- [x] Run, confirm failure.

- [x] Write the doc. Create `showdownbot_studio/docs/security/UNTRUSTED_SERVER_CONTENT.md`:

  ```markdown
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
  - URLs inside chat are never clickable without a deliberate, separate user action â€” no
    auto-linkification that becomes a default click target.
  - Control characters are escaped before display.
  - Message length is capped.
  - Chat content does not appear in logs unless a diagnostic mode is explicitly enabled by the user
    for that session (see `LOGGING_AND_REDACTION.md`).
  - Chat is excluded from replay bundles by default, at the recording stream itself â€” not as a later
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
  table). The module that classifies an event decides what is recoverable â€” `protocol/` for
  parse-level conditions, `net/` for connection-level conditions â€” and a downstream module never
  invents its own recovery logic (spec section 6.1).
  ```

- [x] Run, confirm pass; commit:

  ```
  git add showdownbot_studio/docs/security/UNTRUSTED_SERVER_CONTENT.md showdownbot_studio/tests/python/test_f0_binding_docs.py
  git commit -m "docs(studio): add Phase 3 F0 untrusted server content rules"
  ```

---

## Task 6 â€” `docs/security/HUMAN_COMMAND_INVARIANTS.md`

**Files:**
- Create: `showdownbot_studio/docs/security/HUMAN_COMMAND_INVARIANTS.md`
- Modify: `showdownbot_studio/tests/python/test_f0_binding_docs.py`

This document must carry spec section 3.3's machine-checkable command-origin rules **verbatim**, so
this task's test also asserts each rule string is present byte-for-byte, not merely that headings
exist.

- [x] Write the failing test. Append:

  ```python
  import pytest

  _COMMAND_ORIGIN_RULES = [
      "only the gateway may request choice commands",
      "only the protocol encoder may build command strings",
      "only `net/` may write to the socket",
      "no replay/analyzer/mod/bot module imports the gateway",
      "every choice command carries room ID, connection epoch, and current `rqid`",
      "no request is sent twice",
      "superseded requests are never re-sent",
      "there is no automatic selection on timeout or error",
  ]


  @pytest.mark.architecture
  def test_human_command_invariants_doc_carries_verbatim_rules():
      path = _DOCS_SECURITY / "HUMAN_COMMAND_INVARIANTS.md"
      _assert_doc_has_headings(
          path,
          [
              "## Purpose",
              "## Binding command-origin invariants",
              "## Enforcement mapping",
              "## Gateway bans",
          ],
      )
      text = path.read_text(encoding="utf-8")
      missing = [rule for rule in _COMMAND_ORIGIN_RULES if rule not in text]
      assert not missing, f"HUMAN_COMMAND_INVARIANTS.md missing verbatim rule(s): {missing}"
  ```

  Note the `@pytest.mark.architecture` marker: this is the one doc-existence test also run by the
  dedicated `studio-security-invariants` CI lane (Task 12), because the spec's own CI table (section
  8.2) lists "command-origin checks" as part of that lane's coverage, and this doc is the
  machine-checkable source of those rules. The other seven doc-existence tests stay unmarked â€”
  Task 12's rationale explains why.

- [x] Run and confirm it fails (`pip install -e "./showdownbot_studio/python[dev]"` must already be
  done in your environment for `pytest` itself to be importable; the marker itself needs no
  registration to *run* â€” only to avoid an "unknown marker" warning, which Task 9 fixes):

  ```
  cd showdownbot_studio/python
  python -m pytest -q -k test_human_command_invariants_doc_carries_verbatim_rules
  ```

  Expected: `AssertionError: missing required F0 doc: ...HUMAN_COMMAND_INVARIANTS.md`.

- [x] Write the doc. Create `showdownbot_studio/docs/security/HUMAN_COMMAND_INVARIANTS.md`:

  ```markdown
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

  This is a **structural** guarantee, not a runtime-enforced one â€” GDScript has no engine-level
  `private` keyword (spec section 4.2.3's honesty note). It is upheld by injection discipline, by
  code review, and by the architecture test in the enforcement mapping above.
  ```

- [x] Run and confirm pass:

  ```
  cd showdownbot_studio/python
  python -m pytest -q -k test_human_command_invariants_doc_carries_verbatim_rules
  ```

- [x] Commit:

  ```
  git add showdownbot_studio/docs/security/HUMAN_COMMAND_INVARIANTS.md showdownbot_studio/tests/python/test_f0_binding_docs.py
  git commit -m "docs(studio): add Phase 3 F0 human command invariants"
  ```

---

## Task 7 â€” `docs/architecture/LIVE_STATE_MACHINES.md`

**Files:**
- Create: `showdownbot_studio/docs/architecture/LIVE_STATE_MACHINES.md`
- Modify: `showdownbot_studio/tests/python/test_f0_binding_docs.py`

This is spec section 4.8's binding deliverable: full transition tables for all four state machines,
drafted here (not left for the executing engineer to invent) so implementation only has to copy
them.

- [x] Write the failing test. Append:

  ```python
  def _table_row_count(text: str, heading: str, next_heading: str | None) -> int:
      start = text.index(heading) + len(heading)
      end = text.index(next_heading, start) if next_heading else len(text)
      section = text[start:end]
      rows = [
          line for line in section.splitlines()
          if line.strip().startswith("|")
          and "---" not in line
          and not line.strip().startswith("| Source state")
      ]
      return len(rows)


  def test_live_state_machines_doc_has_full_transition_tables():
      path = _DOCS_ARCHITECTURE / "LIVE_STATE_MACHINES.md"
      _assert_doc_has_headings(
          path,
          [
              "## Purpose",
              "## ConnectionState transitions",
              "## SessionState transitions",
              "## RoomState transitions",
              "## ChoiceRequestState transitions",
              "## Invalid transitions (explicitly rejected)",
              "## Cross-machine interactions",
          ],
      )
      text = path.read_text(encoding="utf-8")
      for state in ["DISCONNECTED", "CONNECTING", "CONNECTED", "RECONNECTING", "EXHAUSTED"]:
          assert state in text, f"ConnectionState state {state} missing from doc"
      for state in ["ANONYMOUS", "AUTHENTICATING", "AUTHENTICATED", "LOGIN_FAILED"]:
          assert state in text, f"SessionState state {state} missing from doc"
      for state in ["NOT_JOINED", "JOINING", "ACTIVE", "LEAVING", "CLOSED"]:
          assert state in text, f"RoomState state {state} missing from doc"
      for state in ["NONE", "OPEN", "SUBMITTING", "SUBMITTED", "REJECTED", "SUPERSEDED"]:
          assert state in text, f"ChoiceRequestState state {state} missing from doc"
      assert _table_row_count(
          text, "## ConnectionState transitions", "## SessionState transitions"
      ) == 11
      assert _table_row_count(
          text, "## SessionState transitions", "## RoomState transitions"
      ) == 6
      assert _table_row_count(
          text, "## RoomState transitions", "## ChoiceRequestState transitions"
      ) == 9
      assert _table_row_count(
          text, "## ChoiceRequestState transitions", "## Invalid transitions (explicitly rejected)"
      ) == 11
  ```

- [x] Run, confirm failure (missing doc).

- [x] Write the doc. Create `showdownbot_studio/docs/architecture/LIVE_STATE_MACHINES.md`:

  ```markdown
  # Phase 3 Live State Machines

  **Status:** binding F0 deliverable (spec `2026-07-25-phase3-client-design.md` section 3.3, section 4.8)

  ## Purpose

  Fixes the full transition table for each of the four binding state machines spec section 4.8
  names, so M1â€“M2 sub-slices implement against a written contract instead of inventing transitions
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
  | `SUBMITTING` | server declines the submitted choice | `REJECTED` | server error surfaced (section 6.1) |
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

  - `ConnectionState`: `DISCONNECTED` â†’ `CONNECTED` directly (must pass through `CONNECTING`);
    `DISCONNECTED` â†’ `RECONNECTING` (no prior connection attempt to reconnect from); `EXHAUSTED` â†’
    `CONNECTED` directly (must pass through `CONNECTING`).
  - `SessionState`: `ANONYMOUS` â†’ `AUTHENTICATED` directly (must pass through `AUTHENTICATING`);
    `AUTHENTICATING` â†’ `AUTHENTICATING` (a repeated submit while authenticating is blocked, not
    queued).
  - `RoomState`: `NOT_JOINED` â†’ `ACTIVE` directly (must pass through `JOINING`); `CLOSED` â†’ `ACTIVE`
    (a closed room never reopens; a new join creates a new `RoomState` instance).
  - `ChoiceRequestState`: `NONE` â†’ `SUBMITTING` directly (must pass through `OPEN`); `SUBMITTED` â†’
    `SUBMITTING` automatically on timeout (explicitly forbidden â€” spec section 6.1, "the client
    never auto-picks a move on timeout"); `SUPERSEDED` â†’ `SUBMITTED` (a superseded request can never
    be submitted).

  ## Cross-machine interactions

  `RoomState`'s reconnect transitions (`ACTIVE` â†’ `JOINING` â†’ `ACTIVE`) and `ChoiceRequestState`'s
  reconnect-triggered transitions both fire from the same underlying event: `ConnectionState`
  reaching `RECONNECTING` then `CONNECTED` again (spec section 6.2). `ChoiceRequestState.SUPERSEDED`
  is the enumerated form of the "stale `rqid`" condition (spec section 6.2, section 7);
  `ConnectionState.EXHAUSTED` is the enumerated form of the "reconnect exhausts backoff" row in spec
  section 6.1. `SessionState` is unaffected by a `RoomState` or `ChoiceRequestState` transition in
  either direction â€” logging out does not, by itself, leave or close a room; leaving a room does
  not, by itself, end a session.
  ```

- [x] Run, confirm pass; commit:

  ```
  git add showdownbot_studio/docs/architecture/LIVE_STATE_MACHINES.md showdownbot_studio/tests/python/test_f0_binding_docs.py
  git commit -m "docs(studio): add Phase 3 F0 live state machine transition tables"
  ```

---

## Task 8 â€” `docs/architecture/MODULE_CATALOG.md`

**Files:**
- Create: `showdownbot_studio/docs/architecture/MODULE_CATALOG.md`
- Modify: `showdownbot_studio/tests/python/test_f0_binding_docs.py`

- [x] Write the failing test. Append:

  ```python
  def test_module_catalog_doc_lists_all_seven_modules():
      path = _DOCS_ARCHITECTURE / "MODULE_CATALOG.md"
      _assert_doc_has_headings(
          path,
          ["## Purpose", "## Module table", "## Communication-path legend"],
      )
      text = path.read_text(encoding="utf-8")
      for module_dir in [
          "`godot/src/net/`",
          "`godot/src/protocol/`",
          "`godot/src/session/`",
          "`godot/src/battle/`",
          "`godot/src/ui/panels/`",
          "`godot/src/replay/`",
          "`godot/src/workspace/`",
      ]:
          assert module_dir in text, f"module directory {module_dir} missing from MODULE_CATALOG.md"
  ```

- [x] Run, confirm failure.

- [x] Write the doc. Create `showdownbot_studio/docs/architecture/MODULE_CATALOG.md`:

  ```markdown
  # Phase 3 Module Catalog

  **Status:** binding F0 deliverable (spec `2026-07-25-phase3-client-design.md` section 3.3, section 4.1)

  ## Purpose

  One row per module named in spec section 4.1: its owner directory, its job, its planned public
  interface, which of the three communication paths (spec section 4.2) it is allowed to use, when it
  is introduced, and what it must never do. This is the document a maintainer reads before touching
  any module tree, per `AGENTS.md` rule 2 ("every module ships a short README...") applied at the
  phase level before any of these directories have production code in them yet.

  ## Module table

  | Module | Directory | Owner (job) | Public interface (planned) | Allowed communication paths | Introduced in | Must not do |
  |---|---|---|---|---|---|---|
  | Net | `godot/src/net/` | `WebSocketTransport` (connection, reconnect, heartbeat, `ConnectionState`); `LoginHttpTransport` (single HTTPS login exchange) | `WebSocketTransport.connect()/disconnect()`, `ConnectionState` signal; `LoginHttpTransport.login(credential) -> LoginResult` | Direct dependency (default); publishes `ConnectionState` changes onto the `ObservationEventBus` | M1a (WebSocket), M1e (reconnect), M2a (login transport) | Parse or encode protocol text; hold battle state; hold `CredentialProvider` state |
  | Protocol | `godot/src/protocol/` | The only module permitted to encode outbound Showdown protocol commands or decode inbound protocol text, into/from typed DTOs under `protocol/dto/`, including the `CanonicalProtocolEventStream` | Decoder entry point consuming raw text; general command encoder; `protocol/dto/*` typed DTOs | Direct dependency (default); hands `CanonicalProtocolEventStream` directly to `battle/` and `replay/` | M1b (decoder, general encoder, room join/leave), M1e (reconnect), M2b (`FormatCatalogDTO`), M2c/M2e/M2f (remaining command families) | Render UI; hold connection sockets; decide whether a human is allowed to send a given command |
  | Session | `godot/src/session/` | `CredentialProvider`, `LoginCoordinator`, `SessionState`; team-bundle loading (`TeamBundleV1`); `session/dto/` | `CredentialProvider` interface; `LoginCoordinator.login()`; `SessionState` state machine; team-bundle loader | Direct dependency (default) | M2aâ€“M2b | Touch raw protocol text; render UI |
  | Battle | `godot/src/battle/` | Pure, deterministic, idempotent `LiveBattleReducer` producing immutable `LiveBattleSnapshot` values from `battle/dto/` DTOs, consuming `CanonicalProtocolEventStream` directly | `LiveBattleReducer.apply(event) -> LiveBattleSnapshot`; `battle/dto/*` typed DTOs | Direct dependency (default); publishes "battle state published"/"battle completed" onto the `ObservationEventBus` | M1c, M1e (reconnect rebuild) | Contain UI nodes; recompute mechanics/damage/legality; hold or import `HumanBattleCommandGateway` |
  | UI panels | `godot/src/ui/panels/` | Board, timeline, move choice, battle chat, connection status; renders via `BoardPresentationAdapter` | Panel scenes/controllers subscribing to the `ObservationEventBus` and to direct battle-state dependencies; the human battle controller holds `HumanBattleCommandGateway` (from M2d) | Subscribes to `ObservationEventBus` (render only); direct dependency for battle-state reads; holds the privileged gateway (M2d onward, human battle controller only) | M1d (board, timeline, connection status), M2dâ€“M2f (move choice, chat) | Produce protocol text directly; decide legality |
  | Replay | `godot/src/replay/` | Record a finished live battle via `LiveRecordingSink` and `ReplayExportGateway`; reuses `BoardPresentationAdapter`/`AbstractBoardView` for its own board rendering; converts live DTOs into recorded-replay events before export; **hosts `BattleBoardSnapshot`/`BattleBoardSlotSnapshot`/`ReplayBoardPresentationAdapter` (F0, this plan)** | `AbstractBoardView.bind(BattleBoardSnapshot)`; `ReplayBoardPresentationAdapter.build_snapshot(BoardModel) -> BattleBoardSnapshot`; `LiveRecordingSink`/`ReplayExportGateway` (M3) | Direct dependency (default); direct consumer of `CanonicalProtocolEventStream` (M3a) | F0 (board-presentation-contract refactor), M3aâ€“M3c | Reinterpret or recompute recorded evidence; assemble canonical bundle bytes itself; hold or import `HumanBattleCommandGateway` |
  | Workspace | `godot/src/workspace/` | `StudioRoot`, `WorkspaceRouter`, `OfflineViewerWorkspace` (wraps the existing `AppShell` unchanged), `LiveClientWorkspace` (Connection, Spectator, Matchmaking, HumanBattle areas, from M1d/M2d) | `WorkspaceRouter.register_workspace()/show_workspace()/get_active_workspace_id()`; `StudioRoot.get_router()` | Direct dependency (default); composes other modules, holds no domain state itself | F0 (scaffold), M1d (Connection + Spectator), M2d (Matchmaking + HumanBattle) | Own battle or credential state; duplicate board/team/replay logic; hold `HumanBattleCommandGateway` outside the HumanBattle area's controller |

  ## Communication-path legend

  Exactly three paths exist (spec section 4.2); a design that reaches for a fourth informal path is
  wrong by construction:

  - **Direct dependency (default, section 4.2.1).** A small, explicit, typed interface wired by
    composition-root/constructor injection, with locally scoped typed signals where a callback shape
    fits better than a return value.
  - **`ObservationEventBus` (section 4.2.2).** A typed, versioned, read-only bus carrying only its
    fixed list: connection status changed, battle state published, battle completed, chat received,
    diagnostic event. Never carries battle commands, login/credential data, a mutable session
    object, or the raw `CanonicalProtocolEventStream`.
  - **Privileged command gateway (section 4.2.3).** `HumanBattleCommandGateway` and its narrowly
    scoped siblings (room join/leave, chat send, challenge/ladder, timer/forfeit/undo). Injected only
    into the intended UI component; never registered on or discoverable through the bus; never
    imported by `replay/`, `battle/`, or an analysis module.
  ```

- [x] Run, confirm pass; commit:

  ```
  git add showdownbot_studio/docs/architecture/MODULE_CATALOG.md showdownbot_studio/tests/python/test_f0_binding_docs.py
  git commit -m "docs(studio): add Phase 3 F0 module catalog"
  ```

---

## Task 9 â€” Gateway forbidden-import architecture test

**Files:**
- Modify: `showdownbot_studio/python/pyproject.toml`
- Create: `showdownbot_studio/tests/python/test_f0_gateway_import_guard.py`

- [x] Register the `architecture` pytest marker. Edit `showdownbot_studio/python/pyproject.toml`,
  changing:

  ```toml
  [tool.pytest.ini_options]
  testpaths = ["../tests/python"]
  pythonpath = ["src"]
  ```

  to:

  ```toml
  [tool.pytest.ini_options]
  testpaths = ["../tests/python"]
  pythonpath = ["src"]
  markers = [
      "architecture: forbidden-dependency and typed-boundary checks (studio-security-invariants CI lane)",
  ]
  ```

- [x] Write the failing test. Create `showdownbot_studio/tests/python/test_f0_gateway_import_guard.py`:

  ```python
  """Forbidden-dependency guard: HumanBattleCommandGateway (spec section 4.2.3) may only be
  referenced from godot/src/ui/panels/ -- the human battle controller's home from M2d onward.
  Today (F0) the gateway does not exist yet and zero references exist anywhere; this test is
  still meaningful because it is fail-checked with a synthetic violation (see this task's
  fail-check steps) before being trusted as a real guard.
  """
  from __future__ import annotations

  import re
  from pathlib import Path

  import pytest

  from conftest import STUDIO_ROOT  # type: ignore[import-not-found]

  _GODOT_SRC = STUDIO_ROOT / "godot" / "src"
  _GATEWAY_IDENTIFIER = "HumanBattleCommandGateway"
  _ALLOWED_HOLDER_DIR = _GODOT_SRC / "ui" / "panels"


  def _all_gd_files() -> list[Path]:
      return sorted(_GODOT_SRC.rglob("*.gd"))


  @pytest.mark.architecture
  def test_gateway_scan_root_finds_expected_file_count():
      # A scan that silently under-matches its root is worse than no guard at all -- it
      # reports green while checking nothing. 45 .gd files exist under godot/src/ as of F0;
      # this floor stays comfortably below that and below every file F0 itself adds.
      found = _all_gd_files()
      assert len(found) >= 40, f"only found {len(found)} .gd files under godot/src -- scan root is wrong"


  @pytest.mark.architecture
  def test_no_module_outside_ui_panels_imports_the_human_battle_command_gateway():
      violations: list[str] = []
      pattern = re.compile(rf"\b{_GATEWAY_IDENTIFIER}\b")
      for path in _all_gd_files():
          if _ALLOWED_HOLDER_DIR in path.parents:
              continue
          text = path.read_text(encoding="utf-8")
          if pattern.search(text):
              violations.append(path.relative_to(STUDIO_ROOT).as_posix())
      assert not violations, (
          f"{_GATEWAY_IDENTIFIER} referenced outside "
          f"{_ALLOWED_HOLDER_DIR.relative_to(STUDIO_ROOT).as_posix()}: {violations}"
      )
  ```

- [x] Run and confirm both pass immediately (no violation exists today, and the file-count sanity
  check already holds). Note this also collects Task 6's `architecture`-marked doc test, which
  landed earlier in this plan and needs no marker registration to be selected by `-m` (only to
  avoid an "unknown marker" warning, which this task's own `pyproject.toml` edit, above, now
  fixes):

  ```
  cd showdownbot_studio/python
  python -m pytest -q -m architecture
  ```

  Expected: `3 passed` (Task 6's doc test plus these two).

- [x] **Fail-check the guard** (scratch change, not committed). Create a temporary synthetic
  violation:

  ```
  showdownbot_studio/godot/src/decision/_scratch_gateway_violation.gd
  ```

  with content:

  ```gdscript
  extends RefCounted
  # Scratch fail-check for test_f0_gateway_import_guard.py -- do not commit.
  var _gw: HumanBattleCommandGateway
  ```

  Run:

  ```
  cd showdownbot_studio/python
  python -m pytest -q -m architecture -k test_no_module_outside_ui_panels_imports_the_human_battle_command_gateway
  ```

  Expected: `1 failed`, listing
  `godot/src/decision/_scratch_gateway_violation.gd` in the assertion's `violations` list.

- [x] Revert the fail-check: delete
  `showdownbot_studio/godot/src/decision/_scratch_gateway_violation.gd`. Re-run the same command and
  confirm `1 passed`.

- [x] Commit only the real changes (the scratch file must not be staged â€” it was already deleted):

  ```
  git add showdownbot_studio/python/pyproject.toml showdownbot_studio/tests/python/test_f0_gateway_import_guard.py
  git commit -m "test(studio): add HumanBattleCommandGateway forbidden-import architecture guard"
  ```

---

## Task 10 â€” Untyped cross-module container architecture test

**Files:**
- Create: `showdownbot_studio/tests/python/architecture_allowlists/untyped_boundary_allowlist.txt`
- Create: `showdownbot_studio/tests/python/test_f0_untyped_boundary_guard.py`

This encodes `AGENTS.md` rule 9 / spec section 10: no cross-module **public** interface may expose
an untyped `Variant`, untyped `Array`, or untyped `Dictionary`. "Cross-module" is defined concretely
as: a `class_name` type declared in one top-level directory under `godot/src/` and referenced (by
identifier) from a `.gd` file under a *different* top-level directory. "Public" is defined as a
`func` whose name does not start with `_`. The check is scoped to **function signatures** (parameter
and return types) only â€” a function's local variables are not part of its public interface.

- [x] Write the allowlist file first (empty of real content, real header â€” not a placeholder, a
  real, currently-empty registry). Create
  `showdownbot_studio/tests/python/architecture_allowlists/untyped_boundary_allowlist.txt`:

  ```
  # Allowlisted audited parsing/serialization boundaries (AGENTS.md rule 9 / spec section 10).
  # Paths are relative to godot/src/. A trailing "/" allowlists every file under that directory
  # prefix; an exact path allowlists only that one file. Add an entry only with an owner-approved
  # PR description explaining why that specific boundary needs an untyped container in its public
  # signature -- this file is read by tests/python/test_f0_untyped_boundary_guard.py.
  bundle/
  protocol/
  ```

  `bundle/` is the existing Phase-0 DTO-deserialization boundary (JSON to typed DTOs) already named
  by `AGENTS.md` rule 9's own boundary list. `protocol/` is the future decoder/encoder + DTO-parsing
  boundary the same rule names explicitly; it does not exist yet, but pre-allowlisting the directory
  it will occupy is a real, spec-named exemption, not a placeholder for an unknown future need. The
  future replay bundle writer (M3b) gets its own allowlist entry when that plan creates the file â€”
  not invented here as a path that does not exist yet.

- [x] Write the failing test. Create `showdownbot_studio/tests/python/test_f0_untyped_boundary_guard.py`:

  ```python
  """No cross-module public interface may expose an untyped Variant/Array/Dictionary
  (AGENTS.md rule 9, spec section 10). See this file's header comment in the allowlist for the
  concrete scope of "cross-module," "public," and the audited-boundary exceptions.
  """
  from __future__ import annotations

  import re
  from pathlib import Path

  import pytest

  from conftest import STUDIO_ROOT  # type: ignore[import-not-found]

  _GODOT_SRC = STUDIO_ROOT / "godot" / "src"
  _ALLOWLIST_FILE = (
      Path(__file__).parent / "architecture_allowlists" / "untyped_boundary_allowlist.txt"
  )
  _CLASS_NAME_RE = re.compile(r"^class_name\s+(\w+)", re.MULTILINE)
  _FUNC_SIG_RE = re.compile(r"^func\s+([a-zA-Z_]\w*)\s*\((.*?)\)\s*(?:->\s*([^:]+))?:", re.MULTILINE | re.DOTALL)
  _BARE_UNTYPED_RE = re.compile(r"\b(Variant|Array|Dictionary)\b(?!\[)")


  def _module_dir(path: Path) -> str:
      return path.relative_to(_GODOT_SRC).parts[0]


  def _all_gd_files() -> list[Path]:
      return sorted(_GODOT_SRC.rglob("*.gd"))


  def _load_allowlist() -> list[str]:
      entries = []
      for line in _ALLOWLIST_FILE.read_text(encoding="utf-8").splitlines():
          line = line.strip()
          if not line or line.startswith("#"):
              continue
          entries.append(line)
      return entries


  def _is_allowlisted(path: Path, allowlist: list[str]) -> bool:
      rel = path.relative_to(_GODOT_SRC).as_posix()
      for entry in allowlist:
          if entry.endswith("/"):
              if rel.startswith(entry):
                  return True
          elif rel == entry:
              return True
      return False


  def _class_names_by_file() -> dict[Path, str]:
      mapping: dict[Path, str] = {}
      for path in _all_gd_files():
          match = _CLASS_NAME_RE.search(path.read_text(encoding="utf-8"))
          if match:
              mapping[path] = match.group(1)
      return mapping


  def _cross_module_classes() -> set[str]:
      by_file = _class_names_by_file()
      file_texts = {path: path.read_text(encoding="utf-8") for path in _all_gd_files()}
      cross_module: set[str] = set()
      for decl_path, class_name in by_file.items():
          decl_module = _module_dir(decl_path)
          pattern = re.compile(rf"\b{re.escape(class_name)}\b")
          for other_path, text in file_texts.items():
              if other_path == decl_path or _module_dir(other_path) == decl_module:
                  continue
              if pattern.search(text):
                  cross_module.add(class_name)
                  break
      return cross_module


  def _public_signature_violations(path: Path) -> list[str]:
      violations = []
      text = path.read_text(encoding="utf-8")
      for match in _FUNC_SIG_RE.finditer(text):
          name, params, ret = match.group(1), match.group(2), match.group(3) or ""
          if name.startswith("_"):
              continue
          if _BARE_UNTYPED_RE.search(params) or _BARE_UNTYPED_RE.search(ret):
              violations.append(f"{path.relative_to(STUDIO_ROOT).as_posix()}::{name}")
      return violations


  @pytest.mark.architecture
  def test_cross_module_class_scan_finds_at_least_one_cross_module_class():
      # A scan that finds zero cross-module classes has a broken module-dir/identifier match,
      # not a codebase with no shared types -- BundleDTO alone is already used from replay/,
      # decision/, diagnostics/, and workspace/ today.
      found = _cross_module_classes()
      assert "BundleDTO" in found, found


  @pytest.mark.architecture
  def test_no_untyped_container_in_cross_module_public_interface():
      allowlist = _load_allowlist()
      by_file = _class_names_by_file()
      cross_module = _cross_module_classes()
      violations: list[str] = []
      for path, class_name in by_file.items():
          if class_name not in cross_module or _is_allowlisted(path, allowlist):
              continue
          violations.extend(_public_signature_violations(path))
      assert not violations, f"untyped container in cross-module public interface: {violations}"
  ```

- [x] Run and confirm both pass immediately:

  ```
  cd showdownbot_studio/python
  python -m pytest -q -m architecture
  ```

  Expected: `5 passed` (Task 6's doc test, Task 9's two, plus these two). Today's only two bare
  `-> Dictionary`/`-> Array` signatures (`BoardModel.get_slot`, `AppShell.get_downgrade_warning_reasons`)
  are both intra-module (verified by grep before writing this plan: `BoardModel` is referenced only
  from `.gd` files under `godot/src/replay/`, and `get_downgrade_warning_reasons` only from
  `godot/src/workspace/app_shell.gd` itself), so neither is in `cross_module` and neither trips the
  guard.

- [x] **Fail-check the guard** (scratch change, not committed). Create two temporary files:

  `showdownbot_studio/godot/src/decision/_scratch_cross_module_violation.gd`:

  ```gdscript
  class_name ScratchCrossModuleViolation
  extends RefCounted
  # Scratch fail-check for test_f0_untyped_boundary_guard.py -- do not commit.


  func public_untyped(data: Dictionary) -> Variant:
  	return data
  ```

  `showdownbot_studio/godot/src/diagnostics/_scratch_cross_module_user.gd`:

  ```gdscript
  extends RefCounted
  # Scratch fail-check for test_f0_untyped_boundary_guard.py -- do not commit.
  var _x: ScratchCrossModuleViolation
  ```

  Run:

  ```
  cd showdownbot_studio/python
  python -m pytest -q -m architecture -k test_no_untyped_container_in_cross_module_public_interface
  ```

  Expected: `1 failed`, listing
  `godot/src/decision/_scratch_cross_module_violation.gd::public_untyped` in the violations list.

- [x] Revert the fail-check: delete both scratch files. Re-run the same command and confirm
  `1 passed`.

- [x] Commit only the real changes:

  ```
  git add showdownbot_studio/tests/python/architecture_allowlists/untyped_boundary_allowlist.txt showdownbot_studio/tests/python/test_f0_untyped_boundary_guard.py
  git commit -m "test(studio): add cross-module untyped-container architecture guard"
  ```

---

## Task 11 â€” Live-DTO-into-bundle-path architecture test

**Files:**
- Create: `showdownbot_studio/tests/python/architecture_allowlists/live_dto_bundle_path_allowlist.txt`
- Create: `showdownbot_studio/tests/python/test_f0_live_dto_bundle_guard.py`

Encodes spec section 4.1.2's boundary: "no live DTO type may be serialized straight into a bundle
file." A "live DTO type" is any `class_name` declared under `godot/src/protocol/dto/`,
`godot/src/session/dto/`, or `godot/src/battle/dto/` (none exist yet in F0). A "bundle path" file is
any `.gd` file anywhere under `godot/src/` whose filename matches `*bundle_writer*.gd` â€” the M3b
plan is expected to name its writer this way; this naming convention is itself part of what F0 fixes
so the M3b plan does not have to invent it. `replay/`'s `LiveRecordingSink` (M3a) legitimately
references live DTO types (that is its entire job â€” converting them), so it must never match this
glob; it is named `*recording_sink*.gd` by convention, not `*bundle_writer*.gd`.

- [x] Write the allowlist file. Create
  `showdownbot_studio/tests/python/architecture_allowlists/live_dto_bundle_path_allowlist.txt`:

  ```
  # Allowlisted exceptions to "no live DTO type referenced from a *bundle_writer*.gd file"
  # (spec section 4.1.2). Paths are relative to godot/src/, one exact file path per line. No
  # exception exists yet -- add one only with an owner-approved PR description explaining why
  # a specific bundle-writer file legitimately needs a live DTO reference. This file is read by
  # tests/python/test_f0_live_dto_bundle_guard.py.
  ```

- [x] Write the failing test. Create `showdownbot_studio/tests/python/test_f0_live_dto_bundle_guard.py`:

  ```python
  """No live DTO type (protocol/dto/, session/dto/, battle/dto/) may be referenced from a
  *bundle_writer*.gd file (spec section 4.1.2). None of those directories or files exist yet
  in F0 -- see this task's fail-check steps for how this is proven meaningful today.
  """
  from __future__ import annotations

  import re
  from pathlib import Path

  import pytest

  from conftest import STUDIO_ROOT  # type: ignore[import-not-found]

  _GODOT_SRC = STUDIO_ROOT / "godot" / "src"
  _LIVE_DTO_DIRS = (
      _GODOT_SRC / "protocol" / "dto",
      _GODOT_SRC / "session" / "dto",
      _GODOT_SRC / "battle" / "dto",
  )
  _BUNDLE_WRITER_GLOB = "*bundle_writer*.gd"
  _ALLOWLIST_FILE = (
      Path(__file__).parent / "architecture_allowlists" / "live_dto_bundle_path_allowlist.txt"
  )
  _CLASS_NAME_RE = re.compile(r"^class_name\s+(\w+)", re.MULTILINE)


  def _bundle_writer_files() -> list[Path]:
      return sorted(_GODOT_SRC.rglob(_BUNDLE_WRITER_GLOB))


  def _live_dto_class_names() -> set[str]:
      names: set[str] = set()
      for live_dir in _LIVE_DTO_DIRS:
          if not live_dir.is_dir():
              continue
          for path in live_dir.rglob("*.gd"):
              match = _CLASS_NAME_RE.search(path.read_text(encoding="utf-8"))
              if match:
                  names.add(match.group(1))
      return names


  def _load_allowlist() -> list[str]:
      entries = []
      for line in _ALLOWLIST_FILE.read_text(encoding="utf-8").splitlines():
          line = line.strip()
          if not line or line.startswith("#"):
              continue
          entries.append(line)
      return entries


  @pytest.mark.architecture
  def test_godot_src_root_exists_for_bundle_writer_scan():
      assert _GODOT_SRC.is_dir()


  @pytest.mark.architecture
  def test_no_live_dto_type_referenced_from_a_bundle_writer_file():
      live_dto_names = _live_dto_class_names()
      allowlist = _load_allowlist()
      violations: list[str] = []
      for path in _bundle_writer_files():
          rel = path.relative_to(_GODOT_SRC).as_posix()
          if rel in allowlist:
              continue
          text = path.read_text(encoding="utf-8")
          for name in live_dto_names:
              if re.search(rf"\b{re.escape(name)}\b", text):
                  violations.append(f"{rel} references live DTO {name}")
      assert not violations, violations
  ```

- [x] Run and confirm both pass immediately (vacuously â€” no live-DTO dirs and no bundle-writer files
  exist yet):

  ```
  cd showdownbot_studio/python
  python -m pytest -q -m architecture
  ```

  Expected: `7 passed` (Task 6's doc test, Task 9's two, Task 10's two, these two).

- [x] **Fail-check the guard** (scratch change, not committed). Create two temporary files:

  `showdownbot_studio/godot/src/protocol/dto/_scratch_live_dto.gd`:

  ```gdscript
  class_name ScratchLiveEventDTO
  extends RefCounted
  # Scratch fail-check for test_f0_live_dto_bundle_guard.py -- do not commit.
  var value: Variant = null
  ```

  `showdownbot_studio/godot/src/replay/_scratch_bundle_writer.gd`:

  ```gdscript
  extends RefCounted
  # Scratch fail-check for test_f0_live_dto_bundle_guard.py -- do not commit.
  var _evt: ScratchLiveEventDTO
  ```

  Run:

  ```
  cd showdownbot_studio/python
  python -m pytest -q -m architecture -k test_no_live_dto_type_referenced_from_a_bundle_writer_file
  ```

  Expected: `1 failed`, listing
  `godot/src/replay/_scratch_bundle_writer.gd references live DTO ScratchLiveEventDTO`.

- [x] Revert the fail-check: delete both scratch files and the now-empty
  `showdownbot_studio/godot/src/protocol/` directory tree. Re-run the same command and confirm
  `1 passed`.

- [x] Commit only the real changes:

  ```
  git add showdownbot_studio/tests/python/architecture_allowlists/live_dto_bundle_path_allowlist.txt showdownbot_studio/tests/python/test_f0_live_dto_bundle_guard.py
  git commit -m "test(studio): add live-DTO-into-bundle-path architecture guard"
  ```

---

## Task 12 â€” `studio-security-invariants` CI lane

**Files:**
- Create: `.github/workflows/studio-security-invariants.yml`

This is its own workflow file, running only the architecture-test subset (`-m architecture`, no
Godot engine download), per spec section 8.2. It does not modify `studio-windows.yml`.

- [x] Create `.github/workflows/studio-security-invariants.yml`:

  ```yaml
  name: studio security invariants lane

  # F0 (showdownbot_studio/docs/plans/2026-07-25-phase3-f0-foundation.md) / spec section 8.2: a
  # lane dedicated to the forbidden-dependency and typed-boundary architecture tests introduced
  # in F0 (tests/python/test_f0_gateway_import_guard.py, test_f0_untyped_boundary_guard.py,
  # test_f0_live_dto_bundle_guard.py, all marked @pytest.mark.architecture), kept separate from
  # studio-windows.yml -- which owns the full pytest + gdUnit regression suite -- so this lane
  # stays fast and never downloads the pinned Godot engine. Do not add gdUnit steps here and do
  # not remove the `-m architecture` filter: without it this job is just a slower duplicate of
  # studio-windows.yml's own pytest step, not the dedicated fast lane spec section 8.2 requires.
  # Do not touch pytest.yml (the bot's own lane, `working-directory: showdown_bot` throughout)
  # or restructure studio-windows.yml.

  on:
    push:
    pull_request:

  jobs:
    studio-security-invariants:
      runs-on: windows-latest
      steps:
        - uses: actions/checkout@v4

        - uses: actions/setup-python@v5
          with:
            python-version: "3.12"

        # Same two installs as studio-windows.yml's pytest step: pytest COLLECTION imports every
        # module under tests/python/, including files that import showdown_bot and
        # showdownbot_studio_exporter, even though the `-m architecture` filter below only RUNS
        # the F0 architecture tests. Skipping these installs would fail collection, not just the
        # filtered-out tests.
        - name: Install showdown_bot (Studio pytest imports its modules via tests/python/conftest.py)
          run: pip install -e ./showdown_bot

        - name: Install showdownbot_studio_exporter (+ pytest)
          run: pip install -e "./showdownbot_studio/python[dev]"

        # No explicit test-path argument, for the same rootdir/pythonpath-inference reason
        # documented in studio-windows.yml -- `-m architecture` filters which of the collected
        # tests actually RUN; it does not change collection or require a path argument.
        - name: Run F0 architecture/forbidden-dependency tests
          working-directory: showdownbot_studio/python
          run: python -m pytest -q -m architecture
  ```

- [x] There is no red/green pair for a CI workflow file itself (it cannot run locally in the same
  sense as a unit test); verify its correctness by construction against the sibling file it mirrors:

  ```
  diff .github/workflows/studio-windows.yml .github/workflows/studio-security-invariants.yml
  ```

  Confirm by inspection: same `runs-on: windows-latest`, same `actions/checkout@v4` and
  `actions/setup-python@v5` steps, same two `pip install` lines, same `working-directory:
  showdownbot_studio/python` convention, and no gdUnit/engine-download steps present in the new file.

- [x] Commit:

  ```
  git add .github/workflows/studio-security-invariants.yml
  git commit -m "ci(studio): add studio-security-invariants lane for F0 architecture tests"
  ```

---

## Task 13 â€” `BattleBoardSlotSnapshot` and `BattleBoardSnapshot` value objects

**Files:**
- Create: `showdownbot_studio/godot/src/replay/battle_board_slot_snapshot.gd`
- Create: `showdownbot_studio/godot/src/replay/battle_board_snapshot.gd`
- Create: `showdownbot_studio/godot/tests/replay/test_battle_board_snapshot.gd`

This introduces the neutral contract spec section 4.7 names â€” `presentation_available`,
`empty_state_reason`, `turn`, `weather`, `terrain`, `slots`, `side_conditions`, `field_conditions` â€”
as typed value objects, satisfying `AGENTS.md` rule 9 by using Godot 4.4+ typed-container syntax
(`Dictionary[String, T]`, `Array[T]`) instead of bare `Dictionary`/`Array` for the two collection
fields, since this class is a deliberate cross-module contract (consumed by both `replay/` today and
`ui/panels/` from M1d onward) rather than an audited parsing boundary. Nothing in this task changes
`AbstractBoardView`, `BoardModel`, or any existing test â€” it only adds two new files with no
production caller yet, so it is pure net-new code, not a refactor step.

- [x] Write the failing test. Create `showdownbot_studio/godot/tests/replay/test_battle_board_snapshot.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func test_default_snapshot_has_four_empty_slots_and_two_side_condition_lists() -> void:
  	var snapshot := BattleBoardSnapshot.new()
  	assert_bool(snapshot.presentation_available).is_false()
  	assert_str(snapshot.empty_state_reason).is_equal("")
  	assert_object(snapshot.get_slot("p1", "a")).is_not_null()
  	assert_object(snapshot.get_slot("p1", "b")).is_not_null()
  	assert_object(snapshot.get_slot("p2", "a")).is_not_null()
  	assert_object(snapshot.get_slot("p2", "b")).is_not_null()
  	assert_bool(snapshot.side_conditions.has("p1")).is_true()
  	assert_bool(snapshot.side_conditions.has("p2")).is_true()


  func test_slot_key_matches_get_slot_addressing() -> void:
  	var snapshot := BattleBoardSnapshot.new()
  	var direct: BattleBoardSlotSnapshot = snapshot.slots[BattleBoardSnapshot.slot_key("p2", "b")]
  	assert_object(direct).is_equal(snapshot.get_slot("p2", "b"))


  func test_slot_snapshot_fields_default_to_null() -> void:
  	var slot := BattleBoardSlotSnapshot.new()
  	assert_object(slot.species).is_null()
  	assert_object(slot.hp_current).is_null()
  	assert_object(slot.hp_maximum).is_null()
  	assert_object(slot.hp_fainted).is_null()
  	assert_object(slot.hp_status).is_null()
  ```

- [x] Run it and confirm it fails (the class does not exist yet):

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/replay/test_battle_board_snapshot.gd"
  ```

  Expected: parse/load error resolving `BattleBoardSnapshot`.

- [x] Write the implementation. Create
  `showdownbot_studio/godot/src/replay/battle_board_slot_snapshot.gd`:

  ```gdscript
  class_name BattleBoardSlotSnapshot
  extends RefCounted

  ## One board slot's presentation fields, all nullable (Variant) -- mirrors the five fields
  ## BoardModel already tracks per slot (species, hp_current, hp_maximum, hp_fainted, hp_status),
  ## just promoted to named typed fields on a dedicated value object instead of raw Dictionary
  ## keys, so BattleBoardSnapshot.slots below can be a TYPED Dictionary (Godot 4.4+
  ## `Dictionary[String, T]` syntax) rather than an untyped one.

  var species: Variant = null
  var hp_current: Variant = null
  var hp_maximum: Variant = null
  var hp_fainted: Variant = null
  var hp_status: Variant = null
  ```

  Create `showdownbot_studio/godot/src/replay/battle_board_snapshot.gd`:

  ```gdscript
  class_name BattleBoardSnapshot
  extends RefCounted

  ## Neutral board-presentation contract (spec docs/specs/2026-07-25-phase3-client-design.md
  ## section 4.7): the shape AbstractBoardView.bind() consumes, produced either by
  ## ReplayBoardPresentationAdapter (this F0 slice) or a future live-battle adapter (M1d,
  ## not built here). `slots` and `side_conditions` use Godot 4.4+ typed-dictionary syntax
  ## (`Dictionary[K, V]`) specifically so this cross-module value object satisfies AGENTS.md
  ## rule 9 ("no cross-module public interface exposes an untyped container") -- a typed
  ## Dictionary is not the "untyped Dictionary" that rule bans.

  const SLOT_KEYS := ["p1a", "p1b", "p2a", "p2b"]

  var presentation_available: bool = false
  var empty_state_reason: String = ""
  var turn: Variant = null
  var weather: Variant = null
  var terrain: Variant = null
  var slots: Dictionary[String, BattleBoardSlotSnapshot] = {}
  var side_conditions: Dictionary[String, PackedStringArray] = {}
  var field_conditions: PackedStringArray = PackedStringArray()


  func _init() -> void:
  	for key in SLOT_KEYS:
  		slots[key] = BattleBoardSlotSnapshot.new()
  	side_conditions["p1"] = PackedStringArray()
  	side_conditions["p2"] = PackedStringArray()


  static func slot_key(side: String, slot: String) -> String:
  	return "%s%s" % [side, slot]


  func get_slot(side: String, slot: String) -> BattleBoardSlotSnapshot:
  	return slots[slot_key(side, slot)]
  ```

- [x] Run again and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/replay/test_battle_board_snapshot.gd"
  ```

  Expected: `3` tests passed, `0` failed.

- [x] Commit:

  ```
  git add showdownbot_studio/godot/src/replay/battle_board_slot_snapshot.gd showdownbot_studio/godot/src/replay/battle_board_snapshot.gd showdownbot_studio/godot/tests/replay/test_battle_board_snapshot.gd
  git commit -m "feat(studio): add BattleBoardSnapshot/BattleBoardSlotSnapshot value objects"
  ```

---

## Task 14 â€” `ReplayBoardPresentationAdapter`

**Files:**
- Create: `showdownbot_studio/godot/src/replay/replay_board_presentation_adapter.gd`
- Create: `showdownbot_studio/godot/tests/replay/test_replay_board_presentation_adapter.gd`

This is the "replay adapter" spec section 4.7 requires: it moves `EMPTY_REPLAY_TEXT` and the
`has_replay` check out of `AbstractBoardView` (Task 15 removes them from there) and converts a
`BoardModel` into a `BattleBoardSnapshot`. Writing and green-lighting this adapter *before* changing
`AbstractBoardView.bind()`'s signature (Task 15) is the characterization step spec section 4.7 asks
for: it locks down the exact mapping from today's `BoardModel` shape to the new contract while
`AbstractBoardView` still only knows about `BoardModel`, so Task 15's signature change has nothing
left to invent.

- [x] Write the failing test. Create
  `showdownbot_studio/godot/tests/replay/test_replay_board_presentation_adapter.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func _make_event(side: String, slot: String, species: String, hp_current: int, hp_maximum: int, status: Variant = null) -> BattleEventDTO:
  	var e := BattleEventDTO.new()
  	e.protocol_index = 1
  	e.type = "switch"
  	e.pokemon_side = side
  	e.pokemon_slot = slot
  	e.pokemon_species = species
  	e.hp_current = hp_current
  	e.hp_maximum = hp_maximum
  	e.hp_fainted = false
  	e.hp_status = status
  	return e


  func test_not_has_replay_yields_unavailable_with_reason() -> void:
  	var board := BoardModel.new()
  	board.has_replay = false
  	var snapshot := ReplayBoardPresentationAdapter.build_snapshot(board)
  	assert_bool(snapshot.presentation_available).is_false()
  	assert_str(snapshot.empty_state_reason).is_equal("No replay evidence in this bundle")


  func test_null_board_yields_unavailable_with_reason() -> void:
  	var snapshot := ReplayBoardPresentationAdapter.build_snapshot(null)
  	assert_bool(snapshot.presentation_available).is_false()
  	assert_str(snapshot.empty_state_reason).is_equal("No replay evidence in this bundle")


  func test_has_replay_true_yields_available_regardless_of_recorded_state() -> void:
  	var board := BoardModel.new()
  	board.has_replay = true
  	board.has_recorded_state = false
  	var snapshot := ReplayBoardPresentationAdapter.build_snapshot(board)
  	assert_bool(snapshot.presentation_available).is_true()
  	assert_str(snapshot.empty_state_reason).is_equal("")


  func test_slot_species_hp_and_status_carry_over() -> void:
  	var board := BoardModel.new()
  	board.has_replay = true
  	board.replace_slot_from_switch("p1", "a", _make_event("p1", "a", "Pikachu", 20, 35, "brn"))
  	var snapshot := ReplayBoardPresentationAdapter.build_snapshot(board)
  	var slot := snapshot.get_slot("p1", "a")
  	assert_str(str(slot.species)).is_equal("Pikachu")
  	assert_int(slot.hp_current).is_equal(20)
  	assert_int(slot.hp_maximum).is_equal(35)
  	assert_str(str(slot.hp_status)).is_equal("brn")


  func test_turn_weather_terrain_and_field_conditions_carry_over() -> void:
  	var board := BoardModel.new()
  	board.has_replay = true
  	board.turn_number = 3
  	board.weather = "RainDance"
  	board.terrain = "Electric Terrain"
  	board.add_field_condition("Trick Room")
  	var snapshot := ReplayBoardPresentationAdapter.build_snapshot(board)
  	assert_int(snapshot.turn).is_equal(3)
  	assert_str(str(snapshot.weather)).is_equal("RainDance")
  	assert_str(str(snapshot.terrain)).is_equal("Electric Terrain")
  	assert_bool(snapshot.field_conditions.has("Trick Room")).is_true()


  func test_side_conditions_carry_over_per_side() -> void:
  	var board := BoardModel.new()
  	board.has_replay = true
  	board.add_side_condition("p1", "Stealth Rock")
  	board.add_side_condition("p2", "Spikes")
  	var snapshot := ReplayBoardPresentationAdapter.build_snapshot(board)
  	assert_bool(snapshot.side_conditions["p1"].has("Stealth Rock")).is_true()
  	assert_bool(snapshot.side_conditions["p2"].has("Spikes")).is_true()
  ```

- [x] Run and confirm it fails (`ReplayBoardPresentationAdapter` does not exist yet):

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/replay/test_replay_board_presentation_adapter.gd"
  ```

- [x] Write the implementation. Create
  `showdownbot_studio/godot/src/replay/replay_board_presentation_adapter.gd`:

  ```gdscript
  class_name ReplayBoardPresentationAdapter
  extends RefCounted

  ## Converts the existing Phase-0 BoardModel into the neutral BattleBoardSnapshot contract
  ## (spec docs/specs/2026-07-25-phase3-client-design.md section 4.7). Owns the replay-specific
  ## empty-state wording that used to live directly in AbstractBoardView
  ## (godot/src/replay/abstract_board_view.gd's old EMPTY_REPLAY_TEXT constant, removed there
  ## in the same F0 slice, Task 15) -- AbstractBoardView itself no longer knows this string, or
  ## anything about BoardModel or "has_replay" at all.

  const EMPTY_REPLAY_TEXT := "No replay evidence in this bundle"


  static func build_snapshot(board: BoardModel) -> BattleBoardSnapshot:
  	var snapshot := BattleBoardSnapshot.new()
  	if board == null or not board.has_replay:
  		snapshot.presentation_available = false
  		snapshot.empty_state_reason = EMPTY_REPLAY_TEXT
  		return snapshot
  	snapshot.presentation_available = true
  	snapshot.empty_state_reason = ""
  	snapshot.turn = board.turn_number
  	snapshot.weather = board.weather
  	snapshot.terrain = board.terrain
  	snapshot.field_conditions = board.field_conditions
  	for side in ["p1", "p2"]:
  		snapshot.side_conditions[side] = board.side_conditions[side]
  		for slot in ["a", "b"]:
  			var cell: Dictionary = board.get_slot(side, slot)
  			var slot_snapshot := snapshot.get_slot(side, slot)
  			slot_snapshot.species = cell["species"]
  			slot_snapshot.hp_current = cell["hp_current"]
  			slot_snapshot.hp_maximum = cell["hp_maximum"]
  			slot_snapshot.hp_fainted = cell["hp_fainted"]
  			slot_snapshot.hp_status = cell["hp_status"]
  	return snapshot
  ```

- [x] Run again and confirm it passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/replay/test_replay_board_presentation_adapter.gd"
  ```

  Expected: `6` tests passed, `0` failed.

- [x] Commit:

  ```
  git add showdownbot_studio/godot/src/replay/replay_board_presentation_adapter.gd showdownbot_studio/godot/tests/replay/test_replay_board_presentation_adapter.gd
  git commit -m "feat(studio): add ReplayBoardPresentationAdapter (BoardModel -> BattleBoardSnapshot)"
  ```

---

## Task 15 â€” Retype `AbstractBoardView.bind()` and rewire `replay/` callers

**Files:**
- Modify: `showdownbot_studio/godot/src/replay/abstract_board_view.gd`
- Modify: `showdownbot_studio/godot/src/replay/replay_workspace.gd`
- Modify: `showdownbot_studio/godot/tests/replay/test_abstract_board_view.gd`

This is the actual signature-breaking step. Per spec section 8's TDD carve-out ("a pure
refactoring â€” no behavior change, existing tests pass unmodified â€” does not require an artificially
reddened test"), the observable behavior is unchanged (same rendered species/HP/status/weather/
terrain/field/side-condition text, same empty-state visibility), so this task updates the existing
test file's call sites to the new signature in the same commit as the production change, rather than
reddening then greening a copy. Task 16 is the separate, deliberate fail-check that proves the moved
guard logic is actually exercised.

- [x] Confirm the pre-refactor baseline is green before touching anything:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/replay/"
  ```

  Record the reported pass count.

- [x] Edit `showdownbot_studio/godot/src/replay/abstract_board_view.gd`. Replace the top of the file
  (constant and `_bound`/`bind` declarations) and the two internal rendering functions:

  ```gdscript
  class_name AbstractBoardView
  extends VBoxContainer

  @onready var _loading: Label = $LoadingLabel
  @onready var _empty: Label = $EmptyStateLabel
  @onready var _turn: Label = $MetaRow/TurnLabel
  @onready var _weather: Label = $MetaRow/WeatherLabel
  @onready var _terrain: Label = $MetaRow/TerrainLabel
  @onready var _field_conditions: Label = $MetaRow/FieldConditionsLabel
  @onready var _p1_side: Label = $SideConditionsRow/P1SideLabel
  @onready var _p2_side: Label = $SideConditionsRow/P2SideLabel
  @onready var _p1a_species: Label = $Slots/P1ASpecies
  @onready var _p1a_hp: Label = $Slots/P1AHP
  @onready var _p1a_status: Label = $Slots/P1AStatus
  @onready var _p1b_species: Label = $Slots/P1BSpecies
  @onready var _p1b_hp: Label = $Slots/P1BHP
  @onready var _p1b_status: Label = $Slots/P1BStatus
  @onready var _p2a_species: Label = $Slots/P2ASpecies
  @onready var _p2a_hp: Label = $Slots/P2AHP
  @onready var _p2a_status: Label = $Slots/P2AStatus
  @onready var _p2b_species: Label = $Slots/P2BSpecies
  @onready var _p2b_hp: Label = $Slots/P2BHP
  @onready var _p2b_status: Label = $Slots/P2BStatus

  var _bound: BattleBoardSnapshot = null


  func bind(snapshot: BattleBoardSnapshot) -> void:
  	_bound = snapshot
  	if snapshot == null or not snapshot.presentation_available:
  		_empty.visible = true
  		_empty.text = "" if snapshot == null else snapshot.empty_state_reason
  		_clear_slots_and_meta()
  		return
  	_empty.visible = false
  	_empty.text = ""
  	_render(snapshot)
  ```

  (`set_loading`, `get_slot_species`, `get_slot_hp_text`, `get_weather_text`, `get_terrain_text`,
  `get_field_conditions_text`, `get_side_conditions_text`, `get_empty_state_visible`,
  `_clear_slots_and_meta`, and `_slot_label` are unchanged â€” leave them exactly as they are.) Replace
  `_render` and `_write_slot`:

  ```gdscript
  func _render(snapshot: BattleBoardSnapshot) -> void:
  	_turn.text = "" if snapshot.turn == null else "turn %s" % str(snapshot.turn)
  	_weather.text = "" if snapshot.weather == null else str(snapshot.weather)
  	_terrain.text = "" if snapshot.terrain == null else str(snapshot.terrain)
  	_field_conditions.text = ", ".join(snapshot.field_conditions)
  	_p1_side.text = ", ".join(snapshot.side_conditions["p1"])
  	_p2_side.text = ", ".join(snapshot.side_conditions["p2"])
  	_write_slot(_p1a_species, _p1a_hp, _p1a_status, snapshot.get_slot("p1", "a"))
  	_write_slot(_p1b_species, _p1b_hp, _p1b_status, snapshot.get_slot("p1", "b"))
  	_write_slot(_p2a_species, _p2a_hp, _p2a_status, snapshot.get_slot("p2", "a"))
  	_write_slot(_p2b_species, _p2b_hp, _p2b_status, snapshot.get_slot("p2", "b"))


  func _write_slot(species_lbl: Label, hp_lbl: Label, status_lbl: Label, cell: BattleBoardSlotSnapshot) -> void:
  	species_lbl.text = "" if cell.species == null else str(cell.species)
  	if cell.hp_current == null and cell.hp_maximum == null:
  		hp_lbl.text = ""
  	else:
  		hp_lbl.text = "%s/%s" % [
  			"?" if cell.hp_current == null else str(cell.hp_current),
  			"?" if cell.hp_maximum == null else str(cell.hp_maximum),
  		]
  	status_lbl.text = "" if cell.hp_status == null else str(cell.hp_status)
  ```

  Delete the old `const EMPTY_REPLAY_TEXT := "No replay evidence in this bundle"` line â€” it now lives
  only in `ReplayBoardPresentationAdapter` (Task 14).

- [x] Edit `showdownbot_studio/godot/src/replay/replay_workspace.gd`. `clear()` and
  `_on_selection_changed()` now route through the adapter instead of calling `bind()` with a raw
  `BoardModel` (or `null`):

  ```gdscript
  func clear() -> void:
  	_controller.clear()
  	_replay = null
  	_bundle = null
  	_board = null
  	_timeline_view.bind(null, null)
  	_board_view.bind(ReplayBoardPresentationAdapter.build_snapshot(null))
  	set_loading(false)
  	_timeline_view.set_controls_enabled(false)
  ```

  ```gdscript
  func _on_selection_changed(entry_index: int) -> void:
  	_timeline_view.set_selected_entry_index(entry_index)
  	if _replay == null or _bundle == null:
  		_board = null
  		_board_view.bind(ReplayBoardPresentationAdapter.build_snapshot(null))
  		return
  	_board = ReplayPresenter.build_board(_bundle, _replay, entry_index)
  	_board_view.bind(ReplayBoardPresentationAdapter.build_snapshot(_board))
  ```

  Every other function in `replay_workspace.gd` (`_ready`, `set_loading`, `reset`,
  `get_timeline_controller`, `get_timeline_view`, `get_board_view`, `get_board_model`) is unchanged â€”
  `get_board_model()` still returns the raw `BoardModel` for existing callers.

- [x] Update the existing test file's call sites. Edit
  `showdownbot_studio/godot/tests/replay/test_abstract_board_view.gd`: every `view.bind(board)` call
  becomes `view.bind(ReplayBoardPresentationAdapter.build_snapshot(board))`. Concretely:

  ```gdscript
  func test_bind_shows_species_hp_status() -> void:
  	var view := _spawn_view()
  	var board := BoardModel.new()
  	board.has_replay = true
  	board.replace_slot_from_switch("p1", "a", _make_event(1, "switch", {
  		"pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": "Pikachu",
  		"hp_current": 20, "hp_maximum": 35, "hp_fainted": false, "hp_status": "brn",
  	}))
  	board.recompute_has_recorded_state()
  	view.bind(ReplayBoardPresentationAdapter.build_snapshot(board))
  	assert_str(view.get_slot_species("p1", "a")).is_equal("Pikachu")
  	assert_str(view.get_slot_hp_text("p1", "a")).is_equal("20/35")
  	assert_str(view.get_node("Slots/P1AStatus").text).is_equal("brn")


  func test_bind_shows_weather_terrain_field_and_side_conditions() -> void:
  	var view := _spawn_view()
  	var board := BoardModel.new()
  	board.has_replay = true
  	board.weather = "RainDance"
  	board.terrain = "Electric Terrain"
  	board.add_field_condition("Trick Room")
  	board.add_side_condition("p1", "Stealth Rock")
  	board.add_side_condition("p2", "Spikes")
  	board.recompute_has_recorded_state()
  	view.bind(ReplayBoardPresentationAdapter.build_snapshot(board))
  	assert_str(view.get_weather_text()).is_equal("RainDance")
  	assert_str(view.get_terrain_text()).is_equal("Electric Terrain")
  	assert_bool(view.get_field_conditions_text().contains("Trick Room")).is_true()
  	assert_bool(view.get_side_conditions_text("p1").contains("Stealth Rock")).is_true()
  	assert_bool(view.get_side_conditions_text("p2").contains("Spikes")).is_true()


  func test_empty_state_only_when_not_has_replay() -> void:
  	var view: AbstractBoardView = preload("res://src/replay/abstract_board_view.tscn").instantiate()
  	add_child(view)
  	var no_replay := BoardModel.new()
  	no_replay.has_replay = false
  	view.bind(ReplayBoardPresentationAdapter.build_snapshot(no_replay))
  	assert_bool(view.get_empty_state_visible()).is_true()

  	var trusted_empty := BoardModel.new()
  	trusted_empty.has_replay = true
  	trusted_empty.has_recorded_state = false
  	view.bind(ReplayBoardPresentationAdapter.build_snapshot(trusted_empty))
  	assert_bool(view.get_empty_state_visible()).is_false()
  ```

  (`test_set_loading_shows_and_clears` is unchanged â€” it never calls `bind()`.)

- [x] Run the full `replay/` gdUnit suite and confirm the same pass count as the pre-refactor
  baseline:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/replay/"
  ```

  Expected: identical total pass count to the number recorded in this task's first step, `0` failed.

- [x] Run the full existing gdUnit suite to confirm nothing outside `replay/` regressed (`ReplayWorkspace`
  is also exercised from `workspace/`'s tests via `AppShell`):

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/"
  ./showdownbot_studio/godot/tools/check_gdunit_truncation.ps1
  ```

  Expected: `0` failed, and the truncation check reports the run was not truncated.

- [x] Commit:

  ```
  git add showdownbot_studio/godot/src/replay/abstract_board_view.gd showdownbot_studio/godot/src/replay/replay_workspace.gd showdownbot_studio/godot/tests/replay/test_abstract_board_view.gd
  git commit -m "refactor(studio): retype AbstractBoardView.bind() to BattleBoardSnapshot"
  ```

---

## Task 16 â€” Fail-check the moved empty-state guard

**Files:** none committed by this task (scratch-only, reverted at the end).

Spec section 4.7 requires the refactor itself be "protected by targeted fail-checks (break the
guard, confirm red)." This proves `test_empty_state_only_when_not_has_replay` actually exercises the
`presentation_available`/`empty_state_reason` logic that Task 14 moved into
`ReplayBoardPresentationAdapter`, rather than passing vacuously.

- [x] Confirm current green baseline:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/replay/test_abstract_board_view.gd"
  ```

  Expected: all tests pass.

- [x] Break the guard. In `showdownbot_studio/godot/src/replay/replay_board_presentation_adapter.gd`,
  temporarily change:

  ```gdscript
  	if board == null or not board.has_replay:
  		snapshot.presentation_available = false
  ```

  to:

  ```gdscript
  	if board == null or not board.has_replay:
  		snapshot.presentation_available = true  # FAIL-CHECK: deliberately wrong, revert below
  ```

- [x] Run and confirm it goes red:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/replay/test_abstract_board_view.gd"
  ```

  Expected: `test_empty_state_only_when_not_has_replay` fails â€”
  `view.get_empty_state_visible()` returns `false` where the assertion expects `true`.

- [x] Revert the deliberate break back to `snapshot.presentation_available = false`. Run again and
  confirm green:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/replay/test_abstract_board_view.gd"
  ```

  Expected: all tests pass.

- [x] Nothing to commit for this task â€” the file is back to Task 15's committed content. Confirm the
  working tree is clean for this file:

  ```
  git diff --quiet showdownbot_studio/godot/src/replay/replay_board_presentation_adapter.gd
  ```

  (exits `0` / no output if clean).

---

## Task 17 â€” `WorkspaceRouter`

**Files:**
- Create: `showdownbot_studio/godot/src/workspace/workspace_router.gd`
- Create: `showdownbot_studio/godot/tests/workspace/test_workspace_router.gd`

Per spec section 4.6: "`WorkspaceRouter` â€” switches between the two top-level workspaces below. It
holds no domain state of its own." F0 only has one real workspace to register
(`OfflineViewerWorkspace`, Task 18) â€” `LiveClientWorkspace` does not exist until M1d â€” so this task
builds an ID-keyed registry that "handles being a single-workspace router cleanly for now" (spec
section 3.3) rather than hardcoding an assumption of exactly two workspaces.

- [x] Write the failing test. Create `showdownbot_studio/godot/tests/workspace/test_workspace_router.gd`:

  ```gdscript
  extends GdUnitTestSuite


  func after_test() -> void:
  	for child in get_children():
  		if child is WorkspaceRouter:
  			remove_child(child)
  			child.free()


  func _make_router() -> WorkspaceRouter:
  	var router := WorkspaceRouter.new()
  	add_child(router)
  	return router


  func test_register_and_show_single_workspace() -> void:
  	var router := _make_router()
  	var ws := Control.new()
  	router.register_workspace("only", ws)
  	router.show_workspace("only")
  	assert_str(router.get_active_workspace_id()).is_equal("only")
  	assert_bool(ws.visible).is_true()
  	ws.free()


  func test_show_unknown_workspace_id_does_not_change_active_id() -> void:
  	var router := _make_router()
  	var ws := Control.new()
  	router.register_workspace("only", ws)
  	router.show_workspace("only")
  	router.show_workspace("missing")
  	assert_str(router.get_active_workspace_id()).is_equal("only")
  	ws.free()


  func test_registered_workspace_ids_reports_exactly_registered_set() -> void:
  	var router := _make_router()
  	var a := Control.new()
  	var b := Control.new()
  	router.register_workspace("a", a)
  	router.register_workspace("b", b)
  	assert_int(router.get_registered_workspace_ids().size()).is_equal(2)
  	assert_bool(router.get_registered_workspace_ids().has("a")).is_true()
  	assert_bool(router.get_registered_workspace_ids().has("b")).is_true()
  	a.free()
  	b.free()


  func test_switching_workspace_hides_previous_and_shows_next() -> void:
  	var router := _make_router()
  	var a := Control.new()
  	var b := Control.new()
  	router.register_workspace("a", a)
  	router.register_workspace("b", b)
  	router.show_workspace("a")
  	router.show_workspace("b")
  	assert_bool(a.visible).is_false()
  	assert_bool(b.visible).is_true()
  	a.free()
  	b.free()
  ```

- [x] Run and confirm it fails (`WorkspaceRouter` does not exist yet):

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/workspace/test_workspace_router.gd"
  ```

- [x] Write the implementation. Create `showdownbot_studio/godot/src/workspace/workspace_router.gd`:

  ```gdscript
  class_name WorkspaceRouter
  extends Control

  ## Switches between registered top-level workspaces (spec
  ## docs/specs/2026-07-25-phase3-client-design.md section 4.6). Holds no domain state of its
  ## own -- no battle, credential, or team-bundle data lives here, only the registry of which
  ## Control node is currently visible. F0 registers exactly one workspace
  ## (OfflineViewerWorkspace, godot/src/workspace/offline_viewer_workspace.gd); LiveClientWorkspace
  ## does not exist until M1d, so this registry is keyed by String id rather than hardcoding an
  ## assumption of exactly two workspaces.

  signal active_workspace_changed(workspace_id: String)

  var _workspaces: Dictionary[String, Control] = {}
  var _active_id: String = ""


  func register_workspace(workspace_id: String, workspace: Control) -> void:
  	_workspaces[workspace_id] = workspace
  	workspace.visible = false
  	if workspace.get_parent() != self:
  		add_child(workspace)


  func show_workspace(workspace_id: String) -> void:
  	if not _workspaces.has(workspace_id):
  		push_error("WorkspaceRouter: unknown workspace id %s" % workspace_id)
  		return
  	for id in _workspaces.keys():
  		_workspaces[id].visible = (id == workspace_id)
  	_active_id = workspace_id
  	active_workspace_changed.emit(workspace_id)


  func get_active_workspace_id() -> String:
  	return _active_id


  func get_registered_workspace_ids() -> Array[String]:
  	var ids: Array[String] = []
  	for id in _workspaces.keys():
  		ids.append(id)
  	return ids


  func get_workspace(workspace_id: String) -> Control:
  	return _workspaces.get(workspace_id, null)
  ```

- [x] Run again and confirm pass:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/workspace/test_workspace_router.gd"
  ```

  Expected: `4` tests passed, `0` failed.

- [x] Commit:

  ```
  git add showdownbot_studio/godot/src/workspace/workspace_router.gd showdownbot_studio/godot/tests/workspace/test_workspace_router.gd
  git commit -m "feat(studio): add WorkspaceRouter (holds no domain state)"
  ```

---

## Task 18 â€” `OfflineViewerWorkspace`, `StudioRoot`, and the new main scene

**Files:**
- Create: `showdownbot_studio/godot/src/workspace/offline_viewer_workspace.gd`
- Create: `showdownbot_studio/godot/src/workspace/offline_viewer_workspace.tscn`
- Create: `showdownbot_studio/godot/src/workspace/studio_root.gd`
- Create: `showdownbot_studio/godot/src/workspace/studio_root.tscn`
- Modify: `showdownbot_studio/godot/project.godot`
- Create: `showdownbot_studio/godot/tests/workspace/test_studio_root.gd`

Per spec section 4.6: `OfflineViewerWorkspace` "wraps the existing `AppShell` content **unchanged**,"
and `StudioRoot` "is the new application entry point... never owns battle or credential state."
`AppShell`'s own `.gd`/`.tscn` files are not modified anywhere in this task.

- [x] Write the failing test. Create `showdownbot_studio/godot/tests/workspace/test_studio_root.gd`:

  ```gdscript
  extends GdUnitTestSuite

  const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"
  const _STUDIO_ROOT_SCENE := preload("res://src/workspace/studio_root.tscn")


  func _fixture_path(relative: String) -> String:
  	return ProjectSettings.globalize_path(_FIXTURES_ROOT.path_join(relative))


  func after_test() -> void:
  	for child in get_children():
  		if child is StudioRoot:
  			remove_child(child)
  			child.free()


  func _spawn_root() -> StudioRoot:
  	var root: StudioRoot = _STUDIO_ROOT_SCENE.instantiate()
  	add_child(root)
  	return root


  func test_studio_root_shows_offline_viewer_workspace_by_default() -> void:
  	var root := _spawn_root()
  	await await_idle_frame()
  	assert_str(root.get_router().get_active_workspace_id()).is_equal(StudioRoot.OFFLINE_VIEWER_WORKSPACE_ID)
  	assert_bool(root.get_offline_viewer_workspace().visible).is_true()


  func test_studio_root_router_has_exactly_one_registered_workspace() -> void:
  	var root := _spawn_root()
  	await await_idle_frame()
  	assert_int(root.get_router().get_registered_workspace_ids().size()).is_equal(1)


  func test_offline_viewer_workspace_opens_fixture01_through_wrapped_app_shell() -> void:
  	var root := _spawn_root()
  	await await_idle_frame()
  	var shell: AppShell = root.get_offline_viewer_workspace().get_app_shell()
  	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
  	var frames := 0
  	while not shell.is_settled() and frames < 600:
  		await await_idle_frame()
  		frames += 1
  	assert_bool(shell.is_settled()).is_true()
  	assert_str(shell.get_declared_mode()).is_equal(BundleMode.REPLAY_TRACE)
  	assert_int(shell.get_decision_count()).is_equal(3)
  ```

- [x] Run and confirm it fails (`StudioRoot` and its scene do not exist yet):

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/workspace/test_studio_root.gd"
  ```

- [x] Write `OfflineViewerWorkspace`. Create
  `showdownbot_studio/godot/src/workspace/offline_viewer_workspace.gd`:

  ```gdscript
  class_name OfflineViewerWorkspace
  extends Control

  ## Wraps the existing AppShell content unchanged (spec
  ## docs/specs/2026-07-25-phase3-client-design.md section 4.6): Phase 0's viewer keeps working
  ## exactly as it does today. This class adds a routing seam above AppShell, never a
  ## modification inside it -- app_shell.gd and app_shell.tscn are untouched by this task.

  @onready var _app_shell: AppShell = $AppShell


  func get_app_shell() -> AppShell:
  	return _app_shell
  ```

  Create `showdownbot_studio/godot/src/workspace/offline_viewer_workspace.tscn`:

  ```
  [gd_scene load_steps=3 format=3]

  [ext_resource type="Script" path="res://src/workspace/offline_viewer_workspace.gd" id="1_offline"]
  [ext_resource type="PackedScene" path="res://src/workspace/app_shell.tscn" id="2_shell"]

  [node name="OfflineViewerWorkspace" type="Control"]
  layout_mode = 3
  anchors_preset = 15
  anchor_right = 1.0
  anchor_bottom = 1.0
  grow_horizontal = 2
  grow_vertical = 2
  script = ExtResource("1_offline")

  [node name="AppShell" parent="." instance=ExtResource("2_shell")]
  layout_mode = 1
  anchors_preset = 15
  anchor_right = 1.0
  anchor_bottom = 1.0
  grow_horizontal = 2
  grow_vertical = 2
  ```

- [x] Write `StudioRoot`. Create `showdownbot_studio/godot/src/workspace/studio_root.gd`:

  ```gdscript
  class_name StudioRoot
  extends Control

  ## New application entry point (spec docs/specs/2026-07-25-phase3-client-design.md section
  ## 4.6): owns only navigation and workspace lifecycle. It never owns battle or credential
  ## state -- those stay inside battle/ and session/ once those modules exist (M1c, M2a), reached
  ## only through the three communication paths (section 4.2). F0 registers exactly one
  ## workspace; StudioRoot's fuller cross-workspace settings-ownership story (global scale/
  ## density/theme, currently owned end-to-end by AppShell/WorkspaceLayout for the single
  ## Phase-0 workspace) is deferred until a second real workspace (LiveClientWorkspace, M1d)
  ## exists to share it with -- see this plan's Task 18 notes.

  const OFFLINE_VIEWER_WORKSPACE_ID := "offline_viewer"

  @onready var _router: WorkspaceRouter = $WorkspaceRouter
  @onready var _offline_viewer: OfflineViewerWorkspace = $WorkspaceRouter/OfflineViewerWorkspace


  func _ready() -> void:
  	_router.register_workspace(OFFLINE_VIEWER_WORKSPACE_ID, _offline_viewer)
  	_router.show_workspace(OFFLINE_VIEWER_WORKSPACE_ID)


  func get_router() -> WorkspaceRouter:
  	return _router


  func get_offline_viewer_workspace() -> OfflineViewerWorkspace:
  	return _offline_viewer
  ```

  Create `showdownbot_studio/godot/src/workspace/studio_root.tscn`:

  ```
  [gd_scene load_steps=4 format=3]

  [ext_resource type="Script" path="res://src/workspace/studio_root.gd" id="1_root"]
  [ext_resource type="Script" path="res://src/workspace/workspace_router.gd" id="2_router"]
  [ext_resource type="PackedScene" path="res://src/workspace/offline_viewer_workspace.tscn" id="3_offline"]

  [node name="StudioRoot" type="Control"]
  layout_mode = 3
  anchors_preset = 15
  anchor_right = 1.0
  anchor_bottom = 1.0
  grow_horizontal = 2
  grow_vertical = 2
  script = ExtResource("1_root")

  [node name="WorkspaceRouter" type="Control" parent="."]
  layout_mode = 1
  anchors_preset = 15
  anchor_right = 1.0
  anchor_bottom = 1.0
  grow_horizontal = 2
  grow_vertical = 2
  script = ExtResource("2_router")

  [node name="OfflineViewerWorkspace" parent="WorkspaceRouter" instance=ExtResource("3_offline")]
  layout_mode = 1
  anchors_preset = 15
  anchor_right = 1.0
  anchor_bottom = 1.0
  grow_horizontal = 2
  grow_vertical = 2
  ```

- [x] Point the project's main scene at `StudioRoot`. Edit `showdownbot_studio/godot/project.godot`,
  changing:

  ```
  run/main_scene="res://src/workspace/app_shell.tscn"
  ```

  to:

  ```
  run/main_scene="res://src/workspace/studio_root.tscn"
  ```

  This is safe: every existing gdUnit test that needs `AppShell` preloads
  `res://src/workspace/app_shell.tscn` directly rather than depending on the project's main scene
  (verified during planning â€” see this plan's Ordering rationale section), so nothing else changes
  behavior as a result of this one line.

- [x] Run and confirm the new test passes:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/workspace/test_studio_root.gd"
  ```

  Expected: `3` tests passed, `0` failed.

- [x] Run the full existing gdUnit suite to confirm the `project.godot` change broke nothing:

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/"
  ./showdownbot_studio/godot/tools/check_gdunit_truncation.ps1
  ```

  Expected: `0` failed, run not truncated.

- [x] Commit:

  ```
  git add showdownbot_studio/godot/src/workspace/offline_viewer_workspace.gd showdownbot_studio/godot/src/workspace/offline_viewer_workspace.tscn showdownbot_studio/godot/src/workspace/studio_root.gd showdownbot_studio/godot/src/workspace/studio_root.tscn showdownbot_studio/godot/project.godot showdownbot_studio/godot/tests/workspace/test_studio_root.gd
  git commit -m "feat(studio): add StudioRoot/OfflineViewerWorkspace scaffold as the new main scene"
  ```

---

## Task 19 â€” Full-suite verification

**Files:** none (verification only).

- [x] Run the full Python suite exactly as `studio-windows.yml` and `studio-security-invariants.yml`
  do, and compare the collected count against this plan's recorded baseline (114):

  ```
  cd showdownbot_studio/python
  python -m pytest -q --collect-only
  ```

  Expected new count: `114` (baseline) `+ 8` (Task 1â€“8: one doc-existence test each, in
  `test_f0_binding_docs.py`) `+ 6` (Task 9: two; Task 10: two; Task 11: two, in their own three
  files) = **128** tests collected. Record the actual reported count; if it differs from 128,
  recount which task added how many test functions before treating the run as green â€” do not
  assume the arithmetic above is correct without checking it against the actual file contents
  landed by Tasks 1â€“11.

- [x] Run the full Python suite for real (not collect-only):

  ```
  cd showdownbot_studio/python
  python -m pytest -q
  ```

  Expected: all tests pass, `0` failed.

- [x] Run the dedicated architecture-only lane locally, exactly as `studio-security-invariants.yml`
  does:

  ```
  cd showdownbot_studio/python
  python -m pytest -q -m architecture
  ```

  Expected: `7` tests passed (Task 6's one marked doc test, Task 9's two, Task 10's two, Task 11's
  two), `0` failed.

- [x] Run the full gdUnit suite exactly as `studio-windows.yml` does, and record the reported total
  test count (there is no pre-recorded gdUnit baseline in this plan â€” record what the run reports
  now, and separately confirm it is at least the pre-F0 total by re-reading this plan's Task
  13/14/17/18 new-test counts: `3 + 6 + 4 + 3 = 16` new gdUnit tests added, on top of whatever the
  suite reported before Task 13's first commit):

  ```
  ./showdownbot_studio/godot/tools/run_gdunit_headless.ps1 -a "res://tests/"
  ./showdownbot_studio/godot/tools/check_gdunit_truncation.ps1
  ```

  Expected: `0` failed; the truncation check passes (declared count equals executed-plus-skipped
  count); the reported total is the pre-F0 total plus 16.

- [x] Confirm no stray scratch files from Tasks 9â€“11's or Task 16's fail-checks were left behind:

  ```
  git status --porcelain showdownbot_studio/godot/src
  ```

  Expected: no output (a non-empty result means a `_scratch_*.gd` file or an uncommitted edit to
  `replay_board_presentation_adapter.gd` was left over â€” delete/revert it before considering F0
  done).

- [x] Run `git diff --check` across the full set of F0 commits before treating the slice as
  commit-ready, per this repository's working agreement:

  ```
  git diff --check main
  ```

  Expected: no output (no whitespace errors).
