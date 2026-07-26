# Pokémon Showdown Client User Research — July 2026

**Status:** qualitative research snapshot; §8 adds a second round
**Date:** 2026-07-16 (round 1) / 2026-07-25 (round 2, §8)
**Purpose:** inform ShowdownBot Studio product requirements; not a representative user survey

## 1. Sources and method

This snapshot compares current official development, public beta feedback, official suggestions,
and feedback on recent community tools.

Sources:

- [Official Preact-client overview](https://github.com/smogon/pokemon-showdown-client/issues/2715)
- [July 2026 Preact beta feedback](https://www.reddit.com/r/stunfisk/comments/1upuqo1/help_test_the_new_pokemon_showdown_client/)
- [Official Pokémon Showdown Suggestions forum](https://www.smogon.com/forums/forums/suggestions.517/)
- [Battleframe desktop-client discussion](https://www.reddit.com/r/stunfisk/comments/1ryflrx/i_built_a_desktop_pok%C3%A9mon_showdown_client_that/)
- [Champions/VGC all-in-one team-tool discussion](https://www.reddit.com/r/stunfisk/comments/1sfpz4e/built_an_allinone_vgc_team_builder_for_pokemon/)
- [Replay search / team visibility suggestion](https://www.smogon.com/forums/threads/is-it-possible-add-searching-and-seeing-the-used-pokemon-in-replays.3770814/)

Limits:

- Comments are self-selected qualitative reports.
- A repeated complaint is a useful design signal, not a measured prevalence rate.
- Some reports concern the legacy client, others the July 2026 Preact beta, and others third-party
  wrappers. They are classified by durable failure type rather than treated as one identical build.
- The Preact beta is changing quickly; pixel-level bugs may be fixed before Studio development.

## 2. Findings

| Finding | Evidence signal | Durable implication | Studio phase |
|---|---|---|---|
| Controls become unreachable under zoom/small windows | Beta and Battleframe reports | Scale, scroll, and minimum-window gates | Phase 0 |
| Sidebar/chat competes with battle controls | Beta mobile reports | Resizable/collapsible docks | Phase 0+ |
| Information density preferences differ | Old vs. new teambuilder and color feedback | Compact/Comfortable modes | Phase 0+ |
| Waiting vs. required selection is unclear | Beta battle feedback | Persistent explicit state banner | Phase 0+ |
| Team/format/folder names lose space | Beta team-list feedback | Full-value details and resizable lists | Phase 0+ |
| Turn/notification cues matter | Favicon and skip-control feedback | Visible timeline and native notifications later | Phase 0 / Phase 3 |
| Teambuilding requires many external tools | Champions all-in-one tool motivation | Integrated analyzer using shared Python domain logic | Phase 2 |
| Replay discovery and inspection are shallow | MMR/team/search/last-turn suggestions | Strong in-bundle navigation first; search later | Phase 0 / future |
| Browser extensions break across client rewrites | Showdex beta warning and wrapper integration | Stable versioned add-on API, not DOM injection | Phase 4 |
| Desktop users expect native discovery and control | Login/fullscreen/scale/controller feedback | Desktop workspace conventions | Phase 0+ |
| Accessibility/clutter is an active concern | Official suggestions and zoom reports | Text/icon semantics, keyboard access, density control | Phase 0+ |
| Format-aware Champions data is incomplete or confusing | Dex/teambuilder suggestions and third-party tools | Format-aware Python adapter and validation | Phase 2/3 |

## 3. Detailed pain points

### 3.1 Scaling and layout

Reported symptoms include:

- bottom battle controls below a non-scrollable fold at 150–175% zoom;
- mobile sidebar occupying roughly a third of the display;
- integrated chat covering team or action areas;
- highly zoomed teambuilder views that show less information than the legacy client;
- long format/folder names consuming most of a team-list row;
- touch controls and EV sliders moving the page unexpectedly;
- desktop-wrapper battle views hiding the bottom action row.

The recurring failure is not one CSS bug. It is insufficient layout resilience across scale, DPI,
window size, content length, and panel combinations.

### 3.2 State clarity

Reported ambiguity includes:

- no clear waiting-for-opponent indication;
- passive view and active selection looking too similar;
- selected team-preview controls appearing disabled;
- weak feedback after submitting a choice;
- missing opponent-moved notification;
- insufficient hints for abrupt multi-turn state changes.

For Studio, the equivalent high-risk ambiguity is showing a normal-looking decision when trace data
is missing, degraded, ambiguous, or produced by a fallback.

### 3.3 Density and customization

Users disagree about integrated chat and colorful type backgrounds. This is evidence against one
fixed density/style rather than evidence that either preference is wrong. Requested responses
include old-interface options, wider/resizable lists, collapsible format groups, and customizable
colorful/default views.

### 3.4 Competitive-tool fragmentation

The Champions/VGC tool discussion explicitly cites switching among Showdown, damage calculators,
Poképaste, and usage/statistics tools. Desired combined functions include:

- offensive and defensive damage benchmarks;
- speed tiers and Trick Room/Tailwind conditions;
- type coverage;
- team import/export;
- meta threat lists;
- team/archetype browsing;
- move, ability, and playstyle filters.

These signals support a later Team/Matchup Analyzer. They do not justify adding a teambuilder or
calculator to the viewer slice.

### 3.5 Replays

Current suggestions seek:

- MMR filtering;
- seeing teams or Pokémon before opening each replay;
- searching replays by Pokémon;
- previous/last-turn instant navigation;
- annotations.

Studio's unique opportunity is deeper: connect replay events to DecisionTrace candidates, beliefs,
scores, chosen structural identity, fallbacks, and provenance.

### 3.6 Extension compatibility

The Preact beta feedback explicitly warns that Showdex is partly broken. Battleframe reports that
wrapping the official client does not provide plug-and-play compatibility with existing extensions;
dedicated integration is necessary. This makes DOM compatibility an unstable foundation for a new
client.

### 3.7 Desktop expectations

Community desktop feedback asks for:

- discoverable login and navigation;
- fullscreen;
- scale controls;
- animated presentation;
- controller and handheld support;
- integration of popular extensions.

Only fullscreen-safe layout, scale, keyboard input, and local file handling belong in Studio Phase
0. The remainder stays phased or unscheduled.

## 4. Positive feedback and features not to regress conceptually

The current beta also receives strong praise for:

- smoother mobile battle interaction;
- integrated battle/chat access;
- improved horizontal/mobile layouts;
- auto-reconnect;
- viewing the team while waiting;
- mobile teambuilder parity;
- better format/team selectors;
- keyboard navigation;
- bookmarkable team URLs;
- a modernized architecture that is easier to extend.

Studio should complement these improvements, not clone the official client for appearance alone.

## 5. Granular observation ledger

This ledger preserves individual observations even when they are too isolated, transient, or
phase-specific to become requirements today.

### 5.1 July 2026 Preact beta reports

| Observation | Classification |
|---|---|
| Mobile battle UI described as smoother and less clunky | Positive signal |
| Integrated chat praised by some users | Positive/preference split |
| Integrated chat blocks or competes with team/action controls for others | Layout defect/preference split |
| Legacy zoomed-out teambuilder shows more information at once | Density preference |
| Controls disappear below fold at high browser zoom; page may not scroll | Accessibility/layout defect |
| Sidebar cannot always be hidden at particular iOS Safari zoom/layout combinations | Browser/layout defect |
| Chrome/Safari mobile layouts behave differently | Browser-compatibility risk |
| Team list leaves too little room for names after long format/folder labels | Information-layout defect |
| Wider or user-resizable team list requested | Customization request |
| Format selector no longer collapses unused sections | Navigation regression report |
| No clear waiting-for-opponent indicator | State-clarity defect |
| Passive viewing and active selection are hard to distinguish | State-clarity defect |
| Team-preview selection can look disabled or be hard to undo | Interaction-clarity defect |
| Skip-animation control is smaller/moved and conflicts with muscle memory | Interaction regression report |
| Missing favicon red-dot notification when opponent acts | Notification regression report |
| Hover information reported absent in at least one random-battle context | Format-specific beta bug report |
| Touch EV sliders can move the page unexpectedly | Touch-input defect |
| Long-lived users request an old-interface option | Transition/customization request |
| Colorful Pokémon backgrounds praised by some and seen as clutter by others | Visual-preference split |
| Default versus colorful setting suggested | Customization request |
| Poképaste export removal questioned while hosted team storage remains limited | Workflow/data-portability concern |
| Top-of-page mobile advertisement placement disliked | Hosting/UI complaint; outside Studio v0 |
| Login failure reported with iCloud Private Relay | Authentication/network compatibility report |
| Japanese-language support requested | Localization request; unscheduled |
| Showdex reported partially broken against the beta | Extension-compatibility risk |
| Bookmarkable per-team URLs and browser back/forward navigation praised | Positive navigation signal |
| Viewing team while waiting praised | Positive information-access signal |
| Reduced text-field auto-zoom praised | Positive mobile-accessibility signal |

### 5.2 Official Suggestions forum observations

| Observation | Classification |
|---|---|
| Improve clarity and remove clutter for impaired users | Accessibility request |
| Hide verbose custom-challenge clauses/bans/unbans | Progressive-disclosure request |
| Add generation- and Champions-specific Dex tabs | Format-awareness request |
| Add MMR filter to replay search | Replay discovery request |
| Display bench Pokémon HP | Battle-state visibility request |
| Clone IVs and moves when checking Mega in teambuilder | Champions/Mega workflow request |
| Hint when multi-turn locking moves end abruptly | Battle-state explanation request |
| Search weakness-reducing berries by type | Teambuilder search request |
| Expose raw minor room activity | Diagnostics/transparency request |
| Filter move list by ability | Teambuilder search request |
| Prevent mobile screen sleep while watching replays | Replay/mobile request; outside desktop v0 |

### 5.3 Desktop-wrapper observations

| Observation | Classification |
|---|---|
| Native game-like presentation attracts interest | Desktop product signal |
| Existing Showdex cannot be loaded without dedicated integration | Plugin architecture signal |
| Battle view can become too zoomed to reach actions | Scale/layout defect |
| A battle-scale slider was added as a mitigation | Design response worth retaining |
| Login route was hard to discover | Navigation/discoverability defect |
| Fullscreen was expected | Desktop convention |
| Additional animated sprites requested | Presentation request; unscheduled |
| Controller and Linux/Android-handheld support requested | Input/platform request; unscheduled |

### 5.4 Champions/VGC tool observations

| Observation | Classification |
|---|---|
| Users want Showdown, calc, Poképaste, meta data, and teams in one place | Tool-fragmentation signal |
| Damage benchmarks, type coverage, and speed tiers are highly valued | Analyzer product signal |
| Ability, move, and playstyle filters requested | Role/search product signal |
| Trick Room, Tailwind, and normal speed comparison must be easy to discover | Analyzer UX signal |
| Champions stat-point versus EV conversion confused tools/users | Format-fidelity risk |
| Outdated learnsets/moves caused immediate trust problems | Data-provenance risk |
| Community team browsing by Pokémon/archetype is valued | Future discovery signal |

## 6. Product conclusions

1. Replay + DecisionTrace is the strongest differentiated Phase-0 value.
2. Scaling and information-state clarity are acceptance gates, not polish.
3. User-controlled density is safer than a single fixed layout.
4. Team analysis is valuable but belongs in a later phase sharing Python-domain outputs.
5. A future extension system must use stable capabilities, not Chrome DOM compatibility.
6. Desktop demand exists, but a native shell does not automatically fix usability.
7. The official client is a moving target; Studio should rely on protocol/data contracts, not UI
   structure.

## 7. Engineering feasibility and prior-art review

A follow-up review on 2026-07-16 checked the proposed Phase-0 architecture against Godot's current
desktop capabilities and analysis-tool patterns.

### 7.1 Verified Godot constraints

- Godot 4.5 introduced AccessKit-based screen-reader support and describes the integration as
  experimental. Phase 0 therefore treats keyboard access, focus, scaling, contrast, and redundant
  text/icon semantics as release gates while reporting screen-reader behavior as best effort.
- Godot's customizable long-list story does not provide a general built-in recycling control. An
  open virtual-scrolling proposal and the documented `Tree` performance failure class justify
  bounded rendering as a design requirement rather than a fixture-dependent optimization.
- Godot supports background work, but the active scene tree is not thread-safe. Bundle reading,
  hashing, parsing, and immutable DTO construction may run in a worker; node updates return to the
  main thread.
- Desktop DPI behavior varies by platform. Studio needs a user scale override and a manual test that
  moves the window between monitors with different scale factors.
- gdUnit4 provides Godot-4-native command-line execution and JUnit output. It is selected for
  Phase-0 UI tests, with an exact compatible version pinned in the implementation plan.

Sources:

- [Godot 4.5 release notes](https://godotengine.org/releases/4.5/)
- [Godot thread-safe APIs](https://docs.godotengine.org/en/4.5/tutorials/performance/thread_safe_apis.html)
- [Godot multiple resolutions](https://docs.godotengine.org/en/4.5/tutorials/rendering/multiple_resolutions.html)
- [Tree performance issue #70869](https://github.com/godotengine/godot/issues/70869)
- [Virtual-scrolling proposal #9678](https://github.com/godotengine/godot-proposals/issues/9678)
- [gdUnit4](https://github.com/godot-gdunit-labs/gdUnit4)

### 7.2 Deterministic evidence transport

The original draft required byte-identical bundles without defining a byte profile. Phase 0 now
uses a directory rather than ZIP, excludes wall-clock export metadata, hashes every present data
file, and canonicalizes JSON/JSONL with RFC 8785. This avoids timestamp and entry-order variance
while keeping the artifact directly inspectable.

Source: [RFC 8785 — JSON Canonicalization Scheme](https://datatracker.ietf.org/doc/html/rfc8785).

### 7.3 Analysis-GUI patterns

Chess-engine GUIs demonstrate two useful patterns for candidate-based analysis:

- direct navigation to a stable analysis position;
- a compact overview of close evaluations and warnings before opening full detail.

Phase 0 adopts the low-cost portions: `--decision <battle_id>:<decision_index>` and exporter-made
`top1_top2_margin`, `warning_count`, and `fallback_used`. A full score-over-time graph remains a
v0.1 presentation item so the initial viewer stays small.

Reference: [En Croissant](https://encroissant.org/).

### 7.4 Showdown protocol reference

The `pkmn/ps` ecosystem, especially `@pkmn/protocol`, is a useful MIT-licensed differential oracle
for normalized protocol behavior. Phase 0 does not add it as a runtime dependency. Any reuse beyond
reference tests requires an explicit dependency and license decision.

Reference: [`pkmn/ps`](https://github.com/pkmn/ps).

### 7.5 Shared domain-module candidates

The strongest later Studio modules are Python-domain modules that can also improve the bot. This
is planning input for Phase 2 and beyond, not an expansion of the Phase-0 viewer.

| Candidate | Verified repository/source state | Product routing |
|---|---|---|
| Usage/meta-prior snapshots | The repository has curated `likely_sets`, move, and Protect priors, but no Smogon usage-statistics ingest. Smogon's programmatic `chaos.json` family includes a metagame identifier, cutoff, battle count, abilities, items, stats/spreads, moves, teammates, and counters. | Highest-value future shared module. Freeze source month/date, `format_id`, rating cutoff, content hash, and terms status before deriving bot priors or Studio views. |
| Team import and validation | Showdown documents export, JSON, and packed team formats. This repository already loads packed teams and uses the pinned official Showdown CLI to `pack-team` and `validate-team` in panel gates. | Standardize the existing paths behind a versioned adapter/schema; do not build a second parser or validator in Godot. |
| Damage and speed analysis | The bot already owns a pinned `@smogon/calc` bridge plus format-aware speed logic. | Expose display DTOs from Python for Phase 2; never add an independent GDScript calculator. |
| Tournament teams/archetypes | Champions panel provenance already cites specific Limitless team pages, but no general ingest contract or terms review exists. | Research-gated candidate only. Do not scrape or treat it as a bot prior until provenance, permission, format identity, and snapshot rules are approved. |

Smogon usage data is preferable to making Pikalytics a data dependency. Text paste is sufficient
for an initial team-import boundary; Poképaste scraping is not required. Limitless and wrapper
libraries remain research references until a separate source and license/terms audit approves an
ingest.

Studio-only later modules remain routed to their existing phases: replay-URL import after the
offline bundle contract, notifications and rooms/ladder in the full-client phase, and themes in the
add-on phase. Fast doubles simulation and live timer management remain bot-roadmap concerns rather
than Studio modules.

Primary references:

- [`pkmn/stats` output contract](https://github.com/pkmn/stats/blob/main/stats/OUTPUT.md)
- [Pokémon Showdown team-format documentation](https://github.com/smogon/pokemon-showdown/blob/master/sim/TEAMS.md)
- [Limitless VGC teams](https://limitlessvgc.com/teams) (research candidate; terms review pending)

### 7.6 Feature-backlog review: analysis, training, and local simulation

An external feature review compared Studio with chess, RTS, and fighting-game analysis tools. The
product patterns are useful, but its central premise needs correction: Showdown replays are already
structured protocol data, not video. They support parsing and querying, but they do not necessarily
contain a complete resumable simulator state, hidden information, or RNG state.

The proposed `@pkmn/sim` dependency is therefore not a single enabler that automatically unlocks
replay takeover, what-if analysis, mistake training, and a scenario sandbox. The package extracts
the official Showdown simulator and supports Generations 1–9, but ships a selected format set;
additional formats or mods may require separately supplied data and validation.

The repository already has a stronger first candidate for Champions: its pinned, patched
`smogon/pokemon-showdown` checkout runs `gen9championsvgc2026regma`, injects deterministic
per-battle seeds, and records the seed actually used. This proves seed control, not takeover. The
current harness does not persist Showdown's complete simulator input log or a resumable checkpoint,
so that capture contract and a turn-N conformance harness remain prerequisites.

| # | Candidate | Routing decision |
|---|---|---|
| 1 | Replay takeover from an arbitrary turn | Two separate products: exact takeover only for capture-time seed + complete teams + input-log/checkpoint evidence; public-replay takeover is optional, counterfactual, and hypothesis-labeled. |
| 2 | Eval/momentum graph | v0.1 candidate using recorded aggregate scores and warning markers only. No viewer-side recomputation or claim of objective game-state value. |
| 3 | One-ply what-if panel | Existing calc can provide assumption-labeled ranges without exact takeover. A complete alternate turn still requires a simulator and hidden-state hypothesis contract. |
| 4 | "Learn from your mistakes" mode | Later training research. Critical-turn labels need a validated metric and must not be presented as ground-truth blunders. |
| 5 | Local replay library with faceted search | Strong post-v0 candidate after the bundle/replay identity contract stabilizes. Local SQLite is an implementation option, not yet an architectural commitment. |
| 6 | Cross-replay statistics | Follows the replay library. Every statistic must expose corpus, visibility, format, and sample-size provenance. |
| 7 | Auto-synchronized damage panel | Phase 2 for replay analysis and Phase 3 for live battles, backed only by the existing Python/Node calc adapter. |
| 8 | Speed/initiative board | Phase 2. Separate recorded facts from prior-based estimates and expose the usage-snapshot version. |
| 9 | Persistent state banner | Already a Phase-0 viewer requirement and later reusable by the full client. |
| 10 | Team-preview matchup matrix | Phase 2 candidate prepared asynchronously and progressively. No unmeasured latency promise and no hidden-opponent truth. |
| 11 | Usage-integrated team analysis with freshness badge | Accepted Phase-2 direction through the provenance-complete usage/meta-prior schema. A full teambuilder remains outside the current slice. |
| 12 | Offline team validation | Existing repository capability to standardize behind the team import/validation schema, not a greenfield validator. |
| 13 | Scenario sandbox | Research only, behind the same simulation/parity gate as replay takeover. |
| 14 | Team benchmark/regression assertions | Strong later Phase-2 candidate: saved, versioned claims re-evaluated by the pinned calc when a team or usage snapshot changes. |

Smaller candidates are routed as follows: session restore is a v0.1 desktop-quality item;
annotations use a portable sidecar after the replay identity contract stabilizes; color-vision
support and redundant text/icon semantics are already cross-cutting requirements rather than a
separate feature.

The recommended order remains Phase 0 first, then stable replay/bundle identities, then shared
usage and team-validation adapters. A replay library and team regression checks may follow. A
Champions-aware audit of the pinned Showdown simulator can then make a scenario sandbox eligible;
exact takeover follows only after capture-time input logging/checkpoints and turn-N conformance.
Approximate public-replay takeover remains optional and separately labeled.

References:

- [`@pkmn/sim` package scope and format limitations](https://www.npmjs.com/package/@pkmn/sim)
- [Repository seeded-Showdown harness](../../../tools/eval/patches/README.md)
- [Pinned eval-server provenance](../../../config/eval/provenance.yaml)
- [Lichess "Learn from your mistakes"](https://lichess.org/blog/WFvLpiQAACMA8e9D/learn-from-your-mistakes)
- [Sc2ReplayStats](https://sc2replaystats.com/)
- [Showdex](https://github.com/doshidak/showdex)

## 8. Round 2 (2026-07-25): official issue tracker, userscripts, and recurring workarounds

A second research round, performed after the Phase 3 design
([`../specs/2026-07-25-phase3-client-design.md`](../specs/2026-07-25-phase3-client-design.md)) was
approved, examined current open issues in the official client repository, recent community posts,
and recurring user workarounds. Each finding below is routed against the now-binding Phase-3 spec:
**[binding]** = already required by an approved document, **[input]** = design input for a named
later plan, **[owner]** = needs an owner decision before it can bind anything.

### 8.1 Sources and limits

- [Configurable-shortcut issue, 2026-06-28](https://github.com/smogon/pokemon-showdown-client/issues/2713)
  (explicitly cites repeated mouse clicks and accessibility)
- [Mobile chat-drag issue #2355](https://github.com/smogon/pokemon-showdown-client/issues/2355) and
  the open mobile/responsive issue set (tab bar on narrow widths, on-screen-keyboard popping on
  move/switch selection, PWA requests)
- [Teambuilder Mega-form semantics issue #2707](https://github.com/smogon/pokemon-showdown-client/issues/2707)
- Open tooltip-staleness issues (Illusion reveal, Preact switch-menu desync, delayed status/ability
  effects)
- A screen-reader accessibility issue open since 2017
- [Userscript round-up post](https://www.reddit.com/r/pokemonshowdown/comments/1v24636/showdown_userscripts/)
  (global keyboard navigation, per-pane font sizes, auto-queue, ladder stats per keypress)
- [Format-availability confusion thread](https://www.reddit.com/r/pokemonshowdown/comments/1kk918g/gen_9_hackmon/)
- [Storage-loss confusion thread](https://www.reddit.com/r/pokemonshowdown/comments/1l34w9z/why_does_this_keep_happening/)

Same limits as §1, sharpened: GitHub issues over-weight technically fluent users, Reddit
over-weights salient single problems. The load-bearing observation is the **agreement** between
official issues and community workarounds, and the round-1/round-2 convergence on the same failure
classes (state clarity, scaling, accessibility, fragmentation).

**Central insight:** complaints rarely target the client's basic layout — users value its speed and
directness. The friction is unnecessary clicking, unclear/inconsistent states, weak accessibility,
limited customization, unreliable tooltips, and semantically ambiguous validation. For Studio:
do not rebuild Showdown prettier; remove the friction without losing the speed.

### 8.2 Findings and routing

| Finding | Durable implication | Routing |
|---|---|---|
| Repeated mouse work; users script their own shortcuts | A real command/shortcut layer (moves, slots, switch targets, palette), all configurable, auto-paused while typing in chat | **[input]** M2 plan (choice UI M2e, chat M2f); MASTER_SPEC §5 already requires keyboard operation, the configurable layer is new |
| A shortcut must never send a battle choice without a visible review step | Two-step choice submit: `Enter` opens a choice review, a second `Enter` inside the review sends | **[owner]** candidate spec §7 addition — fits the existing five pre-send checks and the human-provenance rule, but the explicit review step is not yet in the spec |
| Desktop patterns collapse on small windows | Explicit layout breakpoints (large: field+log / actions+chat; medium: chat as tab; small: single column with `[Log] [Chat] [Analysis]` tabs), collapsible log/chat, persisted panel sizes, no hover-only functions, 32–36 px minimum targets | **[binding]** MASTER_SPEC §5 (scaling, resizable/collapsible panels, density) already gates this; the concrete breakpoint model is **[input]** for M1d's `LiveClientWorkspace` |
| Teambuilder shows desired end state, stores a different validated state (Mega forms) | Always separate displayed form / initial battle form / transformation condition / validation basis; a validation *report*, never a bare "Valid" | **[input]** Phase 2 (Team Analyzer) design; out of Phase-3 v1 scope (no teambuilder, spec §3.2) |
| Format exists in teambuilder but is not ladder-playable | Distinguish exists / legal / ladder / challenge-only / spectatable explicitly | **[binding]** M2b's `FormatCatalogDTO` already models `supports_ladder`/`supports_challenge` from the server-authoritative `\|formats\|`; the status-wording guidance is **[input]** for M2b UI |
| Tooltips go stale (Illusion, switch-menu desync) and users decide on them | Every displayed datum carries provenance and freshness: KNOWN / INFERRED / POSSIBLE / STALE / UNKNOWN; identity changes trigger visible revalidation, never silent overwrite | **[input]** M1d spectator UI shows server-revealed facts only; the full confidence framework is design input for the M2 battle UI and matches the repo's existing provenance discipline (state banner, DecisionTrace) |
| Accessibility structurally unplanned upstream (2017 issue still open) | Full keyboard navigation, visible focus, screen-reader names for moves/slots/targets, live announcements, color+text+symbol redundancy, per-pane font scaling, reduced-motion and high-contrast modes | **[binding]** MASTER_SPEC §5 + §7.1's Godot AccessKit caveat already gate the keyboard/focus/contrast subset; per-pane scaling and reduced-motion/high-contrast are **[input]** (M1d onward) |
| Users lose teams/settings stored invisibly in browser storage | Profiles with explicit storage classes (stored locally / session only / exportable / sensitive), atomic writes, backups, crash recovery, visible write-failure — never a fake success | **[binding]** in part: fail-closed writes and no-silent-loss are AGENTS.md rule 10 + `TeamBundleV1`'s atomic/fail-closed contract; the profile system itself is **[input]** for a later workspace-storage slice (MASTER_SPEC §3.2 "later workspace storage") |
| Replays treated as playback, not analysis objects | Turn timeline, jump-to-turn, event filters, speed control, auto-pause on KO/switch/Tera/setup/unknown-event, per-decision bookmarks, annotations, turn/state diff, DecisionTrace beside the replay, visible separation of event vs. parser vs. model vs. human annotation | **[binding]** in part: Phase 0 already ships timeline + DecisionTrace + interestingness navigation; the rest extends §7.6's post-v0 candidate table (auto-pause, bookmarks, state-diff, side-by-side are new entries in that list) |
| Chat and battle log conflated | Separate tools: filterable, provenance-carrying, turn-grouped log vs. optional, separately zoomed, non-auto-linking chat; battle mode may open with log only | **[binding]** spec §5.2 (chat trust boundary, no auto-links) + separate panels in §4.1; log-first default and per-pane zoom are **[input]** for M1d/M2f |

### 8.3 Prioritized product opportunities (round-2 view)

- **P0 — must beat Showdown:** explicit command review before send **[owner]**; no silent state
  assumptions, clean reconnect/stale-request handling, unknown events kept visible — all already
  **binding** (spec §6.1–§6.3, §7); keyboard control; log/chat separation; atomic recoverable team
  storage; tooltip provenance.
- **P1 — strong user value:** replay timeline (partly shipped in Phase 0), configurable shortcuts,
  per-pane font sizes, layout profiles, format-availability explanations, validation report,
  filterable battle log, DecisionTrace inspector (shipped, Phase 0), turn/state diff, local
  annotations.
- **P2 — differentiation:** side-by-side replay comparison, human-vs-bot decision comparison,
  damage-range evidence, hidden-information uncertainty display, Bo3 session workspace, turn
  bookmarks, exportable incident report, capability-scoped mod system (Phase 4), command palette,
  accessibility profiles.

### 8.3.1 Decide before the M2 plan is written (binding checklist)

Most UX work belongs *after* M2's protocol and request model are real: colors, typography, icons,
spacing, and battle-screen mockups would only churn. Three decisions are the exception — they are
architectural, they are cheap to fix now and expensive to retrofit, and each must be an explicit
owner sign-off item in the M2 spec/plan round (the same mechanism that settled the
`ObservationEventBus` placement and the CLI test-infrastructure exception during M1).

| Decision | Why it cannot wait for "after M2" |
|---|---|
| **Two-step choice review** (first confirm opens a review of the selected actions; a second, separate confirmation sends) | Touches the choice lifecycle in spec §7 directly — the five pre-send checks and the human-provenance rule. Decided before M2e: one line in the plan. Decided after: rework of both the choice UI and the gateway flow. Already flagged as an **[owner]** candidate in §8.2. |
| **Input routing / shortcut layer** (which component owns keyboard input; shortcuts auto-pause while typing in chat; configurability) | This is input *architecture*, not a key map. Retrofitting a global shortcut layer after the battle UI exists means touching every panel. MASTER_SPEC §5 already requires keyboard operation; what is undecided is who routes it. |
| **Panel / layout model** (which surfaces are docks, what collapses, what is persisted, the explicit breakpoints) | The live workspace has three panels today and will have roughly eight after M2 — today is the cheapest possible moment. MASTER_SPEC §5 already binds scaling, resizable/collapsible panels and density modes; the concrete breakpoint model is what is missing. |

Explicitly **not** required before M2, despite appearing in §8.2: the KNOWN/INFERRED/POSSIBLE/
STALE/UNKNOWN provenance framework. A human-operated client only knows what the server reveals, so
in M2 essentially every displayed value is KNOWN; the framework earns its keep once bot inferences
and DecisionTrace data sit beside live state. The `major`/`minor` schema discipline
(`MASTER_SPEC.md` §3.3) lets those fields be added later without a breaking change, so deferring
carries no architectural debt.

### 8.4 What not to copy

Permanent technical status columns; information-dense home screens; desktop layouts merely
compressed for small windows; tooltips as the only information source; identical treatment of chat
and battle log; "Valid" without explanation; automatic resumption of old requests (already
forbidden, spec §6.2); silently updated client-side assumptions (already forbidden, AGENTS.md rule
10); mouse-only essential workflows; invisible browser-local storage as the primary data store.

### 8.5 Round-2 design conclusion

The strongest direction: **Showdown's speed, a Lichess-like analysis hierarchy, a Slippi-like
replay workflow, and Godot-style contextual tooling.** The battle screen should feel normal and
familiar; the innovation sits underneath — state safety, analysis, keyboard workflows, storage,
provenance, replays. This confirms rather than revises the Phase-3 architecture: nothing found in
round 2 contradicts an approved decision, and the two genuinely new binding candidates (two-step
choice review; configurable-shortcut layer) both route to the M2 plan for an owner decision.
