# Slice 2b-1: Dataset Loader + Split + Baseline Evaluator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the offline data tooling for the Phase-3 reranker — load the rollout-label JSONL, group by decision, split by game (no leakage), and a baseline evaluator that reproduces the 2b-0 QA numbers — with explicit near-equal/zero-gap handling. **No model. No live behavior change.**

**Architecture:** Two new modules in the existing `learning/` package. `dataset.py` owns loading + grouping + splitting + action-class derivation. `baseline_eval.py` owns metrics + markdown report + a CLI. The eval reads the frozen schema (`learning/schema.py`) and is pure/offline. A regression test pins the evaluator to the committed 100-game dataset's exact numbers.

**Tech Stack:** Python 3, stdlib only (json, gzip, dataclasses, hashlib, random, statistics, argparse). Reuse `learning/schema.py` (`from_jsonl_line`, `LABEL_KEYS`, `validate_row`) and the bot's existing move metadata for action-class derivation. pytest for tests.

---

## Context the worker needs

- **Row contract** (`learning/schema.py`): every JSONL line is `{"features":{...}, "metadata":{...}, "label":{...}}`. One row per **(decision × candidate)**. Group by `metadata.game_id` then `metadata.decision_id`. Candidate order = `metadata.candidate_index`.
- **Key label fields:** `teacher_best` (bool), `chosen_by_current_heuristic` (bool, exactly one True per decision), `value_gap_to_best` (≤ 0.0; 0.0 means tied-with-best), `teacher_rank`, `heuristic_rank`, `counterfactual_value_raw`.
- **Committed dataset:** `data/datasets/phase3-slice2b/rollout_labels_100g_gen9vgc2025regi_h1_v1.jsonl.gz` (660 KB, repo root). The raw `.jsonl` is gitignored. QA report: `reports/2026-06-30-slice2b-100game-dataset-report.md`. Manifest: `data/datasets/phase3-slice2b/manifest.json`.
- **Feature gotcha (2b-0 QA):** `slot*_is_damaging`, `slot*_is_protect`, `slot*_move_category`, `slot*_move_type`, `slot*_actor_species_id`, `slot*_priority`, `tera_used`, … are constant/dead in this export. **Do NOT classify actions with those flags.** Derive action class from `slot1_move_id` + `slot1_action_type` + the bot's move metadata (category). Feature-extractor fix is a later slice (priority 3).
- **The exact numbers to reproduce** (from the committed dataset, seed-independent except the split):
  - rows 4658, games 100, decisions 951, multi-candidate 851, forced/single 100.
  - candidate-count distribution `{1:100, 2:101, 5:144, 6:606}`.
  - unique-`teacher_best` decisions 851; explicit teacher-best ties 100.
  - heuristic==teacher_best, multi **topset** (heuristic choice ∈ teacher-best set): 524/851 = 61.6%.
  - heuristic==teacher_best, **unique-multi-strict** (exactly one heuristic choice AND exactly one teacher-best): 424/751 = 56.5%.
  - ATTACK agreement 317/643 = 49.3%; protect agreement 107/108 = 99.1%.
  - contestable `abs(non_best_gap) ≤ 0.5`: 529/951 = 55.6% (multi 529/851 = 62.2%).
  - exact-zero-gap non-best alternative: 348/951 = 36.6%.
  - nonzero near-equal `0 < abs(gap) ≤ 0.5`: 279/951 = 29.3%.
  - seed-42 80/10/10 by game: train 80g/762d/3729r, val 10g/95d/467r, test 10g/94d/462r.

## File Structure

- Create `showdown_bot/src/showdown_bot/learning/dataset.py` — loading, `Decision`, grouping, `split_by_game`, `action_class`.
- Create `showdown_bot/src/showdown_bot/learning/baseline_eval.py` — `BaselineMetrics`, `evaluate_baseline`, `format_report`, CLI `__main__`.
- Create `showdown_bot/tests/test_dataset.py` — loading, grouping, ties, action-class, split leakage/determinism.
- Create `showdown_bot/tests/test_baseline_eval.py` — metric math on tiny fixtures + near-equal/zero-gap + the **committed-dataset regression test**.

Run tests: `cd showdown_bot && python -m pytest -q tests/test_dataset.py tests/test_baseline_eval.py`. Full suite: `cd showdown_bot && python -m pytest -q`.

---

### Task 1: `dataset.py` — load + Decision grouping + action class

