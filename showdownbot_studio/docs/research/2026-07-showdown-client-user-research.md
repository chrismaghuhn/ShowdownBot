# Pokémon Showdown Client User Research — July 2026

**Status:** qualitative research snapshot
**Date:** 2026-07-16
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
