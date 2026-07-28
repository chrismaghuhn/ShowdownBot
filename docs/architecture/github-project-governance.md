# GitHub Project "ShowdownBot — North Star" — Governance

**Project URL:** https://github.com/users/chrismaghuhn/projects/2
**Created:** 2026-07-28

---

## Purpose

The GitHub Project is the **live operational board** for tracking what is open, what is
blocked, and what comes next. It is not a replacement for `docs/ROADMAP.md` — each has a
distinct role, and neither duplicates the other.

---

## Split Authority

| Concern | Authoritative source |
|---|---|
| What is open / blocked / next | GitHub Project (board + fields) |
| Detailed technical status, evidence chains, provenance | `docs/ROADMAP.md` on `main` |
| Approved specs, plans, decision records | `docs/projects/<project>/` on `main` |
| Frozen evidence, gate artifacts | `data/eval/` on `main` |
| Orientation for new sessions | `docs/PROJECT_INDEX.md` on `main` |

**Rule:** The Project board answers "what should I work on now?" The repo answers "what
exactly happened, and can I reproduce it?"

---

## Field Contract

Each issue in the project carries these fields. Values are set at creation and updated as
work progresses.

| Field | Type | Options | Semantics |
|---|---|---|---|
| Status | Single select | Inbox, Needs Decision, Ready, In Progress, In Review, Blocked, Resolved | Workflow state (7 options) |
| Priority | Single select | P0, P1, P2, P3 | Urgency; P0 = current sprint |
| Track | Single select | Bot Strength, Evaluation / Provenance, Depth-2 / Search, Champions, Studio, Infrastructure | Domain grouping |
| Work Type | Single select | Bug, Improvement, Experiment, Gate, Decision, Documentation | Nature of the work |
| Evidence | Single select | None, Spec Approved, Implemented, Verified, Frozen | Evidence maturity ladder |
| Verdict | Single select | Not Applicable, Not Run, PASS, FAIL, NO-GO, Inconclusive | Gate outcome |
| Target | Single select | Now, Next, Later, Parked | Planning horizon |
| Start Date | Date | — | When work began |

### Evidence ladder

Evidence progresses monotonically: None → Spec Approved → Implemented → Verified →
Frozen. It never moves backward. "Spec Approved" means a spec exists and was approved —
the code may or may not be implemented yet. "Implemented" means the code is written and
tested. "Verified" means a preflight or dry-run passed. "Frozen" means evidence is
committed to `main` under `data/eval/`.

### Verdict semantics

- **Not Applicable** — the issue has no gate (e.g. a bug fix, an improvement).
- **Not Run** — a gate exists but has not been executed yet.
- **PASS / FAIL / NO-GO** — the gate ran and produced this result. FAIL is a technical
  failure (e.g. safety violation); NO-GO is a strength verdict that did not meet the bar.
- **Inconclusive** — the gate ran but the result is ambiguous (e.g. underpowered test).

---

## Issue Body Contract

Every issue uses this template:

```
## Outcome
## Why now
## Sources
## Scope
## Non-goals
## Acceptance criteria
## Evidence required
## Resolution rule
```

**Outcome** is the end state in one sentence. **Why now** explains sequencing. **Sources**
links to roadmap, specs, or evidence. **Non-goals** are explicit boundaries. **Acceptance
criteria** are checkboxes. **Evidence required** names what must exist before closing.
**Resolution rule** defines when the issue may be closed.

---

## Hierarchy

Issues use GitHub's native parent/sub-issue relationships. A parent issue is a container
— its scope is the union of its sub-issues. A parent closes when all sub-issues close or
are explicitly deferred.

Dependencies use the "blocked by" relationship where available, or are documented in the
issue body when the API doesn't support it.

---

## Workflows

These GitHub Project workflows should be enabled:

| Workflow | Trigger | Action |
|---|---|---|
| Item added to project | Issue added | Set Status → Inbox |
| Item closed | Issue closed | Set Status → Resolved |
| Auto-close issue | — | **DISABLED** (gates must be closed manually) |
| Pull request merged | — | **DISABLED** (merging a PR does not close the issue) |

Auto-close and PR-merged workflows are disabled because gate issues require explicit
human sign-off — a merged PR is evidence, not resolution.

---

## Views

The project should have these views:

| View | Type | Purpose |
|---|---|---|
| North Star | Table (by Status) | Default view — all issues; convert to Board layout when issue count warrants it |
| Now | Table filtered to Target = Now | Current sprint focus |
| Gates & Evidence | Table filtered to Work Type = Gate | Gate status at a glance |
| Blocked | Table filtered to Status = Blocked | What's waiting on what |
| Roadmap | Roadmap (by Target) | Planning horizon |
| Resolved | Table filtered to Status = Resolved | History |

---

## Labels

All project issues carry the `north-star` label for easy filtering outside the project.
Additional labels by track: `champions`, `evaluation`, `depth-2`, `studio`.

---

## Authority Handoff

Both `AGENTS.md` and `docs/PROJECT_INDEX.md` previously declared `docs/ROADMAP.md` as
the sole authoritative source for status and sequencing. This governance document
introduces a split: the GitHub Project is authoritative for "what is open / blocked /
next" (operational status), while `docs/ROADMAP.md` remains authoritative for technical
detail, evidence chains, and provenance.

**Resolved in this PR:** `AGENTS.md` is tracked and updated to reference both sources
with their respective roles. `docs/PROJECT_INDEX.md` is updated likewise.

---

## Migration Audit

### What moved to the Project

- Open work items that were previously tracked only as prose in `docs/ROADMAP.md`
- Sequencing relationships (blocked-by) that were previously implicit in roadmap text
- "What should I work on next?" decisions that required reading 700+ lines of roadmap

### What stays in the repo

- All technical detail, evidence chains, and provenance (unchanged)
- Approved specs, plans, and decision records (unchanged)
- Frozen evidence under `data/eval/` (unchanged)
- `docs/PROJECT_INDEX.md` as the orientation card (unchanged)
- `docs/ROADMAP.md` as the authoritative technical status matrix (unchanged, but
  "what's open" queries should prefer the Project board)

### What changed about existing processes

- New issues get a `north-star` label and are added to the Project with all fields set.
- Issue closure requires meeting the Resolution Rule in the issue body — no auto-close.
- The Project board is the first place to look for "what's next"; the roadmap is the
  first place to look for "what exactly happened."

### What did NOT change

- The gate process (fail-closed, manual sign-off, frozen evidence) is unchanged.
- The claim discipline (no strength claims from safety passes, etc.) is unchanged.
- The holdout process and ledger are unchanged.
- `docs/ROADMAP.md` is still updated when slices land — it is not deprecated.
