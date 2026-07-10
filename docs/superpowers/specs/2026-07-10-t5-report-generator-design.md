# 2b-3.5 T5 — Report Generator — Design

> One slice (user decision 2026-07-10), clear module boundaries. Implements the T5 half of the
> reviewed architecture `docs/superpowers/reviews/2026-07-01-fable-t5-t6-eval-architecture-review.md`
> — that artifact carries the full statistical rationale; this spec pins the promoted decisions and
> the module/API shape. T6 (ledger, baseline manifest, held-out runner) is explicitly NOT here.

**Goal:** A deterministic report generator that turns one or two eval runs into an auditable
readout: safety gates before statistics, per-cell Wilson tables, and (paired mode) exact-binomial
McNemar with the positive-evidence-only verdict rules. Its two most important outputs are the
provenance audit and the discordant-battle list — the statistics are deliberately conservative.

**The asymmetric core rule (from the review, §10):** the override needs POSITIVE evidence of
improvement; absence of evidence never unblocks anything. "No significant difference" is never
safety evidence. Every verdict path below encodes this.

## 1. Modules

### 1.1 `eval/stats.py` — pure statistics, stdlib only
- `wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]` — Wilson score
  interval on a proportion; ties count as losses upstream (the function sees wins/n only).
- `exact_binom_two_sided_p(k: int, n: int) -> float` — exact two-sided binomial test at p=0.5 via
  `math.comb` (sum of all outcome probabilities ≤ prob(k)). No scipy/numpy/chi-square — the
  chi-square approximation is invalid at this N.
- `mcnemar_counts(pairs) -> McnemarCounts` — dataclass `n11/n00/n10/n01` (+ properties
  `n_discordant`, `delta = (n10-n01)/N`); ties land in `n00` (not-a-win).
- **Pinned verdict constants (code, with rationale docstrings — review §3/§4):**
  - `N_DISCORDANT_MATH_FLOOR = 6` — below this the exact test cannot reach p<0.05 at all.
  - `N_DISCORDANT_CLAIM_MIN = 10` — minimum for ANY claim in a verdict line.
  - `LOSING_CELL_WILSON_UPPER = 0.5` — a cell whose Wilson upper bound < 0.5 is a "losing cell".
  - `TIE_FLAG_RATE = 0.02` — tie share above this gets flagged (degeneracy suspicion).
- Pinned test values: `exact_binom_two_sided_p(6, 6) == 0.03125`; `(5, 6) → 0.21875`;
  Wilson checked against known published values.

### 1.2 `eval/pairing.py` — the pairing validator (review §2)
- `RunBundle` (see §1.3) pairs of rows in, validated `Pair` list out:
  `pair_runs(bundle_a, bundle_b) -> list[Pair]` with `Pair(battle_id, cell, hero_win_a,
  hero_win_b, row_a, row_b)`; `cell = (opp_policy, opp_team_hash)`.
- Fail-fast (each its own exception subclass of a common `PairingError`), never warn-and-continue:
  - pairability: `schedule_hash`, `seed_base`, `panel_hash`, `format_id` must match across runs;
    **`config_hash_A == config_hash_B` → refuse** (self-comparison reads as "perfectly stable").
  - per-pair `seed_a == seed_b` (must hold by construction; mismatch = corrupted data).
  - row identity `(battle_id, config_hash)` unique per run; duplicates fail.
  - missing pairs → refuse the WHOLE analysis (dropping = selection bias correlated with crashes).
  - row count == schedule rows for each run.
- `hero_win = (winner == "hero")`; tie = not-a-win everywhere; tie counts reported separately.

### 1.3 `eval/report.py` — the deterministic generator (review §5/§8)
- **Input = `RunBundle`:** paths to result JSONL + its `.manifest.json` sidecar + seed log +
  schedule YAML + panel YAML. Single-bundle call → single-run report; two bundles → paired report.
- **Audits its inputs, never trusts rows (review "closing calibration"):** re-runs
  `verify_schedule_alignment` on the seed log; recomputes panel_hash from the panel file and team
  content hashes from the team files; computes input-file sha256s for the provenance block;
  cross-checks rows against the manifest sidecar (run_id, config_hash, seed_base, git_sha, dirty).
- **Safety gates FIRST (any FAIL → no strength claims anywhere in the report):** invalid>0;
  crashes>0; any `end_reason != normal`; p95 latency > `eval/gates.load_latency_budget_ms()`
  (FAIL for gate runs, WARN for dev smokes — mode flag); any `dirty` row (same FAIL/WARN split);
  panel_hash null/mismatch; seed-log misalignment; any non-reproducible policy row; row-integrity
  (count, duplicates, non-constant config/schedule/panel hash within a run); split integrity
  (held-out hash in a dev-labeled run or vice versa).
