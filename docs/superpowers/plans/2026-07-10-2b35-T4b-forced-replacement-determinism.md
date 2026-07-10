# 2b-3.5 T4b — Forced-Replacement Determinism — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. **Git owner:
> Bau-Claude.** Steps use `- [ ]`. Implements the approved spec
> `docs/superpowers/specs/2026-07-10-t4b-forced-replacement-determinism-design.md` (option C).
> Touches `battle/` (INV-1 live path) — behavior change is user-approved and documented.

**Goal:** Forced replacements are enumerated, evaluated, and deterministic; the last-resort
fallbacks are deterministic; the full T4 re-run passes 21/21 gates + 10/10 prefix + 51/51
double-run reproduction.

**Architecture:** Pair-level force-phase logic in `battle/actions.py` (`enumerate_my_actions`);
a deterministic `pick_default_pair` in `battle/random_agent.py` wired into the two fallback call
sites (`battle/decision.py`, `battle/baselines.py`). No new evaluation code — replacement joint
actions flow through the existing pipeline. `pick_random_pair` and the `random` policy stay
random.

**Tech Stack:** stdlib only; existing test fixture pattern (`tests/fixtures/request_force_switch.json`
+ `tests/test_legal_actions.py`); committed T4 evidence logs as fixture source.

**Suite baseline:** 676 passed. Branch: create `feat/slice-2b35-t4b-forced-replacement-determinism`
off `main`.

---

## The enumeration contract (force phase) — single source of truth for Tasks 1–3

Let `bench` = side mons with `active=false` and no `fnt` in condition; `n_forced` = number of
`true` entries in `force_switch`; `want = min(len(bench), n_forced)`.

- Per forced slot: switch actions for every bench mon; **plus `pass` ONLY when
  `len(bench) < n_forced`** (fewer replacements than forced slots — someone must pass).
- Non-forced slots in a force phase: `pass` (unchanged).
- Joint filter in a force phase: drop same-target double switches (always illegal); drop joint
  actions whose total switch count `!= want` (you must switch as many as you can — `(pass, pass)`
  with a live bench mon is illegal, `(switch, switch)` with one bench mon impossible).
- The voluntary prune `allow_double_switch=False` applies ONLY outside force phases.

Shapes this must produce (F-fixtures, Task 1):
| Fixture | force_switch | bench | legal joint set |
|---|---|---|---|
| F1 double, 2 bench | [true,true] | {X,Y} | (X,Y), (Y,X) — 2 |
| F2 single, 2 bench | [false,true] | {X,Y} | (pass,X), (pass,Y) — 2 |
| F3 double, 1 bench | [true,true] | {X} | (X,pass), (pass,X) — 2 |
| F4 single, 1 bench | [false,true] | {X} | (pass,X) — 1 |

F2 is battle 9's real hero request (committed log); F1 mirrors battle 9's villain double
replacement; F3 is the suspected battle-19 shape (`forceSwitch:[true,true]` confirmed in its log).

---

### Task 1: Fixtures from reality + failing enumeration tests

**Files:**
- Create: `showdown_bot/tests/fixtures/t4b_force_single_2bench.json` (extracted), plus synthetic
  F1/F3/F4 request dicts inline in the test file
- Test: `showdown_bot/tests/test_actions_force_phase.py` (new file)

- [ ] **Step 1: Extract the real request.** From repo root:

```bash
zcat data/eval/t4/room_raw_divergent/run1-idx09-regi-319.log.gz | grep -o '|request|{"forceSwitch".*' | head -1 | sed 's/^|request|//' > showdown_bot/tests/fixtures/t4b_force_single_2bench.json
python -c "import json; d=json.load(open('showdown_bot/tests/fixtures/t4b_force_single_2bench.json')); print(d['forceSwitch'], [m['ident'] for m in d['side']['pokemon']])"
```

Expected: `[False, True]` + 4 idents (Incineroar/Rillaboom actives, Tornadus/Flutter Mane bench).
Also confirm battle 19's shape for the record (goes into the test docstring):
`zcat data/eval/t4/room_raw_divergent/run1-idx19-regi-329.log.gz | grep -o '"forceSwitch":\[[a-z,]*\]'` → `[true,true]`.

- [ ] **Step 2: Write the failing tests** (`tests/test_actions_force_phase.py`). Follow the
request-parsing pattern used by `tests/test_legal_actions.py` with
`tests/fixtures/request_force_switch.json` (read that test file first and reuse its
parse/builder helper — do NOT invent a new request constructor). Build F1/F3/F4 as synthetic
request dicts with the same JSON shape as the extracted F2 (copy it and edit `forceSwitch` +
`condition` fields: for F1 both actives `0 fnt` + forceSwitch [true,true]; for F3 additionally
one bench mon set to `0 fnt`; for F4 one bench mon `0 fnt` + forceSwitch [false,true]).

