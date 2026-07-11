# tera_used Root-Cause Diagnosis

Slice 2b-2b, Task 3. Read-only analysis — no production code changed. Companion to
`reports/2026-07-11-2b2b-feature-ablation.md`: `tera_used` is one of the 7
`dropped_constant_columns` in that report (and in
`models/reranker/2026-07-11-2b25a-attack-manifest.json`), so it never entered the LOCO/SCO
partition. This report answers *why* it's constant.

**Verdict up front:** two independent, confirmed root causes, and one correction to the prior
(2b-2.5a offline-eval) hypothesis. `tera_used` is **not** a truncation artifact — Tera actions are
never enumerated as candidates in the first place, so there is nothing for `top_k` to truncate. And
the heuristic **does** occasionally Tera (rare, but not zero as an earlier informal pass on this
diagnosis assumed) — those decisions are silently dropped from the exported dataset by a separate,
also-structural mechanism. See the "correction" callout in the data-rarity section below.

## 1. Measurement: tera_used is constant across the committed dataset

`data/datasets/phase3-slice2b25a/dataset.jsonl.gz`, 17458 rows total (each row is
`{"features": {...}, "label": {...}, "metadata": {...}}`; the columns below live under `features`):

| column | value counts |
|---|---|
| `tera_used` | `False`: 17458 / 17458 (100%) |
| `slot1_is_switch` (control) | `False`: 16068, `True`: 1390 |

The control column has real variance, so the extractor pipeline and the read itself are not
broken — `tera_used` specifically collapses to a single value. Confirmed by direct re-count
(gzip + json, full scan, no sampling).

## 2. Root cause A — structural non-capture (Tera is never an enumerated candidate)

`showdown_bot/src/showdown_bot/battle/actions.py`:

- `JointAction` docstring (line 17): *"A both-slots decision for one turn, **WITHOUT Tera**... Tera
  is intentionally stripped from enumeration ... and re-applied as a single overlay ... via
  `with_tera`."*
- `_slot_actions()` (lines 82–86) explicitly filters: `moves = [a for a in _slot_move_actions(...)
  if not a.terastallize]`.
- `enumerate_my_actions()` (line 90) builds every `JointAction` from `_slot_actions()` — so its
  entire output space is Tera-free by construction.

`showdown_bot/src/showdown_bot/battle/decision.py`:

- Line 231: `my_actions = enumerate_my_actions(req, ...)` — the non-Tera space above.
- Line 281: `items = [(ja, score_plan(plan)) for ja, plan in plans.items()]` — built from `plans`,
  which is keyed by `my_actions` (line 237-243). Still Tera-free.
- Lines 286–290: `best_ja = _maybe_tera(req, best_ja, ...)` — `_maybe_tera` (def at line 544) is a
  **post-hoc overlay** applied only to the single non-Tera winner: it tries
  `best_ja.with_tera(i)` (line 559, `actions.py:30`) and keeps it only if it beats the non-Tera
  line by `tera_margin` (default 1.0). It runs *after* `pick_best` has already chosen from the
  Tera-free `items`.
- Lines 394–400: `scored = [(ja, scores, aggregate_scores(...)) for ja, scores in items]` →
  `cands = scored[:TOP_K_TRACE_CANDIDATES]` (`TOP_K_TRACE_CANDIDATES = 6`, line 30). `items` is the
  same Tera-free list from line 281 — **every entry in `cands` is Tera-free by construction**,
  regardless of `TOP_K_TRACE_CANDIDATES`'s value.
- Line 413: `trace.chosen_candidate_id = _label_ja(req, best_ja)` — but `best_ja` here is the
  *post-overlay* value from line 286-290, which **can** be Tera'd.
- `_label_ja` (lines 128–141) appends `" tera"` to the label when `sa.terastallize` is set (lines
  137–138).

Net effect: `cands` (the exported candidate list) can never contain a Tera'd entry, but
`chosen_candidate_id` can be a Tera-labeled string that does not match any label in `cands`. This
mismatch is not cosmetic — it breaks the rollout/export path (root cause B, next section).

`showdown_bot/src/showdown_bot/learning/features.py:394`:
`out["tera_used"] = bool(ja.slot0.terastallize or ja.slot1.terastallize)` — confirmed to read the
Tera flags correctly off whichever `JointAction` it's given. The extractor itself is not the bug;
it is simply never handed a Tera'd candidate to extract from, because Tera'd actions never appear
in the candidate list that gets exported as rows.

## 3. Root cause B — hero-Tera decisions are silently dropped, not merely unlabeled

`showdown_bot/src/showdown_bot/learning/rollout.py:347–351`:

```python
if trace.chosen_candidate_id not in teacher_values:
    raise RolloutLabelError(
        f"chosen_candidate_id {trace.chosen_candidate_id!r} is not among the "
        f"rollout candidates ({list(teacher_values)!r})"
    )
```

