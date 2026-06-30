# Brain V1 — Northstar (pointer)

The detailed architecture and execution-slice documents for the bot's decision ("Brain") component live
**outside this repo**, in the external folder `TestBOtpläne/` (sibling of this repo under
`Documents/`). Kept external on purpose; this file is the in-repo pointer so contributors don't lose the
context.

## Canonical docs (external `TestBOtpläne/`)

- `README.md` — index + reading order
- `00-overview-and-assumptions.md` … `09-roadmap.md` — **northstar architecture** (the broad vision):
  hybrid Expectiminimax + RL-reranker over the existing heuristic core, 4 memory systems, Bayesian
  prior + hidden-info world-sampling, teampreview, self-play infra, SOTA delimitation, risks, phased
  roadmap with Elo milestones.
- `10-execution-slices.md` — **binding commit-slice plan**. For implementation order, **`10` wins** over
  the broader northstar docs.

## How it attaches to this repo (no rewrite)

The existing heuristic core is reused as the search/safety-floor layer; the frozen `learning/` schema +
`DecisionTrace` are the RL data tap. Brain↔client seam is `battle/decision.py::choose_with_fallback(...)`
— the Brain only replaces its internals; the client signature is unchanged.

## Hard invariants (from `10`)

- **INV-1** Live-path allowlist: only legal actions, heuristic safety floor, fast anytime/timeout-safe
  rerank, timeouts + fallback, telemetry. Nothing heavy in the live path.
- **INV-2** Memory = priors only. Memory may change probabilities, never directly pick a move; every
  decision goes through search → fusion → safety-floor.
- **INV-3** Anytime/abortable: after every search step a valid action is ready; budget out → best-known
  candidate.
- **INV-4** One layer at a time + ablation gate before default-on.
- **INV-5** No LLM anywhere (incl. offline).
- **INV-6** No label leakage: model input = `learning/schema.py::FEATURE_COLUMNS` only; everything in
  `LABEL_KEYS` and outcome-bearing `METADATA_KEYS` is forbidden as a feature (the heuristic *rank* is a
  label; heuristic *scores/gaps* are allowed features; `format_id` is the only intentional overlap). Each
  training run writes a feature allowlist + denylist to its report.
- **INV-7** Model-artifact safety: each artifact carries `dataset_hash`, `feature_schema_hash`,
  `training_config_hash`, `eval_report`; on load, `feature_schema_hash` is checked against the active
  schema — mismatch/load-failure → automatic fallback to heuristic-only.

## Slice order (binding)

```
2b-1  loader + split + baseline eval                         (planned; this branch)
2b-2  offline reranker — groupwise (lambdarank), ATTACK-focus,
      near-equal-safe regret-vs-teacher eval; NOT live
2b-3  shadow mode — compute heuristic + reranker, use heuristic, log overrides
2b-4  gated override — narrow auditable attack-only override, safety-floor has veto
2c    search/fusion — CVaR + light world-sampling on the existing curated meta prior, timeout-safe
3     memory systems — priors only (INV-2), minimal set; cross-game opponent behavior deferred to V2
4     JS-sim self-play (Phase 4)
```

Each slice ships with an explicit ablation and a gate vs. the previous config (INV-4).
