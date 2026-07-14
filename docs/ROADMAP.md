# Canonical Roadmap & Status

**Living document — update as slices land, don't let it drift.** This supersedes the old
layered plans (README, `docs/heuristic_bot/`, and the external `../TestBOtpläne/00-14`
Northstar docs) as the single source of truth for *current status and next decision*.
`TestBOtpläne/` remains valid for deep design rationale on things already built, but it is
**not versioned with the code** and must not be read as an up-to-date execution plan —
verify against this file and git history first.

**New agents:** start with [`docs/PROJECT_INDEX.md`](PROJECT_INDEX.md) for orientation; this
roadmap remains the authoritative status matrix.

Last reconciled: 2026-07-14 (Champions panel v0 P4 pilot smoke PIPELINE-READY, clean provenance), against an external strategic review (adopted with two
corrections, see "Corrections to the external review" below) and this session's own verified
state (depth-2 slice, value-calibration spec).

## Status matrix

| Vorhaben | Status | Evidenz | Nächste Entscheidung |
|---|---|---|---|
| Reranker v1 (dataset/infra, 2b-2.5a) | **Built, in use** | merged `afb9708`; feeds `outcome_join` + value-calibration | keep as foundation, not "parked" |
| Reranker v1 **live override** | **NO-GO** | 2b-4 report: +13 net vs max_damage, McNemar p=0.105 n.s. | not shipped; don't re-attempt without new evidence |
| Scalar aggregation (λ tuning) | **NO-GO** | 4 experiments, see detail table below | stop; no more global-λ experiments |
| +Sampling machinery (K-world) | **Built, off** | latency report: linear-in-K, max K=8 local | hold until calibrated posterior exists (P2/P3) |
| Depth-2 search | **Stage 1+2 GO, merged local main** | `2026-07-12-2c-depth2-derisk-verdict.md` | Stage 3 blocked on TWO things: the panel actually being *run* (below), AND the accuracy chosen-line cap/fallback gate FAIL (row below) being re-derisked first |
| Generalisation analyzer (05) | **Built (tool only)** | merged `35956df` | materialize the actual archetype×opponent panel — data doesn't exist yet |
| VGC-Bench ingestion | **Part A done** | `6210e4d` | Part B (player-perspective, OTS-vs-reveal, legality, leakage audit) |
| Value calibration study | **Spec Revision 2 committed** (T3A arm, disjoint verdict, outcome-encoding, sklearn dep, fold-local categorical encoding all addressed) | `docs/superpowers/specs/2026-07-12-value-calibration-design.md` Rev 2, commit `8e4c47f` | implementation plan once Rev 2 explicitly signed off |
| Outcome-join (04) | **Built** | merged `725257e`/`fea284b`; 299-game reference smoke | consumed by value-calibration study |
| Teacher-disagreement atlas | **Built** | `5830e9e` | diagnostic only — not a strength gate |
| Diagnostics-v0 | **Built** | `849b5c7` | diagnostic only — not a strength gate |
| Belief (item/spread/move priors) | **Not started** | — | P2, after the panel + data-identity fix |
| Value-head (trained model) | **Not started, gated** | — | only after value-calibration says GO |
| PPO/full self-play RL | **Not started, deliberately deferred** | ps-ppo-reference eval | P5, after search/belief/value-labels stabilize |
| Accuracy / hit-probability evaluation | **Default-on safety-clean; strength UNDERPOWERED (unfavorable direction, no claim)** | Gate-B cap=6 PASS 6/944=0.64%; default-on live dev-strength A/B @ `a956b6b` (`reports/2026-07-14-accuracy-default-on-devstrength-verdict.md`: SAFETY-PASS, n_discordant=6, 0 A-only / 6 B-only discordants — follow-up risk signal, not regression proven) | `SHOWDOWN_ACCURACY_MODE` **default-on** when unset; cap **6**; explicit opt-out unchanged; **no GO on strength** — next step user-gated (larger strength run vs Champions-readiness) |
| Champions panel v0 (format target) | **P4 PASS — PIPELINE-READY** | P0–P3 on main; P4 dev-only smoke @ `04b0eb7` (`dirty=false`): 6/6 rows, crashes=0, invalid=0; schedule `e8a58dc`; verdict `reports/champions-panel-v0-pilot-smoke.md` | **FormatConfig + Champions move parser** before strength/decision-quality; rain held-out blocked (Solar Beam target gap) |

