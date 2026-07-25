# ShowdownBot Studio

ShowdownBot Studio is a **desktop analysis and client companion** for the ShowdownBot project. It
lives in this monorepo so its trace, provenance, format, and protocol contracts can evolve
alongside the bot without mixing the two products' runtime code.

The long-term direction includes replay analysis, live spectating, team analysis, a full Pokémon
Showdown protocol client, controlled add-ons, and external bot adapters. Delivery is phased.

**Phase 0 — the offline Replay + DecisionTrace Viewer — is built, merged and closed** (Godot
4.5.2, Windows). **Phase 3 — the full protocol client — is authorized** with its own approved
design; every other phase remains unauthorized. See the stop line under Status.

## Status

- Product north star: design approved; written master spec is non-binding context for Phase 0
  (separate review later / before later phases).
- Viewer v0: design + bundle contract approved (incl. §14.1 Amendment A). Implementation **index**
  APPROVED ([`docs/plans/`](docs/plans/)).
- **Plan A** merged via PR **#41** (exporter + fixtures).
- **Plan B** merged via PR **#44** (Godot shell + sealed DTO loader).
- **Plan C** merged via PR **#46** (replay board + timeline) @ `1b0be1d`.
- **Plan D** merged via PR **#47** (+ follow-ups PR **#48**) @ `0256602` (candidate table +
  decision detail).
- **Plan E** merged: E1 shipped as `e757772`, E2–E7 merged via PR **#71** (`4ed406c`)
  (diagnostics, scale/density, keyboard shortcuts, layout shell).
- **Plan F** merged via PR **#73**, with closeout follow-ups **#74**–**#81**. F1's CI-wiring task
  is closed: `.github/workflows/studio-windows.yml` (PR **#76**) runs both suites on
  `windows-latest`, so counts reported here are CI-verified rather than local-only. It also carries
  a truncation guard, because gdUnit4 once reported 14 of 33 cases as a complete "PASSED" run.
- **Phase 0 is CLOSED (2026-07-25).** Choice Point 4's J2 condition — manual evidence *filed*
  **and** explicitly *signed off* — was met by PR **#81**.
- Post-closeout PRs **#82**–**#86** were **test coverage only**, no feature scope. They ran a
  fail-check pass — break the guard, confirm the test goes red — that is now complete for the
  python suite and a 20-guard sample on the Godot side. It closed 8 defects that green suites had
  not seen, including a containment guard whose two tests self-skipped for a wrong reason on every
  run, locally and in CI. See
  [`docs/plans/evidence/viewer-v0-gate-coverage-recheck.md`](docs/plans/evidence/viewer-v0-gate-coverage-recheck.md)
  — and read it before picking work from the older gate-coverage audit, whose status column is a
  snapshot of a superseded tree.
- **Phase 3 is authorized** — design approved 2026-07-25
  ([`docs/specs/2026-07-25-phase3-client-design.md`](docs/specs/2026-07-25-phase3-client-design.md)).
  **Its F0 architecture foundation is merged** (PR **#88**: binding security/architecture documents,
  forbidden-dependency architecture guards + `studio-security-invariants` CI lane, the neutral
  `BattleBoardSnapshot` board-presentation contract, and the `StudioRoot`/`WorkspaceRouter` shell).
- **Phase 1 is no longer authorized as an independent product phase**; its read-only spectator
  scope is subsumed by Phase 3 Milestone M1.
- **Phases 2, 4, and 5 remain unauthorized** — each needs its own approved design + plan first.
- Approval of the M1 implementation plan does not authorize M1a implementation. M1a requires a
  separate explicit implementation go-ahead.
- Active ShowdownBot work remains governed by [`../docs/ROADMAP.md`](../docs/ROADMAP.md).

## Start here

0. [`AGENTS.md`](AGENTS.md) — non-negotiable maintainer rules and safety defaults; read first
   before changing anything under `showdownbot_studio/`.
1. [`docs/plans/README.md`](docs/plans/README.md) — Viewer v0 plan order and approval status (A–F).
2. [`docs/specs/viewer-v0-design.md`](docs/specs/viewer-v0-design.md) — first bounded product slice.
3. [`docs/specs/viewer-v0-bundle-contract-design.md`](docs/specs/viewer-v0-bundle-contract-design.md) — binding bundle/exporter contract.
4. [`docs/architecture/PROJECT_BOUNDARIES.md`](docs/architecture/PROJECT_BOUNDARIES.md) — ownership and dependency rules.
5. [`docs/design/viewer-v0-mockups/`](docs/design/viewer-v0-mockups/) — accepted visual direction and its binding review corrections.
6. [`docs/MASTER_SPEC.md`](docs/MASTER_SPEC.md) — product-family context (not binding for Phase 0).

## Repository layout

| Path | Purpose |
|---|---|
| `docs/` | Master spec, research, slice specs, decisions, and plans |
| `godot/` | Typed-GDScript desktop application (Plans B–C on tip) |
| `python/` | Deterministic exporters and protocol/domain adapters (Plan A on tip) |
| `schemas/` | Future versioned cross-process and bundle contracts |
| `fixtures/` | Small, provenance-clean viewer fixtures |
| `tests/` | Contract and end-to-end verification |

The placeholder READMEs reserve responsibilities only where a later plan has not yet landed.
