# 2b-2.5a Reranker Offline Eval — Enriched Retrain (Panel-Diverse Dataset)

Slice 2b-2.5a reruns the unchanged 2b-2a pipeline (`reranker_features` /
`reranker_train` / `reranker_eval`) on a new, panel-diverse, Kaggle-generated
dataset (4 hero teams × 3 panel villains × 5 policies × 5 seeds = 300 games,
17458 rows) to test the hypothesis that the ~18 dead class-A features from
2b-2a were "mirror-data artifacts" — constant only because 2b-2a's dataset was
a single team mirroring itself.

**Result: the KPI target was not met.** `dropped_constant_columns` fell from
28 to 24 (target ≤ 12, stretch ~10). Only 3 of the 15 explicitly-named class-A
features reactivated. Root-cause analysis below shows most of the remainder
are **not** mirror-data artifacts at all — they are pre-existing feature-
extractor wiring gaps that panel-diverse data cannot fix by construction. This
is a genuine, actionable finding, not a data problem.

Like 2b-2a, this remains an offline, teacher-labeled experiment — see the
optimistic-metric caveat below.

## KPI: `dropped_constant_columns`

| | 2b-2a | 2b-2.5a | Target |
|---|---|---|---|
| dropped constant columns | 28 | **24** | ≤ 12 (stretch ~10) |
| live feature count | 45 | 49 | — |
| categorical features | 9 | 10 | — |

**KPI: MISSED** (24 > 12).

### Reactivated (4)

