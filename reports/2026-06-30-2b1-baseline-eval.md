# Baseline Evaluation Report

- rows 4658 · games 100 · decisions 951 (multi 851, forced 100, trainable 951, ties 100)

## Heuristic vs Teacher
- topset agreement (multi): 524/851 = 61.6%
- unique-strict agreement: 424/751 = 56.5%
- mean regret (|value_gap| of chosen, multi): 0.9035
- override opportunity (multi, chosen != teacher_best): 327/851 = 38.4%

## Near-equal / zero-gap (training-safety)
- wrong-but-near-equal (disagree, |gap| <= 0.5): 113
- contestable decisions (>=1 non-best |gap| <= 0.5): 529/951 = 55.6%
- zero-gap non-best alternative: 348/951 = 36.6%
- nonzero near-equal (0 < |gap| <= 0.5): 279/951 = 29.3%
- non-best value_gap: median -1.366, mean -2.664, min -17.4745

## By chosen joint-action class (unique-strict multi only)
- attack: 317/643 = 49.3%
- protect: 107/108 = 99.1%

## Per-split (seed 42)
- train: 80g/762d/3729r · strict 339/602 = 56.3% · ATTACK 254/516 = 49.2%
- val: 10g/95d/467r · strict 43/75 = 57.3% · ATTACK 32/64 = 50.0%
- test: 10g/94d/462r · strict 42/74 = 56.8% · ATTACK 31/63 = 49.2%
