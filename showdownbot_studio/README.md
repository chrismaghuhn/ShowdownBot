# ShowdownBot Studio

ShowdownBot Studio is a planned **desktop analysis and client companion** for the ShowdownBot
project. It lives in this monorepo so its trace, provenance, format, and protocol contracts can
evolve alongside the bot without mixing the two products' runtime code.

The long-term direction includes replay analysis, live spectating, team analysis, a full Pokémon
Showdown protocol client, controlled add-ons, and external bot adapters. Delivery is phased. The
first possible implementation slice is only the offline Replay + DecisionTrace Viewer.

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
- **Plan F** APPROVED (Rev. 6) and its implementation is running on branch
  `studio/plan-f-acceptance` — **not yet merged to `main`, and not complete.** F1–F3 (fixture
  catalogue, automated gates, honesty audit) and F4 (this docs closeout) are done on that branch;
  F1's own CI-wiring task is still open (no `showdownbot_studio/` job exists in
  `.github/workflows/` yet — every green count reported anywhere in this plan set is a local
  measurement, not CI-verified) and the gate fail-check pass is partial. See
  [`docs/plans/evidence/viewer-v0-f-merge-readiness.md`](docs/plans/evidence/viewer-v0-f-merge-readiness.md)
  for the full state before any merge decision.
- **Phase 1+ (Live Spectator, Team Analyzer, full client, add-ons, external bots) remain explicitly
  unauthorized** — Plan F's own stop line (§8) forbids growing this plan set toward them; each
  needs its own approved design + plan first.
- Active ShowdownBot work remains governed by [`../docs/ROADMAP.md`](../docs/ROADMAP.md).

## Start here

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
