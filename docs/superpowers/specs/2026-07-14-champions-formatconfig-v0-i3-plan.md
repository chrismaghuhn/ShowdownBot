# Champions FormatConfig v0 — I3 Config Threading (Implementation Plan)

**Status:** PROPOSED — pending review (**no implementation** until approved)
**Date:** 2026-07-14 (rev 2 — runner IN scope, hermetic agent_choose tests)
**Builds on:** [`2026-07-14-champions-formatconfig-v0-design.md`](2026-07-14-champions-formatconfig-v0-design.md) §7 · I1 (`86c144e`) · I2 (`a705e36`)

## 0. Goal

Thread `FormatConfig` generically from format yaml → **both live decision entry points**
(gauntlet **and** ladder runner) → decision core, so `tera: false` (and future format flags)
are enforced in code — not only in yaml comments.

Secondary: pin with hermetic tests that `heuristic` / `max_damage` do **not** take the
`choose_for_request` random path when `book` is present, and that `format_config` is forwarded.

**Non-goal for I3:** SpeedOracle, calc stat_points adapter, Mega overlay, strength runs.

---

## 1. Current state (verified)

### 1.1 Gauntlet load site

`_load_belief_deps(format_id)` in `gauntlet.py` already calls `load_format_config(format_id)`
inside a broad `try/except`, but **discards `cfg`** and returns only:

```python
(book, priors, opp_sets)  # cfg thrown away
```

Callers: `run_local_gauntlet`, `build_schedule_export_runtime`. One test monkeypatch:
`test_gauntlet_duplicate_win_callback.py` → `(None, None, None)`.

### 1.2 Runner load site (parallel, also discards cfg)

`runner.py` already mirrors gauntlet belief loading with module-level caches:

| Helper | Cache | Loads cfg internally? |
|--------|-------|------------------------|
| `_get_book(format_id)` | `_book_cache` | yes — discarded after spread load |
| `_get_priors(format_id)` | `_priors_cache` | yes — discarded after priors load |

`handle_battle_message` calls `choose_with_fallback(...)` with book/priors but **no**
`format_config`. If only gauntlet is threaded, we get:

- Gauntlet eval: respects `cfg.tera`
- Ladder runner: does **not**
- Direct `heuristic_choose_for_request` callers: legacy `None`

That split is inconsistent for a multi-format adapter — **runner is IN scope**.

### 1.3 Random fallback gate

```python
# gauntlet.agent_choose
if agent == "random" or state is None or book is None:
    return choose_for_request(req)
```

`_Client._state_for` also returns `None` when `self.book is None`.

**Post-I2 note:** Champions yaml + meta exist; `_load_belief_deps("gen9championsvgc2026regma")`
loads a real `SpreadBook`. P4's random-heuristic issue was **missing yaml**. I3 adds explicit
regression tests and `cfg.tera` enforcement across gauntlet **and** runner.

### 1.4 Tera today

`_maybe_tera` gates only on `req.active[i].can_terastallize` (server). `FormatConfig.tera` is
never read in the decision path.

### 1.5 Callers and I3 scope

| Path | Uses decision core? | I3 scope |
|------|---------------------|----------|
| `gauntlet.agent_choose` / `_Client.handle_request` | yes | **IN** |
| `runner.handle_battle_message` | `choose_with_fallback` | **IN** |
| `learning/decide_adapter` → `_choose_best` | yes | **OUT** (`format_config=None`; legacy) |
| `eval/accuracy_gate_a/b` | direct `heuristic_choose_for_request` | **OUT** (`None`; legacy) |

No Champions-if branches anywhere.

---

## 2. Planned API changes

### 2.1 `_load_belief_deps` → 4-tuple (unchanged)

```python
def _load_belief_deps(format_id: str) -> tuple[
    FormatConfig | None,
    SpreadBook | None,
    ProtectPriors | None,
    dict,  # opp_sets
]:
```

**Load order (fail-soft):**

1. Try `cfg = load_format_config(format_id)` — on failure `cfg = None`.
2. If `cfg is not None`, try book + priors — on failure leave `book/priors = None` but **keep
   `cfg`**.
3. `opp_sets = load_opp_sets_for_format(format_id)` unchanged.

### 2.2 Runner: `_get_format_config(format_id)` with cache

Mirror existing `_book_cache` / `_priors_cache` pattern:

```python
_format_config_cache: dict[str, FormatConfig | None] = {}

def _get_format_config(format_id: str | None) -> FormatConfig | None:
    if not format_id:
        return None
    if format_id not in _format_config_cache:
        try:
            _format_config_cache[format_id] = load_format_config(format_id)
        except Exception:
            _format_config_cache[format_id] = None
    return _format_config_cache[format_id]
```

**Optional refactor (same slice, if small):** have `_get_book` / `_get_priors` reuse
`_get_format_config` instead of calling `load_format_config` twice per format — reduces duplicate
yaml reads, not required for correctness.

