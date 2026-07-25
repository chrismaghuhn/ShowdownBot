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
  repository exporter — never a bare Python interpreter or a package resolved via PATH/ambient
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
client's control — those remain out of scope exactly as they are for any client of a service the
user does not operate.
