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
  APPROVED; **Plan A** APPROVED 2026-07-21 (Rev. 6) as docs only.
  ([`docs/plans/`](docs/plans/)). Plans B–F remain DRAFT. **Plan A code** still requires a separate
  implementation go-ahead.
- Next: Plan A implementation authorization, or Plan B review.
- Godot application: not created.
- Python bundle exporter: not implemented.
- Live client, plugins, mods, and external bots: future phases only.
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
| `godot/` | Future typed-GDScript desktop application |
| `python/` | Future deterministic exporters and protocol/domain adapters |
| `schemas/` | Future versioned cross-process and bundle contracts |
| `fixtures/` | Future small, provenance-clean viewer fixtures |
| `tests/` | Future contract and end-to-end verification |

The placeholder READMEs reserve responsibilities only. They do not authorize implementation.
