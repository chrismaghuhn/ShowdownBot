# ShowdownBot Studio — Desktop Client Master Spec

**Status:** PRODUCT DESIGN APPROVED — written master spec pending user review; no implementation
authorized
**Date:** 2026-07-16
**Platform:** desktop first and desktop only under this master spec
**UI technology:** Godot 4.5.2 with typed GDScript; see
[`decisions/ADR-001-godot-ui-technology.md`](decisions/ADR-001-godot-ui-technology.md)
**Domain technology:** Python remains authoritative for bot logic, export, normalization, and
analysis

## 0. North star

ShowdownBot Studio is a modular desktop workspace for understanding, observing, preparing for, and
eventually participating in Pokémon Showdown battles.

It is not one large implementation slice. It is a product family delivered through separately
approved phases:

1. offline Replay + DecisionTrace Viewer;
2. read-only Live Spectator;
3. Team/Matchup Analyzer;
4. full Showdown protocol client;
5. controlled mods and add-ons;
6. external bot adapters.

Each phase requires its own design, implementation plan, tests, and release gate. Later phases may
reuse earlier contracts but may not silently expand an earlier slice.

## 1. Why a separate top-level project

The viewer begins as developer tooling but the long-term product is larger than a repository tool.
Placing it under `tools/` would encode the wrong permanent boundary. A separate Git repository,
however, would make trace/schema changes harder to coordinate while the contracts are still moving.

`showdownbot_studio/` therefore remains inside the current monorepo while owning its own:

- documentation and decisions;
- Godot application;
- Python adapters/exporters;
- schemas and fixtures;
- tests and release gates.

The bot and Studio remain separate runtime products.

## 2. Product principles

### 2.1 Explain before automating

The first product value is observability: show what happened, what the bot knew, which candidates it
considered, and why the selected action won. Live control comes later.

### 2.2 Stable contracts, replaceable presentation

Godot consumes versioned DTOs and bundles. It does not import Python modules or reproduce battle
mechanics. The UI may be replaced without changing the recorded evidence contract.

### 2.3 Public protocol, private trust boundary

Showdown's public protocol and public data may be used as interoperability inputs. Code or assets
from external projects require a license and provenance review before reuse. Browser DOM structure
is not a supported integration contract.

### 2.4 Accessibility and user-controlled density

Scaling, keyboard access, resizable panels, high-contrast semantics, and compact/comfortable
layouts are cross-cutting requirements, not polish tasks.

For Phase 0, keyboard operation, 75%–200% scaling, contrast, focus visibility, and text/icon
alternatives to color are binding. Godot's screen-reader integration is experimental in the pinned
engine line, so screen-reader support is best effort in Phase 0 and must be reported honestly. It
may become a release gate only after a dedicated accessibility audit.

### 2.5 Fail closed on evidence, fail safely on extensions

Unknown schemas, hash mismatches, ambiguous identities, or missing required provenance never become
silent guesses. Future extensions and bots run with explicit capabilities, timeouts, and isolation.

### 2.6 Reproducibility over visual spectacle

Animations and presentation may improve later, but no UI effect may change recorded evidence or
hide dirty, missing, degraded, or incompatible data.

## 3. System architecture

```text
ShowdownBot / eval artifacts / public Showdown protocol
                         |
                         v
            Python adapters and exporters
                         |
                         v
          versioned schemas and viewer DTOs
                         |
                         v
              Godot desktop workspace
                         |
            future capability boundaries
             /             |            \
       add-on host     live client    bot adapters
```

### 3.1 Godot desktop application

Godot owns:

- windows, docks, navigation, theming, input, and presentation;
- local workspace preferences;
- rendering already-normalized battle and analysis DTOs;
- invoking explicitly configured local adapters through versioned boundaries in later phases.

Godot does not own:

- bot evaluation, damage calculation, beliefs, policy ranking, or trace reconciliation;
- Python package loading inside the Godot process;
- Showdown mechanics simulation;
- arbitrary third-party native code execution.

Phase 0 pins Godot 4.5.2 rather than an open-ended `>= 4.5` range. Engine upgrades require the
viewer acceptance suite, DPI checks, accessibility checks, and the architecture decision to be
reviewed again.