**Files:**
- Create: `showdown_bot/src/showdown_bot/learning/dataset.py`
- Test: `showdown_bot/tests/test_dataset.py`

- [ ] **Step 1: Write failing tests** (grouping, sort, ties, action class)

```python
# tests/test_dataset.py
import gzip, json
from showdown_bot.learning.dataset import (
    load_rows, group_decisions, action_class, Decision,
)

def _row(game, dec, idx, *, move_id="tackle", action_type="move",
         teacher_best=False, chosen=False, gap=-1.0):
    # minimal row honoring the schema's three top-level dicts; only the
    # fields the loader reads need realistic values.
    return {
        "features": {"slot1_move_id": move_id, "slot1_action_type": action_type},
        "metadata": {"game_id": game, "decision_id": dec, "candidate_index": idx},
        "label": {"teacher_best": teacher_best,
                  "chosen_by_current_heuristic": chosen,
                  "value_gap_to_best": gap},
    }

def test_group_by_game_then_decision_sorts_by_candidate_index():
    rows = [_row("g1", "d1", 2), _row("g1", "d1", 0), _row("g1", "d1", 1)]
    decs = group_decisions(rows)
    assert len(decs) == 1
    assert [r["metadata"]["candidate_index"] for r in decs[0].rows] == [0, 1, 2]

def test_same_decision_id_in_two_games_stays_separate():
    rows = [_row("g1", "dX", 0), _row("g2", "dX", 0)]
    decs = group_decisions(rows)
    assert len(decs) == 2  # keyed by (game_id, decision_id), no collision

def test_decision_helpers_chosen_and_teacher_best_and_ties():
    rows = [_row("g", "d", 0, teacher_best=True, chosen=True, gap=0.0),
            _row("g", "d", 1, teacher_best=True, gap=0.0),   # tie at best
            _row("g", "d", 2, gap=-3.0)]
    d = group_decisions(rows)[0]
    assert d.is_multi_candidate
    assert d.chosen_row()["metadata"]["candidate_index"] == 0
    assert len(d.teacher_best_rows()) == 2          # tie counted, not collapsed
    assert d.is_tie                                  # >1 teacher_best
    assert d.zero_gap_nonbest_count() == 1           # idx1: gap 0 but not chosen-best

def test_action_class_from_move_id():
    assert action_class(_row("g","d",0, move_id="protect")) == "protect"
    assert action_class(_row("g","d",0, move_id="tackle")) == "attack"
    assert action_class(_row("g","d",0, action_type="switch", move_id="")) == "switch"
    assert action_class(_row("g","d",0, move_id="tailwind")) == "status"
```

- [ ] **Step 2: Run, verify it fails** — `pytest tests/test_dataset.py -x` → ImportError / NameError.

- [ ] **Step 3: Implement `dataset.py`**

