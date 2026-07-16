# ShowdownBot Studio v0 — Replay + DecisionTrace Viewer

**Status:** DESIGN APPROVED — written spec pending user review; implementation planning and
implementation are **not yet** authorized
**Date:** 2026-07-16
**Product target:** desktop Godot application, typed GDScript UI, Python-generated stable viewer
bundle
**Relationship to bot roadmap:** future developer tooling; **not** the active bot front track and
not a blocker for I7b-B/I7b-C

## 0. Decision

Build a small offline desktop analysis tool named **ShowdownBot Studio**. Version 0 has one job:

> Load a reproducible battle bundle, replay the battle, and explain the bot's recorded decisions
> without recomputing them.

The v0 product is a **Replay + DecisionTrace Inspector**, not a replacement Pokémon Showdown
client. Python remains the source of truth for export, normalization, hashes, and bot-domain data.
Godot renders a stable, versioned bundle and owns only presentation and local navigation.

This design deliberately preserves future room for live spectating, team analysis, a full client,
mods, add-ons, and external bot adapters. None of those systems is implemented or publicly exposed
in v0.

## 1. Research method and limits

Research was performed on 2026-07-16 against five kinds of evidence:

1. the official July 2026 Preact-client change overview;
2. the July 7–8, 2026 public beta feedback thread;
3. the current official Smogon Pokémon Showdown Suggestions forum;
4. feedback on a recent community desktop wrapper;
5. feedback on a recent all-in-one Champions/VGC team tool.

Primary sources:

