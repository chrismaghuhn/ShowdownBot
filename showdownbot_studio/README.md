# ShowdownBot Studio

ShowdownBot Studio is a planned **desktop analysis and client companion** for the ShowdownBot
project. It lives in this monorepo so its trace, provenance, format, and protocol contracts can
evolve alongside the bot without mixing the two products' runtime code.

The long-term direction includes replay analysis, live spectating, team analysis, a full Pokémon
Showdown protocol client, controlled add-ons, and external bot adapters. Delivery is phased. The
first possible implementation slice is only the offline Replay + DecisionTrace Viewer.

## Status

- Product north star: design approved; written master spec pending user review.
- Viewer v0: design approved; implementation plan not started.
- Godot application: not created.
- Python bundle exporter: not implemented.
- Live client, plugins, mods, and external bots: future phases only.
- Active ShowdownBot work remains governed by [`../docs/ROADMAP.md`](../docs/ROADMAP.md).

## Start here

1. [`docs/MASTER_SPEC.md`](docs/MASTER_SPEC.md) — complete product boundary and phased roadmap.
2. [`docs/research/2026-07-showdown-client-user-research.md`](docs/research/2026-07-showdown-client-user-research.md) — current client pain-point research.
3. [`docs/specs/viewer-v0-design.md`](docs/specs/viewer-v0-design.md) — first bounded product slice.
4. [`docs/architecture/PROJECT_BOUNDARIES.md`](docs/architecture/PROJECT_BOUNDARIES.md) — ownership and dependency rules.
5. [`docs/design/viewer-v0-mockups/`](docs/design/viewer-v0-mockups/) — accepted visual direction and its binding review corrections.

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