- **Verdict vocabulary (first line of every report):**
  - Paired mode: `SAFETY-FAIL` > `UNDERPOWERED` (n_discordant < N_DISCORDANT_CLAIM_MIN) >
    `GO` (delta > 0 AND exact p < 0.05 AND n_discordant ≥ 10 AND no losing-cell flip AND no
    weak-policy-only improvement) > `NO-GO` (everything else). Worst-cell callout always on the
    verdict line; losing cells listed in the verdict, not just the table.
  - Single-run mode: only `SINGLE-RUN SAFETY-PASS` / `SINGLE-RUN SAFETY-FAIL` — **a single run can
    never produce a GO** (non-comparative by construction).
  - `n_discordant == 0` is explicitly reported as ambiguous ("behaviorally identical OR mislabeled
    duplicate") — never as stability evidence.
- **Report sections in fixed order (both md and json):** verdict line → provenance block (every
  hash, run_ids, row counts, input sha256s, git shas + dirty) → safety-gates table with measured
  values → per-cell table (n, W/L/T, win rate, Wilson CI) → aggregates (per-policy pooled +
  overall pooled + unweighted cell mean side by side; losing-cell list) → paired section
  (n11/n00/n10/n01, delta both forms, exact p, underpowered banner, **discordant-battle list
  whenever n_discordant ≤ 12**: battle_id, cell, turns, end_hp_diff per battle) → mandatory
  warnings → reproduction block (exact CLI + env to regenerate runs and report).
- **Mandatory verbatim texts as code constants:** the UNDERPOWERED phrasing ("UNDERPOWERED: only
  k discordant pairs. No conclusion is possible in either direction. This is not evidence of
  equivalence and must not be cited to unblock 2b-4."), ceiling-effect caveat, scripted_vgc =
  coverage-not-strength, paired-seeds-diverge-after-first-differing-choice caveat, DEV/HELD-OUT
  banner ("HELD-OUT RUN — these numbers must never inform tuning decisions." when any row is
  heldout-labeled).
- **Determinism:** same input files → byte-identical `report.md` and `report.json`. No wall-clock
  timestamps in the body — all times come from the run manifests. `report.json` carries
  `schema_version: 1` for future gate automation.
- **Never present two-config results as side-by-side independent CIs without the paired section
  adjacent** (review §10.3) — structurally enforced by section order.

### 1.4 CLI
`python -m showdown_bot.cli eval-report --run-a <results.jsonl> --seedlog-a <log> [--run-b ...
--seedlog-b ...] --schedule <yaml> --panel <yaml> --out <dir> [--mode gate|dev]` (default `gate`;
`dev` downgrades ONLY the latency and dirty gates to WARN per §1.3) → writes `report.md` +
`report.json`; exit 0 on SAFETY-PASS/GO/NO-GO/UNDERPOWERED, exit 1 on SAFETY-FAIL (the exit code
signals safety, not strength). Manifest sidecars are found via `<run>.manifest.json` convention.
The runs' `--result-out` naming from T2 stays untouched.

## 2. Test strategy (three tiers)

1. **Stats unit tests** against pinned known values (see §1.1) — pure, no I/O.
2. **Synthetic fixtures** (constructed row dicts / tiny JSONL files) for: every `PairingError`
   class; every verdict path (GO, NO-GO, UNDERPOWERED, SAFETY-FAIL, ambiguous-zero-discordant,
   losing-cell flip blocking GO, weak-policy-only improvement blocking GO); tie handling + tie
   flag; FAIL/WARN mode split for latency and dirty. Necessary because the real fixture is a
   single config — the validator must REJECT pairing it with itself (that rejection is itself a
   test).
3. **Golden report** against the committed real fixture `data/eval/t4/rerun/` (run 1 bundle,
   single-run mode): the generated `report.md`/`report.json` are committed as
   `data/eval/t4/rerun/golden-report.{md,json}` and the test asserts byte-identical regeneration.
   Expected verdict: `SINGLE-RUN SAFETY-PASS`.

## 3. Requirements (testable)

- **R1** `eval/stats.py` functions match the pinned values; constants exist with docstrings.
- **R2** Every pairing violation from §1.2 raises its specific error; a valid synthetic pair set
  round-trips into correct McNemar counts.
- **R3** The generator refuses to emit any strength claim when any safety gate fails (verdict
  SAFETY-FAIL, no GO/NO-GO text anywhere).
- **R4** UNDERPOWERED verdict + verbatim banner whenever n_discordant < 10; no p-value on the
  verdict line in that case; discordant list present whenever n_discordant ≤ 12.
- **R5** Byte-identical regeneration (golden test, run twice in the same test).
- **R6** The generator detects tampered inputs: a mutated seed-log line, a panel file whose hash
  no longer matches rows, and an edited result row (seed/seed_index/schedule fields — caught by
  recomputing `battle_id` and the seed derivation per row) must each surface as SAFETY-FAIL or a
  load-time `ReportInputError` — proven by tests that tamper copies of the real fixture.
  **Documented limitation (amended 2026-07-10 during Task 3):** a PURE winner flip in the result
  JSONL is undetectable — the manifest carries no per-row integrity hashes and the audit does not
  re-parse room_raw. A test pins this limitation explicitly. An `end_hp_diff`-sign-consistency
  heuristic was considered and REJECTED (unsound: a coordinated flip passes; the forfeit/timeout
  exclusion paths would ship untested). Threat model: accidental corruption and process bugs, not
  adversarial edits by the repo owner.
- **R7** Single-run mode on the committed T4-rerun fixture yields `SINGLE-RUN SAFETY-PASS` with
  the per-cell table matching the T4-rerun report's numbers.
- **R8** Full suite green (688 baseline); no `battle/` changes; stdlib-only (no new deps).

## 4. Out of scope

T6 entirely (held-out ledger, access budget, runner refusals, baseline manifest + reproduction
spot-check, held-out gate runs); any 2b-4 verdict automation beyond the report itself; panel
growth; new schedules or runs; changes to result_jsonl writer or CLI gauntlet path.

## 5. References

- Full rationale: `docs/superpowers/reviews/2026-07-01-fable-t5-t6-eval-architecture-review.md`
  (§2 pairing, §3 McNemar + power floor, §4 Wilson + anti-hiding, §5 gates, §8 report, §10
  adversarial failure modes).
- Carried-forward decisions honored: report generator independently re-verifies its inputs;
  thresholds as spec constants; exact binomial, not chi-square (T3f plan, "Carried-forward").
- Fixture: `data/eval/t4/rerun/` (126 sha256-pinned files, T4-rerun PASS run).
