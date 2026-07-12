# Canonical Roadmap & Status

**Living document — update as slices land, don't let it drift.** This supersedes the old
layered plans (README, `docs/heuristic_bot/`, and the external `../TestBOtpläne/00-14`
Northstar docs) as the single source of truth for *current status and next decision*.
`TestBOtpläne/` remains valid for deep design rationale on things already built, but it is
**not versioned with the code** and must not be read as an up-to-date execution plan —
verify against this file and git history first.

Last reconciled: 2026-07-12, against an external strategic review (adopted with two
corrections, see "Corrections to the external review" below) and this session's own verified
state (depth-2 slice, value-calibration spec).

## Status matrix

| Vorhaben | Status | Evidenz | Nächste Entscheidung |
|---|---|---|---|
| Reranker v1 (dataset/infra, 2b-2.5a) | **Built, in use** | merged `afb9708`; feeds `outcome_join` + value-calibration | keep as foundation, not "parked" |
| Reranker v1 **live override** | **NO-GO** | 2b-4 report: +13 net vs max_damage, McNemar p=0.105 n.s. | not shipped; don't re-attempt without new evidence |
| Scalar aggregation (λ tuning) | **NO-GO** | Slice 0b/1 + 2c-aggregation: both dev-GO's = exactly 0 on held-out | stop; no more global-λ experiments |
| +Sampling machinery (K-world) | **Built, off** | latency report: linear-in-K, max K=8 local | hold until calibrated posterior exists (P2/P3) |
| Depth-2 search | **Stage 1+2 GO, merged local main** | `2026-07-12-2c-depth2-derisk-verdict.md` | Stage 3 blocked on the panel actually being *run* (below) |
| Generalisation analyzer (05) | **Built (tool only)** | merged `35956df` | materialize the actual archetype×opponent panel — data doesn't exist yet |
| VGC-Bench ingestion | **Part A done** | `6210e4d` | Part B (player-perspective, OTS-vs-reveal, legality, leakage audit) |
| Value calibration study | **Spec written**, awaiting user sign-off | `docs/superpowers/specs/2026-07-12-value-calibration-design.md`, commit `5981ccb` | implementation plan once spec approved |
| Outcome-join (04) | **Built** | merged `725257e`/`fea284b`; 299-game reference smoke | consumed by value-calibration study |
| Teacher-disagreement atlas | **Built** | `5830e9e` | diagnostic only — not a strength gate |
| Diagnostics-v0 | **Built** | `849b5c7` | diagnostic only — not a strength gate |
| Belief (item/spread/move priors) | **Not started** | — | P2, after the panel + data-identity fix |
| Value-head (trained model) | **Not started, gated** | — | only after value-calibration says GO |
| PPO/full self-play RL | **Not started, deliberately deferred** | ps-ppo-reference eval | P5, after search/belief/value-labels stabilize |

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

## P1 — Nächster realer Stärkeversuch

1. **Materialize the dev-generalization panel (05).** The analyzer/planner exists; the
   actual matrix (hero archetypes × opponent teams × opponent policies, per-cell eval,
   worst-cell protection, paired seeds, staged pilot before the full gate) does not yet
   exist as run data. This is the actual blocker on depth-2 Stage 3, not a parallel task.
2. **Depth-1 vs depth-2(3,3) on that panel.** The most mature, plausible-impact experiment
   on the table — run before any new architecture slice. GO → depth-2 becomes the new
   baseline candidate. NO-GO → analyze the coarse-approximation failure mode, don't just
   re-tune N/M. Inconclusive → panel/opponents aren't discriminating enough.
3. **Bounded ladder calibration** — only after the candidate wins on the diverse dev panel;
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
   instead of a global CVaR scalar (global scalars have a 2-for-2 dev-win/held-out-zero
   track record — see status matrix).

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