`handle_battle_message`:

```python
cfg = _get_format_config(_active_format)
choose = choose_with_fallback(
    req, state=state, book=book, our_side=req.side.id, priors=priors,
    report=report, our_spreads=_our_spreads, opp_sets=_opp_sets,
    format_config=cfg,
)
```

If `cfg is None`: legacy behavior (`format_config=None` inside decision core).

### 2.3 Gauntlet: `_Client` holds `format_config`

```python
def __init__(..., format_config=None, book, priors, format_id, ...):
    self.format_config = format_config
```

`run_local_gauntlet` passes `format_config=cfg` from `_load_belief_deps`.

### 2.4 Threading chain (new optional kwarg)

Add `format_config: FormatConfig | None = None` to:

| Function | File | Notes |
|----------|------|-------|
| `agent_choose` | `gauntlet.py` | forward to CWF; forward to max_damage if signature allows |
| `choose_with_fallback` | `decision.py` | pass via `**deps` to heuristic |
| `heuristic_choose_for_request` | `decision.py` | forward to `_choose_best_ja` |
| `_choose_best_ja` / `_choose_best` | `decision.py` | forward to `_maybe_tera` |
| `_maybe_tera` | `decision.py` | **apply gate here** |

**Default:** `format_config=None` → unchanged behavior (server `can_terastallize` only).

**Do not add** `format_config` to `decide_adapter._CORE_DEP_KEYS` in I3.

### 2.5 `_maybe_tera` gate (unchanged)

```python
if format_config is not None and not format_config.tera:
    return best_ja
```

No format-id string checks.

---

## 3. Planned file changes

| File | Change |
|------|--------|
| `showdown_bot/src/showdown_bot/client/gauntlet.py` | `_load_belief_deps` 4-tuple; `_Client.format_config`; `agent_choose` + `handle_request` threading |
| `showdown_bot/src/showdown_bot/client/runner.py` | `_format_config_cache`, `_get_format_config`; `handle_battle_message` passes `format_config=cfg` |
| `showdown_bot/src/showdown_bot/battle/decision.py` | `format_config` kwarg chain + `_maybe_tera` gate |
| `showdown_bot/tests/test_gauntlet_dispatch.py` | Hermetic `agent_choose` heuristic + max_damage tests |
| `showdown_bot/tests/test_runner_format_config.py` **or** extend existing runner tests | `_get_format_config` + CWF threading |
| `showdown_bot/tests/test_format_config_threading.py` **or** `test_format_config.py` | `_load_belief_deps` Champions 4-tuple |
| `showdown_bot/tests/test_decision_tera_config.py` **or** extend decision tests | `_maybe_tera` + `cfg.tera=False` |
| `showdown_bot/tests/test_gauntlet_duplicate_win_callback.py` | Monkeypatch → 4-tuple |

**Not touched:** `speed.py`, meta yaml, panels/teams, `decide_adapter.py`, accuracy gates.

---

## 4. Test plan

### 4.1 `_load_belief_deps` (Champions)

```python
def test_load_belief_deps_champions_returns_cfg_and_book():
    cfg, book, priors, opp_sets = _load_belief_deps("gen9championsvgc2026regma")
    assert cfg is not None and cfg.tera is False and cfg.mega is True
    assert book is not None and priors is not None
    assert isinstance(opp_sets, dict)
```

### 4.2 Runner `_get_format_config`

```python
def test_get_format_config_loads_and_caches():
    cfg1 = _get_format_config("gen9championsvgc2026regma")
    cfg2 = _get_format_config("gen9championsvgc2026regma")
    assert cfg1 is cfg2  # cache hit
    assert cfg1.tera is False

def test_get_format_config_missing_returns_none():
    assert _get_format_config("does_not_exist") is None
```

**Threading test** (if no existing `handle_battle_message` harness — prefer unit-level):

```python
def test_runner_passes_format_config_to_choose_with_fallback(monkeypatch):
    # monkeypatch choose_with_fallback → record kwargs
    # call handle_battle_message with _active_format set + book available
    # assert captured["format_config"] is not None and .tera matches yaml
```

If `handle_battle_message` async setup is heavy, `_get_format_config` + a direct CWF call with
runner-sourced cfg is sufficient minimum; threading test is preferred when cheap.

### 4.3 Tera gate (`_maybe_tera`)

- Champions cfg + synthetic `canTerastallize` → no overlay.
- Reg-I cfg (`tera=True`) → no early cfg return; existing replay tests stay green.
- `format_config=None` + synthetic `canTerastallize` → legacy unchanged.

### 4.4 `agent_choose` — hermetic threading (no real Calc deps)

**Principle:** I3 tests **threading**, not damage quality. No `_ExplodingDep`, no real
Champions book required for dispatch tests.

**Heuristic:**