### 3.2 Python services and adapters

Python owns:

- deterministic viewer-bundle creation;
- current-to-stable schema normalization;
- artifact and provenance validation;
- later read-only telemetry bridges;
- later team/matchup analyses produced by existing bot-domain code;
- later external-bot process supervision when separately approved.

Every boundary exposed to Godot must be versioned under `schemas/`.

### 3.3 Schemas

Schema families are separate and versioned independently:

- viewer bundle;
- normalized battle/replay events;
- decision and candidate presentation;
- live spectator updates;
- usage and meta-prior snapshots;
- team import and validation;
- team-analysis results;
- client commands and acknowledgements;
- add-on capabilities;
- external bot requests and responses.

A version bump in one family must not force unrelated families to change.

Every schema family uses explicit `major` and `minor` integers. A major change is incompatible and
fails closed. A minor change may only add optional fields or capabilities. Readers may accept a
higher minor of a supported major only when all declared `required_capabilities` are known and all
required fields validate; unknown required capabilities fail closed.

### 3.4 Storage

v0 uses local files only. Later workspace storage may contain preferences, layouts, imported teams,
and explicitly saved sessions. Credentials, if a full client is approved, require a separate secure
storage design and may not be stored in ordinary project JSON.

## 4. Phased product scope

### Phase 0 — Replay + DecisionTrace Viewer

**Goal:** load a frozen local bundle, replay the battle, and inspect recorded bot decisions.

Canonical slice spec: [`specs/viewer-v0-design.md`](specs/viewer-v0-design.md).

Included:

- deterministic Python viewer bundle;
- offline Godot replay and timeline with an abstract, sprite-independent battle board;
- candidate, score, state, warning, and provenance inspection;
- direct launch at a stable `battle_id:decision_index`;
- exporter-prepared decision interestingness values for navigation;
- scalable/resizable desktop workspace;
- fail-closed schema and hash validation.

Excluded: network, login, ladder, chat, team building, public plugins, external bots.

Explicit post-v0 replay candidates are a score-over-time overview derived only from recorded
scores, local session restore, portable annotation sidecars, and a local replay library with
cross-replay statistics. None is required for Phase 0, and none may introduce mechanics
recomputation into the viewer.

### Phase 1 — Live Spectator

**Goal:** observe a running bot battle through the same presentation DTOs without controlling it.

Candidate capabilities:

- live battle state and timeline;
- live DecisionTrace/telemetry updates;
- connection/reconnection status;
- recording into a later-replayable bundle;
- explicit delayed/missing/degraded telemetry states.

Hard boundaries:

- read-only;
- no `/choose` emission;
- no account credential handling;
- no inference from unrecorded opponent truth.

### Phase 2 — Team/Matchup Analyzer

**Goal:** prepare teams and inspect matchup information using existing Python-domain calculations.

Candidate capabilities:

- team import/export;
- threat and role assessment;
- speed tiers and field-condition comparisons;
- damage ranges and survival checks;
- Protect, move, item, and set priors;
- archetype annotations and matchup notes.
- provenance-visible data-freshness badges;
- versioned team benchmark/regression assertions evaluated by the existing calc path.

Hard boundaries:

- Python produces all calculations;
- format-aware validation is mandatory;
- team import reuses the repository's existing Showdown export/packed-team adapters and the
  pinned official Showdown validator path; Godot does not implement a second team parser or
  legality engine;
- usage/meta-prior snapshots record their source, source snapshot date or month, `format_id`,
  rating cutoff, content hash, and license/terms-review status;
- imported usage data is normalized into a versioned snapshot before either the bot or Studio may
  consume it;
- no independent GDScript calculator;
- no second damage-calculation stack; analysis reuses the existing pinned Python/Node calc adapter;
- no claim that priors equal hidden truth;
- no runtime dependency on Pikalytics, Poképaste scraping, or an unreviewed tournament-site
  scraper;
- no online team marketplace in this phase.

