# HeuristicBot — next steps

_Companion: [current_state.md](current_state.md), [benchmarking.md](benchmarking.md)._

**Do not start by tuning another scalar against `max_damage`** (a λ, a penalty
weight, a damage roll). That path is exhausted and the mirror benchmark misleads
([benchmarking.md](benchmarking.md)). Pick ONE of these clean paths instead.

## 1. Consolidate / review / merge the branch

The current state is coherent (move/condition system, own-team truth, opponent
realism, Protect/Fake-Out fixes, tests green) — a good review/merge candidate.
Close it out: relocate these docs (done), final test matrix (documented), a
merge description, then review/merge.

## 2. ML pivot — Phase 3: Learned Action Reranker (the real path past ~37%)

Keep the heuristic as the **candidate generator**; a small model **reranks** its
candidate joint actions — not a full policy network.

- **Inputs:** the heuristic's candidate actions + features (its own per-line
  scores, predicted in/out damage, game mode, board features, the now-correct
  own/opponent models).
- **Labels:** which candidate was actually better, from **self-play / replay
  outcomes** (preference/imitation learning).
- **Integration:** the reranker re-scores `pick_best`'s candidates; the heuristic
  remains the safety floor (fallback chain unchanged).

This is **multi-part** (data generation → features → label definition → model →
training → integration → evaluation) and must be decomposed into sub-projects;
design the first slice (likely: data generation + a frozen feature schema) on its
own. We already have the honest signal (self-play) and correct features as the
foundation.

## 3. Finalize the "brain document"

Decide which features from the now-correct models (own sets, opponent likely-sets,
speed truth) feed the learner — the feature contract for path 2. See the memory
note `brain-document-sets-prior`.

## Guardrails carried forward

- Mirror-vs-`max_damage` is a **bug detector**, not a target.
- Read behavioural metrics, not just winrate; keep N honest.
- Self-play measures behaviour/symmetry and generates data; it does **not** prove
  strength (shared blind spots).