```python
"""T4b: forced replacements must enumerate per the force-phase contract (plan table F1-F4).

Root cause of the T4 reproduction FAIL (reports/2026-07-10-2b35-T4-smoke.md): these shapes
returned [] from enumerate_my_actions, dropping the choice to an unseeded random fallback.
Battle 19's request was forceSwitch [true,true] (run1-idx19 log); battle 9's hero request
[false,true] is the committed fixture t4b_force_single_2bench.json.
"""
# imports + the reused request-builder helper from test_legal_actions

def _joint_shapes(jas):
    # (slot0.kind/target, slot1.kind/target) canonical tuples for comparison
    return sorted(
        ((ja.slot0.kind, ja.slot0.target_ident), (ja.slot1.kind, ja.slot1.target_ident))
        for ja in jas
    )

def test_f2_single_forced_two_bench_real_request():
    req = _load_fixture_request("t4b_force_single_2bench.json")
    jas = enumerate_my_actions(req)
    assert _joint_shapes(jas) == sorted([
        (("pass", None), ("switch", "Tornadus")),
        (("pass", None), ("switch", "Flutter Mane")),
    ])

def test_f1_double_forced_two_bench_enumerates_both_assignments():
    req = _f1_request()  # synthetic: forceSwitch [true,true], bench {Tornadus, Flutter Mane}
    jas = enumerate_my_actions(req)
    assert _joint_shapes(jas) == sorted([
        (("switch", "Tornadus"), ("switch", "Flutter Mane")),
        (("switch", "Flutter Mane"), ("switch", "Tornadus")),
    ])

def test_f3_double_forced_one_bench_switch_plus_pass():
    req = _f3_request()  # forceSwitch [true,true], bench {Tornadus}
    jas = enumerate_my_actions(req)
    assert _joint_shapes(jas) == sorted([
        (("switch", "Tornadus"), ("pass", None)),
        (("pass", None), ("switch", "Tornadus")),
    ])

def test_f4_single_forced_one_bench():
    req = _f4_request()
    jas = enumerate_my_actions(req)
    assert _joint_shapes(jas) == sorted([(("pass", None), ("switch", "Tornadus"))])

def test_voluntary_double_switch_still_pruned():
    # Normal turn (no force phase): allow_double_switch=False still drops switch+switch.
    req = _load_fixture_request("request_force_switch.json")  # or a normal-turn fixture per test_legal_actions
    # ... follow the existing normal-turn fixture; assert no switch+switch pair present.

def test_enumerate_slot_pairs_nonempty_on_all_force_shapes():
    for req in (_load_fixture_request("t4b_force_single_2bench.json"), _f1_request(), _f3_request(), _f4_request()):
        assert enumerate_slot_pairs(req)  # random/default fallback substrate already legal
```

(Adapt `test_voluntary_double_switch_still_pruned` to the real fixtures available — the assertion
that matters: outside force phases, behavior is unchanged.)

- [ ] **Step 3: Run, expect FAIL:** `python -m pytest showdown_bot/tests/test_actions_force_phase.py -q`
— F1/F3 (and possibly F2) fail with empty enumeration or missing pass-variants.
RECORD which of F1–F4 fail — that empirically pins RC-3 for the report.

- [ ] **Step 4: Commit** (tests + fixture only; they may stay red across the commit boundary? NO —
house rule is green commits. Therefore: commit Task 1 TOGETHER with Task 2's fix in Task 2 Step 5.
Do not commit here; hand off the failing-test state to Task 2.)

### Task 2: Enumeration fix

**Files:**
- Modify: `showdown_bot/src/showdown_bot/battle/actions.py` (`_slot_actions`, `enumerate_my_actions`)
- Test: the Task 1 file (must go green)

- [ ] **Step 1: Implement** in `actions.py`:

```python
def _bench_count(req: BattleRequest) -> int:
    return sum(
        1 for mon in req.side.pokemon if not mon.active and "fnt" not in mon.condition
    )
```

In `_slot_actions`, forced branch (currently `return _slot_move_actions(active_index, req)`):

```python
    if forced:
        out = _slot_move_actions(active_index, req)
        n_forced = sum(1 for f in (req.force_switch or []) if f)
        # Fewer live bench mons than forced slots: someone must pass (the server accepts
        # the switch in either forced slot). Offer pass so the joint filter can pick the
        # maximal-switch assignments.
        if _bench_count(req) < n_forced and not any(a.kind == "pass" for a in out):
            out.append(SlotAction(kind="pass"))
        return out
```

In `enumerate_my_actions`, replace the pair loop's switch+switch handling and add the
maximal-switch filter:

