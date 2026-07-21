# Viewer v0 — Implementation Index

**Status:** APPROVED — 2026-07-21 (Rev. 2). Orders plans A–F and records hard dependencies.
**Does not authorize code.** Code for plan X starts only after plan X is marked APPROVED.
**Date:** 2026-07-21 · **Rev.:** 2
**Product:** ShowdownBot Studio Phase 0 — Offline Replay + DecisionTrace Viewer

**Delivery tip (status only; does not change authorization rules):** Plan **A** merged PR **#41**;
Plan **B** merged PR **#44**; Plan **C** merged PR **#46**; Plan **D** merged PR **#47** (+
follow-ups PR **#48**) @ `0256602`. **Next:** Plan **E** DRAFT under review
(`2026-07-21-viewer-v0-e-diagnostics-a11y-layout.md`). Plan F remains DRAFT. Code for E/F
starts only after each plan is APPROVED + separate go-ahead.

## 1. Why this index

[`../specs/viewer-v0-design.md`](../specs/viewer-v0-design.md) §11 and
[`../specs/viewer-v0-bundle-contract-design.md`](../specs/viewer-v0-bundle-contract-design.md) §17
authorize a reviewed implementation plan for steps 1–7. This index orders those steps into six
plan documents (A–F).

**Code authorization:** each plan A–F must be marked APPROVED before its code starts. Approving
this index alone does **not** authorize building A–F. A plan must not start before its hard
dependencies in §3 are met.

## 2. Spec authority

### 2.1 Binding for this plan set (approved)

| Role | Path |
|---|---|
| Viewer UX / Godot slice | [`../specs/viewer-v0-design.md`](../specs/viewer-v0-design.md) |
| Bundle / exporter (wins on conflict) | [`../specs/viewer-v0-bundle-contract-design.md`](../specs/viewer-v0-bundle-contract-design.md) |
| Ownership / deps | [`../architecture/PROJECT_BOUNDARIES.md`](../architecture/PROJECT_BOUNDARIES.md) |
| Godot pin | [`../decisions/ADR-001-godot-ui-technology.md`](../decisions/ADR-001-godot-ui-technology.md) |
| License / privacy | [`../research/2026-07-license-data-audit.md`](../research/2026-07-license-data-audit.md) |
| Visual direction | [`../design/viewer-v0-mockups/README.md`](../design/viewer-v0-mockups/README.md) |

### 2.2 Context — master spec not binding for Phase 0 planning

| Role | Path | Status |
|---|---|---|
| Product family / later phases | [`../MASTER_SPEC.md`](../MASTER_SPEC.md) | Product design approved; written text still pending full review |

**User decision (2026-07-21):** The master spec blocks neither this index approval nor review of
Plan A. The APPROVED Viewer v0 design + bundle contract (§2.1) are sufficient Phase-0 authority.
The master spec remains **non-binding context** for now. It must be reviewed separately — at latest
before later phases are planned, or sooner if its wording would change Phase-0 boundaries (in which
case this index must be re-reviewed).

## 3. Delivery order and dependency graph

### 3.1 Merge / delivery sequence (linear)

Suggested merge order — not a claim that every plan is only blocked on its predecessor:

```text
A → B → C → D → E → F
```

| Plan | Outcome when done |
|---|---|
| A | Portable bundle exists; fail-closed export; two exports of the same frozen source produce the same relative file list and per-file SHA-256 digests (source bytes are **re-serialized, never copied**); `candidate_key` remains an opaque string and is byte-identical source→bundle |
| B | Open / validate / load DTOs off the main thread |
| C | Abstract board + protocol/decision timeline |
| D | Candidates, chosen key, scores, navigation fields |
| E | Banners, provenance, scale / density / keyboard gates |
| F | Full fixture catalogue + headless gdUnit4 + closeout |

### 3.2 Hard dependencies (code start gates)

```text
A
└──► B          (requires Plan A fixture 1)
     └──► C     (requires B loader + DTO types; fixtures 1, 4, 5)
          └──► D  (requires B DTOs + C timeline selection; fixtures 1, 3, 16)
               └──► E  (requires B–D surfaces to decorate)
                    └──► F  (requires A–E green; remaining fixtures from §3.3)
```

Rules:

- **B** must not start until A has shipped trusted fixture **1**.
- **C** must not start until B loader + DTO types exist.
- **D** must not start until B DTOs and C timeline selection exist (D is not “B-only”).
- **E** must not start until B–D surfaces exist (E is not “B-only”).
- **F** must not start until A–E are green against the fixture responsibilities in §3.3.
- No parallel start that skips an edge above. Remaining Plan A fixture work after the §3.3
  minimum may continue while B–E run, but F cannot close until those fixtures land.

### 3.3 Fixture responsibility split

| Owner | Fixtures | Role |
|---|---|---|
| **Plan A (minimum before B / for early consumers)** | **1, 3, 4, 5, 6, 10, 16** | Required set A must land; fixture **1** gates B; 3/16 gate D; 4/5 gate C/E modes; 6 gates B refuse; 10 gates A privacy closeout |
| **Plan F (catalogue closeout)** | **2, 7–9, 11–15, 17–23** | Completes bundle-contract §14 catalogue before Viewer v0 acceptance |