```python
def test_agent_choose_heuristic_forwards_format_config_not_random(monkeypatch):
    import showdown_bot.client.gauntlet as g

    random_calls: list = []
    cwf_calls: list = []

    monkeypatch.setattr(g, "choose_for_request", lambda req: random_calls.append(req) or (_ for _ in ()).throw(
        AssertionError("random fallback")))
    monkeypatch.setattr(g, "choose_with_fallback", lambda req, **kw: (
        cwf_calls.append(kw) or f"/choose default|{req.rqid}"))

    cfg = load_format_config("gen9championsvgc2026regma")
    out = agent_choose(
        "heuristic", _req(), state=object(), book=object(), our_side="p1",
        format_config=cfg,
    )

    assert out.startswith("/choose ")
    assert random_calls == []
    assert len(cwf_calls) == 1
    assert cwf_calls[0]["format_config"] is cfg
```

**Max damage** (does not go through CWF):

```python
def test_agent_choose_max_damage_not_random_when_book_present(monkeypatch):
    import showdown_bot.client.gauntlet as g
    import showdown_bot.battle.baselines as baselines

    monkeypatch.setattr(g, "choose_for_request", lambda req: (_ for _ in ()).throw(
        AssertionError("random fallback")))
    monkeypatch.setattr(baselines, "max_damage_choice", lambda req, **kw: f"/choose default|{req.rqid}")

    cfg = load_format_config("gen9championsvgc2026regma")
    out = agent_choose(
        "max_damage", _req(), state=object(), book=object(), our_side="p1",
        format_config=cfg,
    )
    assert out.startswith("/choose ")
```

Optional: assert `max_damage_choice` received `format_config` if we thread it through that
branch (only if signature extended — not required for random-fallback proof).

### 4.5 Regression / focused suite

```bash
python -m pytest \
  showdown_bot/tests/test_gauntlet_dispatch.py \
  showdown_bot/tests/test_runner_format_config.py \
  showdown_bot/tests/test_format_config.py \
  showdown_bot/tests/test_decision_replay.py \
  showdown_bot/tests/test_decision_trace.py \
  showdown_bot/tests/test_world_sampling_decision.py \
  -q
```

No full suite required if focused set green + `git diff --check` clean.

---

## 5. Backward compatibility

| Scenario | Expected behavior |
|----------|-------------------|
| `format_config=None` (decide_adapter, accuracy gates) | Legacy: Tera via server only |
| Reg-I gauntlet + runner with threaded `cfg.tera=True` | Unchanged Tera overlay semantics |
| Champions with `cfg.tera=False` | Overlay suppressed even with synthetic `canTerastallize` |
| Missing format yaml | `_get_format_config` → `None`; runner CWF gets `format_config=None` |
| Gauntlet missing yaml | `cfg=None`, `book=None` → random path |
| `_load_belief_deps` monkeypatches | Update to 4-tuple |

**Risk — tuple expansion:** 3 gauntlet call sites + 1 test mock; low blast radius.

**Risk — runner cache staleness:** Same as existing `_book_cache` — format yaml edits in-process
require restart (acceptable; matches today).

**Risk — duplicate `load_format_config` in runner:** Mitigated if `_get_book`/`_get_priors` reuse
`_get_format_config` (optional small refactor in same slice).

---

## 6. Out of scope (explicit)

- `SpeedOracle` / `max_per_stat` (I4)
- Stat Points calc adapter
- Mega Evolution decision overlay
- `format_config.mega` / `stat_investment` in decision logic
- Strength / decision-quality / McNemar runs
- Live gauntlet smoke beyond hermetic unit tests
- Panel / team / schedule / meta yaml changes
- Champions `if format_id == ...` in decision core
- `decide_adapter` / accuracy gate threading
- New meta files

---

## 7. Implementation order (post-review)

1. `_load_belief_deps` 4-tuple + gauntlet call sites / monkeypatch fix.
2. `runner._get_format_config` + `handle_battle_message` threading.
3. `_Client.format_config` + `agent_choose` threading.
4. `decision.py` kwarg chain + `_maybe_tera` gate.
5. Tests (§4) — hermetic dispatch tests first, then tera gate, then runner.
6. Focused pytest + `git diff --check`.

**Stop line:** No SpeedOracle changes, no strength eval.

---

## 8. Commit message (draft)

```
feat(format): thread FormatConfig into decision path
```

Body (optional):

- Return cfg from `_load_belief_deps`; cache via `runner._get_format_config`
- Thread `format_config` through gauntlet + runner into `choose_with_fallback`
- Gate `_maybe_tera` on `format_config.tera`
- Hermetic tests: no random fallback when book present; cfg forwarded

---

## 9. Review ask

1. Approve `_load_belief_deps` 4-tuple (vs separate loader helper only).
2. Approve `format_config=None` legacy default in decision core (no implicit yaml load there).
3. Approve runner `_get_format_config` cache mirroring `_get_book` pattern.
4. Approve hermetic `agent_choose` tests (no real Calc deps).
5. Approve test file split: new `test_runner_format_config.py` vs extend existing runner tests.