- [Official Preact-client overview](https://github.com/smogon/pokemon-showdown-client/issues/2715)
- [July 2026 Preact beta feedback](https://www.reddit.com/r/stunfisk/comments/1upuqo1/help_test_the_new_pokemon_showdown_client/)
- [Official Pokémon Showdown Suggestions forum](https://www.smogon.com/forums/forums/suggestions.517/)
- [Battleframe desktop-client discussion](https://www.reddit.com/r/stunfisk/comments/1ryflrx/i_built_a_desktop_pok%C3%A9mon_showdown_client_that/)
- [Champions/VGC all-in-one team-tool discussion](https://www.reddit.com/r/stunfisk/comments/1sfpz4e/built_an_allinone_vgc_team_builder_for_pokemon/)
- [Replay search / team visibility suggestion](https://www.smogon.com/forums/threads/is-it-possible-add-searching-and-seeing-the-used-pokemon-in-replays.3770814/)

These sources are **qualitative**, not a representative user survey. Individual bug reports do not
establish prevalence. Repeated themes across independent sources are treated as design signals,
not population estimates. The official client is also in an active rewrite; beta-specific defects
may disappear quickly. The design therefore targets durable needs rather than pixel parity with
either the legacy or Preact client.

## 2. Research findings

### 2.1 Layout, scaling, and unreachable controls

Repeated reports describe controls falling below a non-scrollable viewport at high browser zoom,
mobile sidebars consuming a large fraction of the screen, chat covering team/action controls, and
team names losing space to long format/folder labels. A community desktop wrapper reproduced the
same failure class: a zoomed battle view made the bottom action row unreachable and required a
later scale slider.

**Design consequence:** v0 must treat scale, scrollability, and dock resizing as foundational. No
critical control may depend on one window size, DPI setting, or content length.

### 2.2 Information density and visual clutter

The same layouts receive opposite feedback: integrated chat and colored panels help some users and
distract others. Some beta testers prefer the legacy teambuilder because it exposes more information
at once; others prefer the modernized presentation.

**Design consequence:** v0 provides user-controlled density instead of declaring one universal
layout. Color is secondary information, never the only information channel.

### 2.3 Unclear battle and interaction state

Current feedback calls out missing or weak distinctions between:

- waiting for the opponent;
- passive battle viewing;
- required active selection;
- team preview selection;
- an already-submitted choice;
- a recoverable client warning.

Users also notice missing turn notifications and small/moved animation controls because those cues
carry important workflow state.

**Design consequence:** ShowdownBot Studio must always state what the viewer is showing and whether
the underlying evidence is complete. Bot-specific degradation must be more prominent than ordinary
animation state.

### 2.4 Competitive tooling is fragmented

Competitive players commonly move between Showdown, damage calculators, Poképaste, usage data,
speed tiers, matchup notes, and team browsers. Recent Champions tools are explicitly motivated by
the cost of switching among these services. Users value damage benchmarks, speed tiers, type
coverage, team import/export, and archetype search in one workspace.

**Design consequence:** a later Team/Matchup Analyzer is justified, but it must consume the bot's
existing calculation and metadata contracts. v0 does not create a second calculator or teambuilder.

### 2.5 Replay discovery and analysis are shallow

Current suggestions ask for replay MMR filters, visible teams without opening every replay, better
search, last-turn navigation, and annotation. The normal client can present a replay, but it does
not explain a bot's candidate set, beliefs, fallbacks, or ranking decision.

**Design consequence:** synchronized Replay + DecisionTrace inspection is the strongest distinct
product niche. Search and annotation across public replay databases are later concerns; precise
navigation inside one frozen bundle is v0.

### 2.6 Extension demand is real, but DOM coupling is fragile

Showdex compatibility was reported partially broken during the Preact transition. The Battleframe
desktop wrapper similarly found that third-party Showdown extensions do not become plug-and-play
merely because the official client is embedded; dedicated integration was required.

**Design consequence:** never promise Chrome-extension compatibility. A future plugin model must
use a versioned ShowdownBot Studio API with explicit permissions and stable data contracts, not DOM
injection or access to internal Godot nodes.

### 2.7 Desktop expectations

Desktop-wrapper feedback asks for discoverable login, fullscreen, reliable scaling, native
notifications, controller support, and richer presentation. These are legitimate future product
signals, but only scaling, fullscreen-safe layout, keyboard navigation, and local file handling are
relevant to v0.

### 2.8 Positive signals worth preserving

The research is not uniformly negative. Users praise the Preact client's smoother mobile battles,
integrated chat, improved keyboard support, auto-reconnect, ability to inspect the team while
waiting, and bookmarkable team navigation. The official rewrite also makes future feature changes
easier.

**Design consequence:** do not rebuild the official client merely to modernize its appearance.
ShowdownBot Studio should complement Showdown with analysis and observability the official client
does not provide.

## 3. Product scope

### 3.1 Primary users

1. A bot developer diagnosing why a recorded decision was made.
2. A reviewer validating that trace, result, and provenance artifacts agree.
3. A researcher comparing candidate scores, beliefs, fallbacks, and state degradation across turns.

v0 is not designed for ordinary ladder play.

### 3.2 Primary workflow

1. Select a local viewer bundle.
2. Validate its manifest and supported schema versions.
3. Open the battle at team preview or the first recorded event.
4. Navigate by turn or decision.
5. Inspect the candidate set and selected action for the active decision.
6. Inspect scores, breakdowns, state summary, warnings, and provenance.
7. Copy stable identifiers or export a small diagnostic summary.

### 3.3 v0 capabilities

- Offline load of one viewer bundle at a time.
- Battle replay driven by a normalized Showdown protocol log.
- Turn and decision timeline.
- DecisionTrace candidate table.
- Chosen-candidate emphasis based on structural candidate identity.
- Candidate-detail view for recorded score vectors and breakdowns.
- Recorded state-summary and belief/hypothesis inspection when present.
- Provenance panel: bundle version, trace schema, format, Git SHA, config hash, and source hashes.
- Visible degradation/warning markers.
- Keyboard-first navigation and configurable UI scale/density.

## 4. Explicit non-goals

v0 does **not** include:

- Showdown login, account storage, challenges, laddering, chat, or rooms;
- a live Showdown WebSocket connection;
- a team builder, damage calculator, usage-data client, or Poképaste replacement;
- public replay search or download;
- decision recomputation, alternative-policy execution, or Python code execution inside Godot;
- a public plugin SDK, mod marketplace, or Chrome-extension bridge;
- external bot execution or Foul Play integration;
- mobile, browser, console, or controller targets;
- bundled third-party sprite packs;
- write-back into frozen evaluation artifacts;
- any strength, safety, or correctness claim about the bot.

## 5. Architecture

### 5.1 Process boundary

```text
repository artifacts
  results / normalized log / DecisionTrace / provenance / optional evidence
                  |
                  v
Python bundle exporter + validator
                  |
                  v
versioned, immutable viewer bundle
                  |
                  v
Godot desktop viewer (typed GDScript, read-only)
```

Python owns all domain-sensitive normalization and validation. Godot must not import repository
Python modules, invoke the bot, run a calculator, infer missing candidate identity, or reinterpret
an unsupported trace schema.

### 5.2 Stable viewer bundle

The implementation plan must define one deterministic bundle layout. At minimum its manifest must
contain:

```json
{
  "viewer_bundle_version": "showdownbot-viewer-v1",
  "battle_id": "gen9championsvgc2026regma-example",
  "format_id": "gen9championsvgc2026regma",
  "git_sha": "0000000000000000000000000000000000000000",
  "config_hash": "0000000000000000",
  "trace_schema_version": "decision-trace-v3",
  "source_hashes": {
    "battle_log": "0000000000000000000000000000000000000000000000000000000000000000",
    "decision_trace": "0000000000000000000000000000000000000000000000000000000000000000"
  },
  "files": {
    "battle_log": "battle.log",
    "decisions": "decisions.jsonl",
    "warnings": "warnings.json"
  }
}
```

Exact names may change in the implementation plan, but the following contracts are binding:

- paths are bundle-relative, never absolute workstation paths;
- every included data file has a content hash;
- the manifest version and trace schema are separate fields;
- JSON/JSONL only in v0; no pickle or executable payload;
- identical normalized inputs produce byte-identical bundles;
- source artifacts are never modified;
- unsupported major bundle versions fail closed;
- optional data is declared explicitly, never inferred from a missing file.

### 5.3 Identity and synchronization

Replay and trace synchronization must use recorded identity, not row position alone:

- `battle_id` must match the bundle manifest;
- `decision_index` must be unique within the battle;
- `turn_number` locates the replay time but does not uniquely identify a decision;
- candidate selection uses the validated structural `candidate_key`;
- `request_hash` and observable-state hash are displayed when present;
- duplicate or non-canonical candidate keys are bundle-validation errors;
- the viewer never guesses a chosen candidate from a display label.

Team preview, forced replacement, regular turns, and decisions without a replay event all remain
distinct timeline entries.

### 5.4 Godot component boundaries

| Component | Responsibility | Must not do |
|---|---|---|
| `BundleLoader` | Open local bundle, validate shape/version/hashes | Parse repository-specific raw artifacts |
| `BattleTimeline` | Map normalized events and decisions into ordered entries | Guess missing joins |
| `ReplayPresenter` | Render recorded field state and protocol events | Simulate battle mechanics |
| `DecisionPresenter` | Show candidates, chosen key, scores, stages, fallbacks | Re-rank candidates |
| `DiagnosticsPresenter` | Show warnings, degradation, missing evidence | Hide invalid data |
| `ProvenancePresenter` | Show hashes, versions, format, run identity | Change provenance |
| `WorkspaceLayout` | Docks, scale, density, keyboard focus | Persist battle data |

Each component communicates through typed viewer DTOs. UI nodes do not read JSON directly outside
`BundleLoader`.

## 6. UX requirements

### 6.1 Layout

The default workspace contains:

- battle/replay area;
- timeline;
- candidate table;
- candidate/state detail tabs;
- diagnostics and provenance access.

Panels are resizable and individually collapsible. A small window may stack or tab panels, but must
not make timeline or file-close controls unreachable.

### 6.2 Scale and density

- UI scale range: **75%–200%**.
- Presets: **Compact** and **Comfortable**.
- Text and controls remain readable at every supported scale.
- Long battle, format, team, move, and candidate labels truncate visually with a full-value tooltip
  or detail view; identifiers are never truncated when copied.
- All scrollable content remains scrollable after scaling.

### 6.3 Keyboard navigation

At minimum:

- previous/next timeline entry;
- previous/next decision;
- play/pause replay;
- jump to selected candidate;
- focus candidate search/filter;
- open diagnostics;
- reset layout/scale.

Bindings must be visible in the UI and remappable only if doing so is cheap in the implementation
plan. Remapping is not otherwise required for v0.

### 6.4 State banner

Exactly one prominent state banner is always visible. Supported states include:

- `TEAM PREVIEW`
- `DECISION RECORDED`
- `FORCED REPLACEMENT`
- `WAITING / NO DECISION ROW`
- `TRACE MISSING`
- `STATE DEGRADED`
- `FALLBACK USED`
- `BUNDLE INVALID`

Warnings use text and an icon in addition to color. Error red, warning amber, and selected green may
be used, but color alone is insufficient.

### 6.5 Candidate inspection

The candidate table must support deterministic sorting and filtering by available recorded fields:

- chosen/not chosen;
- action label;
- structural candidate key;
- selection stage;
- aggregate score;
- risk/accuracy/tempo fields when present;
- Mega/Tera choice;
- fallback/degradation status.

The viewer shows `not recorded` rather than inventing zero, false, or an empty list for absent
optional fields.

### 6.6 Raw evidence

Raw JSON may be available behind an explicit diagnostic tab, but it is not the primary interface.
The tab must show bundle-normalized content, not unrestricted file-system browsing.

## 7. Error and degradation behavior

| Condition | Required behavior |
|---|---|
| Unknown bundle major version | Refuse to open; show supported versions |
| Hash mismatch | Refuse trusted mode; identify the mismatching file |
| Supported bundle with optional file absent | Open degraded mode; persistent warning |
| Replay present, trace absent | Replay-only degraded mode; no candidate panel claims |
| Trace present, replay absent | Trace-only degraded mode; no simulated field state |
| Duplicate decision index | Refuse decision synchronization |
| Unknown trace schema | Refuse trace inspection; allow replay only when independently valid |
| Chosen key absent from candidates | Mark decision invalid; never choose by label |
| Unsupported candidate field | Preserve for raw display if bundle-compatible; do not reinterpret |
| Malformed protocol event | Mark exact timeline location and continue only if exporter classifies it recoverable |

The Python exporter decides whether malformed source material is recoverable. Godot follows the
bundle's explicit classification and does not invent recovery logic.

## 8. Reproducibility and privacy

- Viewer bundles are read-only evidence artifacts.
- Export must remove absolute local paths unless explicitly whitelisted as portable metadata.
- Raw room logs are excluded by default; normalized logs and hashes are preferred.
- A diagnostic summary copied from the viewer contains stable identifiers and warnings, not local
  paths or credentials.
- Network access is disabled/not used by v0.
- The viewer displays dirty-worktree provenance when present and never hides it.
- Bundle generation records exporter version and source hashes.

## 9. Acceptance criteria

### 9.1 Bundle/export acceptance

- A frozen committed battle can be exported twice to byte-identical bundles.
- A one-byte data mutation produces a hash failure.
- Absolute source paths do not appear in the bundle.
- Current committed DecisionTrace v3 candidate keys validate and resolve exactly.
- A supported older trace fixture either migrates deterministically in Python or is rejected with a
  precise explanation; Godot contains no legacy migration logic.

### 9.2 Viewer acceptance

- The same decision is reached through turn navigation and decision navigation.
- The chosen structural key highlights exactly one candidate.
- Team preview, regular turns, and forced replacement are visually distinct.
- A state-degraded trace row is visible without opening raw JSON.
- Missing optional data shows `not recorded`.
- Invalid bundle/hash/schema cases follow §7.
- All primary controls remain reachable at 75%, 100%, 150%, and 200% scale in the minimum supported
  desktop window.
- Compact and Comfortable layouts preserve the same information and selection.
- Keyboard-only inspection of a bundle is possible.

### 9.3 Performance acceptance

The implementation plan must pin measurable desktop targets after a representative committed
fixture is selected. At minimum:

- opening the reference bundle must not block the UI indefinitely;
- timeline navigation must feel immediate after load;
- large candidate tables must use bounded rendering or virtualization if the reference fixture
  demonstrates a need.

No arbitrary performance number is approved here without a measured fixture baseline.

## 10. Future architecture hooks — not v0 features

### 10.1 Live Spectator

Later, a separate adapter may convert live protocol and bot telemetry into the same viewer DTOs.
The viewer itself must not depend on WebSocket semantics in v0.

### 10.2 Team/Matchup Analyzer

Later panels may expose threat assessment, speed tiers, Protect priors, damage ranges, and role
classification. They must reuse Python-produced domain results rather than port bot mechanics to
GDScript.

### 10.3 Full Showdown client

A future client may add login, rooms, challenges, battles, chat, and notifications. That requires a
separate protocol/security/licensing design and must not be inferred from this viewer spec.

### 10.4 Mods and add-ons

Future add-ons should be manifest-based, versioned, permission-scoped, and isolated from core Godot
nodes. Likely extension points are panels, data annotations, themes, sprite packs, exporters, and
commands. v0 exposes no third-party SDK.

### 10.5 External bot adapters

Future bots such as Foul Play or user-supplied agents should run out of process behind a versioned
request/response protocol with timeouts, capability declarations, and clear trust boundaries. They
must never be loaded as arbitrary in-process GDScript or native libraries by default.

## 11. Implementation sequencing gate

After the user approves this written spec, it authorizes implementation planning only. The plan
must split work at least into:

1. bundle contract and deterministic Python exporter;
2. exporter fixtures and validation tests;
3. Godot project shell and typed DTO loader;
4. replay/timeline presentation;
5. DecisionTrace candidate inspection;
6. diagnostics, accessibility, scale, and layout gates;
7. frozen end-to-end viewer bundle acceptance.

No live-client, plugin, team-analysis, or external-bot task may be added to that plan without a
separate design approval.

## 12. Research-to-requirement traceability

| Research signal | v0 requirement |
|---|---|
| Controls lost below fold / zoom failures | §6.1–6.2 scale, resize, scroll, reachability gates |
| Chat/sidebar competes with primary controls | Collapsible docks; no mandatory secondary panel |
| Dense vs. colorful preference split | Compact/Comfortable; color is secondary |
| Waiting/selection state unclear | §6.4 persistent state banner |
| Missing notification/turn clarity | Timeline state and warning markers |
| Long format/team names truncate badly | Full-value tooltip/detail and stable copy |
| Replay search/last-turn/annotation demand | v0 precise in-bundle navigation; broader search deferred |
| Tool fragmentation | Future analyzer hook; no duplicate calculator in v0 |
| Showdex breaks across client rewrites | Versioned future API; no DOM/extension compatibility claim |
| Desktop scale/login/fullscreen feedback | Scale/layout in v0; login deferred to full-client design |
| Preact improvements praised | Complement official client; do not clone/rewrite it |