Plan A may emit additional catalogue entries early; it is not required to. Plan F owns proving the
F-column set exists and passes gates.

## 4. Target tree (Studio-only)

Nothing under `showdown_bot/`, `config/eval/`, `data/eval/`, or `reports/` is modified by Viewer v0
plans. Studio consumes frozen artifacts as **read-only inputs**.

```text
showdownbot_studio/
  python/
    showdownbot_studio_exporter/     # package name TBD in Plan A
      __init__.py
      cli.py
      canonicalize.py                # RFC 8785
      hash.py
      privacy.py                     # portable-pseudonymous-v1
      provenance.py
      join.py                        # request_hash → request_protocol_index
      export_battle.py
      export_decisions.py
      validate_bundle.py
      warnings.py
  schemas/
    viewer-bundle-1.0/               # frozen JSON Schema / field docs (optional aid)
  fixtures/
    viewer-v0/                       # catalogue §14 — small, clean
  godot/
    project.godot                    # Godot 4.5.2
    addons/gdUnit4/                  # pinned version in Plan B
    src/
      bundle/
      timeline/
      replay/
      decision/
      diagnostics/
      workspace/
    tests/
  tests/
    python/                          # pytest for exporter
    # Godot tests live under godot/tests via gdUnit4
  docs/plans/                        # this set
```

## 5. Cross-cutting rules (all plans)

1. **Fail closed** on unknown major, unknown required capability, hash mismatch, identity conflict.
2. **Re-serialize, never copy** source bytes into the bundle.
3. **`candidate_key` is an opaque string** — never parse/re-emit inner JSON; source→bundle bytes
   for that string are identical.
4. **No data from `config_hash`** — identity tag only; ship optional config-manifest pre-image.
5. **Godot never** recomputes mechanics, scores, beliefs, rankings, or migrations.
6. **Privacy at export** — source untouched; portable bundle uses seat pseudonyms only.
7. **Bounded rendering** — no one Control per unbounded row (104-candidate fixture is the proof).
8. **Offline only** — no network in Phase 0 runtime.
9. **TDD** for exporter and contract tests; Godot tests via pinned gdUnit4 headless CI.
10. **Open design inputs** ([bundle contract](../specs/viewer-v0-bundle-contract-design.md) §16)
    stay missing — render `not recorded` / omit `suspected`; do not invent producers.

## 6. Explicit non-goals (entire v0 program)

- Live spectator, login, chat, ladder, rooms
- Team builder / second calc / usage client
- Public replay search/download
- Plugins, mods, external bots
- Bundled Pokémon artwork / runtime sprites
- Write-back into frozen eval artifacts
- Strength / safety / correctness claims about the bot
- Score-over-time graph (v0.1 candidate only)
- Changing bot trace production to close §16 gaps (separate bot-side design if ever approved)

## 7. Approval and execution gates

For each plan A–F:

1. User reviews and marks the plan **APPROVED** (or requests edits).
2. Isolated branch/worktree under Studio paths only.
3. Task-level TDD / gdUnit4 as specified in that plan.
4. `git diff --check` clean at each logical commit.
5. No merge of later-phase tasks.
6. Hard dependencies in §3.2 satisfied before code starts.

Closeout (Plan F) additionally requires: privacy counterexample green, mixed-DPI manual Windows
check recorded, abstract-board no-artwork fixture understandable, deep-link diagnostic failures.

## 8. Suggested commit cadence (high level)

| Plan | Logical commits (sketch) |
|---|---|
| A | canonicalize → privacy → export decisions → export battle/join → validate → fixtures **1, 3, 4, 5, 6, 10, 16** |
| B | Godot project pin → DTO types → worker BundleLoader → open/refuse paths |
| C | timeline model → abstract board → play/pause sync |
| D | candidate table → detail tabs → navigation fields / deep link |
| E | state banner → provenance → scale/density/keyboard → layout reset |
| F | fixtures **2, 7–9, 11–15, 17–23** + CI matrix → a11y checklist evidence → docs status bump |

## 9. Open questions for plan approval

1. ~~Exact Python package layout / install entrypoint name.~~ — **proposed closed in Plan A Rev. 3**
   (`showdownbot-studio-exporter` / `python/src` / console script). Binding when Plan A is APPROVED.
2. Exact gdUnit4 release pin verified against Godot 4.5.2. → Plan B
3. ~~JSON Schema under `schemas/` in A?~~ — **proposed closed in Plan A Rev. 3**: deferred; contract
   §10 remains authority. Binding when Plan A is APPROVED.
4. Minimum supported desktop window size numbers for Plan E (spec requires reachability; numbers TBD
   against the representative fixture). → Plan E
5. ~~User decision on [`../MASTER_SPEC.md`](../MASTER_SPEC.md)~~ — **closed 2026-07-21** (see §2.2):
   non-binding context for Phase 0; separate review later / before later phases.

Items 2 and 4 must be closed in the approved Plan B/E texts before coding those plans. Items 1 and 3
become binding on Plan A APPROVED.
