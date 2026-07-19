# Fast-Board Protect Discipline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.
> Steps use checkbox (`- [ ]`) syntax.

**Goal:** An env-gated, byte-identical-when-off `fast_board` Protect penalty that mirrors the
existing `endgame` Protect mechanism, targeting the atlas-confirmed Protect-spam in both-Tailwind
boards — then a Kaggle A/B + atlas re-measure to judge whether it is a real lever.

**Architecture:** thread a `fast_board: bool` context (both sides Tailwind) from `battle/decision.py`
into `battle/evaluate.py::score_outcome_with_breakdown`, exactly like `endgame`. New weight
`fast_board_protect` (default 0.0) + env `SHOWDOWN_FAST_BOARD_PROTECT_PENALTY`. Spec:
`docs/projects/core-bot/specs/2026-07-11-fast-board-protect-discipline-design.md`.

**Tech stack:** existing repo (pytest). **Constraint:** Task 1 = local, NO battles. Run only
touched test files per task; full suite once at closeout (1 strict-xfail known; calc tests need
`npm ci --prefix tools/calc`). Kaggle battles only in Task 2 (controller).

---

### Task 1: fast_board context + penalty (env-gated, byte-identical off) (Sonnet)

**Files:** Modify `battle/evaluate.py`, `battle/decision.py`, `battle/resolve.py`(if it threads
endgame), `eval/config_env.py`; tests `test_evaluate*.py` + a decision-level test + config_env test.

- [ ] Study how `endgame` is threaded end-to-end: grep `endgame` across battle/ — where it is
  COMPUTED (`decision.py`), how it flows into `evaluate_line`/`score_outcome`/
  `score_outcome_with_breakdown`, and how `endgame_protect` is applied (evaluate.py ~146). Mirror
  that path exactly for a new `fast_board: bool`.
- [ ] `EvalWeights`: add `fast_board_protect: float = 0.0` (default 0 = OFF). `OutcomeBreakdown`:
  add `fast_board_protect_penalty: float = 0.0`.
- [ ] `score_outcome_with_breakdown(outcome, our_side, weights, *, endgame=False, fast_board=False)`:
  in the SAME `if any(f.startswith(f"protect:{our_side}") ...)` block, when `fast_board` AND the
  Protect blocked nothing (`not blocked`), add `w.fast_board_protect` (and record it in the
  breakdown). Keep it ADDITIVE to the existing `protect_stall` (a wasted Protect on a fast board is
  penalized by both). Thread `fast_board` through `score_outcome` + `evaluate_line` + any caller
  in the resolver, defaulting False everywhere.
- [ ] `decision.py`: compute `fast_board = <both sides have Tailwind>` from `state.field.tailwind`
  (both `our_side` and the opp side truthy) right where `endgame` is computed, and pass it into the
  evaluation calls. Add a helper `_is_fast_board(field) -> bool` (both-Tailwind; unit-testable).
- [ ] `EvalWeights.from_env` (or wherever `SHOWDOWN_PROTECT_PENALTY` is read — grep it): read
  `SHOWDOWN_FAST_BOARD_PROTECT_PENALTY` → `fast_board_protect` (float; default 0.0 keeps OFF).
  Classify `SHOWDOWN_FAST_BOARD_PROTECT_PENALTY` in `config_env.py` (BEHAVIOR_AFFECTING) + extend
  the drift test.
- [ ] Failing tests then implement:
  - both-Tailwind outcome, we Protect + block nothing: `score_outcome(..., fast_board=True)` with
    `fast_board_protect=-2.0` < the same with weight 0.0; the breakdown carries the penalty.
  - a Protect that BLOCKS a hit on a fast board → NOT extra-penalized (only wasted Protects).
  - single-Tailwind / no-Tailwind (`fast_board=False`) → unchanged regardless of the weight.
  - `_is_fast_board`: both-Tailwind True; one-side / none False.
  - **byte-identical-off:** with the env unset (weight 0.0), a fixture decision's score/choice is
    identical to before (a golden value or an equality vs weight-absent).
  - config_env: the new env classified; drift test green.
- [ ] Run touched tests. Commit `feat(play-quality): env-gated fast-board Protect penalty (atlas-aimed)`.

### Task 2 (controller-orchestrated): Kaggle A/B + atlas re-measure

- [ ] A both-Tailwind-inducing eval schedule (or reuse panel_v001 — several teams set Tailwind;
  confirm a decent both-Tailwind rate) run TWICE on Kaggle: `SHOWDOWN_FAST_BOARD_PROTECT_PENALTY`
  OFF vs ON (same seeds, Channel A). Pull results.
- [ ] **Behavioral (light):** diagnostics-v0 `bucket_delta` on the two runs' hero logs — does the
  over-defensive habit drop? + winrate sanity.
- [ ] **Atlas re-measure (principled):** a focused both-Tailwind datagen re-label with the flag ON
  (small schedule), re-run `teacher_disagreement`, compare `tailwind_both` disagreement rate / mean
  regret vs the committed 92% / 9.19. Report the delta.
- [ ] Verdict: lever (disagreement + over-defensive habit drop, winrate holds) OR depth-bound
  (flat → belief/search motivation). Commit evidence + a short report either way.

### Task 3: closeout

- [ ] Full suite once: green + 1 xfailed (known). Report `reports/2026-07-11-fast-board-protect-discipline.md`
  with the change, the A/B + atlas-re-measure numbers, and the honest lever-vs-depth verdict.
- [ ] `git diff main --stat` → merge decision. (Even a "no lever" result merges the env-gated code
  OFF-by-default + the honest report — it is a documented negative + a belief/search motivator.)

## Self-review (writing-plans)

- Spec coverage: mechanism-1 penalty→Task 1; measurement→Task 2; verdict→Task 3. ✓
- Byte-identical-off preserves the dataset/atlas/recorded runs + all tests. ✓
- Mirrors the proven `endgame` Protect mechanism (low-risk pattern). ✓
- Honest scope: attacks the tunable Protect half only; pivot-depth explicitly deferred. ✓
- Principled gauge (atlas, not confounded winrate-vs-max_damage). ✓
