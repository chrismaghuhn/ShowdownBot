# Working Agreement

## Hard rules

These are the irreversible or trust-destroying ones. Everything below elaborates; these do not
bend.

- Do not force-push, push directly to `main`, merge, delete branches, or remove worktrees without
  explicit approval.
- Do not start a later phase or broaden a slice without explicit approval.
- Never claim a check passed that you did not run and read. Name what you ran; name what was only
  reported by CI or another agent.
- Never turn a safety, parser, provenance, or pipeline smoke into a strength claim.
- Do not violate INV-1…INV-7 (`docs/architecture/brain-v1-northstar.md`). Relitigating one needs an
  approved decision record, not an argument in a plan.
- Stage files intentionally. Never use broad staging when unrelated files are present.

## Partnership

- Work as a critical collaborator, not an order-taker.
- Never agree reflexively. Verify load-bearing claims, reviews, and assumptions against the code,
  committed artifacts, or authoritative external sources before building on them.
- When a proposal is wrong, incomplete, or weakly supported, say so plainly and explain the
  evidence. Distinguish verified facts, reported results, and inference.

## Sources of Truth

1. `docs/PROJECT_INDEX.md` for orientation. Read the `Purpose`, `Current North Star`, and
   `Current Priority` sections, then grep for the active slice. Do not read it end-to-end.
2. For **what is open / blocked / next** (operational status): the GitHub Project
   "ShowdownBot — North Star" (`docs/architecture/github-project-governance.md` for the field
   contract and views).
3. For **detailed technical status, evidence chains, and provenance**: `docs/ROADMAP.md` is
   authoritative. It is large; grep it for the active slice rather than reading it whole.
4. For the active slice: its approved spec and plan, relevant reports, tests, and Git history.

When summaries conflict, trust current code, committed evidence, the roadmap, and Git history.
Do not duplicate volatile phase status, commit hashes, or measurements in this file.
If the GitHub Project is temporarily inaccessible, state that limitation explicitly, continue from
the roadmap, current code, committed evidence, and Git history, and do not claim that operational
status was verified.

The canonical Brain V1 architecture documents live **outside this repository**
(`TestBOtpläne/`, sibling of the repo). An agent working only from the repo does not have them:
say so rather than reconstructing them from `docs/architecture/brain-v1-northstar.md`, which is a
pointer, not the source.

## Repository map

- `showdown_bot/src/showdown_bot/` — the package.
  `client/` (connection, auth, runner, gauntlet) · `protocol/` · `battle/` (the Brain seam is
  `battle/decision.py::choose_with_fallback`) · `engine/` (`belief/`, `calc/`) · `eval/` ·
  `learning/` · `models/` · `team/` · `analysis/` · `research/` · `cli.py`
- `showdown_bot/tests/` — the pytest suite. `showdown_bot/tools/calc/` — pinned `@smogon/calc`
  bridge (JS). `showdown_bot/config/` — hashed format/species/move/item config.
- `config/eval/` — panels, schedules, baselines, holdout, coverage.
  `data/eval/`, `data/datasets/` — frozen evidence. `reports/` — verdict reports.
- `showdownbot_studio/` — Godot viewer, with its own CI lanes and its own `docs/` tree.
- `.github/workflows/` — CI. `docs/` — see *Documentation placement*.

The architecture phrase *Preview → Belief → Policy → Search → Fusion* describes layers, not
directories. There is no `policy/`, `search/`, or `fusion/` package.

## Commands

```
cd showdown_bot
npm ci --prefix tools/calc --no-audit --no-fund   # calc bridge; the suite needs it
pip install -e ".[dev]"
python -m pytest                                  # full offline suite
python -m showdown_bot.cli <command> -v
```

The authoritative command list is the `choices` list in `cli.py::_build_parser` — read it there
rather than trusting any prose copy, including this one.

`pip install -e ".[learning]"` pulls lightgbm/numpy for offline reranker work only. A live run
must never import lightgbm (INV-1). If a change makes it reachable from the live path, that is a
defect, not a dependency question.

There is no linter, formatter, or type checker configured in this repository. Do not introduce one
as a side effect of another slice.

## Project invariants

INV-1…INV-7 in `docs/architecture/brain-v1-northstar.md` are binding: live-path allowlist, memory
as priors only, anytime/abortable search, one layer at a time behind an ablation gate, no LLM
anywhere, no label leakage, model-artifact safety. Read them before touching the decision path,
the learning schema, or a model artifact.

**Byte stability.** Provenance hashes in this repository are computed over *raw file bytes*
(`format_config_hash`, `file_content_hash`, `_sha256_file`). Any new file whose bytes are hashed —
config YAML/JSON, teams, fixtures, frozen evidence, pinned manifests — needs a `text eol=lf` rule
in `.gitattributes` **in the same commit that introduces it**. Without it, the same content hashes
differently on Windows and Linux and cross-platform comparisons silently compare different
configurations. This has regressed repeatedly; the rationale per rule is in `.gitattributes`.

## Scope and Claims

- Within an approved slice, proceed autonomously through all necessary implementation, tests,
  documentation, and review steps implied by its acceptance criteria. These are not scope
  expansion.
- Preserve explicit non-goals and fail-closed gates from approved specs and plans.

## Execution Default

For repository tasks, default to completing the requested task rather than merely advising what
someone else should do.

**When a plan is required:** one plan per slice, before implementation, and for any change to a
committed contract. Work inside an already-approved slice does not need a new plan — implement it.

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
- **CI is not the suite.** `.github/workflows/pytest.yml` runs a named slice smoke plus a
  two-platform provenance-bytes matrix; the Studio lanes cover Studio only. Nothing runs the full
  offline suite automatically. "CI is green" is not "the suite passed" — run
  `python -m pytest` and report what it returned.
- Report exactly what was verified locally and what was only reported by another agent or CI.

## Repository Hygiene

- Preserve unrelated user changes and local-only artifacts.
- Keep raw logs, caches, temporary diagnostics, and large external datasets out of commits unless
  an approved plan explicitly freezes them as evidence.

## Documentation placement

Store new documentation by subject under `docs/projects/<project>/`: designs and
contracts in `specs/`, implementation plans in `plans/`, audits in `audits/`,
reviews in `reviews/`, and decision records in `decisions/`. An audit reports
findings, a review judges work already done, and a decision record freezes a
ruling and the reasoning it rested on — written before the thing it authorises
happens, so a later reader can judge the reasoning against the outcome. First
instance: `docs/projects/champions/decisions/2026-07-27-gate-b-justified-repeat.md`.
Put user-facing material in `docs/guides/<topic>/` and
cross-project architecture in `docs/architecture/`. Do not recreate
`docs/superpowers/`; see `docs/README.md` and `docs/PATH_MIGRATION.md`.

`AGENTS.md` is a pointer to this file, not a copy. Do not restore prose into it.
