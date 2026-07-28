# Working Agreement

## Partnership

- Work as a critical collaborator, not an order-taker.
- Never agree reflexively. Verify load-bearing claims, reviews, and assumptions against the code,
  committed artifacts, or authoritative external sources before building on them.
- When a proposal is wrong, incomplete, or weakly supported, say so plainly and explain the
  evidence. Distinguish verified facts, reported results, and inference.

## Sources of Truth

1. Read `docs/PROJECT_INDEX.md` for orientation.
2. For **what is open / blocked / next** (operational status): check the GitHub Project
   "ShowdownBot — North Star" (`docs/architecture/github-project-governance.md` for the
   field contract and views).
3. For **detailed technical status, evidence chains, and provenance**: treat
   `docs/ROADMAP.md` as the authoritative source.
4. For the active slice, read its approved spec and plan, relevant reports, tests, and Git history.

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

## Documentation placement

Store new documentation by subject under `docs/projects/<project>/`: designs and
contracts in `specs/`, implementation plans in `plans/`, audits in `audits/`, and
reviews in `reviews/`. Put user-facing material in `docs/guides/<topic>/` and
cross-project architecture in `docs/architecture/`. Do not recreate
`docs/superpowers/`; see `docs/README.md` and `docs/PATH_MIGRATION.md`.
