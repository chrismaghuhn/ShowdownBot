# 2b-3.5 T4b — Forced-Replacement Determinism — Design

> Fix slice for the T4 reproduction-gate FAIL (`reports/2026-07-10-2b35-T4-smoke.md`). Touches
> `battle/` (INV-1 live path) — user-approved design (option C, 2026-07-10): fix the enumeration
> AND make the last-resort fallbacks deterministic. Acceptance = full T4 re-run passing 21/21
> gates + 10/10 prefix + 51/51 double-run reproduction.

## 1. Problem

T4 proved the eval pipeline at scale (21/21 gates) but battle-level reproduction failed: 48/51
across two full runs, 9/10 on the prefix re-run. All divergences (seed_index 9, 19, 48) begin at a
**post-faint forced-replacement `|switch|` line**; server seed logs are byte-identical across runs,
so the nondeterminism is purely client-side. Run 1's client log shows **4 mid-battle**
`heuristic failed, falling back: no legal joint actions` warnings whose fallback then succeeded
(3 divergent battles + 1 coincidental same pick — binary-choice randomness).

## 2. Root cause (what is proven, what is pinned by test)

**Proven in code:**
- **RC-1 (double replacement):** `enumerate_my_actions` (`battle/actions.py:112-116`) drops ALL
  switch+switch joint actions when `allow_double_switch=False` (the default). The prune was meant
  for *voluntary* double switches but also kills *forced* double replacements, where switch+switch
  is the only legal shape → empty list → `ValueError("no legal joint actions")`
  (`battle/decision.py:233`).
- **RC-2 (nondeterministic endpoint):** when the heuristic raises, `choose_with_fallback` calls
  `max_damage_choice` (`decision.py:627`), whose `enumerate_my_actions(req)` fails the same way, so
  its INTERNAL default fallback returns `pick_random_pair(req)` (`battle/baselines.py:43-44`) —
  and `pick_random_pair` defaults to an **unseeded `random.Random()`**
  (`battle/random_agent.py:10-11`). (This is why no "max_damage fallback failed" warning appears:
  max_damage *succeeds* by returning the random pick. The committed T4 report describes the chain
  as falling through to `decision.py:632`; the observable endpoint — unseeded `pick_random_pair` —
  is the same, but the hop happens one level earlier. The T4b report carries a one-line erratum.)
- **RC-3 candidate (single replacement / one-bench double):** the single-replacement enumeration
  path (`legal_actions._slot_move_actions:64-68` → `_bench_switch_targets:21-30`) looks correct in
  isolation, yet battles 19/48 diverged at *single* replacement switches. A further hole exists —
  e.g. a double-forced phase with one bench mon, where the same-target filter
  (`actions.py:112-114`) empties the pair list. **The exact shape is NOT guessed in this spec:**
  the real `|request|` JSON frames of the divergent battles are committed in
  `data/eval/t4/room_raw_divergent/` (gunzip → the `|request|` lines preceding the divergent
  `|switch|`), and the implementation plan MUST reconstruct failing tests from those recorded
  requests first.

## 3. Design (approved option C)

### 3.1 Enumeration fix — `battle/actions.py`
- The voluntary-double-switch prune applies ONLY outside force phases:
  `if not allow_double_switch and not in_force_phase: continue` (the always-illegal same-target
  filter stays unconditional).
- Whatever RC-3 turns out to be (from the recorded-request failing tests): after the fix,
  `enumerate_my_actions` returns a **non-empty** list covering the legal replacement assignments
  for EVERY force-switch request shape observed (single forced slot; double forced with ≥2 bench;
  double forced with exactly 1 bench — where the legal shape is one switch + one pass, in either
  slot order the server accepts).

### 3.2 Heuristic evaluates replacements — no new code path
The enumerated replacement joint actions flow through the EXISTING evaluation pipeline
(`_choose_best_ja` → plans → `score_outcome`), exactly like voluntary switches on normal turns.
Deterministic tie-break = the existing `pick_best` enumeration-order behavior. If the pipeline
turns out to assume `req.active` is present (force requests carry no `active` block), that
assumption is fixed as part of this slice — exposed by TDD, not worked around by re-raising into
the fallback.

### 3.3 Deterministic last-resort fallbacks
- New `pick_default_pair(req) -> SlotPair` in `battle/random_agent.py` (beside `pick_random_pair`):
  returns `enumerate_slot_pairs(req)[0]` (enumeration order is deterministic), raising the same
  `ValueError("No legal actions for request")` when empty.
