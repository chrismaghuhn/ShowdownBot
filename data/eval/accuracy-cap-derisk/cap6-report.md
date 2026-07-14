# Cap=6 Report -- Accuracy Branch-Cap De-Risk Study

**No strength or winrate claim anywhere in this report -- pure measurement, matching the parent accuracy-offline-gate's own framing** (same convention as `reports/2026-07-13-accuracy-offline-gate-verdict.md`'s boxed disclaimer). This report does not, by itself, license any default-on decision, any change to `SHOWDOWN_ACCURACY_BRANCH_CAP`, or any Depth-2 Stage 3 work. See the plan closeout report (`reports/2026-07-13-accuracy-cap-derisk-verdict.md`) for the full framing.

- report schema version: `cap-derisk-rendered-report-v1`
- cap report source commit: `f091691349c8494cead04262f00aabb9fc2a548d`
- cap report elapsed seconds (real, full run, off+on combined): 88.9

## Cap-hit verdict (spec Sec.2.5)

- **numerator (decisions with >=1 accuracy_branch_cap_hits on the chosen candidate): 6**
- **denominator (n_decisions_compared): 881**
- **point estimate (rate): 0.006810 (0.68%)**
- g (distinct games/battles): 85
- bootstrap upper bound (one-sided 95%, B=10,000 resamples, seed 20260713, game-clustered): 0.013714 (1.37%)
- PASS threshold: 0.05 (5.00%)
- **verdict: PASS** -- point estimate (0.68%) is at or below the 5.00% threshold and the bootstrap upper bound (1.37%) clears it too.
- exception_count (ambiguous_label-excluded decisions, same 63 as cap=4 -- see the ambiguous-candidate diagnostic report for the full classification): 63

## Cap=4 reference row (FROZEN, cited only -- never recomputed here)

Cited from `data/eval/accuracy-gate/gate-b-report.json` (sha256 `cfcffd1d20ac1d7fd3446b465d1058c2ff3aa533140af14cc901af3baeb9ee86`):

- numerator: 114
- denominator: 881
- point estimate: 0.129398 (12.94%)
- bootstrap upper bound: 0.161331 (16.13%)
- **verdict: FAIL**

## Action-changed counts (spec Sec.2.4/2.7 -- `compare_action_tables`, directions explicitly labeled)

### `cap4 -> cap6`

- **action_changed_count: 0 / 944**
- score_changed_count: 115 / 944 (real score movement without ever flipping the chosen action)

### `off -> cap6`

