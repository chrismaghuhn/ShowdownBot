# 2b-2a Reranker Offline Eval

2b-2a uses feature-limited 45-live-feature input; this is a lower-bound experiment, not a final judgment on reranker viability.

## A) ATTACK-strict (PRIMARY GATE)
- decisions 63
- mean regret: heuristic 1.3067  vs  model 0.053
- wrong-but-near-equal: heuristic 10  vs  model 1

## B) all-strict (diagnostic)
- decisions 74
- mean regret: heuristic 1.1125  vs  model 0.5398

## C) contestable-only (diagnostic)
- decisions 28
- mean regret: heuristic 1.3855  vs  model 0.1193

## Verdict: GO (gate passes)