- `choose_with_fallback` last resort (`decision.py:632`): `pick_random_pair` → `pick_default_pair`.
- `max_damage_choice._default_fallback` (`baselines.py:43-44`): `pick_random_pair` →
  `pick_default_pair`. This deliberately supersedes the T3c note "default None preserves
  pick_random_pair behavior byte-for-byte" — that promise is the bug. Docstring updated.
- The fallback chain itself (heuristic → max_damage → last resort → `/choose default`) stays —
  safety floor unchanged (INV-1/INV-3); only its endpoint becomes deterministic, so ANY future
  enumeration hole degrades to deterministic-but-dumb instead of nondeterministic.

### 3.4 Explicitly unchanged
- `pick_random_pair` itself and the `random` villain policy (stays random; registry
  `reproducible=False` unchanged; still excluded from seeded schedules).
- Fallback ordering/logging, `/choose` encoding, schedule/battle_id identity, eval/opponents
  policies, panel, T4 matrix/schedules.

## 4. Requirements (testable)

- **R1** For every recorded force-switch request from `data/eval/t4/room_raw_divergent/` (and
  synthetic variants: single forced, double forced ≥2 bench, double forced 1 bench, forced with
  trapped/fainted edge), `enumerate_my_actions` returns a non-empty legal set. The previously
  raising shapes are regression-locked.
- **R2** `heuristic_choose_for_request` on those requests returns a valid `/choose` string,
  identical across repeated calls in fresh processes (determinism), chosen via evaluation (not
  fallback) — asserted by the absence of the fallback warning.
- **R3** `pick_default_pair` is deterministic and equals the first `enumerate_slot_pairs` entry;
  both fallback call sites use it; `pick_random_pair` remains unseeded-random and unreferenced by
  the fallback path.
- **R4** Full existing suite stays green (676 at time of writing) — including 1c
  `decide_adapter`/rollout tests (synthesized force-switch requests now enumerate; teacher-rollout
  label changes are acceptable and expected, but tests must pass as written or be updated with
  documented reasoning in the plan).
- **R5 (acceptance)** Full T4 re-run with the existing runbook and schedules, on the FRESH seed
  base `t4rerun2026` (so re-run artifacts can never be confused with the failed run's; the
  schedules and matrix stay identical): 21/21 pipeline gates PASS, prefix
  reproduction **10/10**, full double-run **51/51** byte-identical (normalized, name-canonicalized),
  0 mid-battle fallback warnings. The re-run report supersedes the FAIL verdict; its artifacts
  become the T5 fixture.

## 5. Consequences (accepted)

- **Live behavior changes:** replacements are now evaluated instead of random. Pre-fix runs are
  not comparable across the fix (T5/T6 handle this via the baseline manifest's git_sha +
  reproduction spot-check). T4 reference numbers get superseded by the re-run.
- **Offline teacher/rollouts** (`learning/decide_adapter` synthesizes force-switch requests)
  inherit the fix — rollout labels may shift; datasets are regenerated in 2b-2.5 anyway.
- The bug class (unseeded randomness reachable from the live decision path) is closed by
  construction; a drift test idea for later (T5-era, not this slice): grep-gate that
  `battle/` never calls `random` outside `random_agent.py`.

## 6. Out of scope

No policy tuning, no new evaluation features, no panel/schedule/matrix changes, no T5 statistics,
no changes to eval/opponents, no dataset regeneration. The T4 re-run reuses the existing committed
schedules and runbook verbatim.

## 7. Testing strategy

1. **Fixtures from reality:** extract the `|request|` frames immediately preceding each divergent
   `|switch|` from the committed gzipped logs (battle 9 run1/run2/prefix, battles 19/48 run1/run2)
   → parametrized failing tests (RC-1 + RC-3 pinned exactly).
2. **Unit determinism:** repeated-call identity for enumeration, heuristic choice, and
   `pick_default_pair`; double-forced-one-bench shape produces a legal switch+pass.
3. **Fallback wiring:** with a stubbed always-raising heuristic and max_damage, the final choice is
   deterministic across calls.
4. **Live acceptance:** the R5 re-run (three server runs: full, prefix, full2), gate checker +
   comparison scripts from T4 (scratchpad rerun), new report
   `reports/<date>-2b35-T4-rerun.md` + supersession note in git history; erratum line for the
   RC-2 detail.