### Scalar-aggregation experiments (detail — the status-matrix row summarizes these four)

| Experiment | Dev-strength result | Held-out result | Evidence | Merged to main? |
|---|---|---|---|---|
| `must_react_lambda` 0.6→0.8 | +11.3pp vs `max_damage`, p=0.0002 (concentrated in the **sun** cell) | **NO-GO**: n_discordant=0, delta=0.0 exactly, both arms 7/34 — does not generalize | `reports/2026-07-12-heldout-mustreact08-verdict.md` | Yes |
| `risk_lambda` 0.5→0.75 (↑, more variance-penalty) | **−12.67pp regression** — never a dev-GO | not sent to held-out (already dev-NO-GO, nothing to spend held-out on) | 2c-aggregation-investigation memory (0a probe) | Yes |
| `risk_lambda` 0.5→0 / CVaR-mean-control (↓, drop the variance-penalty) | +36.0pp vs `max_damage`, p<0.0001 (concentrated in **trickroom/rain**) | **NO-GO**: n_discordant=8, delta=0.0000 exactly — does not generalize | `reports/2026-07-12-cvar-neutral-devstrength-3arm.md` | **No — `feat/slice-2c-cvar-neutral`, pushed to origin, NOT merged to local main** (see review-process note below) |
| Fast-board Protect-penalty | paired rain A/B: `tailwind_both` 91.7%→90.2% (worse), regret 9.26→9.44 (worse) | not sent to held-out (already offline/atlas NO-GO) | `reports/2026-07-11-fast-board-protect-discipline.md` | Yes |

**Net:** the two large `max_damage`-only dev wins (`must_react_lambda=0.8`, `risk_lambda=0`) both collapsed to *exactly* zero on held-out — both were team-archetype-specific and neither generalized. Combined with `risk_lambda=0.75`'s outright dev regression and fast-board's offline NO-GO, **global scalar tuning is exhausted as a strength lever** — this verdict holds independent of the cvar-neutral merge-status housekeeping item below.

## Corrections to the external review that produced this roadmap

