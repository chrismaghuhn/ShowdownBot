# Godot Application (Viewer v0)

Phase 0 uses **Godot 4.5.2-stable** with typed GDScript (ADR-001). Plan B owns the project
scaffold, sealed DTOs, validator, and worker loader.

## Engine pin

| Artifact | SHA-256 |
|---|---|
| `Godot_v4.5.2-stable_win64.exe.zip` | `3766090865330ab2a0ed33594520394b711c620b1378f9223904faeef60f2f14` |
| `Godot_v4.5.2-stable_win64.exe` | `a2a2eb7eae9ce159042f6dc3aca89f6d0e4cccb92d3a4892cc8128c958b1d466` |
| `Godot_v4.5.2-stable_win64_console.exe` | `446e08f71624052572f96de9031850ba96382ce6752adde38bb955b0a49bed01` |

Digests live in `tools/ENGINE_SHA256SUMS`. Install under `tools/engine/` (gitignored): verify ZIP →
extract → verify **editor and console** EXEs → install. Runtime `verify_engine_pin.ps1` always
checks both EXEs (and the ZIP when present) before any launch.

Plan B: `docs/plans/2026-07-21-viewer-v0-b-godot-shell-and-loader.md`
(**APPROVED** 2026-07-21, Rev. 6 — docs/pin only).

Do **not** use Godot 4.7.x. A stray `Godot_v4.7.1-stable_win64.exe` in this folder is gitignored;
delete or move it — Plan B does not run against it.

## gdUnit4

Vendored at `addons/gdUnit4/` in Plan B task B0 — **v6.1.3**
(`1579130d73f15f628fd0cfdbf7d60bdc39144a26`), MIT. See `THIRD_PARTY_NOTICES.md` (B0).

## Status

Plan B docs/pin APPROVED. No Godot project code until Plan A/PR #41 merged + separate
implementation go-ahead.