| feature | class | why it reactivated |
|---|---|---|
| `field_weather` | A (named) | genuine mirror-data artifact — fixed_team.txt (2b-2a's only team) never triggers weather; sun/rain hero panels now do |
| `trick_room_active` | A (named) | same — the trickroom hero panel now actually sets Trick Room |
| `tailwind_opp` | A (named) | same — opponent-side tailwind now occurs across the diverse villain panel |
| `ko_secured_count` | B (sentinel, bonus) | not required by R4; reactivated anyway from the larger/more varied game sample |

## Class-A feature status (spec R4 list)

R4 named class-A features: `field_weather`, `trick_room_active`, `tailwind_opp`,
`mirror_flag`, `slot*_move_*`, `tera_used`, `slot*_species_ids`.

| feature | status | root cause |
|---|---|---|
| `field_weather` | ALIVE | reactivated (mirror-data artifact, fixed) |
| `trick_room_active` | ALIVE | reactivated |
| `tailwind_opp` | ALIVE | reactivated |
| `mirror_flag` | **DEAD** | wiring gap — see (B) below |
| `slot1_move_type` / `slot2_move_type` | **DEAD** | wiring gap — see (A) below |
| `slot1_move_category` / `slot2_move_category` | **DEAD** | wiring gap — see (A) |
| `tera_used` | **DEAD** | likely candidate-truncation — see (C) below |
| `slot1_actor_species_id` / `slot2_actor_species_id` | **DEAD** | wiring gap — see (A) |
| `slot1_switch_target_species_id` / `slot2_switch_target_species_id` | **DEAD** | wiring gap — see (A) |
| `slot1_target_species_id_if_known` / `slot2_target_species_id_if_known` | **DEAD** | wiring gap — see (A) |

11 of 15 named class-A features are still dead. Six related, non-R4-named
columns share root cause (A) and are dead for the same reason:
`slot1_priority`/`slot2_priority`, `slot1_is_damaging`/`slot2_is_damaging`,
`slot1_is_protect`/`slot2_is_protect` — on top of the 10 R4-named columns
under (A), that's 16 columns sharing this one root cause.

## Diagnosis of still-dead class-A features

### (A) `dex=None` / `move_meta=None` hardcoded in the export runtime — 16 columns

`showdown_bot/src/showdown_bot/client/gauntlet.py` builds every
`DatasetExportRuntime` (both the live per-battle path at lines 233–243, and
`build_schedule_export_runtime()` at lines 567–577 — the function the T2
gauntlet CLI actually uses for schedule-driven datagen, i.e. **the exact path
the Kaggle kernels ran**) with:

```python
dex=None,
move_meta=None,
```

In `showdown_bot/src/showdown_bot/learning/features.py::_slot_action_features`,
every move/species field is gated on these being non-`None`
(`if meta is not None: ... else: <sentinel>`, `if ... and ctx.dex is not None`).
Since they are always `None`, the function always takes the sentinel branch —
**regardless of how many distinct moves or species actually appear** —
producing exactly the observed pattern:

```
slot1_move_type distribution: {'__none__': 17458}   # 100% sentinel, all 17458 rows
slot1_actor_species_id distribution: {'__none__': 17458}
```
even though `slot1_move_id` (unaffected — resolved directly from the request,
not through `ctx.move_meta`) shows 32 distinct move ids in the same dataset.

This is **not** a mirror-data artifact — 2b-2a's single-team dataset had this
exact same bug (all 16 of these columns are also in 2b-2a's 28), and no amount
of hero/opponent diversity can reactivate a feature whose extractor branch is
unconditionally skipped. It is a pre-existing wiring gap: the data needed
already exists in-repo and is cheap to provide —
`showdown_bot.engine.moves._move_table()` (a `dict[str, MoveMeta]`, data-driven
from `config/moves/movedata.json`, already exposes `.get(move_id)` with
`.move_type` / `.category` / `.priority` / `.is_damaging` matching the exact
attribute names `features.py` reads) and `showdown_bot.battle.opponent.SpeciesDex`
(a species-id normalizer) are both available locally — they are simply never
passed as `move_meta=` / `dex=` into `DatasetExportRuntime.from_env(...)` at
either gauntlet.py call site. Fixing this is a follow-up-slice candidate, not
something achievable by regenerating data.

Affected (16): `slot{1,2}_move_type`, `slot{1,2}_move_category`,
`slot{1,2}_priority`, `slot{1,2}_is_damaging`, `slot{1,2}_is_protect`,
`slot{1,2}_actor_species_id`, `slot{1,2}_switch_target_species_id`,
`slot{1,2}_target_species_id_if_known`.

### (B) `mirror_flag=False` hardcoded — 1 column

Both `gauntlet.py` call sites (line 236 and line 570) pass `mirror_flag=False`
unconditionally to the export runtime — never computed from whether the
battle is actually hero-vs-self. Confirmed: `mirror_flag` is `False` for all
17458 rows. Same category as (A): a wiring gap that data diversity cannot
touch, since the flag was never wired to real mirror/non-mirror detection in
either the 2b-2a or 2b-2.5a run.

### (C) `tera_used` — always False, likely candidate-truncation — 1 column

`tera_used` (`showdown_bot/src/showdown_bot/learning/features.py:394`) is
computed correctly from the joint action's `terastallize` flags, and does not
depend on `dex`/`move_meta` — so this is a distinct issue from (A)/(B). Ruled
out: "no team ever defines a Tera Type" — 3 of the 4 hero team files used in
this dataset (`teams/panel_v001/{trickroom,sun,rain}_dev.txt`) do specify
`Tera Type:` per Pokémon (only `teams/fixed_team.txt` lacks it), so tera
candidates should be legal in at least 3 of the 4 hero schedules. Yet
`tera_used` is `False` for all 17458 rows, including those hero subsets.

Leading hypothesis: the rollout teacher only labels the **top-K=6**
heuristic-ranked candidates per decision (`RolloutConfig.top_k = 6` in
`showdown_bot/src/showdown_bot/learning/teacher.py`, applied in
`rollout.py:334` — `for c in trace.candidates[: cfg.top_k]`). If terastallizing
variants are consistently ranked below the top 6 by the single-turn heuristic
score (plausible — the heuristic likely doesn't model Tera's permanent,
multi-turn value well relative to the non-tera version of the same move), they
would never survive to become an exported/labeled candidate row, independent
of how often Tera is actually legal. This is a hypothesis, not confirmed by a
battle re-run (out of scope here — no local battles per the hard constraint);
flagged for follow-up investigation alongside (A)/(B).

## Still-dead class-B features (expected — out of scope, 2b-2.5b)

`screens_ours`, `screens_opp`, `fakeout_invalid_penalty`, `action_economy_score`,
`protect_prior_target1`, `protect_prior_target2` — 6 of the original ~7
sentinel-capture features remain dead (`ko_secured_count` reactivated as a
bonus). Per spec, class-B sentinel capture is explicitly deferred to 2b-2.5b;
no capture code was added in this slice, so these stay constant as expected.

## A) ATTACK-strict (PRIMARY GATE)

- decisions 213
- mean regret: heuristic 1.7064  vs  model 0.8877
- wrong-but-near-equal: heuristic 19  vs  model 16

## B) all-strict (diagnostic)

- decisions 339
- mean regret: heuristic 1.927  vs  model 1.1402

## C) contestable-only (diagnostic)

- decisions 111
- mean regret: heuristic 1.3639  vs  model 0.9444

## Verdict: GO (gate passes)

`model_regret (0.8877) < heuristic_regret (1.7064)` and
`model_wrong_near_equal (16) <= heuristic_wrong_near_equal (19)` — same gate
definition as 2b-2a, still passes.

## Side-by-side with 2b-2a

| metric | 2b-2a | 2b-2.5a |
|---|---|---|
| dataset | single mirror team, 100 games | 4 hero panels × 3 villains, 300 games |
| dataset rows | 4658 | 17458 |
| live features | 45 | 49 |
| dropped constant columns | 28 | 24 |
| test split (games / decisions / rows) | 10 / 94 / 462 | 30 / 416 / 2255 |
| ATTACK-strict decisions | 63 | 213 |
| ATTACK heuristic regret | 1.3067 | 1.7064 |
| ATTACK model regret | 0.053 | 0.8877 |
| ATTACK wrong-near-equal (heur / model) | 10 / 1 | 19 / 16 |
| all-strict decisions | 74 | 339 |
| all-strict heuristic / model regret | 1.1125 / 0.5398 | 1.927 / 1.1402 |
| contestable decisions | 28 | 111 |
| contestable heuristic / model regret | 1.3855 / 0.1193 | 1.3639 / 0.9444 |
| Verdict | GO | GO |

**Caveat — regret magnitudes are not directly comparable.** The 2b-2.5a test
set is ~3.4x larger, drawn from 4 structurally different hero panels
(including hero teams that lose more often than they win — e.g. trickroom
11/74, rain 32/75 — vs. 2b-2a's single mirrored team) and against a 5-policy
diverse opponent mix instead of one mirror opponent. Absolute regret values
being higher across the board (both heuristic AND model) reflects a harder,
more varied evaluation distribution, not model regression — what is
comparable is the **relative** ordering (model beats heuristic in every
bucket, gate still passes) and the near-equal-mistake counts.

### The optimistic-metric caveat (carried over from 2b-2a, and from the spec)

Regret-vs-teacher is computed against the rollout teacher's own value
estimates on **teacher-labeled offline data** — the model is evaluated on the
same kind of signal it was trained to imitate, not against real head-to-head
play. This is an optimistic, offline proxy metric. It is useful for
comparing feature/model variants in isolation (which is what this slice
does), but it does not establish that this reranker beats the heuristic in
actual games. That claim is out of scope for 2b-2.5a: the paired live/shadow
strength evaluation belongs to 2b-2b / 2b-4.

## Kaggle provenance summary

### Phase 1 — validation gate

`KAGGLE-REPRO: PASS (10/10 winner+seed match, 10/10 room logs byte-identical
after normalization)` — kernel `chrismaghuhn/sb-repro-validation` v3, repo sha
`4f75696987b488867af024ce045944b4214ef8f2`, schedule
`config/eval/schedules/t4_smoke_v001_prefix.yaml`, seed base `t4rerun2026`.
Two earlier bootstrap attempts failed on image quirks (v1: `pip install -e`
not importable same-process; v2: `@smogon/calc` dist/ missing on fresh clone)
before v3 passed. Archived at `data/eval/kaggle-validation/` (verdict, results,
seed log, room dumps, sha256, full provenance.json).

### Phase 2 — datagen kernels (per hero)

| hero | kernel | version | repo sha | games | rows | hero wins | villain wins |
|---|---|---|---|---|---|---|---|
| fixed | sb-datagen-fixed | 3 | `adefdf802c3f1b95bfd5ab0def32c02281b67ec8` | 75 | 4374 | 30 | 45 |
| trickroom | sb-datagen-trickroom | 7 | `ee89eaa591a5b97098af2dbb6e79c1b4f1b97569` | 74* | 1922 | 11 | 64 |
| sun | sb-datagen-sun | 4 | `463a5965a125f9096e5e225561624b09be0273f5` | 75 | 3581 | 59 | 16 |
| rain | sb-datagen-rain | 4 | `463a5965a125f9096e5e225561624b09be0273f5` | 75 | 7581 | 32 | 43 |

\* trickroom ran 75 games but one produced zero sampled decisions (legitimate
blowout); coverage gate (ceil(0.9×75)=68) still passed at 74/75. See
`data/datasets/phase3-slice2b25a/manifest.json` notes.

Total: 300 games played, 299 with rows, 17458 dataset rows, teacher=rollout.
Per-kernel evidence (results/seed-logs/manifests) archived under
`data/datasets/phase3-slice2b25a/evidence/{fixed,trickroom,sun,rain}/`.

## Reproduction commands

```bash
# Retrain + offline eval (this report's numbers)
python -m showdown_bot.learning.reranker_train \
  data/datasets/phase3-slice2b25a/dataset.jsonl.gz \
  --out-model models/reranker/2026-07-11-2b25a-attack-lgbm.txt \
  --out-manifest models/reranker/2026-07-11-2b25a-attack-manifest.json \
  --out-report reports/2026-07-11-2b25a-offline-eval.md
```

Dataset sha256 (raw jsonl, as hashed by `reranker_train.sha256_of_file`):
`948570bb33e2923cdc8357f17dfd8db782a5d71cbc29645ace9c148da28f7572` (differs
from the committed `.gz`-file sha256 in `data/datasets/phase3-slice2b25a/sha256.txt`,
which hashes the compressed bytes, not the decompressed content — expected,
same convention as 2b-2a). `reranker_train`'s built-in sha check only warns
(does not fail) when the dataset sha differs from the pinned 2b-0 sha, since
this is intentionally a different dataset.

## Artifacts

- `models/reranker/2026-07-11-2b25a-attack-lgbm.txt` — trained booster
- `models/reranker/2026-07-11-2b25a-attack-manifest.json` — INV-7 manifest (feature names, encodings, dropped columns, split counts, metrics)
- `reports/2026-07-11-2b25a-offline-eval.md` — this report
- Prior (2b-2a, untouched): `models/reranker/2026-07-01-2b2a-attack-{lgbm.txt,manifest.json}`, `reports/2026-07-01-2b2a-reranker-offline-eval.md`

Nothing goes live from this slice — shadow/override paths are untouched.