```python
    out: list[JointAction] = []
    n_forced = sum(1 for f in (req.force_switch or []) if f)
    want_switches = min(_bench_count(req), n_forced) if in_force_phase else None
    for a0, a1 in product(s0, s1):
        if a0.kind == "switch" and a1.kind == "switch":
            if a0.target_ident == a1.target_ident:
                continue
            if not allow_double_switch and not in_force_phase:
                continue
        if want_switches is not None:
            n_sw = (a0.kind == "switch") + (a1.kind == "switch")
            if n_sw != want_switches:
                continue
        out.append(JointAction(slot0=a0, slot1=a1))
    return out
```

Update the module docstring pruning note: double-switch prune is voluntary-turns-only (T4b);
force phases enumerate the maximal-switch assignments.

- [ ] **Step 2: Run Task 1 tests, expect PASS** (all of them, including the voluntary-prune
regression and `enumerate_slot_pairs` checks).

- [ ] **Step 3: Run the FULL suite** — expect 676 + new, 0 failures. If an existing test
legitimately asserted the old force-phase behavior, update it with a comment referencing this plan
(document in the report-back which ones).

- [ ] **Step 4: Commit** (Task 1 + Task 2 together, green):

```bash
git add showdown_bot/src/showdown_bot/battle/actions.py showdown_bot/tests/test_actions_force_phase.py showdown_bot/tests/fixtures/t4b_force_single_2bench.json
git commit -m "fix(2b-3.5 T4b): enumerate forced replacements (force-phase contract)"
```

### Task 3: Heuristic end-to-end on force requests (evaluated + deterministic)

**Files:**
- Test: extend `showdown_bot/tests/test_actions_force_phase.py`
- Modify (only if the test exposes gaps): `showdown_bot/src/showdown_bot/battle/decision.py`

- [ ] **Step 1: Write the failing/characterization test.** Follow the fake/stub pattern of the
existing `heuristic_choose_for_request` tests (find them via
`grep -rn "heuristic_choose_for_request" showdown_bot/tests/` — reuse their state/calc fakes; do
NOT build a real calc backend). For each of F1–F4:

```python
def test_heuristic_answers_force_requests_deterministically(caplog):
    for req in _all_f_fixtures():
        choices = set()
        for _ in range(5):
            with caplog.at_level(logging.WARNING):
                choices.add(heuristic_choose_for_request(req, **_fake_deps()))
        assert len(choices) == 1                      # deterministic
        assert "/choose" in next(iter(choices))       # valid encoding
    assert "falling back" not in caplog.text          # evaluated, NOT the fallback path
```

- [ ] **Step 2: Run.** If it passes immediately after Task 2 (evaluation already handles
switch-only joint actions), record that and move on. If it fails (e.g. evaluation assumes
`req.active` is present), fix the exposed assumption in `decision.py` minimally — the joint
actions themselves are already the same `SlotAction(kind="switch")` shape voluntary switches use.
STOP and report BLOCKED if the fix would require restructuring beyond a guard/branch.

- [ ] **Step 3: Full suite green. Commit:**

```bash
git add showdown_bot/tests/test_actions_force_phase.py showdown_bot/src/showdown_bot/battle/decision.py
git commit -m "feat(2b-3.5 T4b): heuristic evaluates forced replacements deterministically"
```

(Drop the decision.py path from `git add` if it needed no change.)

### Task 4: Deterministic last-resort fallbacks

**Files:**
- Modify: `showdown_bot/src/showdown_bot/battle/random_agent.py`, `battle/decision.py:631-634`,
  `battle/baselines.py:38-46`
- Test: `showdown_bot/tests/test_actions_force_phase.py` (extend) or the existing fallback tests
  (find via `grep -rn "pick_random_pair\|choose_with_fallback" showdown_bot/tests/`)

- [ ] **Step 1: Failing tests:**

```python
def test_pick_default_pair_is_first_legal_and_deterministic():
    req = _load_fixture_request("t4b_force_single_2bench.json")
    assert pick_default_pair(req) == enumerate_slot_pairs(req)[0]
    assert pick_default_pair(req) == pick_default_pair(req)

def test_pick_default_pair_raises_on_no_actions():
    # same empty-request shape the pick_random_pair test uses
    ...

def test_choose_with_fallback_last_resort_is_deterministic(monkeypatch):
    # monkeypatch the heuristic core AND max_damage_choice to raise;
    # call choose_with_fallback 5x on the F2 fixture -> identical choice strings.

def test_max_damage_default_fallback_is_deterministic(monkeypatch):
    # force max_damage_choice's no-legal-action path (monkeypatch enumerate_my_actions -> []);
    # 5 calls -> identical result; and it does NOT call pick_random_pair (monkeypatch it to raise AssertionError).
```

- [ ] **Step 2: Implement.** In `random_agent.py` (beside `pick_random_pair`, which stays
UNCHANGED):