`teacher_values` is keyed off the same candidate-label space as `cands` (Tera-free, per root cause
A). So whenever the heuristic actually spends Tera (`chosen_candidate_id` carries the `" tera"`
suffix), this lookup fails by construction and `RolloutLabelError` fires.

`showdown_bot/src/showdown_bot/learning/export_runtime.py`, `DatasetExportRuntime.observe()`
(lines 290–345): the call to `self._provider.labels_for_decision(...)` (line 325) is wrapped in
`except RolloutLabelError as exc:` (line 328) → `self.skipped_count += 1` (line 329), a debug log
line, a skip-rate threshold check (`_check_threshold`, line 347), and **no row is added** — `n`
stays `0` (comment at line 332), the decision is not exported. Confirmed this is the *only* catch
site: the module docstring at line 13 states `observe`` gates on SamplingPolicy, catches ONLY
RolloutLabelError`, and every other exception is left to propagate (hard-fail).

So: it's not that a hero-Tera decision gets exported *without* Tera signal — it is dropped from
the dataset entirely.

## 4. Data measurement — the heuristic is rare-but-not-zero on Tera (correction)

**This corrects an earlier informal claim of zero events for the trickroom-hero logs. The real
count is nonzero — reported prominently per the verification brief, not glossed over.**

Measured directly against `C:/tmp/kaggle25a/datagen/trickroom_regen/room_raw/*.log.gz` (75 files,
matching `data/datasets/phase3-slice2b25a/manifest.json`'s `trickroom` hero: same `run_id`
`6c7ab8a2ad570c34`, 74/75 games contributed rows to the committed dataset). Counted lines that
**start with** `|-terastallize|` (real protocol events), separately from the 2634 substring hits of
`"canTerastallize"` inside `|request|` JSON blobs (those are legality flags, not actions — the
earlier informal pass conflated "0 real events" with "these `canTerastallize` mentions don't
count," which is correct, but then undercounted the real events too):

| | count |
|---|---|
| real `\|-terastallize\|` protocol events, trickroom_regen | **19** (not 0) |
| ... on the Heuristic side (`p1`, the exported/self side) | **4**, across 4 distinct games |
| ... on the opponent side (`p2` = `BaselineBot*`, not exported) | 15 |

`trickroom_regen`'s `|player|` lines confirm `p1` = `HeuristicBot*`, `p2` = `BaselineBot*` for every
file — this is not self-play, so the side matters: only the `p1` (Heuristic) events are relevant to
`tera_used`, which is computed from *our* joint action (`features.py:394`), not the opponent's.

Extending the same count to all four hero quarters that make up the committed 17458-row dataset
(`fixed_regen`, `trickroom_regen`, `sun_regen`, `rain_regen` — 75 room logs each, 300 games total,
matching `manifest.json`'s `total_games_played: 300`):

| hero | games | total `\|-terastallize\|` events | Heuristic-side events | games with Heuristic Tera |
|---|---|---|---|---|
| fixed | 75 | 15 | 0 | 0 |
| trickroom | 75 | 19 | 4 | 4 |
| sun | 75 | 15 | 0 | 0 |
| rain | 75 | 15 | 0 | 0 |
| **total** | **300** | **64** | **4** | **4** |

So across the entire 300-game corpus backing the committed dataset, the heuristic terastallized in
**4 games out of 300 (1.3%), all within the `trickroom` hero (4/75 = 5.3% of trickroom games)**,
and zero times in the `fixed`/`sun`/`rain` heroes. This is genuinely rare — but it is not zero, and
those 4 real Tera decisions are exactly the ones root cause B (section 3) predicts get silently
skipped: `tera_used=True` never appears in the 17458 exported rows despite at least 4 real
Tera'd decisions existing in the underlying games. (We don't have per-decision skip logs from these
Kaggle runs at the sampled log level to name the exact 4 skipped decisions by turn number — the
runtime only logs skips at `logger.debug`, which wasn't captured — but the code path in section 3
guarantees a Tera'd `chosen_candidate_id` cannot match `cands`, so this is not a coincidence.)

The rarity is plausibly tied to the same TR-piloting weakness documented in
`heuristic-moves-conditions-spec`/`play-quality-levers` memory (2026-07-10 finding): the heuristic
has no TR-setup logic, so `trickroom`-hero games are where it's most often in a losing, high-`risk`
position — plausibly the scenario where `_maybe_tera`'s margin-beating overlay fires. Not confirmed
causally here (out of scope, no battle re-runs), just noted as a plausible parallel structural gap.

## 5. Why this is NOT the top-6 truncation the 2b-2.5a offline-eval report hypothesized

`reports/2026-07-11-2b25a-offline-eval.md`, diagnosis (C), hypothesized:

> "the rollout teacher only labels the top-K=6 heuristic-ranked candidates per decision
> (`RolloutConfig.top_k = 6` ... `rollout.py:334` — `for c in trace.candidates[: cfg.top_k]`). If
> terastallizing variants are consistently ranked below the top 6 ... they would never survive to
> become an exported/labeled candidate row..."

This is refuted by the code trace in section 2: `trace.candidates` (what `rollout.py:334` truncates)
is built from `cands` (`decision.py:399-400`), which is itself built from `items`/`my_actions` — the
Tera-free enumeration from `actions.py`. Tera'd variants are never *in* the pre-truncation list to
begin with, so there is no rank for them to fall out of. Raising `top_k`, or ensuring Tera survives
truncation, would not change anything: the truncation operates on an already-Tera-free set.
`TOP_K_TRACE_CANDIDATES` (`decision.py:30`, also 6) is the decision-trace-side analog and has the
same property. **Truncation is a red herring for `tera_used` specifically** — the real cause is
upstream, at enumeration (root cause A), reinforced by the rollout-label mismatch (root cause B).

## 6. Conclusion

Two independent, both-confirmed mechanisms, plus the rarity data point:

1. **Structural non-capture.** Tera is architecturally an overlay on the single chosen action, not
   a first-class enumerated candidate (`actions.py` docstring, by design — halves the search space
   the heuristic has to score every turn). `tera_used` can **never** be `True` for an exported row,
   independent of how often Tera is actually used, because the candidate list it's extracted from
   is Tera-free by construction.
2. **Rollout-label mismatch drops hero-Tera decisions entirely.** On the rare occasions the
   heuristic *does* spend Tera (4/300 games measured, all in the `trickroom` hero), the resulting
   decision's `chosen_candidate_id` can't match any rollout candidate, `RolloutLabelError` fires,
   and `export_runtime.py::observe()` silently skips the row (caught, counted, not raised) — so even
   if (1) were somehow not true, these specific decisions would still never reach the dataset.

Both are real and both are structural, not a data-volume problem — more battles or more panel
diversity would not fix either. (Given the corrected rarity number, it's also not simply "nothing to
capture": 4 real Tera decisions in this corpus *were* thrown away by mechanism 2, not just
hypothetically.)

## 7. Recommendation (future slice, not this one)

To give the reranker any Tera signal at all requires two changes, and both are prerequisites:

- **Enumerate Tera as a first-class candidate** in `decision.py`/`actions.py` (a real enumeration
  change, not a labeling fix) so Tera'd actions can appear in `cands`/`trace.candidates` and get a
  matching rollout-teacher label instead of hitting `RolloutLabelError`.
- **A reason to expect nonzero signal once captured**: per the 2026-07-10 TR-piloting finding
  (`play-quality-levers` memory), a "Tera-piloting" lever (when to spend Tera, not just whether it's
  legal) is itself an open play-quality gap, parallel to TR-piloting. Capturing `tera_used` without
  first improving *when* the heuristic Teras would just faithfully record a bad, rare policy.

For **this** slice: `tera_used` is correctly pruned as `dropped_constant` (confirmed dead, not a
data-volume artifact) — no action needed on the current dataset/model. Revisit both the enumeration
gap and Tera-piloting together in a future slice; do not regenerate data for this alone.

## Verification appendix (how each number was produced)

- `tera_used`/`slot1_is_switch` counts: full-scan `gzip.open(..., 'rt')` + `json.loads` over
  `data/datasets/phase3-slice2b25a/dataset.jsonl.gz`, counting `row["features"][col]` per line (all
  17458 rows, no sampling).
- Code trace: direct `Read`/`Grep` of `showdown_bot/src/showdown_bot/battle/actions.py`,
  `battle/decision.py`, `learning/rollout.py`, `learning/export_runtime.py`,
  `learning/features.py` at the cited line numbers (re-read fresh in this session, not taken on
  faith from a prior pass).
- Tera event counts: `gzip.open(..., 'rt')` per `*.log.gz` in each hero's `room_raw/` dir, splitting
  on newlines, counting lines with `line.startswith("|-terastallize|")` (not substring match, to
  exclude `canTerastallize` JSON mentions), cross-referencing `|player|` lines to attribute each
  event to `p1`/`p2` and thus Heuristic vs. Baseline side. Hero provenance cross-checked against
  `data/datasets/phase3-slice2b25a/manifest.json` (`run_id` match, `distinct_games` match).

## Cross-references

- `reports/2026-07-11-2b2b-feature-ablation.md` — `tera_used` is one of the 7
  `dropped_constant_columns` reported there (constant-column drop happens before the LOCO/SCO
  partition even runs, so it's absent from that report's tables by construction).
- `reports/2026-07-11-2b25a-offline-eval.md`, diagnosis (C) — the truncation hypothesis this report
  refutes.
- `data/datasets/phase3-slice2b25a/manifest.json` — hero/game/run-id provenance used to match the
  local `room_raw/` logs to the committed dataset.