```python
"""Offline dataset tooling for the Phase-3 reranker (slice 2b-1).

Pure/offline: loads rollout-label JSONL, groups rows into Decisions
(keyed by (game_id, decision_id)), derives an action class from move_id
(the slot*_is_* / move_category feature flags are dead in the 2b-0 export),
and splits by game with no leakage. No model, no live behavior.
"""
from __future__ import annotations

import gzip
import json
import random
from dataclasses import dataclass

from showdown_bot.engine.moves import get_move_meta, to_id  # move_id -> MoveMeta (.category/.is_damaging)

# Protect-family moves (normalized id form). The dead `slot*_is_protect` flag
# can't be used (constant False in the 2b-0 export — it ran with move_meta=None);
# the protect family is a small named set, everything else is classified by the
# move's real category via get_move_meta().
PROTECT_MOVE_IDS = frozenset({
    "protect", "detect", "spikyshield", "kingsshield", "banefulbunker",
    "obstruct", "silktrap", "burningbulwark", "maxguard",
})


def _open(path: str):
    return gzip.open(path, "rt", encoding="utf-8") if str(path).endswith(".gz") \
        else open(path, "rt", encoding="utf-8")


def load_rows(path: str) -> list[dict]:
    """Load a rollout-label JSONL (.jsonl or .jsonl.gz) into raw dict rows."""
    rows = []
    with _open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def action_class(row: dict) -> str:
    """Coarse action class of slot1 derived from move_id + action_type.
    One of: 'switch' | 'protect' | 'attack' | 'status'. Uses the bot's real
    move metadata (get_move_meta) for category; protect family special-cased
    by id. NB: get_move_meta defaults unknown ids to a damaging move, so a
    real (known) move_id classifies exactly."""
    f = row["features"]
    if f.get("slot1_action_type") == "switch" or f.get("slot1_is_switch") is True:
        return "switch"
    mid = f.get("slot1_move_id") or ""
    if not mid:
        return "switch"  # non-move action with no move id (e.g. pass/forced)
    if to_id(mid) in PROTECT_MOVE_IDS:
        return "protect"
    return "attack" if get_move_meta(mid).is_damaging else "status"


@dataclass
class Decision:
    game_id: str
    decision_id: str
    rows: list[dict]  # sorted by candidate_index

    @property
    def is_multi_candidate(self) -> bool:
        return len(self.rows) > 1

    def chosen_row(self) -> dict | None:
        cs = [r for r in self.rows if r["label"]["chosen_by_current_heuristic"]]
        return cs[0] if cs else None

    def teacher_best_rows(self) -> list[dict]:
        return [r for r in self.rows if r["label"]["teacher_best"]]

    @property
    def is_tie(self) -> bool:
        return len(self.teacher_best_rows()) > 1

    def zero_gap_nonbest_count(self) -> int:
        return sum(1 for r in self.rows
                   if not r["label"]["teacher_best"]
                   and r["label"]["value_gap_to_best"] == 0.0)


def group_decisions(rows: list[dict]) -> list[Decision]:
    """Group rows by (game_id, decision_id); sort each group by candidate_index.
    Deterministic order: by first-seen (game_id, decision_id)."""
    order: list[tuple[str, str]] = []
    buckets: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        m = r["metadata"]
        key = (m["game_id"], m["decision_id"])
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(r)
    out = []
    for key in order:
        grp = sorted(buckets[key], key=lambda r: r["metadata"]["candidate_index"])
        out.append(Decision(game_id=key[0], decision_id=key[1], rows=grp))
    return out
```

> **Worker note:** `get_move_meta`/`to_id` are the real loaders in `showdown_bot/src/showdown_bot/engine/moves.py` (movedata at `showdown_bot/config/moves/movedata.json`, present in the repo — no monkeypatch needed; `tackle`→attack, `tailwind`→status, `protect`→protect all resolve against real data). After wiring, confirm `action_class` on the committed dataset yields **643 attack + 108 protect** chosen rows among unique-multi decisions (Task 4 asserts this).

- [ ] **Step 4: Run tests, verify pass** — `cd showdown_bot && python -m pytest tests/test_dataset.py -q`. The action-class test needs no monkeypatch: `get_move_meta` reads the repo's real `movedata.json`.

- [ ] **Step 5: Commit** — `git add showdown_bot/src/showdown_bot/learning/dataset.py showdown_bot/tests/test_dataset.py && git commit -m "feat(2b-1): dataset loader + Decision grouping + action_class"`

---

### Task 2: `split_by_game` — seeded, no leakage

**Files:**
- Modify: `showdown_bot/src/showdown_bot/learning/dataset.py`
- Test: `showdown_bot/tests/test_dataset.py`

- [ ] **Step 1: Write failing tests**

```python
from showdown_bot.learning.dataset import split_by_game, Split

def _decs(n_games, per_game=3):
    rows = []
    for g in range(n_games):
        for d in range(per_game):
            rows.append(_row(f"g{g}", f"g{g}-d{d}", 0, chosen=True, teacher_best=True))
            rows.append(_row(f"g{g}", f"g{g}-d{d}", 1))
    return group_decisions(rows)

def test_split_by_game_is_disjoint_and_covers_all():
    decs = _decs(100)
    sp = split_by_game(decs, seed=42, ratios=(0.8, 0.1, 0.1))
    gtr = {d.game_id for d in sp.train}
    gva = {d.game_id for d in sp.val}
    gte = {d.game_id for d in sp.test}
    assert gtr.isdisjoint(gva) and gtr.isdisjoint(gte) and gva.isdisjoint(gte)
    assert gtr | gva | gte == {f"g{i}" for i in range(100)}
    assert (len(gtr), len(gva), len(gte)) == (80, 10, 10)

def test_no_decision_leaks_across_splits():
    decs = _decs(50)
    sp = split_by_game(decs, seed=7, ratios=(0.8, 0.1, 0.1))
    ids = lambda part: {(d.game_id, d.decision_id) for d in part}
    assert ids(sp.train).isdisjoint(ids(sp.val))
    assert ids(sp.train).isdisjoint(ids(sp.test))
    assert ids(sp.val).isdisjoint(ids(sp.test))

def test_split_is_deterministic_for_seed():
    decs = _decs(30)
    a = split_by_game(decs, seed=42, ratios=(0.8, 0.1, 0.1))
    b = split_by_game(decs, seed=42, ratios=(0.8, 0.1, 0.1))
    assert [d.decision_id for d in a.train] == [d.decision_id for d in b.train]
```

