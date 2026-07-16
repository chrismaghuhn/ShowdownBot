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
approved external data snapshot -> Python domain adapter -> Studio schemas -> Godot
```

Disallowed:

```text
Godot -> import Python bot modules
Godot -> recompute policy/damage/beliefs
showdown_bot decision core -> depend on Studio UI
viewer bundle -> execute embedded code
plugin -> unrestricted Godot internals/credentials/filesystem/network
Godot -> scrape usage, paste, or tournament sites
Godot -> implement a second team validator or damage calculator
```

Shared domain modules may serve both the bot and Studio, but remain Python-owned and expose
versioned schemas. Existing bot capabilities are reused behind adapters: packed-team loading,
official Showdown team validation/packing, and the pinned calc bridge are not reimplemented in
GDScript. External usage or tournament data must first become a provenance-complete frozen
snapshot; live scraping is not a cross-boundary contract.

Approval is artifact-specific. A software repository's license does not automatically approve its
externally sourced data, artwork, audio, analyses, or hosted API responses. Until redistribution
rights are approved, external statistics and tournament data stay user-local: Studio may ship a
reviewed importer, but not the downloaded snapshot.

## 3. Phase-0 boundary

- Offline only.
- Godot receives deterministic local JSON/JSONL bundle data.
- The bundle is a canonical directory with no archive timestamps or export-time metadata.
- Python performs source validation and legacy normalization.
- Godot rejects unsupported versions and hash mismatches.
- Bundle loading and DTO construction stay off the main UI thread; scene-tree mutation stays on it.
- Existing source artifacts remain unchanged.
- Untouched replay/log sources remain outside portable bundles. Python emits a separate normalized
  bundle that excludes chat/PM, source URLs, raw HTML, cleartext player identities, and reversible
  identity maps under `portable-pseudonymous-v1`.

## 4. Later live boundary

The Live Spectator and full client must use a separate protocol adapter that emits the same style of
typed DTOs. The UI must not parse raw WebSocket text throughout arbitrary nodes.

Remote visual assets are not implied by the live boundary. A later approved sprite provider must be
optional, host-allowlisted, bounded and clearable in its cache, non-prefetching, and unable to place
asset bytes into bundles or exports. Failure always degrades to the abstract board. Direct hotlinking
and a Studio-operated mirror remain unapproved until a separate legal and upstream-service review.

## 5. Later add-on boundary

Add-ons use a versioned capability API. Direct scene-tree mutation, credential access, arbitrary
native library loading, and implicit network/filesystem access are outside the default trust model.

## 6. Later external-bot boundary

Bots run out of process and communicate through normalized requests, legal actions, deadlines, and
results. A bot crash or timeout must be distinguishable from a client or server error.

## 7. Later simulation boundary

A replay protocol log is structured evidence, not a guaranteed resumable simulator snapshot. Any
future replay takeover, what-if analysis, mistake-training mode, or scenario sandbox requires a
separate architecture decision and format-specific parity audit. The design must account for
hidden information, RNG state, omitted simulator internals, and exact reconstruction semantics.

For Studio-controlled captures, exact replay or takeover may record the original seed, complete
teams, ordered simulator input log, and/or a verified simulator checkpoint at capture time. Exact
support still requires a conformance harness that resumes at turn N and reproduces the remaining
protocol output. Public replays without those inputs remain analysis-only or explicitly
counterfactual.

The repository's pinned and patched `smogon/pokemon-showdown` checkout is the first simulation
distribution to audit for Champions because current eval runs already exercise that format there.
`@pkmn/sim` remains a secondary research candidate; its packaged formats and mods must not be
assumed to cover Champions or other custom Showdown formats. Neither is an approved Studio runtime
dependency. Simulation runs out of process behind a versioned adapter; Godot never owns simulator
state or mechanics.

## 8. Change rule

Changing these boundaries requires a reviewed architecture decision under `docs/decisions/`. An
implementation plan may refine APIs inside a boundary but may not erase the boundary itself.
