# Gate B Report -- Confirmatory Run (Full Deduplicated Corpus)

**This is the load-bearing real run of the accuracy-offline-gate plan.** It replays every real (state, request) MOVE decision in the full deduplicated corpus through `heuristic_choose_for_request` twice -- once with `SHOWDOWN_ACCURACY_MODE` off, once on -- and applies spec Sec.4's acceptance rules. **No default-on decision, strength claim, or Depth-2 Stage 3 work follows from this report alone** (spec Sec.1, Sec.8); see the plan closeout report (`reports/2026-07-13-accuracy-offline-gate-verdict.md`) for the full framing.

- report schema version: `gate-b-report-v1`
- source commit: `a7ebe424820736fbf3f344e1a1db560fe4a9f3d6`
- elapsed seconds (real, full run, off+on combined): 92.1
- ms/decision average (off+on combined): 97.6

## Dedup breakdown (separate numbers, spec Sec.6 item 5 -- not folded into one figure)

- `.log.gz` files found under the 4 canonical corpus directories: 197
- excluded total: 112
  - excluded as `duplicate_seed_identity`: 105
  - excluded as `excluded_diagnostic_artifact`: 7
- final deduplicated unique battles (G): 85
- expected G (Task 4's verified real-corpus number): 85
- **G matches expected: True**

## Decision extraction

- `force_switch`: 152
- `move`: 944
- `team_preview`: 85
- excluded from Gate B as team_preview: 85 (carries no move-accuracy content, spec Sec.6 item 4)
- excluded from Gate B as force_switch: 152 (carries no move-accuracy content, spec Sec.6 item 4)
- MOVE decisions replayed (off+on each): 944
- **n_decisions_compared (MOVE decisions that did NOT raise): 881**

## Acceptance rule (spec Sec.4)

- no_exceptions: **False**
- no_nans: **True** (swept over every replayed decision, not just diverging ones)
- exception_count: **63**
- off_path_byte_identical: None (not recomputed here -- verified separately by Task 4/7's frozen-baseline diff; see the closeout report)
- latency_within_budget: None (not a per-run gate field in this module; see the latency figures above and the closeout report's runtime-extrapolation discussion)

### Exceptions -- honest, full accounting (not hidden)

All exceptions this run are `RuntimeError` raised by `_chosen_candidate` (`eval/accuracy_gate_b.py`) on an AMBIGUOUS `candidate_id`: `decision.py`'s `_label_ja` renders every non-move slot action as the bare string `"switch"` (dropping which benched mon it switches to), so two structurally different joint actions that switch to different bench mons in the same slot can render a byte-identical `candidate_id` (e.g. `"(switch, pass)"`). This is documented, expected, and correctly caught (Task 10) -- these decisions are excluded from `n_decisions_compared` and from the cap-hit numerator/denominator, not silently miscounted. Every exception shares the identical message template below, differing only in `request_hash` and the specific `chosen_candidate_id` substituted in:

> `RuntimeError: ambiguous chosen_candidate_id='<label>' matches 2 candidates -- _label_ja's non-injective switch-slot labeling (decision.py's _label_ja renders every non-move slot action as the bare kind string, e.g. 'switch', dropping the target mon) makes candidate_id ambiguous here; refusing to guess which one was actually chosen`

Full list (request_hash, ambiguous label, candidate match count):

| request_hash | ambiguous candidate_id | matches |
| --- | --- | ---: |
| `b8dc10833f23e0119a190d9e88c7259bdad55f14c21fee0467cc5c15a0c67c48` | '(Knock Off->1, switch)' | 2 |
| `1615465a574379dba0c6aacca892583992665b0426eac5b8cf8e726a1b3043f8` | '(Flare Blitz->2, switch)' | 2 |
| `a50f28feb8fd2fe8ff3245b26fd3167fc7ab9d408904ee2e21a5d88eda98f341` | '(Flare Blitz->1, switch)' | 2 |
| `bbc9a92fad4398b702232762fd4b512330790e93712cb9359ac5031b6e6a1f2c` | '(Knock Off->1, switch)' | 2 |
| `0381eba0b0c0a635f3b107ceab1da2ae332579a1d3bc64f589facabcd985c14c` | '(Knock Off->1, switch)' | 2 |
| `333c8350fe113a0b78111de27936e040d6dea5543d1d7a0b59b9503665e2d957` | '(Flare Blitz->1, switch)' | 2 |
| `e802d46751010d37943a8133a55e1d3a9d61661c6f14f1a884a2758eb61faf23` | '(switch, Grassy Glide->2)' | 2 |
| `52a1b5a7f53fc4ecda7356c9f1985c5bbe6b57d50d89640e704dfba7cdf7b675` | '(Knock Off->1, switch)' | 2 |
| `50e422a06076baf5f575d965023bbf11f3907e0b9f15994b9265a485123933e5` | '(Knock Off->1, switch)' | 2 |
| `95a8a80ce524d179d97043f00bfff262f9f9a245d797408e3831163ae7177c00` | '(Protect, switch)' | 2 |
| `43a61edc7fa86d5694c3b3cea84111607f2d1bf966d6ccf78a71ab9229981ed9` | '(switch, Tailwind)' | 2 |
| `31c4a796efe86556c3cc2e2dafb502e0c46ed24a9eea93d004cbf4b083b6cc90` | '(Knock Off->1, switch)' | 2 |
| `3602d7bd1a81a06d68c21697147f5d47c1c6d3f0bfcd1bdc5a5f71ebc4e3a5e9` | '(Knock Off->1, switch)' | 2 |
| `027875d07f4185b693030f964eeda762f5ce2f79cead4842e439055cfe603698` | '(Knock Off->1, switch)' | 2 |
| `9d3530501059c22c52ccddcb69ec95c11881309a252649d07c6d9cf67ce01e47` | '(Knock Off->1, switch)' | 2 |
| `a1e03c1298f9974892bc94c05dc85aaf6fa841d53b4c72716f438db2a21e4824` | '(Knock Off->1, switch)' | 2 |
| `134eb1adaaaf0c5988a4e028a24576c883d0f26a80f42507b7e2e97c5d3195f3` | '(switch, Grassy Glide->2)' | 2 |
| `c1e1d0cafcd2b73247e3860d9c2a50b29852ecbccd57abd4638027e648bc3581` | '(Knock Off->1, switch)' | 2 |
| `284db14780bd7b47620c6e8967d090a287f371370f5c834b21c37242e8b36177` | '(Knock Off->1, switch)' | 2 |
| `9027493100565bf8496c56fc604994770e56f577b8c0296a573144165d26e5d7` | '(switch, Grassy Glide->2)' | 2 |
| `9cc92d9bf258d0079714ff713c3ab53468172169b3acbd9f99c7fcfd9fb2c4dd` | '(Knock Off->1, switch)' | 2 |
| `b1253e20f251e1922f82cb352f663eec8ef3ca71b1b8c56b6984c7128dbe7831` | '(switch, Grassy Glide->2)' | 2 |
| `78d6665a7215def7a9d79ab54e32c903802c0fce1230d5ff147e600dce448ae0` | '(switch, Wood Hammer->2)' | 2 |
| `70dd6ecb75ca05d1dbfb03cfeb98308c0796d07f9d611eb3c8aa3a90f70de733` | '(Protect, switch)' | 2 |
| `0fb53bfe324c4da7e48f6b8ee07aa1c541dee0d7b5797d7015d7dad23f7d4d3d` | '(switch, Tailwind)' | 2 |
| `9742b349666de8486711cee2c3ff10bd25478f62724eabbb82f88f67208b2409` | '(switch, Tailwind)' | 2 |
| `650da41c3b5ed2077cdeb25cc88d99c2352c4130260bdabab694050ccf90e771` | '(Knock Off->1, switch)' | 2 |
| `4c3d45b9737416ff384f097f1f1f8162e72cb6dc27df716ad4924685b297efef` | '(Knock Off->1, switch)' | 2 |
| `ce8bbb1b5e1ee0c287c79b9908645efd35759b84eb3f4ec415f217fc28171fcb` | '(Knock Off->1, switch)' | 2 |
| `28cc4f532d77b48301312e0a1759eeec47753721b85096c2386f993ca1b19634` | '(Knock Off->1, switch)' | 2 |
| `3badae8648984257c44eb11e0851e0285414757cbd6dc2f4269891b8697b215b` | '(Knock Off->1, switch)' | 2 |
| `ec21eb900c18068aa949f07e8bfa24dc23b568078416f91c3ae87f8cc6114ed1` | '(Flare Blitz->1, switch)' | 2 |
| `49a2f9e5c8895b5abd83a9ffeb007177ba6db05ef61c01be53200895fbda8547` | '(Flare Blitz->1, switch)' | 2 |
| `5742e663fe91530cfde73bae8f7d67b4322b62d8aeab8b816cc12f1e661604f4` | '(Flare Blitz->2, switch)' | 2 |
| `a48b496949419c927e342354b22e22613e0cfdbe76be21a9c201c0fc29b4b388` | '(Knock Off->1, switch)' | 2 |
| `c61cdd05229005b72cb74becc91ede11e5b3f87eb33b1b9a6e9d05c007193139` | '(Knock Off->1, switch)' | 2 |
| `17bb03d65e098f200f1670ff246fe5b81cb13c54a06386e5d5907ae680b82b2c` | '(switch, Grassy Glide->2)' | 2 |
| `8ac3f3edcc970d27f377c5eebcacae67c785991808e60136b1fa40f4b28d11d5` | '(Knock Off->1, switch)' | 2 |
| `a771b7b8ba4839639b5353fc482fad527f69bd78965c0ab261996d0c5e78e257` | '(Knock Off->1, switch)' | 2 |
| `80bf82f794aa001b2e8e32b7547086f7edf04cf71fbd0f8c29b9de6f73bc75d4` | '(Flare Blitz->2, switch)' | 2 |
| `bb61809781a1e48b05edd713043dc4728fe2f799a337793a75fa6f1cdea23689` | '(Knock Off->1, switch)' | 2 |
| `003a9d946087a9d6bede87ab8c1b312208d8830533e7f6cde0f602f93b29e2d5` | '(Knock Off->1, switch)' | 2 |
| `b883bc2845004d8d472f1423d317ab4dd55cd3d2604063de0acbf5d3b7c1444d` | '(switch, Grassy Glide->1)' | 2 |
| `cdb04b6bdd533e5ebd5c7377839fbc6845ebfd6bdd51a80fc70e16fd66ecb8d6` | '(Flare Blitz->2, switch)' | 2 |
| `d5a40999b32965968b81b9e17083bf68e04cbbda5877852f639a1ddd7640a284` | '(switch, Grassy Glide->1)' | 2 |
| `f3179277378cf6a9ccb09bb7977049a3bc2511c918f077b7fe17cbb72d0e596b` | '(switch, Grassy Glide->1)' | 2 |
| `1af3113e64c27509d00904dd4e9e7b1ec85201ef1d9440345bdf312a18a106ec` | '(switch, Grassy Glide->1)' | 2 |
| `fbbd06ad2525d7df32c3d3cbe48c839675bb06ee26c3007a963261e148550f4b` | '(switch, Grassy Glide->1)' | 2 |
| `972ab02728ba70ea996cd7e5359608f1212761918539e85e428b61eb0e1d2c79` | '(switch, Grassy Glide->2)' | 2 |
| `08b1b9b6a77ea504c2f7033123c8e5e29884c6fc0b22487eef07873201ca4710` | '(switch, Grassy Glide->2)' | 2 |
| `bd6d6c9dcac2cc3b1709703da13d095d81a8f10195dd577349616a2a7162086a` | '(Flare Blitz->2, switch)' | 2 |
| `77239d6d9f006f9931368383344f87c45f415ac80bdef991429ace91bd421687` | '(switch, Wood Hammer->2)' | 2 |
| `452639f750cb238296c61c95d9a83f4cc1e3e9119fab1c4b9230f4a4e80fedf9` | '(switch, Grassy Glide->2)' | 2 |
| `83df3edccff649e7c4c55b0f280749672a2e2878776f279b9047d7199c21ef04` | '(switch, Wood Hammer->2)' | 2 |
| `27252c21bfa49508f6a45c46da883de5563439b445fbe0e90a1625ad0046a39c` | '(switch, Grassy Glide->2)' | 2 |
| `b0dd4ed48f1732607901e748e084334988b0b1ae8e6484812dceaf5eb232703e` | '(switch, Grassy Glide->2)' | 2 |
| `531c98b46b1f4de9adea8a9d7fe952f9efa4241cded3bc61a9b055f153983655` | '(switch, Grassy Glide->1)' | 2 |
| `b8462715fd2fda7a17e636d0df35ca9a81af284ebef7a500e235a39d96fd96b3` | '(switch, Wood Hammer->2)' | 2 |
| `6f81751e9d1dd949772ad5745aaf170e129d30039425c3c687c026681ea5e4b1` | '(switch, Grassy Glide->1)' | 2 |
| `78af422776da47beeb59a15d3a79e9f50745e6c510e5df0a801b2da4a13b6c65` | '(switch, Grassy Glide->2)' | 2 |
| `ec7a1c21ec470cbbcad36948546f4c1b199f2accfa792f0430f27e4d90aa0c83` | '(switch, Grassy Glide->2)' | 2 |
| `8789765eb3a7b0da1d7b0b9c0b6d7d7a01a89476df21bbd1a77605e61d8c0190` | '(switch, Grassy Glide->1)' | 2 |
| `194383bb6acb18c0a27eff1fe31efc1039139cedbb04ded67fb69be6c6aeae99` | '(Flare Blitz->2, switch)' | 2 |

## Cap-hit verdict (spec Sec.4)

- **verdict: FAIL**
- numerator (decisions with >=1 accuracy_branch_cap_hits on the chosen candidate): 114
- denominator (n_decisions, i.e. n_decisions_compared): 881
- point estimate (rate): 0.129398
- g (distinct games / battles): 85
- branch used: **nonzero -- game-clustered bootstrap** (numerator > 0, so the zero-event Clopper-Pearson branch does not apply)
- bootstrap upper bound (one-sided 95%, B=10,000 resamples, game-clustered): 0.161331
- PASS threshold: 0.05
- verdict logic: point_estimate (0.129398) > 0.05 -> **FAIL is asserted directly from the point estimate**, without even needing the bootstrap upper bound (which is still reported above for completeness).

## Decision diffs -- full per-diff capture schema (spec Sec.5)

**diff_count: 20** (decisions where the chosen action differs off vs on)

### Diff 1: `13be4e9d2001423e8ade4774ea40435132dd6935152e77e204194037823aa97a`

- off_chosen_action: `/choose move 2 1, move 2|22`
- on_chosen_action: `/choose move 2 2, move 2|22`
- off_score: 14.939000
- on_score: 13.868726
- off_margin_to_runner_up: 0.000000
- on_margin_to_runner_up: 0.586798
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **False**
- mechanically_explained: **False** (never True when events_complete is False, spec Sec.4)
- left_top_k: ['(Knock Off->1, Bleakwind Storm)']
- entered_top_k: ['(Flare Blitz->2, Protect)']

### Diff 2: `c81f5552e049dd8c43f8dd316316f3c1d17e77505a0820426d62f550b0307155`

- off_chosen_action: `/choose move 2 1, move 2|24`
- on_chosen_action: `/choose move 2 2, move 2|24`
- off_score: 17.320000
- on_score: 15.994181
- off_margin_to_runner_up: 0.000000
- on_margin_to_runner_up: 0.252345
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **False**
- mechanically_explained: **False** (never True when events_complete is False, spec Sec.4)
- left_top_k: ['(Knock Off->1, Bleakwind Storm)']
- entered_top_k: ['(Flare Blitz->1, Tailwind)']

### Diff 3: `7a66a35c57f426c114d4f0a3240cb52fd3db9608bbcae62970642f99a50904a6`

- off_chosen_action: `/choose switch Rillaboom, move 2|30`
- on_chosen_action: `/choose move 2 2, move 2|30`
- off_score: 13.874000
- on_score: 13.674800
- off_margin_to_runner_up: 0.000000
- on_margin_to_runner_up: 0.000000
- tera_changed: False
- action_diff_kind: `SWITCH`
- events_complete: **False**
- mechanically_explained: **False** (never True when events_complete is False, spec Sec.4)
- left_top_k: []
- entered_top_k: []

### Diff 4: `64855f995a10e4e99dc10b81f75382a0514571a1461900d12830f959f2068924`

- off_chosen_action: `/choose move 3 1, move 2|18`
- on_chosen_action: `/choose move 4, move 2|18`
- off_score: 8.412905
- on_score: 7.088310
- off_margin_to_runner_up: 0.000000
- on_margin_to_runner_up: 1.072140
- tera_changed: False
- action_diff_kind: `PROTECT`
- events_complete: **False**
- mechanically_explained: **False** (never True when events_complete is False, spec Sec.4)
- left_top_k: ['(Flare Blitz->1, Bleakwind Storm)']
- entered_top_k: []

### Diff 5: `fd125392554f6c28f27e3d46347bd580c185641007aa57a734aa238756db7949`

- off_chosen_action: `/choose move 1 1, move 2|18`
- on_chosen_action: `/choose move 2 2, move 1|18`
- off_score: 9.735297
- on_score: 9.092495
- off_margin_to_runner_up: 0.642802
- on_margin_to_runner_up: 0.000000
- tera_changed: False
- action_diff_kind: `ATTACK_MOVE`
- events_complete: **True**
- mechanically_explained: **True** (never True when events_complete is False, spec Sec.4)
- left_top_k: []
- entered_top_k: []

### Diff 6: `66bbe54051f3f5e68a510f868b3338530be711b052152871985c94c327d81ac5`

- off_chosen_action: `/choose move 2 2, move 2|14`
- on_chosen_action: `/choose move 4, move 4|14`
- off_score: 2.763125
- on_score: 2.520000
- off_margin_to_runner_up: 0.011881
- on_margin_to_runner_up: 0.604548
- tera_changed: False
- action_diff_kind: `PROTECT`
- events_complete: **True**
- mechanically_explained: **True** (never True when events_complete is False, spec Sec.4)
- left_top_k: []
- entered_top_k: []

### Diff 7: `f49a6daebf70095b091a049687183c16ac0d711e6b457a61b15c9130466becaa`

- off_chosen_action: `/choose move 2 2, move 2|14`
- on_chosen_action: `/choose move 4, move 4|14`
- off_score: 2.727125
- on_score: 2.520000
- off_margin_to_runner_up: 0.011881
- on_margin_to_runner_up: 0.634428
- tera_changed: False
- action_diff_kind: `PROTECT`
- events_complete: **True**
- mechanically_explained: **True** (never True when events_complete is False, spec Sec.4)
- left_top_k: []
- entered_top_k: []

### Diff 8: `288a03b5a271d81f7cd6327832bc5eb1242a0d7910780c714bc4844710fdcc31`

- off_chosen_action: `/choose move 2, move 3 1|42`
- on_chosen_action: `/choose move 1, move 1 1|42`
- off_score: 3.933750
- on_score: 3.725371
- off_margin_to_runner_up: 0.000000
- on_margin_to_runner_up: 0.000000
- tera_changed: False
- action_diff_kind: `ATTACK_MOVE`
- events_complete: **True**
- mechanically_explained: **True** (never True when events_complete is False, spec Sec.4)
- left_top_k: []
- entered_top_k: []

### Diff 9: `4dbeadd1d3c102799f425c4558014e3254797d531a4d8e73ffdcecf4bbc0f5a5`

- off_chosen_action: `/choose move 2 1, move 2|24`
- on_chosen_action: `/choose move 3 2, move 2|24`
- off_score: 13.002056
- on_score: 11.392701
- off_margin_to_runner_up: 0.000000
- on_margin_to_runner_up: 0.007627
- tera_changed: False
- action_diff_kind: `ATTACK_MOVE`
- events_complete: **False**
- mechanically_explained: **False** (never True when events_complete is False, spec Sec.4)
- left_top_k: []
- entered_top_k: []

### Diff 10: `ba13e18872f1b6cdbdacbd84567bc866c8dfc6f42b13839d0f71999917d95d86`

- off_chosen_action: `/choose move 2 1, move 2|26`
- on_chosen_action: `/choose move 3 2, move 2|26`
- off_score: 13.002056
- on_score: 11.392701
- off_margin_to_runner_up: 0.000000
- on_margin_to_runner_up: 0.007627
- tera_changed: False
- action_diff_kind: `ATTACK_MOVE`
- events_complete: **False**
- mechanically_explained: **False** (never True when events_complete is False, spec Sec.4)
- left_top_k: []
- entered_top_k: []

### Diff 11: `d4ae9c5d7b4bced5919ab258410ca416677aee542d502af9cd1134b8fa801dd0`

- off_chosen_action: `/choose move 1 1, move 2|34`
- on_chosen_action: `/choose move 2 1, move 2|34`
- off_score: 14.036250
- on_score: 11.279854
- off_margin_to_runner_up: 0.000000
- on_margin_to_runner_up: 0.520886
- tera_changed: False
- action_diff_kind: `ATTACK_MOVE`
- events_complete: **True**
- mechanically_explained: **True** (never True when events_complete is False, spec Sec.4)
- left_top_k: []
- entered_top_k: []

### Diff 12: `6ae2d3ffbbd3c169a98f107f31c1bf86e31210a1f83595a2deec86c4926970a1`

- off_chosen_action: `/choose move 2 1, move 2|36`
- on_chosen_action: `/choose move 3 2, move 2|36`
- off_score: 14.205000
- on_score: 13.029870
- off_margin_to_runner_up: 0.000000
- on_margin_to_runner_up: 1.171554
- tera_changed: False
- action_diff_kind: `ATTACK_MOVE`
- events_complete: **False**
- mechanically_explained: **False** (never True when events_complete is False, spec Sec.4)
- left_top_k: []
- entered_top_k: []

### Diff 13: `10f7668ff6ac7385b675f504a377c0f55fd3643b59ef2ed00d16dca3145885e4`

- off_chosen_action: `/choose move 1 1, move 2|28`
- on_chosen_action: `/choose move 1 2, move 1|28`
- off_score: 9.577431
- on_score: 8.607824
- off_margin_to_runner_up: 0.645576
- on_margin_to_runner_up: 0.000000
- tera_changed: False
- action_diff_kind: `ATTACK_MOVE`
- events_complete: **True**
- mechanically_explained: **True** (never True when events_complete is False, spec Sec.4)
- left_top_k: ['(Grassy Glide->1, Bleakwind Storm)', '(Wood Hammer->1, Bleakwind Storm)', '(Wood Hammer->2, Bleakwind Storm)']
- entered_top_k: ['(Fake Out->2, Taunt->1)', '(Fake Out->2, Taunt->2)', '(Grassy Glide->2, Taunt->1)']

### Diff 14: `6f3473bf32fe11d38f990916a7ac35729c0c1e9f5141273af644967bda69beef`

- off_chosen_action: `/choose move 2 1, pass|26`
- on_chosen_action: `/choose move 2 2, pass|26`
- off_score: -11.517228
- on_score: -11.237341
- off_margin_to_runner_up: 0.000000
- on_margin_to_runner_up: 0.001481
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **True**
- mechanically_explained: **True** (never True when events_complete is False, spec Sec.4)
- left_top_k: []
- entered_top_k: []

### Diff 15: `5b6eee6f87787ae1ad41533c942c7d57341fd044d9a469a88b2d45f9f5c64bcc`

- off_chosen_action: `/choose pass, move 2 1|30`
- on_chosen_action: `/choose pass, move 2 2|30`
- off_score: -11.384455
- on_score: -10.902372
- off_margin_to_runner_up: 0.000000
- on_margin_to_runner_up: 0.000000
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **True**
- mechanically_explained: **True** (never True when events_complete is False, spec Sec.4)
- left_top_k: []
- entered_top_k: []

### Diff 16: `4e0527daccb056472531b2786a972ec79e327812c05213fe3b6aee40e7ccbd1a`

- off_chosen_action: `/choose pass, move 2 1|30`
- on_chosen_action: `/choose pass, move 2 2|30`
- off_score: -9.498098
- on_score: -8.045499
- off_margin_to_runner_up: 0.000000
- on_margin_to_runner_up: 0.708416
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **True**
- mechanically_explained: **True** (never True when events_complete is False, spec Sec.4)
- left_top_k: []
- entered_top_k: []

### Diff 17: `855488d7fa91a944ce0c84c8f546170fe6a144e8db3ccd70d55a2b053ca5d306`

- off_chosen_action: `/choose move 2 1, pass|32`
- on_chosen_action: `/choose move 2 2, pass|32`
- off_score: -11.719208
- on_score: -11.405160
- off_margin_to_runner_up: 0.000000
- on_margin_to_runner_up: 0.028877
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **True**
- mechanically_explained: **True** (never True when events_complete is False, spec Sec.4)
- left_top_k: []
- entered_top_k: []

### Diff 18: `ff63ca794bbc1e2fcf34471bd90e22e758ff06ddba03c8e87621331deb3aa62f`

- off_chosen_action: `/choose pass, move 1 1|22`
- on_chosen_action: `/choose pass, move 1 2|22`
- off_score: -12.640000
- on_score: -11.552500
- off_margin_to_runner_up: 0.000000
- on_margin_to_runner_up: 0.575025
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **True**
- mechanically_explained: **True** (never True when events_complete is False, spec Sec.4)
- left_top_k: []
- entered_top_k: []

### Diff 19: `1dd3dc748e38366963422ef4aaa6061ca10b7ef18c9b87bb26dc9ea346efede0`

- off_chosen_action: `/choose pass, move 1 1|24`
- on_chosen_action: `/choose pass, move 1 2|24`
- off_score: -11.680000
- on_score: -10.620480
- off_margin_to_runner_up: 0.000000
- on_margin_to_runner_up: 0.575025
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **True**
- mechanically_explained: **True** (never True when events_complete is False, spec Sec.4)
- left_top_k: []
- entered_top_k: []

### Diff 20: `9aa671d71bbbb9479306b804e2bc82e06b958beca9e26e055e7e5b916847f093`

- off_chosen_action: `/choose move 2 1, pass|28`
- on_chosen_action: `/choose move 2 2, pass|28`
- off_score: -11.588515
- on_score: -11.306727
- off_margin_to_runner_up: 0.000000
- on_margin_to_runner_up: 0.001481
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **True**
- mechanically_explained: **True** (never True when events_complete is False, spec Sec.4)
- left_top_k: []
- entered_top_k: []

## Provenance note

This report was generated by `scripts/run_accuracy_gate_b.py` (Task 11), which reuses Task 4/7's exact corpus-extraction/dedup wiring and Task 9's real `CalcClient`/`DamageOracle`/`SpeedOracle`/`SpeciesDex` construction pattern -- no sampling or truncation; every MOVE decision in the full deduplicated corpus was attempted.