- [ ] **Step 2: Run, verify fail** — ImportError `Split`/`split_by_game`.

- [ ] **Step 3: Implement**

```python
@dataclass
class Split:
    train: list[Decision]
    val: list[Decision]
    test: list[Decision]


def split_by_game(decisions: list[Decision], *, seed: int = 42,
                  ratios: tuple[float, float, float] = (0.8, 0.1, 0.1)) -> Split:
    """Partition decisions into train/val/test by GAME (never by row/decision).
    All decisions of a game go to one split. Deterministic for a given seed."""
    assert abs(sum(ratios) - 1.0) < 1e-9, "ratios must sum to 1"
    games = sorted({d.game_id for d in decisions})
    rng = random.Random(seed)
    rng.shuffle(games)
    n = len(games)
    n_tr = int(round(n * ratios[0]))
    n_va = int(round(n * ratios[1]))
    tr = set(games[:n_tr]); va = set(games[n_tr:n_tr + n_va]); te = set(games[n_tr + n_va:])
    bucket = {"tr": [], "va": [], "te": []}
    for d in decisions:
        key = "tr" if d.game_id in tr else ("va" if d.game_id in va else "te")
        bucket[key].append(d)
    return Split(train=bucket["tr"], val=bucket["va"], test=bucket["te"])
```

- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat(2b-1): split_by_game (seeded, leakage-free)"`

---

### Task 3: `baseline_eval.py` — metrics + near-equal/zero-gap + report + CLI

**Files:**
- Create: `showdown_bot/src/showdown_bot/learning/baseline_eval.py`
- Test: `showdown_bot/tests/test_baseline_eval.py`

- [ ] **Step 1: Write failing tests** (metric math on tiny fixtures, incl. the two hard requirements)

