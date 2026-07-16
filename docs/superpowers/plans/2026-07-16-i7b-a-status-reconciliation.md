# I7b-A Status Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the local root-guidance commits while integrating merged PR #12 and updating the living project-status documents to the post-I7b-A state.

**Architecture:** First merge `origin/main` into the divergent local `main` without rewriting history. Then update only `docs/ROADMAP.md` and `docs/PROJECT_INDEX.md`; historical specs, plans, reports, code, tests, and eval artifacts remain unchanged.

**Tech Stack:** Git, Markdown, PowerShell verification commands

---

### Task 1: Reconcile local and remote main histories

**Files:**
- Preserve: `CLAUDE.md`
- Preserve: `docs/superpowers/specs/2026-07-16-claude-md-restoration-design.md`
- Preserve: `docs/superpowers/plans/2026-07-16-restore-root-claude-md.md`
- Preserve: `docs/superpowers/specs/2026-07-16-i7b-a-status-reconciliation-design.md`

- [ ] **Step 1: Refresh and validate the two tips**

Run:

```powershell
git fetch origin
git rev-parse --short origin/main
git rev-parse --short main
git status --short
```

Expected: `origin/main` is `cdc55c2`; local `main` contains the four local documentation commits;
the only working-tree entry is `tools/_pkmn_differential_audit/`.

- [ ] **Step 2: Merge without rewriting history**

Run:

```powershell
git merge --no-edit origin/main
```

Expected: a normal conflict-free merge commit. If a conflict occurs, stop without resolving it.

- [ ] **Step 3: Verify both histories survived**

Run:

```powershell
git merge-base --is-ancestor origin/main HEAD
git merge-base --is-ancestor 249d3bc HEAD
git merge-base --is-ancestor 1ecddf4 HEAD
git status --short
```

Expected: every ancestor check exits zero; only the audit helper directory remains untracked.

### Task 2: Update the two living status sources

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/PROJECT_INDEX.md`

- [ ] **Step 1: Correct the shared status model**

Apply these exact facts consistently in both files:

```text
I7b-A: IMPLEMENTED · CODE-REVIEWED · MERGED via PR #12 @ cdc55c2
Verification: 2132 passed, 2 skipped, 1 xfailed
Runtime status: additive/inert; no Decision/Scoring/Search caller passes the new kwargs yet
I7b-B: NOT STARTED · review-gated · next implementation decision
I7b-C: NOT STARTED · review-gated after I7b-B
Strength: NO-GO until complete I7b requirements plus dedicated latency gate
```

In `docs/ROADMAP.md` update the `Last reconciled` paragraph and the complete `Champions panel v0`
status-matrix row. In `docs/PROJECT_INDEX.md` update `Last reconciled`, Current Priority item 1,
the Champions status table, the I7b evidence row, and the two I7b open-blocker bullets.

- [ ] **Step 2: Prove stale claims are gone without weakening gates**

Run:

```powershell
rg -n "I7b-A implementation authorized.*NOT IMPLEMENTED|no I7b code|no I7b tests|implement I7b-A" docs/ROADMAP.md docs/PROJECT_INDEX.md
rg -n "I7b-B.*NOT STARTED|I7b-C.*NOT STARTED|Strength.*NO-GO|latency" docs/ROADMAP.md docs/PROJECT_INDEX.md
git diff --check
git diff -- docs/ROADMAP.md docs/PROJECT_INDEX.md
```

Expected: the stale-claim scan has no matches; the retained-gate scan finds both future slices and
the Strength/latency gate; the diff contains only factual status changes and is whitespace-clean.

- [ ] **Step 3: Commit only the living status documents**

Run:

```powershell
git add -- docs/ROADMAP.md docs/PROJECT_INDEX.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: reconcile roadmap after I7b-A merge"
```

Expected: exactly the two status documents are staged and committed. Do not push.
