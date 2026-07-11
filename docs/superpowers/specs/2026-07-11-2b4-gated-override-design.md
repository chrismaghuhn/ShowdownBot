# 2b-4 — Gated Reranker Override (determinism-first, dev-panel strength)

**Status:** roadmap slice after 2b-2b (merged `9ca680e`). The slice that finally lets the
reranker DRIVE the bot (not just shadow-log) and measures whether that is actually stronger —
under the harness's own reproducibility discipline.

## The ordering that defines this slice

The reranker override is a candidate for a *strength claim*. A strength claim is only
meaningful if the candidate agent is byte-reproducible (else the paired comparison is noise).
So the mandatory order is:

1. **Determinism gate (Channel A double-run identity).** Run the override agent twice on the
   same seeded schedule; the two runs must be byte-identical (winner/turns/normalized_room_log
   sha per battle, exactly like the T4 identity check). If the reranker's override introduces
   ANY nondeterminism (LightGBM predict order, timeout-dependent fallback, feature-hash
   instability), this fails and NO strength claim is made until it is fixed. **Identity before
   strength — non-negotiable.**
2. **Dev-panel strength eval** (only after 1 passes). Override-agent-vs-baseline paired against
   heuristic-vs-baseline on the SAME seeds over the DEV panel (panel_v001), using the T5 paired
   McNemar machinery → GO / NO-GO / UNDERPOWERED verdict. Dev panel, NOT held-out — repeatable,
   spends no one-shot budget.
3. **Held-out confirmation — OUT OF SCOPE for this slice, gated behind explicit user approval.**
   The held-out set is a one-shot resource (one run per config_hash lineage, T6 ledger). We
   spend it only after a dev-panel GO and only when the user explicitly says so. This slice
   produces the dev-panel result and STOPS.

## The override agent

New agent policy `heuristic_reranker` (name TBD in plan): runs the heuristic to produce the
decision trace (candidates + authoritative heuristic pick), scores the top-K candidates with a
committed reranker model, and **overrides** the choice to the reranker's argmax candidate —
translated back to the exact `choose` string for that candidate's JointAction.

**Fail-safe contract (identical to shadow's robustness, but now load-bearing):** on ANY
reranker failure (model load, feature extraction, predict, timeout, reranker argmax not
resolvable to a legal choose string), the agent returns the HEURISTIC's choose string
unchanged. The override is strictly "reranker when it cleanly produces a legal alternative,
heuristic otherwise" — so the override agent is never *worse-behaved* than the heuristic on the
error path, and the fallback path is itself deterministic (no RNG).

**Determinism requirements (what the gate enforces):**
- LightGBM `booster.predict` is deterministic for a fixed model + input; argmax tie-break must
  be explicit and stable (lowest candidate_index on score ties — pin it).
- The reranker scoring must NOT depend on wall-clock (no timeout-based branch in the committed
  determinism config; the shadow's 50ms timeout is a shadow-only affordance — the override runs
  the score inline and deterministically, or a MISS is a deterministic fallback keyed on data,
  never on time).
- Feature vector + schema hashes are content-derived (already true in reranker_features).

**INV-1 (live-path safety):** the override still goes through the same legal-action enumeration
and the same fallback chain endpoints; it only re-picks AMONG the heuristic's own legal
candidates. It never invents an action outside `trace.candidates`. INV-5 (no LLM) unaffected.

## Reuse (build nothing that exists)

- Determinism gate: the T4 double-run identity mechanism + `normalize_battle_log`/row sha (T4c).
- Strength stats: T5 `stats.py` (exact McNemar, Wilson), `pairing.py`, `report.py` paired mode.
- Battle execution: the 2b-2.5a Kaggle kernel path (seeded schedule runner) — the user's local
  CPU constraint (PTCG training) still holds unless they say otherwise, so battles run on
  Kaggle. The override agent must be selectable in a schedule and the model is committed
  (`models/reranker/2026-07-11-2b25a-attack-lgbm.txt`) so the pinned-sha clone has it; LightGBM
  is in the Kaggle image.
- Provenance: run manifests (config_hash now includes the override + model sha), environment
  block (T4c).

## Non-goals

Held-out spend (deferred, user-gated); training a NEW model (uses the committed 2b-2.5a model);
live-ladder deployment; changing the shipped default agent (override is opt-in via env/agent
name until a strength claim is earned). No new features (2b-2.5b is separate).

## Testing strategy

- Override agent: unit tests with a stub/tiny booster — override picks the argmax candidate;
  fail-safe returns the exact heuristic choose on every failure mode; tie-break is stable; the
  chosen candidate's choose string is legal + matches the JointAction. NO battles.
- Determinism config: a unit proving the scoring path has no wall-clock branch (the override
  config differs from shadow's timeout affordance).
- The Kaggle determinism gate + dev strength run are controller-orchestrated (like datagen),
  their evidence committed under `data/eval/2b4/`.