Shared Phase-2 domain modules are Python-owned and may serve both products. The first candidates
are a provenance-complete usage-statistics snapshot adapter and a stable team-import/validation
adapter. This ordering is planning input only: neither module is authorized by this master spec,
and neither expands Phase 0.

Replay takeover, interactive what-if simulation, mistake-training puzzles, and a scenario sandbox
are not implied by Phase 2. They require a separately approved simulation design proving exact
format support, state reconstruction, hidden-information rules, RNG handling, and reproducibility.
Selecting a simulator package alone does not authorize or unlock those features.

Two takeover classes must remain distinct. **Exact takeover** is eligible only for battles captured
under Studio control with a pinned simulator build, complete teams, original seed, ordered input
log or verified simulator checkpoint, and a conformance replay against the original output.
**Approximate takeover** from a public replay may use explicit hidden-state hypotheses and a new
future RNG stream, but must be labeled counterfactual and may never be presented as the original
battle continuing exactly.

### Phase 3 — Full Showdown protocol client

**Goal:** provide a native desktop client capable of ordinary Showdown account and battle workflows.

Candidate capabilities:

- server connection and authentication;
- rooms, private messages, challenges, and notifications;
- team selection and format-aware challenges;
- battle requests and legal `/choose` encoding;
- reconnect and resynchronization;
- spectating and replay save/export.

Required separate gates:

- protocol compatibility against a pinned and live Showdown client/server;
- credential and session-token security;
- rate-limit and reconnect behavior;
- format/command compatibility;
- licensing review for reused code and assets;
- clear separation between human client actions and bot automation.

The full client may embed Studio analysis panels, but analysis must never silently submit a choice.

### Phase 4 — Mods and add-ons

**Goal:** allow controlled extension without depending on browser DOM injection.

Candidate extension types:

- panels and annotations;
- themes and approved sprite packs;
- import/export adapters;
- commands and keyboard workflows;
- local data providers;
- analysis overlays.

Required properties:

- manifest with ID, version, API range, author, and permissions;
- capability-based access;
- disable/uninstall/recovery path;
- deterministic load order;
- no default access to credentials or unrestricted filesystem/network;
- crash isolation where technically possible;
- compatibility diagnostics after API upgrades.

There is no marketplace commitment. Local installation is the first conceivable delivery model.

### Phase 5 — External bot adapters

**Goal:** allow separately installed bots, including Foul Play-like agents, to participate through a
documented process boundary.

Candidate contract:

- normalized observation/request;
- legal-action set;
- selected action plus optional explanation/telemetry;
- declared formats and capabilities;
- deadline, cancellation, and timeout behavior;
- deterministic seed/provenance fields when supported;
- health and version negotiation.

Required isolation:

- out of process by default;
- no arbitrary bot code loaded into Godot;
- explicit user selection of the active bot;
- safe fallback on timeout/crash;
- no hidden access to opponent team files or private bot state;
- automation and ladder use must respect Showdown rules and receive a separate policy review.

## 5. Cross-phase UX requirements

All implemented phases must preserve:

- desktop UI scaling from at least 75% to 200%;
- reachable primary controls at the minimum supported window size;
- resizable/collapsible panels;
- Compact and Comfortable density modes;
- keyboard-first primary workflows;
- text/icon semantics in addition to color;
- visible connection, selection, waiting, degraded, and error states;
- full-value inspection for truncated names and identifiers;
- layouts that survive long format, folder, team, and candidate names;
- a reset-to-safe-layout action.

Phase 0 uses an abstract board made from text, HP bars, status chips, field conditions, and
project-owned semantic icons. Pokémon artwork and third-party sprite packs are optional future
presentation layers, never a dependency for battle comprehension.

## 6. Cross-phase observability and provenance

Studio must make the following visible when available:

- source and bundle schema versions;
- battle, decision, candidate, request, and config identity;
- Git SHA, dirty status, format ID, and content hashes;
- missing or degraded evidence;
- active adapter/add-on/bot versions;
- timeouts, fallbacks, reconnects, and rejected commands.

The client must never turn a viewer, parser, pipeline, or safety smoke into a bot-strength claim.