```python
# tests/test_baseline_eval.py
from showdown_bot.learning.dataset import group_decisions, Decision
from showdown_bot.learning.baseline_eval import evaluate_baseline, BaselineMetrics

def _r(game, dec, idx, **lbl):
    base = {"teacher_best": False, "chosen_by_current_heuristic": False,
            "value_gap_to_best": -1.0}
    base.update(lbl)
    return {"features": {"slot1_move_id": "tackle", "slot1_action_type": "move"},
            "metadata": {"game_id": game, "decision_id": dec, "candidate_index": idx},
            "label": base}

def test_agreement_counts_topset_and_strict():
    # decision A: heuristic-chosen IS teacher_best (agree)
    A = [_r("g","A",0, teacher_best=True, chosen_by_current_heuristic=True, value_gap_to_best=0.0),
         _r("g","A",1, value_gap_to_best=-2.0)]
    # decision B: heuristic-chosen is NOT teacher_best (disagree), gap -0.3 -> near-equal-safe
    B = [_r("g","B",0, teacher_best=True, value_gap_to_best=0.0),
         _r("g","B",1, chosen_by_current_heuristic=True, value_gap_to_best=-0.3)]
    m = evaluate_baseline(group_decisions(A + B))
    assert m.multi_decisions == 2
    assert m.agree_topset == 1 and m.agree_topset_total == 2          # 50%
    assert m.wrong_but_near_equal == 1                               # B is a cheap miss
    assert m.mean_regret == 0.15                                     # (0.0 + 0.3)/2

def test_tie_decision_excluded_from_strict_but_in_topset():
    T = [_r("g","T",0, teacher_best=True, chosen_by_current_heuristic=True, value_gap_to_best=0.0),
         _r("g","T",1, teacher_best=True, value_gap_to_best=0.0),
         _r("g","T",2, value_gap_to_best=-1.0)]
    m = evaluate_baseline(group_decisions(T))
    assert m.ties == 1
    assert m.agree_topset == 1                  # chosen ∈ teacher-best set
    assert m.strict_total == 0                  # tie excluded from unique-strict

def test_zero_gap_nonbest_flagged():
    Z = [_r("g","Z",0, teacher_best=True, chosen_by_current_heuristic=True, value_gap_to_best=0.0),
         _r("g","Z",1, value_gap_to_best=0.0),   # equal value, not marked best
         _r("g","Z",2, value_gap_to_best=-5.0)]
    m = evaluate_baseline(group_decisions(Z))
    assert m.zero_gap_nonbest_decisions == 1
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement `baseline_eval.py`** (dataclass + the metric pass; reuse `dataset.action_class`)

```python
"""Baseline evaluator for the Phase-3 reranker dataset (slice 2b-1).

Reproduces the 2b-0 QA metrics on any rollout-label JSONL: heuristic vs
teacher agreement (topset + unique-strict), per action class (ATTACK!),
contestability, and explicit near-equal / zero-gap handling. Offline only.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

from showdown_bot.learning.dataset import (
    Decision, action_class, group_decisions, load_rows, split_by_game,
)

NEAR_EQUAL = 0.5  # |value_gap| <= 0.5 is "near-equal"


@dataclass
class BaselineMetrics:
    rows: int = 0
    games: int = 0
    decisions: int = 0
    multi_decisions: int = 0
    forced_decisions: int = 0
    ties: int = 0
    # agreement
    agree_topset: int = 0          # chosen ∈ teacher-best set (multi)
    agree_topset_total: int = 0
    agree_strict: int = 0          # unique chosen == unique teacher_best (multi, non-tie)
    strict_total: int = 0
    # near-equal / zero-gap (the 2b-2 training-safety signal)
    wrong_but_near_equal: int = 0      # disagree but |chosen gap| <= 0.5
    mean_regret: float = 0.0           # mean |chosen value_gap| over multi
    contestable_decisions: int = 0     # >=1 non-best alt with |gap| <= 0.5
    zero_gap_nonbest_decisions: int = 0
    nonzero_near_equal_decisions: int = 0
    # per action class (chosen row), multi only
    by_action: dict | None = None      # cls -> (agree, total)


def _pct(a: int, b: int) -> str:
    return f"{a}/{b} = {100*a/b:.1f}%" if b else f"{a}/0 = n/a"


def evaluate_baseline(decisions: list[Decision]) -> BaselineMetrics:
    m = BaselineMetrics(by_action={})
    m.decisions = len(decisions)
    m.games = len({d.game_id for d in decisions})
    m.rows = sum(len(d.rows) for d in decisions)
    regrets: list[float] = []
    for d in decisions:
        if d.is_tie:
            m.ties += 1
        # contestable / zero-gap (all decisions)
        near = [r for r in d.rows
                if not r["label"]["teacher_best"]
                and r["label"]["value_gap_to_best"] is not None
                and abs(r["label"]["value_gap_to_best"]) <= NEAR_EQUAL]
        if near:
            m.contestable_decisions += 1
        if d.zero_gap_nonbest_count() > 0:
            m.zero_gap_nonbest_decisions += 1
        if any(0.0 < abs(r["label"]["value_gap_to_best"]) <= NEAR_EQUAL for r in near):
            m.nonzero_near_equal_decisions += 1
        if not d.is_multi_candidate:
            m.forced_decisions += 1
            continue
        m.multi_decisions += 1
        chosen = d.chosen_row()
        if chosen is None:
            continue
        gap = chosen["label"]["value_gap_to_best"]
        regrets.append(abs(gap) if gap is not None else 0.0)
        in_best = chosen["label"]["teacher_best"]
        # topset agreement
        m.agree_topset_total += 1
        if in_best:
            m.agree_topset += 1
        else:
            if gap is not None and abs(gap) <= NEAR_EQUAL:
                m.wrong_but_near_equal += 1
        # strict (exactly one chosen, exactly one teacher_best) + per-action-class.
        # by_action is computed on the SAME unique-strict set so its denominators
        # match the 2b-0 QA report (attack 643 + protect 108 == strict_total 751).
        if not d.is_tie:
            m.strict_total += 1
            if in_best:
                m.agree_strict += 1
            cls = action_class(chosen)
            agree, total = m.by_action.get(cls, (0, 0))
            m.by_action[cls] = (agree + (1 if in_best else 0), total + 1)
    m.mean_regret = round(sum(regrets) / len(regrets), 4) if regrets else 0.0
    return m


def format_report(m: BaselineMetrics) -> str:
    lines = ["# Baseline Evaluation Report", "",
             f"- rows {m.rows} · games {m.games} · decisions {m.decisions} "
             f"(multi {m.multi_decisions}, forced {m.forced_decisions}, ties {m.ties})",
             "",
             "## Heuristic vs Teacher",
             f"- topset agreement (multi): {_pct(m.agree_topset, m.agree_topset_total)}",
             f"- unique-strict agreement: {_pct(m.agree_strict, m.strict_total)}",
             f"- mean regret (|value_gap| of chosen, multi): {m.mean_regret}",
             "",
             "## Near-equal / zero-gap (training-safety)",
             f"- wrong-but-near-equal (disagree, |gap| ≤ {NEAR_EQUAL}): {m.wrong_but_near_equal}",
             f"- contestable decisions (≥1 non-best |gap| ≤ {NEAR_EQUAL}): "
             f"{_pct(m.contestable_decisions, m.decisions)}",
             f"- zero-gap non-best alternative: {_pct(m.zero_gap_nonbest_decisions, m.decisions)}",
             f"- nonzero near-equal (0 < |gap| ≤ {NEAR_EQUAL}): "
             f"{_pct(m.nonzero_near_equal_decisions, m.decisions)}",
             "",
             "## By chosen action class (multi)"]
    for cls in sorted(m.by_action or {}):
        a, t = m.by_action[cls]
        lines.append(f"- {cls}: {_pct(a, t)}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Baseline eval for rollout-label JSONL")
    ap.add_argument("path", help="path to .jsonl or .jsonl.gz")
    ap.add_argument("--split-seed", type=int, default=None,
                    help="if set, also print per-split (train/val/test) headline metrics")
    ap.add_argument("--out", default=None, help="write the markdown report to this path")
    args = ap.parse_args(argv)
    decisions = group_decisions(load_rows(args.path))
    m = evaluate_baseline(decisions)
    report = format_report(m)
    if args.split_seed is not None:
        sp = split_by_game(decisions, seed=args.split_seed)
        report += "\n## Per-split (seed %d)\n" % args.split_seed
        for name, part in (("train", sp.train), ("val", sp.val), ("test", sp.test)):
            pm = evaluate_baseline(part)
            report += (f"- {name}: {pm.games}g/{pm.decisions}d/{pm.rows}r · "
                       f"strict {_pct(pm.agree_strict, pm.strict_total)} · "
                       f"ATTACK {_pct(*(pm.by_action or {}).get('attack', (0,0)))}\n")
    print(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(report)
    return m


if __name__ == "__main__":
    main()
```

> **Also include (rounds out the user's metric list; secondary to the two hard requirements, reporting-only):**
> add to `BaselineMetrics` + `format_report`: `trainable_decisions` (decisions where every row has `metadata.teacher_config.trainable_label is True` — should be all 951 here), a `value_gap` distribution over non-best rows (median/mean/min — the QA report had median −1.366, mean −2.664, min −17.47), and `override_opportunity` (multi decisions that are contestable AND the heuristic chose a non-`teacher_best` row — the addressable set a reranker could fix). These don't gate Task 4.

- [ ] **Step 4: Run tests, verify pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat(2b-1): baseline_eval (agreement + near-equal/zero-gap + CLI)"`

---

### Task 4: Regression test — reproduce the committed 100-game numbers (HARD REQUIREMENT)

**Files:**
- Test: `showdown_bot/tests/test_baseline_eval.py` (add)

This is the user's hard requirement: *"Eval reproduziert diese Zahlen exakt/nah."* Pin the evaluator to the committed dataset.

- [ ] **Step 1: Write the failing test**

```python
import gzip, os
import pytest
from pathlib import Path
from showdown_bot.learning.dataset import group_decisions, load_rows, split_by_game
from showdown_bot.learning.baseline_eval import evaluate_baseline

_DS = Path(__file__).resolve().parents[2] / "data" / "datasets" / "phase3-slice2b" \
      / "rollout_labels_100g_gen9vgc2025regi_h1_v1.jsonl.gz"

@pytest.mark.skipif(not _DS.exists(), reason="committed dataset artifact missing")
def test_baseline_reproduces_2b0_qa_numbers():
    decs = group_decisions(load_rows(str(_DS)))
    m = evaluate_baseline(decs)
    assert (m.rows, m.games, m.decisions) == (4658, 100, 951)
    assert (m.multi_decisions, m.forced_decisions, m.ties) == (851, 100, 100)
    assert (m.agree_topset, m.agree_topset_total) == (524, 851)        # 61.6%
    assert (m.agree_strict, m.strict_total) == (424, 751)              # 56.5%
    assert m.zero_gap_nonbest_decisions == 348                        # 36.6%
    assert m.contestable_decisions == 529                             # 55.6%
    assert m.nonzero_near_equal_decisions == 279                      # 29.3%
    atk = m.by_action["attack"]; pro = m.by_action["protect"]
    assert atk == (317, 643)                                          # ATTACK 49.3%
    assert pro == (107, 108)                                          # protect 99.1%

@pytest.mark.skipif(not _DS.exists(), reason="committed dataset artifact missing")
def test_seed42_split_shapes_match_report():
    decs = group_decisions(load_rows(str(_DS)))
    sp = split_by_game(decs, seed=42, ratios=(0.8, 0.1, 0.1))
    shape = lambda p: (len({d.game_id for d in p}), len(p), sum(len(d.rows) for d in p))
    assert shape(sp.train) == (80, 762, 3729)
    assert shape(sp.val) == (10, 95, 467)
    assert shape(sp.test) == (10, 94, 462)
```

- [ ] **Step 2: Run it.** If counts differ:
  - **Agreement / contestable / zero-gap mismatches** are math-definition bugs → fix `evaluate_baseline` to match the report's definitions (do NOT edit the assertions to match the code — the report numbers are the spec).
  - **ATTACK/protect denominator mismatch (≠643/≠108)** means `action_class` classifies differently than the QA script. Investigate via systematic-debugging: dump the chosen-row move_ids the eval labels `attack` vs `protect`, compare against the protect-id set + move metadata, and reconcile until `attack`=643, `protect`=108. Document any residual delta in the plan/report if a perfect match is impossible (the user accepted "exakt/nah").

- [ ] **Step 3: Verify pass** — `pytest tests/test_baseline_eval.py -q`.

- [ ] **Step 4: Full suite** — `cd showdown_bot && python -m pytest -q` (no regressions).

- [ ] **Step 5: Commit** — `git commit -am "test(2b-1): pin baseline eval to committed 100-game QA numbers"`

---

### Task 5: Run the evaluator end-to-end + write the report

**Files:**
- Create: `reports/2026-06-30-2b1-baseline-eval.md` (generated)

- [ ] **Step 1:** Run the CLI on the committed dataset with the seed-42 split:

```bash
cd "C:/Users/chris/Documents/SHowdown BOt/showdown_bot"
python -m showdown_bot.learning.baseline_eval \
  ../data/datasets/phase3-slice2b/rollout_labels_100g_gen9vgc2025regi_h1_v1.jsonl.gz \
  --split-seed 42 --out ../reports/2026-06-30-2b1-baseline-eval.md
```

- [ ] **Step 2:** Confirm the printed numbers match the 2b-0 QA report (they must — Task 4 pins them).
- [ ] **Step 3: Commit** — `git add reports/2026-06-30-2b1-baseline-eval.md && git commit -m "docs(2b-1): generated baseline eval report"`

---

## Self-Review checklist (done before handoff)

- **Scope:** loader + split + baseline-eval only. **No model, no training, no live wiring.** ✔
- **Hard requirement 1 (reproduce numbers):** Task 4 pins exact counts to the committed dataset. ✔
- **Hard requirement 2 (near-equal/zero-gap):** `wrong_but_near_equal`, `zero_gap_nonbest_decisions`, `nonzero_near_equal_decisions`, `contestable_decisions` + `Decision.zero_gap_nonbest_count()` expose the tie-like structure 2b-2 training must respect. ✔
- **Feature gotcha:** action class from `move_id`/`action_type` + move metadata, never the dead `is_damaging`/`is_protect` flags. ✔
- **Leakage:** split by game; Task 2 tests prove game- and decision-level disjointness + determinism. ✔
- **No live behavior change:** new modules are offline; nothing imports them from the battle/decision path. ✔

## Deferred to 2b-2 (NOT in this plan)
- PyTorch MLP reranker (score each candidate, pick highest).
- Margin-aware / near-equal-safe loss (CE V1 that does NOT hard-penalize zero-gap alternatives; pairwise/soft-margin V2).
- Shadow-mode interface (compute reranker_choice next to heuristic_choice, never used live) gated behind disabled config.
- Feature-extractor fix (populate the dead columns) — priority 3, may precede 2b-2 model quality work.
