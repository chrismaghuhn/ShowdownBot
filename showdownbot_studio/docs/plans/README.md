# Implementation Plans

Phase implementation plans belong here. A plan must reference the approved phase specs that
authorize it and must not mix tasks from later phases. Draft and approved plans may both live
here; the status line on each document is authoritative.

## Viewer v0 — plan set

| Document | Status |
|---|---|
| [`2026-07-21-viewer-v0-implementation-index.md`](2026-07-21-viewer-v0-implementation-index.md) | **APPROVED** 2026-07-21 (Rev. 2) — orders A–F; **does not authorize code** |
| Plan A | **APPROVED** 2026-07-21 (Rev. 6) — docs only; **code needs separate go-ahead** |
| Plans B–F | **DRAFT** — each needs its own APPROVED mark before its code may start |

**Planning authorization:** Viewer v0 design + bundle contract are APPROVED and authorize these
plans. The master spec is non-binding context for Phase 0 (index §2.2).

**Code authorization (fail-closed):**

1. Approving the implementation index alone does **not** authorize any code.
2. A plan must be marked **APPROVED** before its code may be considered; Plan A additionally
   requires a **separate implementation go-ahead** after this docs approval.
3. Plan X must not start before its hard dependencies in the index §3 graph are satisfied.
4. Phases 1–5 remain unauthorized.

| Order | Document | Scope | Status |
|---|---|---|---|
| 0 | [`2026-07-21-viewer-v0-implementation-index.md`](2026-07-21-viewer-v0-implementation-index.md) | Sequencing, gates, non-goals, file map | **APPROVED** |
| A | [`2026-07-21-viewer-v0-a-exporter-and-fixtures.md`](2026-07-21-viewer-v0-a-exporter-and-fixtures.md) | Python exporter + contract fixtures | **APPROVED** 2026-07-21 (Rev. 6) |
| B | [`2026-07-21-viewer-v0-b-godot-shell-and-loader.md`](2026-07-21-viewer-v0-b-godot-shell-and-loader.md) | Godot project + typed DTO loader | DRAFT |
| C | [`2026-07-21-viewer-v0-c-replay-and-timeline.md`](2026-07-21-viewer-v0-c-replay-and-timeline.md) | Abstract board + timeline | DRAFT |
| D | [`2026-07-21-viewer-v0-d-decision-inspection.md`](2026-07-21-viewer-v0-d-decision-inspection.md) | Candidate table + decision detail | DRAFT |
| E | [`2026-07-21-viewer-v0-e-diagnostics-a11y-layout.md`](2026-07-21-viewer-v0-e-diagnostics-a11y-layout.md) | Diagnostics, scale, keyboard, density | DRAFT |
| F | [`2026-07-21-viewer-v0-f-e2e-acceptance.md`](2026-07-21-viewer-v0-f-e2e-acceptance.md) | Frozen end-to-end acceptance | DRAFT |

**Next:** separate implementation go-ahead for Plan A code, or review Plan B (DRAFT). No code
without that go-ahead.

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
