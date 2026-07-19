# Root CLAUDE.md Restoration Design

**Status:** APPROVED for documentation implementation
**Date:** 2026-07-16

## Purpose

Restore a compact, version-controlled `CLAUDE.md` at the repository root. The previous file was
local-only and is no longer recoverable from Git. Claude project memory confirms its central
working agreement: agents must verify load-bearing claims against code and evidence instead of
agreeing reflexively.

## Design

The restored file is a stable working agreement, not a second roadmap. It contains six sections:

1. **Partnership:** critically evaluate proposals and explain disagreements with evidence.
2. **Sources of truth:** read `docs/PROJECT_INDEX.md`, then `docs/ROADMAP.md`, then the active
   spec, plan, reports, tests, and Git history.
3. **Scope discipline:** do not start later phases, make strength claims from safety smokes, or
   broaden the requested slice without explicit approval.
4. **Verification:** independently inspect code and artifacts; run fresh relevant checks before
   claiming success; distinguish self-verified results from reported results.
5. **Repository hygiene:** preserve unrelated changes and local artifacts; stage intentionally;
   avoid force-push, direct `main` pushes, merges, or worktree deletion without approval.
6. **Status ownership:** keep changing priorities, commit hashes, and measured results in the
   project index, roadmap, reports, and Git history rather than duplicating them here.

## Scope

Implementation creates only the root `CLAUDE.md`. It does not modify project status, product code,
tests, evaluation artifacts, or the existing untracked protocol-audit helper directory.

## Verification

- Confirm every referenced path exists.
- Confirm the file contains no current phase status or volatile commit hash.
- Run `git diff --check`.
- Stage and commit only `CLAUDE.md`; preserve unrelated untracked files.