```python
def pick_default_pair(req: BattleRequest) -> SlotPair:
    """Deterministic last-resort: the FIRST legal pair (enumeration order). Used by the
    fallback chain (T4b) so an enumeration hole can never reintroduce nondeterminism;
    the `random` policy keeps using pick_random_pair."""
    pairs = enumerate_slot_pairs(req)
    if not pairs:
        raise ValueError("No legal actions for request")
    return pairs[0]
```

`decision.py` last resort: `encode_choose(pick_default_pair(req), rqid=req.rqid)` (import swap).
`baselines.py` `_default_fallback`: `pick_default_pair` + update the T3c docstring note ("default
fallback is deterministic since T4b; the eval dispatch may still pass its own").

- [ ] **Step 3: Run tests + FULL suite. Expect green** (a pre-existing test may pin the old
random default per T3c "byte-for-byte" — update it with a plan reference; document in report-back).

- [ ] **Step 4: Commit:**

```bash
git add showdown_bot/src/showdown_bot/battle/random_agent.py showdown_bot/src/showdown_bot/battle/decision.py showdown_bot/src/showdown_bot/battle/baselines.py showdown_bot/tests/
git commit -m "fix(2b-3.5 T4b): deterministic last-resort fallback (pick_default_pair)"
```

### Task 5: T4 re-run (operational; acceptance R5)

No source changes. Fresh seed base **`t4rerun2026`**. Reuse the T4 runbook verbatim
(schedules `config/eval/schedules/t4_smoke_v001{,_prefix}.yaml`, env per
`reports/2026-07-10-2b35-T4-smoke.md` §Reproduction commands), outputs under `C:/tmp/t4rerun/`
(NOT the repo — dirty gate). Clean tree required (all Task 1–4 commits landed).

- [ ] Full 51-game run (fresh server, seed log, telemetry, room dump) → gate checker (same
  scratchpad script as T4, PASS required on all 21) → **plus one NEW gate: ZERO mid-battle
  `falling back` warnings in the client log** (end-of-battle wait-request cascades where all
  fallbacks fail are still tolerated; count them separately).
- [ ] Prefix run (same base) → comparison → **10/10 REQUIRED**.
- [ ] Full second run → comparison → **51/51 REQUIRED**.
- [ ] Any failure = BLOCKED with evidence; no retries, no fixes.

### Task 6: Re-run report + T5-fixture artifacts + closeout

- [ ] Copy artifacts to `data/eval/t4/rerun/`: all three runs' result JSONLs + manifests +
  seedlogs + telemetry + gates output + both repro outputs; gzip ALL room logs (51+10+51) under
  `data/eval/t4/rerun/room_raw/{run1,prefix,run2}/`; `sha256.txt` over the lot. Extend
  `.gitattributes` (`data/eval/t4/rerun/room_raw/** binary` is covered by the existing
  `data/eval/t4/**` rules — verify, add only if missing).
- [ ] Report `reports/<run-date>-2b35-T4-rerun.md`: **VERDICT: PASS** (expected) — gates table,
  reproduction evidence (10/10, 51/51), zero-mid-battle-fallback gate, per-cell reference numbers
  (same §6 phrasing rules + verbatim caveats as the T4 report), supersession note ("supersedes the
  2026-07-10 T4 FAIL report; this run's artifacts are the T5 fixture"), and the **RC-2 erratum**
  (the unseeded endpoint was reached via max_damage's internal default fallback
  `baselines.py:43-44`, one level earlier than the T4 report's `decision.py:632` description).
- [ ] Full suite one last time; commit:
  `docs(2b-3.5 T4b): T4 re-run PASS report + T5 fixture artifacts`.

---

## Out of scope
No policy/eval-opponent changes, no panel/matrix/schedule changes, no T5 statistics, no dataset
regeneration, no changes to `pick_random_pair` or the `random` policy, no new telemetry.

## Self-review (writing-plans)
- Spec coverage: R1→Tasks 1–2, R2→Task 3, R3→Task 4, R4→full-suite steps in every task,
  R5→Tasks 5–6 (fresh base t4rerun2026 pinned); RC-2 erratum→Task 6; fixtures-from-reality→Task 1. ✓
- Placeholders: none — code blocks complete; the two "grep first, reuse existing pattern" steps
  point at concrete files (`test_legal_actions.py`, existing fallback tests) rather than TBDs;
  Task 3 explicitly allows a pass-through outcome (characterization) or a minimal guard fix. ✓
- Type consistency: contract table ↔ F-tests ↔ `want_switches` filter use the same
  min(bench, forced) rule; `pick_default_pair` returns `SlotPair` like `pick_random_pair`;
  fallback call sites keep `encode_choose(..., rqid=req.rqid)`. ✓
- Green-commit discipline: Task 1's failing tests commit together with Task 2's fix. ✓
