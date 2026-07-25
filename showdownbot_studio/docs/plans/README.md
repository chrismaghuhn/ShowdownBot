# Implementation Plans

Phase implementation plans belong here. A plan must reference the approved phase specs that
authorize it and must not mix tasks from later phases. Draft and approved plans may both live
here; the status line on each document is authoritative.

## Viewer v0 — plan set

| Document | Status |
|---|---|
| [`2026-07-21-viewer-v0-implementation-index.md`](2026-07-21-viewer-v0-implementation-index.md) | **APPROVED** 2026-07-21 (Rev. 2) — orders A–F; **does not authorize code** |
| Plan A | **APPROVED** + **merged** via PR **#41** |
| Plan B | **APPROVED** + **merged** via PR **#44** |
| Plan C | **APPROVED** + **merged** via PR **#46** @ `1b0be1d` |
| Plan D | **APPROVED** — Rev. 5; **merged** via PR **#47** (+ follow-ups PR **#48**) @ `0256602` |
| Plan E | **APPROVED** — Rev. 3; **merged** — E1 shipped as `e757772`, E2–E7 via PR **#71** (`4ed406c`) |
| Plan F | **APPROVED** + **merged** via PR **#73**, with closeout follow-ups **#74**–**#81** — see [`evidence/viewer-v0-f-merge-readiness.md`](evidence/viewer-v0-f-merge-readiness.md) |

**Phase 0 is closed (2026-07-25).** Choice Point 4's J2 condition — manual evidence *filed* **and**
explicitly *signed off* — was met by PR **#81**. Plan F §8's stop line now applies: Live Spectator,
Team Analyzer, the full client, add-ons and external bots each need their own approved design +
plan before any work starts.

Work merged after closeout (PRs **#82**–**#86**) was **test coverage only** and added no feature
scope. Before opening any slice from the Plan F gate-coverage audit, read
[`evidence/viewer-v0-gate-coverage-recheck.md`](evidence/viewer-v0-gate-coverage-recheck.md):
that audit's status column is a snapshot of a superseded tree, and acting on it cost duplicate
work twice on 2026-07-25.

**Unresolved discrepancy, flagged rather than guessed:** this table says Plan F is Rev. 6 while the
plan's own status line reads *"APPROVED — 2026-07-24 (Rev. 4)"*. One of the two is wrong; the plan
document is normally authoritative on its own revision. Owner to reconcile — not corrected here,
because picking a number without knowing which revision was actually approved would replace a
visible contradiction with an invisible one.

**Planning authorization:** Viewer v0 design + bundle contract are APPROVED and authorize these
plans. The master spec is non-binding context for Phase 0 (index §2.2).

**Code authorization (fail-closed):**

1. Approving the implementation index alone does **not** authorize any code.
2. A plan must be marked **APPROVED** before its code may be considered; after APPROVED, code still
   requires a **separate implementation go-ahead**.
3. Plan X must not start before its hard dependencies in the index §3 graph are satisfied.
4. Phases 1–5 remain unauthorized.

| Order | Document | Scope | Status |
|---|---|---|---|
| 0 | [`2026-07-21-viewer-v0-implementation-index.md`](2026-07-21-viewer-v0-implementation-index.md) | Sequencing, gates, non-goals, file map | **APPROVED** |
| A | [`2026-07-21-viewer-v0-a-exporter-and-fixtures.md`](2026-07-21-viewer-v0-a-exporter-and-fixtures.md) | Python exporter + contract fixtures | **merged** PR #41 |
| B | [`2026-07-21-viewer-v0-b-godot-shell-and-loader.md`](2026-07-21-viewer-v0-b-godot-shell-and-loader.md) | Godot project + typed DTO loader | **merged** PR #44 |
| C | [`2026-07-21-viewer-v0-c-replay-and-timeline.md`](2026-07-21-viewer-v0-c-replay-and-timeline.md) | Abstract board + timeline | **merged** PR #46 |
| D | [`2026-07-21-viewer-v0-d-decision-inspection.md`](2026-07-21-viewer-v0-d-decision-inspection.md) | Candidate table + decision detail | **merged** PR #47 + #48 |
| E | [`2026-07-21-viewer-v0-e-diagnostics-a11y-layout.md`](2026-07-21-viewer-v0-e-diagnostics-a11y-layout.md) | Diagnostics, scale, keyboard, density | **merged** PR #71 |
| F | [`2026-07-21-viewer-v0-f-e2e-acceptance.md`](2026-07-21-viewer-v0-f-e2e-acceptance.md) | Frozen end-to-end acceptance | **APPROVED** + **merged** via PR **#73** (closeout **#74**–**#81**) |

## Phase 3 — plan set

Phase 3 (full protocol client) is authorized by the approved design
[`../specs/2026-07-25-phase3-client-design.md`](../specs/2026-07-25-phase3-client-design.md)
(2026-07-25). Plan status follows the same fail-closed rule as Phase 0: an APPROVED plan still
requires a separate implementation go-ahead before code.

| Order | Document | Scope | Status |
|---|---|---|---|
| F0 | [`2026-07-25-phase3-f0-foundation.md`](2026-07-25-phase3-f0-foundation.md) | Architecture foundation: binding docs, architecture guards + CI lane, board-presentation contract, shell scaffold | **APPROVED** + **merged** via PR **#88** |
| M1 | `2026-07-25-phase3-m1-connect-spectate.md` | Connect + Spectate (M1a–M1e) | DRAFT — revision required (owner review 2026-07-25); not yet committed |

**Phase 1 is no longer an independent product phase** — its read-only spectator scope is subsumed
by Phase 3 Milestone M1. **Phases 2, 4, and 5 remain unauthorized** and have no plans here.

## Authority for this plan set

**Binding (approved for Viewer v0 planning):**

- Slice: [`../specs/viewer-v0-design.md`](../specs/viewer-v0-design.md)
- Bundle contract (wins on conflict): [`../specs/viewer-v0-bundle-contract-design.md`](../specs/viewer-v0-bundle-contract-design.md) (incl. §14.1 Amendment A 2026-07-21)
- Boundaries: [`../architecture/PROJECT_BOUNDARIES.md`](../architecture/PROJECT_BOUNDARIES.md)
- UI ADR: [`../decisions/ADR-001-godot-ui-technology.md`](../decisions/ADR-001-godot-ui-technology.md)
- License / privacy: [`../research/2026-07-license-data-audit.md`](../research/2026-07-license-data-audit.md)
- Visual direction: [`../design/viewer-v0-mockups/README.md`](../design/viewer-v0-mockups/README.md)

**Context — not binding for Phase 0:**

- Master: [`../MASTER_SPEC.md`](../MASTER_SPEC.md) — non-binding context per user decision
  2026-07-21 (index §2.2). Separate review before later phases, or sooner if it would change
  Phase-0 boundaries.

Phases 1–5 (live spectator, analyzer, full client, add-ons, external bots) have **no** plans here.