1. **Git state is not "95/98 commits ahead" — it's a genuine divergence**, verified 2026-07-12:
   `git rev-list --left-right --count origin/main...main` → `1  95`. The one origin-only
   commit (`8b54fc0`, GitHub PR #2 merge of `feat/slice-fast-board-protect`) is
   **content-identical** to a commit already in local main (`7d0bf81` — same slice, merged
   twice via two different paths, two different merge SHAs). Not data loss, but a real
   push-will-be-rejected situation requiring reconciliation before any push. The
   ~95 locally-only commits (2c-aggregation onward: +Sampling, 05-generalisation, depth-2,
   outcome-join, value-calibration spec) are the real backup-risk the review correctly
   flagged. **Reconciliation + push is autonomous-implementer territory, not done here.**
2. **"Reranker v1 → NO-GO, parken" conflates two things.** The reranker *dataset/feature
   infrastructure* (2b-2.5a) is built, merged, and is the direct foundation `outcome_join`
   and the value-calibration study sit on — it is not dead. What is NO-GO is specifically
   *letting the reranker override the live heuristic's choice* (2b-4). Park the override
   idea; keep the infrastructure.
3. **Follow-up review-process note (2026-07-12, same day):** a later review pass flagged
   `docs/ROADMAP.md` as "untracked" and the value-calibration spec as "needs T3A/disjoint-
   verdict/encoding/sklearn revisions" — both checked against the live repo and found
   **stale relative to this session's own commits**: `docs/ROADMAP.md` was already committed
   (`e9ad6fa`) before that pass, and the spec's Revision 2 (`8e4c47f`) already addresses
   exactly those five items. Likely a timing gap between the review snapshot and this
   session's commits, not a real defect — noted here so the history stays legible. What
   *was* a real, new finding from that same pass: the `risk_lambda=0`/CVaR-mean held-out
   evidence lives on an **unmerged** branch (`feat/slice-2c-cvar-neutral`) — folded into the
   scalar-aggregation detail table above. Merging that branch (or copying its report into
   main) is open housekeeping, not done here (touches git state, needs explicit go-ahead).

## P0 — Integrität und Entscheidungsgrundlage

1. **`candidate_id`/chosen-Kollision beheben.** 253/3302 decisions in `phase3-slice2b25a`
   share action-identity across distinct switch targets (verified this session — not a
   score tie, a writer-side identity bug; root cause is in the feature-extraction pipeline,
   not something the calibration study itself can fix). Real, scoped follow-up; can run
   **in parallel with** the value-calibration study, which was deliberately designed to
   detect-and-exclude these rows without needing the underlying bug fixed first — the two
   are not a hard sequential dependency despite the natural reading order.
2. **Value-calibration study: finish.** Spec written (`5981ccb`), awaiting sign-off →
   implementation plan → run. Primary on the 3049 unambiguous decisions, State-only
   sensitivity on all 3302, game-clustered bootstrap, LOTO-by-team_hash. Positive outcome
   = GO for *counterfactual data collection*, not proof a value-head is justified.
3. **This file.** Keep it current; supersede ad-hoc roadmap prose scattered across memory
   entries and old planning docs.
4. **Reproducibility rounding-out.** Python/Node version pins, dependency/lockfile hashes,
   `tools/calc/package-lock.json` provenance, OS/arch, optional container digest. Env
   provenance partially built (T4c hardening); lockfile/container side still open.
5. **Wire `AccuracyDiagnostics` into `DecisionTrace`.** The accuracy/hit-probability slice
   (merged `3fd3b09`) implemented and unit-tested `battle/evaluate.py::accuracy_diagnostics`
   (ko/survival probability, accuracy-required, miss-punish-value) as a standalone function —
   deliberately NOT wired into any live caller during that slice (the trace-assembly code in
   `decision.py` wasn't read/verified as part of that scope, and guessing at the schema was
   judged worse than shipping a clean, tested, unused function). Explicit open item, not a
   silent gap: either add an `accuracy_diagnostics: AccuracyDiagnostics | None = None` field to
   `DecisionTrace` (populated only when `accuracy_mode` is on) or explicitly re-confirm it's
   still not needed — do not let this disappear. Natural to fold into the start of Depth-2
   Stage 3 (P1) if that lands first, since both touch the same trace-assembly code path.
   **Update 2026-07-13 (accuracy-offline-gate plan, spec §2.4):** `CandidateTrace.accuracy_details`
   now makes per-candidate raw accuracy telemetry (`accuracy_leaf_count`,
   `accuracy_branch_cap_hits`, `events_complete`, tie-order breakdowns) reachable on
   `DecisionTrace` — this **partially** addresses this item (the raw ingredients are now on the
   trace) but does **not close it**: `accuracy_diagnostics()` itself (the
   ko/survival-probability/`accuracy_required`/miss-punish-value function) still isn't called
   from any live decision-code caller. See
   `reports/2026-07-13-accuracy-offline-gate-verdict.md` and the design spec's own §2.4 framing
   ("does not close the whole item").
6. **Accuracy chosen-line cap/fallback re-derisking (new, opened by the 2026-07-13 offline-gate
   FAIL result).** The real Gate B run over the full 85-battle/944-decision deduplicated corpus
   found a chosen-line cap-hit rate of 12.9% (114/881), decisively above the gate's pinned 5%
   threshold — i.e. `SHOWDOWN_ACCURACY_BRANCH_CAP`'s default (4) and/or the current always-hit
   fallback-on-cap behavior is being hit far more often than the safety margin assumed when that
   default was pinned (see `reports/2026-07-12-accuracy-slice-latency-gate.md`). This is not
   fixed by this plan — it is the plan's own headline finding, reported honestly per the user's
   explicit instruction not to interpret or soften it.
   **Concrete next step, offline first:** on the SAME 85-battle corpus, compare
   `SHOWDOWN_ACCURACY_BRANCH_CAP` values (6 and 8 are the natural next probes) and/or a less
   optimistic cap-fallback strategy against today's always-hit-on-cap default, each measured on
   the SAME two axes the gate already reports: chosen-line cap-hit rate and real latency (not
   just one or the other — a lower cap-hit rate that blows the latency budget isn't a fix). Only
   after that offline comparison, re-run the EXISTING accuracy-offline-gate (`eval/accuracy_gate_b.py`
   + `accuracy_gate_stats.py`) **unchanged** against whichever cap/fallback choice looks best —
   do **not** retroactively loosen the pinned 5% threshold to make a result pass; the threshold
   was pinned before this run per spec §4 and must stay pinned across this follow-up too.
   **Also open, don't let it quietly disappear:** the 63/944 decisions Task 10's
   `_chosen_candidate` correctly excluded as ambiguous-`candidate_id` (`decision.py`'s `_label_ja`
   collapses different switch targets in the same slot to the identical label, e.g.
   `"(Knock Off->1, switch)"`) need their own separate diagnosis — the gate's FAIL verdict is
   robust to worst-case treatment of these 63 (12.1%–18.8% either way, still decisively above 5%),
   so this is not blocking the verdict above, but the underlying `_label_ja` non-injectivity is a
   real gap in `decision.py`'s candidate labeling that this plan deliberately did not fix (guarded
   at the gate-consumption layer only, per Task 10's own scoping) — these 63 decisions must not
   simply vanish from future decision-diff/accuracy analyses; they need either a `_label_ja` fix
   (switch target disambiguation) or an explicit, tracked sampling/analysis plan of their own.
   **Update 2026-07-13 (accuracy-cap-derisk plan, the concrete next step above, now done —
   `reports/2026-07-13-accuracy-cap-derisk-verdict.md`):** the offline comparison this item asked
   for was run for real, on the same 85-battle/944-decision corpus. **Cap-hit rate: both cap=6 and
   cap=8 PASS the pinned 5% threshold decisively** (numerator 6/881 = 0.68% point estimate, 1.37%
   bootstrap upper bound — both numerically **identical** between cap=6 and cap=8, i.e. cap=8 buys
   zero additional fidelity over cap=6 on this corpus), versus cap=4's frozen 114/881 = 12.9% FAIL
   (cited unchanged, never recomputed). **Zero chosen-action changes** at cap=6 or cap=8 relative
   to cap=4 (only score movement, 115/118 decisions respectively) — raising the cap only refines
   scores here, it never flips a winner on this corpus. **Latency: both cap=6 and cap=8, both
   trace modes, PASS the existing ×5-scaled 1000ms gate on this real corpus** (worst case
   `cap8_trace_enabled` p95×5 ≈ 968ms, a thin ~3.2% margin) — this **disagrees with** the earlier
   accuracy-hit-probability slice's single-board bench, which found cap=6/cap=8 FAILing the same
   scaled gate (`reports/2026-07-12-accuracy-slice-latency-gate.md`); the disagreement is
   attributed to that board being deliberately built to stress accuracy branching harder than this
   real corpus's average decision, not resolved as a contradiction — flagged for whoever weighs a
   real Kaggle-hardware check, since the ×5 multiplier itself is an estimate, not a measured
   constant. **The ambiguous-candidate diagnosis asked for above is now done too:** all 63 excluded
   decisions, at all three caps, classify identically as `label_collision`/`switch_target_omitted`
   (100%, zero `other_pipeline_error`, zero `chosen_candidate_missing`), and the exclusion set is
   completely cap-invariant (`all_three=63`, `cap4_only=cap6_only=cap8_only=0`) — confirming this
   is a pure `_label_ja` labeling defect, not a cap artifact. A fix-feasibility investigation
   (no code change) recommends a stable structural candidate key (per-slot `(kind, move_index,
   target, target_ident, terastallize)`) as the preferred long-term fix, needing either a new
   `DecisionTrace.chosen_joint_action`-style field or a key assigned at enumeration time — still
   unimplemented, still open. **Per the report's own explicit framing: none of the above is a
   default-on decision, a strength claim, or Depth-2 Stage 3 work** — raising
   `SHOWDOWN_ACCURACY_BRANCH_CAP`'s default, fixing `_label_ja`, and resolving the latency-margin
   disagreement (possibly via a real Kaggle-hardware check) all remain separate, explicit,
   user-owned next steps, not scheduled by this update.
   **Update 2026-07-14 (candidate-identity slice merged, Gate-B cap=6/cap=8 re-run on
   `9f64c28`):** the structural candidate-key resolver (`candidate_identity.py`) is now live on
   `main`. Re-running `run_cap_gate_verdicts.py` over the same 85-battle corpus with the unchanged
   `run_gate_b` path changes the Gate-B denominator from **881 → 944** (the 63 historically
   ambiguous-`candidate_id` decisions now resolve cleanly; **0 exceptions** vs the prior 63).
   **Cap=6 and cap=8 remain PASS** at **6/944 = 0.64%** point estimate (bootstrap upper ≈ 1.36%,
   identical between caps — cap=8 still buys zero additional fidelity). **`gate-b-report.json`
   (cap=4) stays frozen/authoritative** at 114/881 = 12.9% FAIL and was **not** recomputed. See
   refreshed `data/eval/accuracy-cap-derisk/cap{6,8}-report.json` and
   `reports/2026-07-13-accuracy-cap-derisk-verdict.md` (2026-07-14 addendum).
   **Update 2026-07-14 (default-on slice, `8c54843`):** production env parsers now default
   `SHOWDOWN_ACCURACY_MODE` on and `SHOWDOWN_ACCURACY_BRANCH_CAP` to **6** when unset; explicit
   `"0"` / `"false"` / `""` remain off. Spec:
   `docs/superpowers/specs/2026-07-14-accuracy-default-on-design.md`. Decision note:
   `reports/2026-07-14-accuracy-default-on-decision-note.md`. **Dev-strength A/B done**
   (`reports/2026-07-14-accuracy-default-on-devstrength-verdict.md`): SAFETY-PASS, strength
   UNDERPOWERED (n_discordant=6); directional warning only (off favored in all discordants) —
   not equivalence, not regression proven.

## P1 — Nächster realer Stärkeversuch

1. **Materialize the dev-generalization panel (05).** The analyzer/planner exists; the
   actual matrix (hero archetypes × opponent teams × opponent policies, per-cell eval,
   worst-cell protection, paired seeds, staged pilot before the full gate) does not yet
   exist as run data. This is the actual blocker on depth-2 Stage 3, not a parallel task.
2. **VGC-Bench compatibility study (read-only, no integration) — sequenced after the
   accuracy-hit-probability slice, before Depth-2 Stage 3.** User verdict (2026-07-13):
   GO for a small integration study, explicitly NOT a rebuild of our bot — neither
   VGC-Bench's resolver nor its RL stack get integrated into our core now. Feeds directly
   into item 1's panel-diversity gap (we currently have only 4 archetypes and a coarse
   LOTO test). Scope:
   - Adapter for our heuristic agent vs. VGC-Bench's Random/MaxBasePower/SimpleHeuristics
     baselines (external comparison point our internal-only benchmark currently lacks).
   - Check whether the 72 holdout teams (or a license/provenance-clean compatible subset)
     can be adopted into our dev panel — directly addresses item 1's team-diversity gap.
   - Trained policies (BC/RL) as a **future opponent population** for opponent-response/
     belief/Depth-2 — comparison opponents, explicitly NOT ground truth.
   - Compatibility checklist: pinned Showdown commit + poke-env version, format/OTS/team-
     preview/action-space compatibility, team-file licenses, adapter-effort estimate,
     whether our `config_hash`/run-manifest provenance chain survives the integration.
   - Concrete smoke matrix: 100–200 games vs. the 3 heuristic baselines.
   - No BC/RL implementation starts from this study — investigation only.
   Related to, but broader than, the existing P2 item 1 ("VGC-Bench Part B" — that one is
   specifically the OTS/hidden-information angle; this item is benchmarking infrastructure
   — baselines, holdout teams, provenance).
3. **Depth-1 vs depth-2(3,3) on that panel.** The most mature, plausible-impact experiment
   on the table — run before any new architecture slice. GO → depth-2 becomes the new
   baseline candidate. NO-GO → analyze the coarse-approximation failure mode, don't just
   re-tune N/M. Inconclusive → panel/opponents aren't discriminating enough.
4. **Bounded ladder calibration** — only after the candidate wins on the diverse dev panel;
   external validation, not the primary optimization loop.

## P2 — Probabilistische Hidden Information

1. VGC-Bench Part B on a small Reg-I sample: player perspective, OTS-vs-reveal
   availability, legality reconstruction, leakage audit, clear provenance.
2. Belief v1 calibrated **offline first** (not live-deciding): item/move/spread log-loss,
   speed-interval coverage, Brier score, posterior mass on the true set, calibration by turn.
3. Battle-local updates (reveals, turn order, damage ranges, item/ability exclusion, tera).
   Beliefs affect priors/world-weights only at this stage.

## P3 — Belief-basierte Suche

1. Dedupe identical sampled worlds before evaluation (fixes the current linear-in-K
   latency finding).
2. K-world sampling vs single-world ablation, start K=4 (comfortable local latency margin).
3. Depth-2 × K-sampling composition — deliberately not combined yet; needs its own budget/
   fusion design.
4. Adaptive risk aggregation from the actual posterior world distribution + position,
   instead of a global CVaR scalar (global aggregation scalars are 2-for-2 on large
   `max_damage`-only dev wins collapsing to exactly zero on held-out — see the
   scalar-aggregation detail table above; the CVaR *operator* itself stays useful for this
   axis, only its global-scalar deployment is ruled out).

## P4 — Lernen aus besserem Teacher-Signal

1. Generate search-teacher data once a stronger search/belief policy exists (better
   counterfactual labels than the current rollout teacher).
2. Value-head and a new reranker tested **separately**, both ablated against the
   then-current search baseline — not introduced simultaneously.
3. Team preview built on the same value/belief building blocks, not a standalone
   90×90 heuristic re-evaluated on the old eval.

## P5 — Langfristige Forschung

Population/league self-play; exploitability/best-response track; BO3 + cross-game
opponent memory; a new engine or Rust hot-paths only after a demonstrated throughput
bottleneck.

## Explicitly parked / stopped

- Further reranker threshold tuning to rescue live override.
- More global λ/penalty scalar experiments.
- `SHOWDOWN_WORLD_SAMPLES` ≥ 16 before world-dedup + real posteriors exist.
- Starting large PPO/transformer infrastructure now.
- Building all four memory systems at once (meta/set/battle-local first; cross-game
  opponent memory is V2).
- Re-opening the current held-out panel for development decisions.
- Teacher-agreement as a primary gate (see `teacher-agreement-winrate-inversion` — it can
  invert relative to real winrate).
- Treating Elo milestones (1300/1500/1700) as technical acceptance criteria before a real
  ladder baseline exists.

## The sequencing logic

```
Datenidentität reparieren
        ↓
Value-Diagnose + Generalisationspanel materialisieren
        ↓
Depth-2 echter Stärke-Gate (Stage 3)
        ↓
kalibrierte Beliefs
        ↓
belief-basiertes Sampling/Search
        ↓
bessere kontrafaktische Labels
        ↓
Value-Head/Reranker neu bewerten
```

Each stage should justify the next. The project's strength is a reproducible measurement
harness (held-out ledger, McNemar gates, paired seeds, byte-identical-off invariants) —
lean on it rather than adding architecture layers whose payoff hasn't been measured.
