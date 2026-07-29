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
If the GitHub Project is temporarily inaccessible, state that limitation explicitly, continue from
the roadmap, current code, committed evidence, and Git history, and do not claim that operational
status was verified.

## Scope and Claims

- Do not start a later phase or broaden a slice without explicit approval.
- Within an approved slice, proceed autonomously through all necessary implementation, tests,
  documentation, and review steps implied by its acceptance criteria. These are not scope
  expansion.
- Do not turn safety, parser, provenance, or pipeline smokes into strength claims.
- Preserve explicit non-goals and fail-closed gates from approved specs and plans.

## Execution Default

For repository tasks, default to completing the requested task rather than merely advising what
someone else should do.

For implementation tasks such as implement, fix, complete, or continue:

1. Inspect the authoritative repository state.
2. Resolve all questions that can be answered from the repository without asking the user.
3. Carry the task through implementation, review, and proportional verification.
4. Do not stop after writing a plan, recommendation, diagnosis, or suggested next step.
5. Ask the user only when a genuinely non-recoverable product decision or external dependency
   blocks further progress.
6. When several valid implementation choices exist, choose the lowest-risk reversible option
   consistent with the approved contracts.
7. Continue with independent, in-scope work even if one subtask is blocked.
8. Return with completed work or a concrete demonstrated blocker, not merely uncertainty.

For investigation, audit, review, or validation tasks:

1. Inspect the authoritative artifacts, relevant production paths, tests, current diff, and history.
2. Follow the evidence until the question is answered or a concrete information gap is demonstrated.
3. Do not modify production code unless the user explicitly requested a fix or implementation.
4. Report findings by severity and distinguish verified facts, reported results, and inference.
5. Do not convert identified problems into completed fixes or strength claims.

A plausible plan is not completion.
A review without inspecting the relevant code is not completion.
A code change without inspecting the final diff and running fresh verification is not completion.

## Plan Quality Gate

Before presenting an implementation plan, perform a fresh repository-grounded planning pass.

A plan is not ready for review until it:

1. Identifies the authoritative spec, current operational state, relevant production paths,
   tests, prior decisions, and current diff.
2. States the exact problem, approved scope, non-goals, and acceptance criteria.
3. Maps every planned change to concrete files, symbols, interfaces, or data contracts where
   these can be determined from the repository.
4. Preserves existing invariants and explicitly identifies any invariant that must change.
5. Describes implementation order, intermediate states, compatibility requirements, and
   fail-closed behavior.
6. Defines proportional verification for each material claim.
7. Separates required work from optional follow-up work.
8. Identifies unresolved product decisions, external dependencies, assumptions, and evidence gaps.
9. Checks whether an existing mechanism already solves the problem before proposing a new one.
10. Includes rollback, migration, or degradation handling when the change can affect persisted
    data, live behavior, evaluation results, or operational safety.

Before returning the plan, review it adversarially for:

- contradictions with committed contracts;
- missed production paths;
- duplicated mechanisms;
- hidden state or ownership problems;
- unsupported strength claims;
- incomplete tests;
- sequencing hazards;
- scope expansion;
- ambiguous completion criteria.

Resolve repository-answerable findings before presenting the plan. Do not use the user as the
first review pass for defects that repository inspection could have found.

When reviewing or revising an existing plan, first reconstruct the problem and a solution
independently from the authoritative repository state. Then compare that result with the current
plan and decide whether it should be accepted, amended, or replaced. Preserving the existing plan
structure has no value by itself.

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
