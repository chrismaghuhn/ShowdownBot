# Viewer v0 — Plan B: Godot Shell and Bundle Loader (Sketch)

**Status:** DRAFT — sketch only; **implementation not authorized**
**Date:** 2026-07-21
**Depends on:** Plan A fixture 1 (+ refuse fixtures 6, 7, 12 as available)
**Unblocks:** Plans C–E

**Authority:** [`../specs/viewer-v0-design.md`](../specs/viewer-v0-design.md) §5.4,
[`../decisions/ADR-001-godot-ui-technology.md`](../decisions/ADR-001-godot-ui-technology.md),
bundle contract §6 / §8.6 / §13.2

## Goal

Create the Godot 4.5.2 project shell and a worker-backed `BundleLoader` that validates a local
bundle and exposes immutable typed DTOs to the scene tree — with fail-closed refuse paths and no
domain recomputation.

## Non-goals

- No replay board, candidate UI, or docks beyond a minimal shell
- No Python in the Godot process
- No network
- No artwork / fonts downloaded at runtime (offline fonts decided in Plan E if needed)

## Architecture

```text
User selects bundle dir
  → BundleLoader (worker): read → hash → parse → DTO build
  → progress + cancel
  → main thread receives immutable DTOs only
  → WorkspaceShell shows open OK / refuse diagnostic
```

## Proposed files

| Path | Responsibility |
|---|---|
| `godot/project.godot` | Engine pin 4.5.2; app metadata |
| `godot/addons/gdUnit4/` | Pinned addon (version locked in this plan on approval) |
| `godot/src/bundle/bundle_dto.gd` | Typed DTO classes |
| `godot/src/bundle/bundle_loader.gd` | Worker load / cancel / progress |
| `godot/src/bundle/bundle_validator.gd` | Reader checks §8.6 / §13.2 |
| `godot/src/workspace/app_shell.tscn` | Minimal window + open/refuse UI |
| `godot/tests/...` | gdUnit4 headless cases |

## Task sketch

### B0 — Project pin

- [ ] Create Godot 4.5.2 project under `godot/`
- [ ] Pin gdUnit4 version verified against 4.5.2; document CLI + JUnit output
- [ ] Headless smoke test runs in CI/local script

### B1 — DTO types

- [ ] Manifest, file entry, privacy, source_provenance, decision row, candidate, battle event
- [ ] Mode derivation from `files` present flags (§11.1.1)
- [ ] No inference of missing optional values (keep null / “not recorded” at UI later)

### B2 — Validator (main-thread-safe pure logic)

- [ ] Unknown major → refuse + list supported
- [ ] Unknown required capability → refuse + name
- [ ] Hash mismatch → refuse + name file
- [ ] Undeclared file on disk → refuse
- [ ] Mode key `required != present` → refuse
- [ ] Optional key `required: true` → refuse
- [ ] Both mode files absent → refuse
- [ ] Field nullability vs mode → refuse

### B3 — Worker loader

- [ ] File IO, hashing, JSON parse, DTO build off main thread
- [ ] Progress events; cancellation
- [ ] Worker never mutates scene tree
- [ ] Representative fixture 1 loads without UI stall (manual + automated timing stub)

### B4 — Shell UX (minimal)

- [ ] Open directory
- [ ] Show trusted-open vs refuse diagnostic
- [ ] Replay-only / trace-only open as modes (not errors) when fixtures 4/5 available
- [ ] CLI/arg passthrough stub for later `--decision` (Plan D owns behavior)

## Acceptance (Plan B done)

- Fixture 1 opens to trusted DTOs
- Fixtures 6/7/12 (when present) refuse with named reason
- gdUnit4 headless suite green for validator + loader
- No scene mutation from worker (test or documented assertion harness)
- Engine upgrade path remains “revisit ADR” — no floating Godot version

## Approval questions

1. Exact gdUnit4 release tag/commit
2. Windows launch script location (`godot/` vs Studio root)