- **action_changed_count: 20 / 944**
- score_changed_count (reported as computed, see note below): 0 / 944
- **note: score axis is skipped for this comparison (legacy_frozen_score not proven equivalent to top_rank_score/chosen_candidate_score, per every row's own score_incompatible_reason) -- the action axis is NOT skipped and is the real, load-bearing number here.**

Full list of the affected decision_ids (20):

- `0bcf37dab347d94d697efebdb1ccab48f8839274c9603d18e22ac41e3d3d6f9f`
- `114d166f756878aeb0a53e07be557600ebaf15ba8fdb0d3ae964c19be30751b9`
- `163b65422982c899975ffb158be5b48cf97b2e9f29226adbf2503f568a34468d`
- `1c4d239a0a4074ba579d6def017c36736f4963ed749bc4cb2c51321b376af9bd`
- `1cdc87f69565d7f4fcc58c91417b2f2c065d45d384562674a976147505b5e49d`
- `3f2873db2bd09054e340d0fcd6f67b98801b7dd75d1b4c2ffdbc44a16dec992d`
- `531d93b4831b29b87a05bb138da71114ce29cfeee1f974cce31669f407b35cb5`
- `5bbea095c8153632877c48d1919e68274ae6c42ff0fae8d6effaccc8c4816077`
- `7a7ee2c6e253b868dc198f3acf39c4167576eec65d41103a34cda13ec909e81f`
- `80e30729e89a4cbbdcf8ade89f02ec03c79f38d09439f4bf33fcc7cca3ef5258`
- `85a7e139d06bc4ddf2f177d7064641c95bd7e59e28a693960489ebfd5424ca22`
- `88669e4633ef1bd2639a18bd776bd448dfd98fcf926588fbc83bc40d0eb23d4f`
- `8afdd099b1bf4cd401cc7002689919cec209b8e7640e7d16aede26d583e03e80`
- `90dcd1774c7b455e18467a126e18ae1f38f50a901712e40f5f35f6f9c5348459`
- `998bb8ca007471268fd2d62f8dc7df911904f6e4ca91979305cbb6e4dcbbe7c4`
- `aa06963f2e157d55de524f355e8626917075485e45e0fa08e6e2167ff0e0da53`
- `add1d683abfa83816793ba6357a763adb04807cc1f5c2adc6fa910a138d9f634`
- `b60f1bcf13f79cd6143a91cb32bdfffeb212b99b4e8424ecd182ff1bc5df5738`
- `b8c3dd62620e8e16eac6f875c399572d70288e3aa7d39c3e7492c78d98aa29be`
- `f2355fefe634fcb7e60eb07bd149091276d9bd089784e7ada6dbbf9da4c7616e`

## Leaf/event/incomplete distributions (spec Sec.2.7 -- own real denominator, NOT claimed to cover all 944)

**events_complete/mechanically_explained are only ever populated on this cap's own off-vs-on diff rows (the decisions where the chosen action actually differed) -- they are never computed for non-diverging decisions. This denominator is diff_count, NOT the full 944-decision corpus (spec Sec.2.7).**

- denominator (this cap's own diff_count): 20
- events_complete=True: 20 / 20
- events_complete=False: 0 / 20 (branch cap was exhausted somewhere in the chosen candidate's own event tree for that decision)
- mechanically_explained=True: 20 / 20 (never True when events_complete is False, per spec)

## Latency (spec Sec.2.6 -- both trace modes, real full-corpus measured count / expected denominator shown side by side)

| series | p50 (ms) | p95 (ms) | max (ms) | measured n | expected denominator | exceptions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `cap6_trace_none` | 39.3 | 173.0 | 278.3 | 944 | 944 | 0 |
| `cap6_trace_enabled` | 46.9 | 183.9 | 258.3 | 944 | 944 | 0 |
| `cap4_trace_none (reference)` | 38.3 | 140.1 | 198.9 | 944 | 944 | 0 |
| `cap4_trace_enabled (reference)` | 45.8 | 151.1 | 258.8 | 944 | 944 | 0 |

- total decisions in corpus (shared denominator basis): 944
- counterbalancing (cap position x trial, verified not confounded with warm-up/order): `{"4": [29, 28, 28], "6": [28, 29, 28], "8": [28, 28, 29]}`
- trace order counts: `{"trace_enabled_first": 127, "trace_none_first": 128}`

## Decision diffs -- full per-diff capture (off vs on, this cap)

**diff_count: 20** (decisions where the chosen action differs off vs on, at cap=6)

### Diff 1: `13be4e9d2001423e8ade4774ea40435132dd6935152e77e204194037823aa97a`

- off_chosen_action: `/choose move 2 1, move 2|22`
- on_chosen_action: `/choose move 2 2, move 2|22`
- off_score: 14.939000
- on_score: 13.576696
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: ['(Knock Off->1, Bleakwind Storm)']
- entered_top_k: ['(Flare Blitz->2, Protect)']

### Diff 2: `c81f5552e049dd8c43f8dd316316f3c1d17e77505a0820426d62f550b0307155`

- off_chosen_action: `/choose move 2 1, move 2|24`
- on_chosen_action: `/choose move 2 2, move 2|24`
- off_score: 17.320000
- on_score: 15.646111
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: ['(Knock Off->1, Bleakwind Storm)']
- entered_top_k: ['(Flare Blitz->1, Tailwind)']

### Diff 3: `7a66a35c57f426c114d4f0a3240cb52fd3db9608bbcae62970642f99a50904a6`

- off_chosen_action: `/choose switch Rillaboom, move 2|30`
- on_chosen_action: `/choose move 2 2, move 2|30`
- off_score: 13.874000
- on_score: 13.412674
- tera_changed: False
- action_diff_kind: `SWITCH`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: []
- entered_top_k: []

### Diff 4: `64855f995a10e4e99dc10b81f75382a0514571a1461900d12830f959f2068924`

- off_chosen_action: `/choose move 3 1, move 2|18`
- on_chosen_action: `/choose move 4, move 2|18`
- off_score: 8.412905
- on_score: 6.868838
- tera_changed: False
- action_diff_kind: `PROTECT`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: ['(Flare Blitz->1, Bleakwind Storm)']
- entered_top_k: []

### Diff 5: `fd125392554f6c28f27e3d46347bd580c185641007aa57a734aa238756db7949`

- off_chosen_action: `/choose move 1 1, move 2|18`
- on_chosen_action: `/choose move 2 2, move 1|18`
- off_score: 9.735297
- on_score: 9.092495
- tera_changed: False
- action_diff_kind: `ATTACK_MOVE`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: []
- entered_top_k: []

### Diff 6: `66bbe54051f3f5e68a510f868b3338530be711b052152871985c94c327d81ac5`

- off_chosen_action: `/choose move 2 2, move 2|14`
- on_chosen_action: `/choose move 4, move 4|14`
- off_score: 2.763125
- on_score: 2.520000
- tera_changed: False
- action_diff_kind: `PROTECT`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: []
- entered_top_k: []

### Diff 7: `f49a6daebf70095b091a049687183c16ac0d711e6b457a61b15c9130466becaa`

- off_chosen_action: `/choose move 2 2, move 2|14`
- on_chosen_action: `/choose move 4, move 4|14`
- off_score: 2.727125
- on_score: 2.520000
- tera_changed: False
- action_diff_kind: `PROTECT`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: []
- entered_top_k: []

### Diff 8: `288a03b5a271d81f7cd6327832bc5eb1242a0d7910780c714bc4844710fdcc31`

- off_chosen_action: `/choose move 2, move 3 1|42`
- on_chosen_action: `/choose move 1, move 1 1|42`
- off_score: 3.933750
- on_score: 3.725371
- tera_changed: False
- action_diff_kind: `ATTACK_MOVE`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: []
- entered_top_k: []

### Diff 9: `4dbeadd1d3c102799f425c4558014e3254797d531a4d8e73ffdcecf4bbc0f5a5`

- off_chosen_action: `/choose move 2 1, move 2|24`
- on_chosen_action: `/choose move 3 2, move 2|24`
- off_score: 13.002056
- on_score: 11.374396
- tera_changed: False
- action_diff_kind: `ATTACK_MOVE`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: []
- entered_top_k: []

### Diff 10: `ba13e18872f1b6cdbdacbd84567bc866c8dfc6f42b13839d0f71999917d95d86`

- off_chosen_action: `/choose move 2 1, move 2|26`
- on_chosen_action: `/choose move 3 2, move 2|26`
- off_score: 13.002056
- on_score: 11.374396
- tera_changed: False
- action_diff_kind: `ATTACK_MOVE`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: []
- entered_top_k: []

### Diff 11: `d4ae9c5d7b4bced5919ab258410ca416677aee542d502af9cd1134b8fa801dd0`

- off_chosen_action: `/choose move 1 1, move 2|34`
- on_chosen_action: `/choose move 2 1, move 2|34`
- off_score: 14.036250
- on_score: 11.279854
- tera_changed: False
- action_diff_kind: `ATTACK_MOVE`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: []
- entered_top_k: []

### Diff 12: `6ae2d3ffbbd3c169a98f107f31c1bf86e31210a1f83595a2deec86c4926970a1`

- off_chosen_action: `/choose move 2 1, move 2|36`
- on_chosen_action: `/choose move 3 2, move 2|36`
- off_score: 14.205000
- on_score: 12.714795
- tera_changed: False
- action_diff_kind: `ATTACK_MOVE`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: []
- entered_top_k: []

### Diff 13: `10f7668ff6ac7385b675f504a377c0f55fd3643b59ef2ed00d16dca3145885e4`

- off_chosen_action: `/choose move 1 1, move 2|28`
- on_chosen_action: `/choose move 1 2, move 1|28`
- off_score: 9.577431
- on_score: 8.607824
- tera_changed: False
- action_diff_kind: `ATTACK_MOVE`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: ['(Grassy Glide->1, Bleakwind Storm)', '(Wood Hammer->1, Bleakwind Storm)', '(Wood Hammer->2, Bleakwind Storm)']
- entered_top_k: ['(Fake Out->2, Taunt->1)', '(Fake Out->2, Taunt->2)', '(Grassy Glide->2, Taunt->1)']

### Diff 14: `6f3473bf32fe11d38f990916a7ac35729c0c1e9f5141273af644967bda69beef`

- off_chosen_action: `/choose move 2 1, pass|26`
- on_chosen_action: `/choose move 2 2, pass|26`
- off_score: -11.517228
- on_score: -11.237341
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: []
- entered_top_k: []

### Diff 15: `5b6eee6f87787ae1ad41533c942c7d57341fd044d9a469a88b2d45f9f5c64bcc`

- off_chosen_action: `/choose pass, move 2 1|30`
- on_chosen_action: `/choose pass, move 2 2|30`
- off_score: -11.384455
- on_score: -10.902372
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: []
- entered_top_k: []

### Diff 16: `4e0527daccb056472531b2786a972ec79e327812c05213fe3b6aee40e7ccbd1a`

- off_chosen_action: `/choose pass, move 2 1|30`
- on_chosen_action: `/choose pass, move 2 2|30`
- off_score: -9.498098
- on_score: -8.045499
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: []
- entered_top_k: []

### Diff 17: `855488d7fa91a944ce0c84c8f546170fe6a144e8db3ccd70d55a2b053ca5d306`

- off_chosen_action: `/choose move 2 1, pass|32`
- on_chosen_action: `/choose move 2 2, pass|32`
- off_score: -11.719208
- on_score: -11.405160
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: []
- entered_top_k: []

### Diff 18: `ff63ca794bbc1e2fcf34471bd90e22e758ff06ddba03c8e87621331deb3aa62f`

- off_chosen_action: `/choose pass, move 1 1|22`
- on_chosen_action: `/choose pass, move 1 2|22`
- off_score: -12.640000
- on_score: -11.552500
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: []
- entered_top_k: []

### Diff 19: `1dd3dc748e38366963422ef4aaa6061ca10b7ef18c9b87bb26dc9ea346efede0`

- off_chosen_action: `/choose pass, move 1 1|24`
- on_chosen_action: `/choose pass, move 1 2|24`
- off_score: -11.680000
- on_score: -10.620480
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: []
- entered_top_k: []

### Diff 20: `9aa671d71bbbb9479306b804e2bc82e06b958beca9e26e055e7e5b916847f093`

- off_chosen_action: `/choose move 2 1, pass|28`
- on_chosen_action: `/choose move 2 2, pass|28`
- off_score: -11.588515
- on_score: -11.306727
- tera_changed: False
- action_diff_kind: `ATTACK_TARGET`
- events_complete: **True**
- mechanically_explained: **True**
- left_top_k: []
- entered_top_k: []

## Provenance note

This report was rendered by `scripts/render_cap_derisk_reports.py` (Task 12) from Task 7's real `cap6-report.json`, Task 8's real `cross-cap-diffs.json`, and Task 9's real `latency-results.json` -- none of these source artifacts were re-run or modified to produce this report; the cap=4 reference row is cited by content hash from the frozen `data/eval/accuracy-gate/gate-b-report.json`, never recomputed.

