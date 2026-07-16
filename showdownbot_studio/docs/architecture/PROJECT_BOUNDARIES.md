# ShowdownBot Studio Project Boundaries

**Status:** design boundary; no runtime code exists yet
**Date:** 2026-07-16

## 1. Ownership

| Area | Owns | Does not own |
|---|---|---|
| Existing `showdown_bot/` | Bot state, decisions, calc, beliefs, eval, trace production | Studio UI |
| `showdownbot_studio/python/` | Stable export/adaptation into Studio schemas | Bot policy changes |
| `showdownbot_studio/schemas/` | Versioned cross-boundary contracts | Runtime implementation |
| `showdownbot_studio/godot/` | Desktop presentation and local interaction | Pokémon mechanics or policy scoring |
| `showdownbot_studio/fixtures/` | Small portable contract examples | Raw private logs or large eval corpora |
| `showdownbot_studio/tests/` | Studio contract and end-to-end gates | Replacement for bot regression suites |

## 2. Dependency direction

Allowed:

```text
showdown_bot artifacts -> Studio Python adapters -> Studio schemas -> Godot
public Showdown protocol -> approved adapter -> Studio schemas -> Godot
```

Disallowed:

```text
Godot -> import Python bot modules
Godot -> recompute policy/damage/beliefs
showdown_bot decision core -> depend on Studio UI
viewer bundle -> execute embedded code
plugin -> unrestricted Godot internals/credentials/filesystem/network
```

## 3. Phase-0 boundary

- Offline only.
- Godot receives deterministic local JSON/JSONL bundle data.
- The bundle is a canonical directory with no archive timestamps or export-time metadata.
- Python performs source validation and legacy normalization.
- Godot rejects unsupported versions and hash mismatches.
- Bundle loading and DTO construction stay off the main UI thread; scene-tree mutation stays on it.
- Existing source artifacts remain unchanged.

## 4. Later live boundary

The Live Spectator and full client must use a separate protocol adapter that emits the same style of
typed DTOs. The UI must not parse raw WebSocket text throughout arbitrary nodes.

## 5. Later add-on boundary

Add-ons use a versioned capability API. Direct scene-tree mutation, credential access, arbitrary
native library loading, and implicit network/filesystem access are outside the default trust model.

## 6. Later external-bot boundary

Bots run out of process and communicate through normalized requests, legal actions, deadlines, and
results. A bot crash or timeout must be distinguishable from a client or server error.

## 7. Change rule

Changing these boundaries requires a reviewed architecture decision under `docs/decisions/`. An
implementation plan may refine APIs inside a boundary but may not erase the boundary itself.