Displayed aggregate candidate scores must always be accompanied by their recorded aggregation
mode. `risk_lambda` and `must_react_lambda` are displayed when recorded. If the source cannot
provide the mode, the exporter emits `null` plus a degradation warning; Studio must not infer it
from `config_hash`.

## 7. Security and trust boundaries

### 7.1 Local files

- Treat imported bundles, teams, replays, themes, and add-ons as untrusted input.
- Reject path traversal and absolute bundle paths.
- Never execute code embedded in a viewer bundle.
- Keep raw logs and credentials out of diagnostic exports by default.

### 7.2 Network

- v0 has no network access.
- Live and full-client phases require explicit host allowlists and connection-state UI.
- Plugins do not inherit network access automatically.

### 7.3 Credentials

- Credential handling begins only with the full-client phase.
- Credentials never enter viewer bundles, trace files, add-on manifests, or bot requests.
- Storage and redaction require their own reviewed design.

### 7.4 Extensions and bots

- Permissions are denied unless declared and approved.
- Version incompatibility fails closed with a diagnostic.
- A failed extension cannot make a battle command appear successfully submitted.
- External bots receive only the contractually allowed observation.

## 8. Licensing and public-source policy

- Public availability does not imply unrestricted reuse.
- The official Showdown client, server, extensions, data packages, sprites, and community tools are
  reviewed separately by artifact and license.
- Protocol behavior may be independently implemented from documented/public behavior.
- Any copied or modified source retains required notices and compatible licensing.
- Asset packs require explicit provenance; Studio does not redistribute arbitrary community assets.
- A future public release needs a release-level license inventory.
- `@pkmn/protocol` and related `pkmn/ps` packages are approved as reference and differential-test
  inputs only; runtime reuse still requires a separate dependency and license decision.

This section is an engineering gate, not legal advice.

## 9. Explicit exclusions

### 9.1 Excluded from the entire current master program

- operating a replacement public Showdown server;
- reimplementing the Showdown battle simulator in Godot;
- moving the ShowdownBot decision core from Python to GDScript;
- mobile, browser, console, or VR builds;
- cloud accounts, cloud synchronization, subscriptions, or payments;
- a public add-on marketplace;
- shipping copyrighted or unverified third-party asset collections;
- loading arbitrary native libraries or Python modules directly into Godot;
- presenting analysis output as guaranteed hidden opponent truth;
- using client work as evidence of bot strength.

These exclusions may change only through a new master-spec revision, not an implementation plan.

### 9.2 Planned eventually, but excluded from early phases

- live connection: excluded from Phase 0;
- battle control, login, chat, rooms, and ladder: excluded from Phases 0–2;
- public add-on API: excluded from Phases 0–3;
- external bots: excluded from Phases 0–4;
- controller/handheld support, animated asset expansion, localization, and public replay discovery:
  unscheduled research items, not commitments.

## 10. Relationship to the current bot repository

- [`../../docs/ROADMAP.md`](../../docs/ROADMAP.md) remains authoritative for bot work.
- Studio does not become the active bot front track merely because this master spec exists.
- Bot trace or schema changes must remain independently useful and tested without Godot.
- Studio adapters consume stable contracts; they do not justify leaking UI concerns into decision
  code.
- Frozen eval artifacts remain under the existing repository conventions unless a future approved
  plan introduces a Studio fixture copy with explicit hashes.

## 11. Release and planning gates

For every phase:

1. approved phase design;
2. reviewed implementation plan;
3. isolated branch/worktree;
4. contract and counterexample tests;
5. accessibility/layout checks proportional to UI scope;
6. deterministic/provenance checks proportional to data scope;
7. security/license review proportional to network, extension, or asset scope;
8. explicit user review before merge and before enabling the next phase.

Phase 0 additionally requires bounded rendering for every unbounded collection, background bundle
loading with visible progress and cancellation, a mixed-DPI desktop check, and headless Godot tests
in CI. The selected Godot test framework is gdUnit4; the implementation plan must pin a version
verified against Godot 4.5.2 and emit JUnit-compatible results.

Only Phase 0 is eligible for implementation planning after the written specs are approved. Phases
1–5 remain product roadmap entries, not authorized implementation work.
