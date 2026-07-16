# Root CLAUDE.md Restoration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore a compact, version-controlled root `CLAUDE.md` that records the project's stable working agreement.

**Architecture:** `CLAUDE.md` contains only durable collaboration, source-of-truth, scope, verification, and repository-hygiene rules. Volatile priorities and measurements remain in `docs/PROJECT_INDEX.md`, `docs/ROADMAP.md`, reports, and Git history.

**Tech Stack:** Markdown, Git, PowerShell verification commands

---

### Task 1: Restore and version the root working agreement

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Confirm the file is absent and unrelated work is preserved**

Run:

```powershell
Test-Path -LiteralPath CLAUDE.md
git status --short
```

Expected: `False`; the existing `tools/_pkmn_differential_audit/` entry remains untracked.

- [ ] **Step 2: Create the compact working agreement**

Create `CLAUDE.md` with exactly this content:

```markdown
# Working Agreement

## Partnership

- Work as a critical collaborator, not an order-taker.
- Never agree reflexively. Verify load-bearing claims, reviews, and assumptions against the code,
  committed artifacts, or authoritative external sources before building on them.
- When a proposal is wrong, incomplete, or weakly supported, say so plainly and explain the
  evidence. Distinguish verified facts, reported results, and inference.

## Sources of Truth

1. Read `docs/PROJECT_INDEX.md` for orientation.
2. Treat `docs/ROADMAP.md` as the authoritative status matrix and sequencing source.
3. For the active slice, read its approved spec and plan, relevant reports, tests, and Git history.

When summaries conflict, trust current code, committed evidence, the roadmap, and Git history.
Do not duplicate volatile phase status, commit hashes, or measurements in this file.

## Scope and Claims

- Do not start a later phase or broaden a slice without explicit approval.
- Do not turn safety, parser, provenance, or pipeline smokes into strength claims.
- Preserve explicit non-goals and fail-closed gates from approved specs and plans.

## Verification

- Inspect the actual diff and relevant production paths; do not accept agent reports on trust.
- Before claiming success, run fresh checks proportional to the change and read their full output.
- Run `git diff --check` for every commit-ready slice.
- Report exactly what was verified locally and what was only reported by another agent or CI.

## Repository Hygiene

- Preserve unrelated user changes and local-only artifacts.
- Stage files intentionally; never use broad staging when unrelated files are present.
- Do not force-push, push directly to `main`, merge, delete branches, or remove worktrees without
  explicit approval.
- Keep raw logs, caches, temporary diagnostics, and large external datasets out of commits unless
  an approved plan explicitly freezes them as evidence.
```

- [ ] **Step 3: Verify content and references**

Run:

```powershell
Test-Path -LiteralPath docs/PROJECT_INDEX.md
Test-Path -LiteralPath docs/ROADMAP.md
rg -n "PLACEHOLDER|[0-9a-f]{7,40}" CLAUDE.md
git diff --check -- CLAUDE.md
git status --short
```

Expected: both paths return `True`; the placeholder/hash scan has no matches; `git diff --check`
is clean; status shows only `CLAUDE.md` plus the pre-existing audit helper directory.

- [ ] **Step 4: Commit only the restored file**

Run:

```powershell
git add -- CLAUDE.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: restore root Claude working agreement"
```

Expected: the staged file list contains only `CLAUDE.md`; the commit succeeds; no push is performed.
