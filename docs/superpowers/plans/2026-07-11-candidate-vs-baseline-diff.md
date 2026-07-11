# Candidate-vs-Baseline-Differenzanalyse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine fail-closed, reproduzierbare Analyse bauen, die gepaarte Baseline-/Candidate-Runs bis zur ersten Zustandsdivergenz auf Entscheidungsebene vergleicht und Outcome-Flips, Matchup-Effekte, Regressionen sowie Wiederholungsstabilität deterministisch berichtet.

**Architecture:** Der bestehende Eval-Pfad bleibt maßgeblich: `pair_runs()` paart Battles, `DecisionTrace` liefert Kandidateninformationen und Result-JSONLs liefern Outcomes/Safety. Ein standardmäßig deaktiviertes Decision-Sidecar bindet jede Hero-Entscheidung über Count und SHA an ihre Result-Zeile. Reine Offline-Module validieren Sidecars, klassifizieren nur Entscheidungen mit identischem sichtbaren Vorzustand und erzeugen JSON/Markdown ohne einen neuen Strength-Verdictbaum.

**Tech Stack:** Python 3.11+, Pydantic v2, stdlib `dataclasses`/`hashlib`/`json`/`gzip`, bestehende ShowdownBot-Evalmodule, pytest.

---

## Dateistruktur

Neu:

- `showdown_bot/src/showdown_bot/eval/decision_capture.py` — kanonische sichtbare Zustände,
  normalisierte `/choose`-Aktionen, Sidecar-Schema, Writer/Loader und Battle-Bindung.
- `showdown_bot/src/showdown_bot/eval/decision_diff.py` — Run-Validierung, Entscheidungsalignment,
  Divergenzklassifikation, Outcome-/Bucket-/Stability-Metriken.
- `showdown_bot/src/showdown_bot/eval/decision_diff_report.py` — deterministisches Reportobjekt und
  Markdown-Rendering; keine Battle- oder CLI-I/O.
- `showdown_bot/tests/test_decision_capture.py` — Hash-, Leakage-, Action- und Writer-Vertrag.
- `showdown_bot/tests/test_decision_diff.py` — Alignment, Divergenzen, Outcomes, Buckets, Stability.
- `showdown_bot/tests/test_decision_diff_report.py` — JSON-Struktur und Markdown-Golden-Struktur.
- `showdown_bot/tests/test_cli_decision_diff.py` — Capture- und Analyse-CLI-Verträge.

Geändert:

- `showdown_bot/src/showdown_bot/battle/decision_trace.py` — optionale Selection-/Fallback-Telemetrie.
- `showdown_bot/src/showdown_bot/battle/decision.py` — Fallback-Stufe ohne Verhaltensänderung markieren.
- `showdown_bot/src/showdown_bot/learning/reranker_override.py` — Override/Failsafe-Grund markieren.
- `showdown_bot/src/showdown_bot/client/gauntlet.py` — Hero-Capture nach erfolgreichem Send.
- `showdown_bot/src/showdown_bot/eval/result_jsonl.py` — optionale Count-/SHA-Bindungsfelder.
- `showdown_bot/src/showdown_bot/cli.py` — `--decision-trace-out` und `decision-diff`.
- `showdown_bot/tests/test_decision_trace.py`, `test_actions_force_phase.py`,
  `test_reranker_override.py`, `test_cli_run_schedule_export.py`, `test_result_jsonl.py` — Regressionen
  an bestehenden Verträgen.

Keine bestehenden Dateien werden umbenannt. Es werden keine lokalen Battles und keine Held-out-Runs
für die Implementierung benötigt.

---

### Task 1: Selection- und Fallback-Telemetrie im bestehenden DecisionTrace

**Files:**

- Modify: `showdown_bot/src/showdown_bot/battle/decision_trace.py`
- Modify: `showdown_bot/src/showdown_bot/battle/decision.py`
- Modify: `showdown_bot/src/showdown_bot/learning/reranker_override.py`
- Test: `showdown_bot/tests/test_decision_trace.py`
- Test: `showdown_bot/tests/test_actions_force_phase.py`
- Test: `showdown_bot/tests/test_reranker_override.py`

- [ ] **Step 1: Failing DTO- und Heuristikpfad-Tests schreiben**

In `test_decision_trace.py` einen Default-Vertrag ergänzen:

```python
def test_selection_telemetry_defaults_to_none():
    trace = DecisionTrace()
    assert trace.selection_stage is None
    assert trace.fallback_reason is None
```

In `test_actions_force_phase.py` den erfolgreichen Heuristikpfad und den deterministischen
Fallback mit einem echten `DecisionTrace` pinnen:

```python
def test_choose_with_fallback_marks_heuristic_stage(decision_fixture):
    req, kw = decision_fixture
    trace = DecisionTrace()
    out = choose_with_fallback(req, trace=trace, **kw)
    assert out.startswith("/choose ")
    assert trace.selection_stage == "heuristic"
    assert trace.fallback_reason is None


def test_choose_with_fallback_marks_server_default(monkeypatch):
    req = _f4_request()
    trace = DecisionTrace()
    monkeypatch.setattr(decision, "pick_default_pair", lambda req: (_ for _ in ()).throw(RuntimeError("no pair")))
    out = choose_with_fallback(req, state=None, book=None, trace=trace)
    assert out == f"/choose default|{req.rqid}"
    assert trace.selection_stage == "server_default"
    assert trace.fallback_reason == "default_pair_error"
```

- [ ] **Step 2: Tests ausführen und erwartetes Rot bestätigen**

Run:

```powershell
python -m pytest tests/test_decision_trace.py::test_selection_telemetry_defaults_to_none tests/test_actions_force_phase.py::test_choose_with_fallback_marks_heuristic_stage tests/test_actions_force_phase.py::test_choose_with_fallback_marks_server_default -q
```

Expected: FAIL wegen fehlender `selection_stage`-/`fallback_reason`-Felder.

- [ ] **Step 3: DTO und einen kleinen Markierungshelper implementieren**

In `decision_trace.py`:

```python
@dataclass
class DecisionTrace:
    game_mode: str | None = None
    chosen_candidate_id: str | None = None
    opponent_responses: list[Any] = field(default_factory=list)
    opponent_response_weights: list[float] = field(default_factory=list)
    candidates: list[CandidateTrace] = field(default_factory=list)
    tempo_features: DecisionTempoFeatures = field(default_factory=DecisionTempoFeatures)
    selection_stage: str | None = None
    fallback_reason: str | None = None
```

In `decision.py` unmittelbar vor `choose_with_fallback`:

```python
def _mark_selection(trace, stage: str, reason: str | None = None) -> None:
    if trace is not None:
        trace.selection_stage = stage
        trace.fallback_reason = reason
```

`choose_with_fallback` so umstellen, dass ausschließlich Telemetrie hinzukommt:

```python
if req.team_preview:
    _mark_selection(trace, "team_preview")
    return encode_team_preview(pick_team_preview_default(req), rqid=req.rqid)

fallback_reason = None
if state is not None and book is not None:
    ex = ThreadPoolExecutor(max_workers=1)
    try:
        fut = ex.submit(
            heuristic_choose_for_request,
            req, state=state, book=book, our_side=our_side, report=report, trace=trace, **deps,
        )
        choice = fut.result(timeout=hard_timeout)
        _mark_selection(trace, "heuristic")
        return choice
    except FutureTimeout:
        fallback_reason = "heuristic_timeout"
        logger.warning("heuristic timed out after %ss, falling back", hard_timeout)
    except Exception as exc:  # noqa: BLE001
        fallback_reason = "heuristic_error"
        logger.warning("heuristic failed, falling back: %s", exc)
    finally:
        ex.shutdown(wait=False, cancel_futures=True)

try:
    from showdown_bot.battle.baselines import max_damage_choice
    if state is not None and book is not None:
        choice = max_damage_choice(req, state=state, book=book, our_side=our_side, **deps)
        _mark_selection(trace, "max_damage_fallback", fallback_reason)
        return choice
except Exception as exc:  # noqa: BLE001
    fallback_reason = "max_damage_error"
    logger.warning("max_damage fallback failed: %s", exc)

try:
    choice = encode_choose(pick_default_pair(req), rqid=req.rqid)
    _mark_selection(trace, "deterministic_default_pair", fallback_reason)
    return choice
except Exception as exc:  # noqa: BLE001
    logger.warning("random fallback failed: %s", exc)

_mark_selection(trace, "server_default", "default_pair_error")
return f"/choose default|{req.rqid}"
```

- [ ] **Step 4: Reranker-Override-Telemetrie testgetrieben ergänzen**

In `test_reranker_override.py` für Erfolg und Schema-Failsafe ergänzen:

```python
def test_override_marks_selection_stage(decision_fixture):
    trace, state, req, heuristic_choose, side = _run_decision(decision_fixture)
    manifest, _rows = _manifest_for(trace, state, req, side)
    scores = [0.0] * len(trace.candidates)
    scores[-1] = 100.0
    override = RerankerOverride(
        booster=_StubBooster(scores, manifest["feature_names"]),
        manifest=manifest, format_id=FORMAT_ID,
    )
    out = override.override_choice(
        trace=trace, state=state, request=req,
        heuristic_choose=heuristic_choose, our_side=side,
    )
    assert out != heuristic_choose
    assert trace.selection_stage == "reranker_override"
    assert trace.fallback_reason is None


def test_schema_failure_marks_heuristic_failsafe(decision_fixture):
    trace, state, req, heuristic_choose, side = _run_decision(decision_fixture)
    manifest, _rows = _manifest_for(trace, state, req, side)
    bad_manifest = dict(manifest)
    bad_manifest["feature_schema_hash"] = "deadbeef"
    override = RerankerOverride(
        booster=_StubBooster([1.0] * len(trace.candidates), manifest["feature_names"]),
        manifest=bad_manifest, format_id=FORMAT_ID,
    )
    out = override.override_choice(
        trace=trace, state=state, request=req,
        heuristic_choose=heuristic_choose, our_side=side,
    )
    assert out == heuristic_choose
    assert trace.selection_stage == "heuristic"
    assert trace.fallback_reason == "reranker_schema_mismatch"
```

In `reranker_override.py` einen lokalen Helper verwenden und jeden frühen Return eindeutig markieren:

```python
def _fallback(trace, choose: str, reason: str) -> str:
    trace.selection_stage = "heuristic"
    trace.fallback_reason = reason
    return choose
```

Erforderliche Gründe: `reranker_schema_mismatch`, `reranker_empty_or_misaligned_scores`,
`reranker_non_joint_action`, `reranker_empty_choose`, `reranker_exception`. Vor erfolgreichem Return:

```python
trace.selection_stage = "reranker_override"
trace.fallback_reason = None
return choose
```

- [ ] **Step 5: Betroffene Tests grün ausführen**

Run:

```powershell
python -m pytest tests/test_decision_trace.py tests/test_actions_force_phase.py tests/test_reranker_override.py tests/test_gauntlet_dispatch.py -q
```

Expected: PASS; bestehende Choice-Strings bleiben unverändert.

- [ ] **Step 6: Commit**

```powershell
git add showdown_bot/src/showdown_bot/battle/decision_trace.py showdown_bot/src/showdown_bot/battle/decision.py showdown_bot/src/showdown_bot/learning/reranker_override.py showdown_bot/tests/test_decision_trace.py showdown_bot/tests/test_actions_force_phase.py showdown_bot/tests/test_reranker_override.py
git commit -m "feat(eval): expose decision selection and fallback telemetry"
```

---

### Task 2: Sichtbaren Vorzustand und `/choose`-Aktionen kanonisieren

**Files:**

- Create: `showdown_bot/src/showdown_bot/eval/decision_capture.py`
- Create: `showdown_bot/tests/test_decision_capture.py`

- [ ] **Step 1: Failing Hash-, Leakage- und Action-Tests schreiben**

Die Tests müssen mindestens diese Fälle enthalten:

```python
@pytest.fixture
def capture_fixture(decision_fixture):
    req, kw = decision_fixture
    return req, copy.deepcopy(kw["state"])


def test_observable_hash_is_order_independent(capture_fixture):
    request, state = capture_fixture
    left = prepare_capture(state, request)
    state.sides["p1"]["a"].boosts = {"spe": 1, "atk": -1}
    right = prepare_capture(state, request)
    state.sides["p1"]["a"].boosts = {"atk": -1, "spe": 1}
    again = prepare_capture(state, request)
    assert right.observable_state_hash == again.observable_state_hash
    assert left.request_hash == right.request_hash


def test_payload_has_explicit_allowlist(capture_fixture):
    _request, state = capture_fixture
    payload = observable_state_payload(state)
    rendered = json.dumps(payload, sort_keys=True)
    assert "game_outcome" not in rendered
    assert "winner" not in rendered
    assert "teacher" not in rendered


@pytest.mark.parametrize(
    ("choose", "kind", "move_id", "target", "tera"),
    [
        ("/choose move 1 1, move 2 2|7", "joint", "fakeout", 1, False),
        ("/choose move 1 1 terastallize, pass|7", "joint", "fakeout", 1, True),
        ("/choose team 1234|7", "team_preview", None, None, False),
        ("/choose default|7", "default", None, None, False),
    ],
)
def test_normalize_choose(choose, kind, move_id, target, tera, capture_fixture):
    request, _state = capture_fixture
    action = normalize_choose(choose, request)
    assert action["kind"] == kind
    if kind == "joint":
        assert action["slots"][0]["move_id"] == move_id
        assert action["slots"][0]["target"] == target
        assert action["slots"][0]["tera"] is tera
```

Zusätzlich: Switch, Protect, negativer Ally-Target, Forced Replacement, ungültiger Move-Index und
unbekanntes Choose-Format.

- [ ] **Step 2: Tests rot ausführen**

Run:

```powershell
python -m pytest tests/test_decision_capture.py -q
```

Expected: collection FAIL, weil `showdown_bot.eval.decision_capture` noch fehlt.

- [ ] **Step 3: Kanonische Payloads und Hashes implementieren**

In `decision_capture.py` folgende öffentliche API anlegen:

```python
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass

from showdown_bot.engine.state import BattleState, PokemonState, to_id
from showdown_bot.models.request import BattleRequest

TRACE_SCHEMA_VERSION = "decision-trace-v1"
PROTECT_IDS = frozenset({
    "protect", "detect", "wideguard", "quickguard", "spikyshield",
    "kingsshield", "banefulbunker", "silktrap", "burningbulwark", "maxguard",
})

class DecisionCaptureError(ValueError):
    pass


@dataclass(frozen=True)
class PreparedCapture:
    observable_state_hash: str
    request_hash: str
    state_summary: dict
    decision_phase: str


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
```

`PokemonState` wird nicht über `__dict__` serialisiert, sondern über diese Allowlist:

```python
def _pokemon_payload(mon: PokemonState) -> dict:
    return {
        "species": mon.species,
        "nickname": mon.nickname,
        "level": mon.level,
        "gender": mon.gender,
        "hp": mon.hp,
        "max_hp": mon.max_hp,
        "boosts": dict(sorted(mon.boosts.items())),
        "status": mon.status,
        "item": mon.item if mon.item_known else None,
        "item_known": mon.item_known,
        "ability": mon.ability,
        "moves": sorted(mon.moves),
        "tera_type": mon.tera_type,
        "terastallized": mon.terastallized,
        "fainted": mon.fainted,
        "types": list(mon.types),
        "consecutive_protect": mon.consecutive_protect,
        "moved_since_switch": mon.moved_since_switch,
        "item_lost": mon.item_lost,
    }


def observable_state_payload(state: BattleState | None) -> dict | None:
    if state is None:
        return None
    return {
        "turn": state.turn,
        "field": {
            "weather": state.field.weather,
            "terrain": state.field.terrain,
            "trick_room": state.field.trick_room,
            "tailwind": dict(sorted(state.field.tailwind.items())),
        },
        "sides": {
            side: {slot: _pokemon_payload(mon) for slot, mon in sorted(slots.items())}
            for side, slots in sorted(state.sides.items())
        },
    }


def request_payload(request: BattleRequest) -> dict:
    return request.model_dump(mode="json", by_alias=True, exclude_none=False)


def prepare_capture(state: BattleState | None, request: BattleRequest) -> PreparedCapture:
    state_payload = observable_state_payload(state)
    req_payload = request_payload(request)
    if request.team_preview:
        phase = "team_preview"
    elif request.force_switch is not None and any(request.force_switch):
        phase = "forced_replacement"
    else:
        phase = "regular_turn"
    return PreparedCapture(
        observable_state_hash=_sha256({"state": state_payload, "request": req_payload}),
        request_hash=_sha256(req_payload),
        state_summary=state_payload or {"turn": 0, "field": {}, "sides": {}},
        decision_phase=phase,
    )
```

- [ ] **Step 4: Choose-Parser minimal und strikt implementieren**

Verbindliche Ausgabeformen:

```python
_MOVE_RE = re.compile(r"^move (?P<index>\d+)(?: (?P<target>-?\d+))?(?: (?P<tera>terastallize))?$")


def _slot_action(token: str, request: BattleRequest, slot_index: int) -> dict:
    token = " ".join(token.strip().lower().split())
    if token == "pass":
        return {"kind": "pass"}
    if token.startswith("switch "):
        target = token[len("switch "):].strip()
        if not target:
            raise DecisionCaptureError("empty switch target")
        return {"kind": "switch", "switch_target": to_id(target)}
    match = _MOVE_RE.fullmatch(token)
    if match is None:
        raise DecisionCaptureError(f"unsupported slot action: {token!r}")
    move_index = int(match.group("index"))
    active = request.active[slot_index] if slot_index < len(request.active) else None
    if active is None or not 1 <= move_index <= len(active.moves):
        raise DecisionCaptureError(f"move index {move_index} unavailable for slot {slot_index}")
    move_id = to_id(active.moves[move_index - 1].id)
    return {
        "kind": "move",
        "move_index": move_index,
        "move_id": move_id,
        "target": int(match.group("target")) if match.group("target") is not None else None,
        "tera": match.group("tera") is not None,
        "is_protect": move_id in PROTECT_IDS,
    }


def normalize_choose(choose: str, request: BattleRequest) -> dict:
    if not choose.startswith("/choose "):
        raise DecisionCaptureError(f"not a /choose command: {choose!r}")
    body = choose[len("/choose "):].split("|", 1)[0].strip()
    if body == "default":
        return {"kind": "default"}
    if body.startswith("team "):
        order = body[len("team "):].strip()
        if not order.isdigit():
            raise DecisionCaptureError(f"invalid team preview order: {order!r}")
        return {"kind": "team_preview", "order": [int(ch) for ch in order]}
    tokens = body.split(", ")
    if len(tokens) != 2:
        raise DecisionCaptureError(f"expected two slot actions: {body!r}")
    slots = [_slot_action(token, request, i) for i, token in enumerate(tokens)]
    return {"kind": "joint", "slots": slots}
```

- [ ] **Step 5: Capture-Primitive-Tests grün ausführen**

Run:

```powershell
python -m pytest tests/test_decision_capture.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add showdown_bot/src/showdown_bot/eval/decision_capture.py showdown_bot/tests/test_decision_capture.py
git commit -m "feat(eval): canonicalize observable decisions and actions"
```

---

### Task 3: Sidecar-Zeilen validieren, schreiben, laden und an Battles binden

**Files:**

- Modify: `showdown_bot/src/showdown_bot/eval/decision_capture.py`
- Modify: `showdown_bot/tests/test_decision_capture.py`
- Modify: `showdown_bot/src/showdown_bot/eval/result_jsonl.py`
- Modify: `showdown_bot/tests/test_result_jsonl.py`

- [ ] **Step 1: Failing Writer-/Bindungstests ergänzen**

```python
@pytest.fixture
def trace_context():
    return BattleTraceContext(
        battle_id="battle-a", seed_index=0, config_id="heuristic",
        config_hash="config-a", schedule_hash="schedule-a",
        format_id="gen9vgc2025regi", git_sha="a" * 40,
    )


@pytest.fixture
def prepared(capture_fixture):
    request, state = capture_fixture
    return prepare_capture(state, request)


def test_writer_binds_count_and_sha(tmp_path, trace_context, prepared, capture_fixture):
    request, _state = capture_fixture
    path = tmp_path / "trace.jsonl"
    writer = DecisionTraceWriter(path)
    writer.write(build_trace_row(
        context=trace_context, prepared=prepared, request=request,
        choose="/choose move 1 1, move 2 2|7", trace=None,
        decision_index=0, decision_latency_ms=12.5,
    ))
    binding = writer.finish_battle(trace_context.battle_id)
    assert binding["decision_trace_count"] == 1
    assert len(binding["decision_trace_sha256"]) == 64
    assert load_decision_trace(path)[0]["battle_id"] == trace_context.battle_id


def test_writer_refuses_duplicate_decision_key(tmp_path, trace_context, prepared, capture_fixture):
    request, _state = capture_fixture
    writer = DecisionTraceWriter(tmp_path / "trace.jsonl.gz")
    row = build_trace_row(
        context=trace_context, prepared=prepared, request=request,
        choose="/choose move 1 1, move 2 2|7", trace=None,
        decision_index=0, decision_latency_ms=1.0,
    )
    writer.write(row)
    with pytest.raises(DecisionCaptureError, match="duplicate decision key"):
        writer.write(row)
```

In `test_result_jsonl.py` pinnen, dass die beiden neuen Felder optional sind, bei Anwesenheit aber
Typ und SHA-Form validiert werden.

- [ ] **Step 2: Tests rot ausführen**

Run:

```powershell
python -m pytest tests/test_decision_capture.py tests/test_result_jsonl.py -q
```

Expected: FAIL wegen fehlender Writer-/Row-API.

- [ ] **Step 3: Kontext, Row-Builder und strikte Validierung implementieren**

In `decision_capture.py`:

```python
@dataclass(frozen=True)
class BattleTraceContext:
    battle_id: str
    seed_index: int
    config_id: str
    config_hash: str
    schedule_hash: str
    format_id: str
    git_sha: str
    our_side: str = "p1"


def build_trace_row(*, context: BattleTraceContext, prepared: PreparedCapture,
                    request: BattleRequest, choose: str, trace, decision_index: int,
                    decision_latency_ms: float,
                    selection_stage_override: str | None = None,
                    fallback_reason_override: str | None = None) -> dict:
    candidates = [] if trace is None else [
        {"candidate_id": c.candidate_id, "rank": c.rank, "aggregate_score": c.aggregate_score}
        for c in trace.candidates
    ]
    row = {
        "trace_schema_version": TRACE_SCHEMA_VERSION,
        "battle_id": context.battle_id,
        "seed_index": context.seed_index,
        "decision_index": decision_index,
        "turn_number": prepared.state_summary.get("turn", 0),
        "our_side": context.our_side,
        "config_id": context.config_id,
        "config_hash": context.config_hash,
        "schedule_hash": context.schedule_hash,
        "format_id": context.format_id,
        "git_sha": context.git_sha,
        "observable_state_hash": prepared.observable_state_hash,
        "request_hash": prepared.request_hash,
        "decision_phase": prepared.decision_phase,
        "state_summary": prepared.state_summary,
        "actual_choose_string": choose,
        "normalized_action": normalize_choose(choose, request),
        "chosen_candidate_id": None if trace is None else trace.chosen_candidate_id,
        "chosen_rank": next((c.rank for c in trace.candidates
                             if c.candidate_id == trace.chosen_candidate_id), None)
                       if trace is not None else None,
        "candidates": candidates,
        "selection_stage": selection_stage_override if selection_stage_override is not None else
                           (None if trace is None else trace.selection_stage),
        "fallback_reason": fallback_reason_override if fallback_reason_override is not None else
                           (None if trace is None else trace.fallback_reason),
        "decision_latency_ms": float(decision_latency_ms),
    }
    validate_trace_row(row)
    return row
```

`validate_trace_row` verwendet exakte Feldmengen und lehnt unbekannte Felder ab:

```python
_REQUIRED_TRACE_FIELDS = frozenset({
    "trace_schema_version", "battle_id", "seed_index", "decision_index", "turn_number",
    "our_side", "config_id", "config_hash", "schedule_hash", "format_id", "git_sha",
    "observable_state_hash", "request_hash", "decision_phase", "state_summary",
    "actual_choose_string", "normalized_action", "candidates", "decision_latency_ms",
})
_NULLABLE_TRACE_FIELDS = frozenset({
    "chosen_candidate_id", "chosen_rank", "selection_stage", "fallback_reason",
})


def validate_trace_row(row: dict) -> None:
    missing = _REQUIRED_TRACE_FIELDS - set(row)
    unknown = set(row) - _REQUIRED_TRACE_FIELDS - _NULLABLE_TRACE_FIELDS
    if missing or unknown:
        raise DecisionCaptureError(f"trace fields missing={sorted(missing)} unknown={sorted(unknown)}")
    if row["trace_schema_version"] != TRACE_SCHEMA_VERSION:
        raise DecisionCaptureError("unknown trace schema version")
    if row["decision_phase"] not in {"team_preview", "forced_replacement", "regular_turn"}:
        raise DecisionCaptureError("unknown decision phase")
    for key in ("seed_index", "decision_index", "turn_number"):
        if not isinstance(row[key], int) or row[key] < 0:
            raise DecisionCaptureError(f"{key} must be a non-negative int")
    for key in ("observable_state_hash", "request_hash"):
        if not isinstance(row[key], str) or re.fullmatch(r"[0-9a-f]{64}", row[key]) is None:
            raise DecisionCaptureError(f"{key} must be lowercase sha256 hex")
    if not isinstance(row["decision_latency_ms"], (int, float)) or not math.isfinite(row["decision_latency_ms"]):
        raise DecisionCaptureError("decision_latency_ms must be finite")
    for candidate in row["candidates"]:
        score = candidate["aggregate_score"]
        if not isinstance(score, (int, float)) or not math.isfinite(score):
            raise DecisionCaptureError("candidate aggregate_score must be finite")
```

- [ ] **Step 4: Writer, Gzip-Loader und per-Battle-SHA implementieren**

```python
def _open_text(path, mode: str):
    path = Path(path)
    return gzip.open(path, mode + "t", encoding="utf-8", newline="\n") \
        if path.suffix == ".gz" else open(path, mode, encoding="utf-8", newline="\n")


class DecisionTraceWriter:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.exists() and self.path.stat().st_size:
            raise DecisionCaptureError(f"trace output must be missing or empty: {self.path}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._keys = set()
        self._lines_by_battle = {}
        self._errors_by_battle = {}

    def write(self, row: dict) -> None:
        battle_id = str(row.get("battle_id", ""))
        try:
            validate_trace_row(row)
            key = (battle_id, row["decision_index"], row["our_side"])
            if key in self._keys:
                raise DecisionCaptureError(f"duplicate decision key: {key!r}")
            line = _canonical_json(row) + "\n"
            with _open_text(self.path, "a") as fh:
                fh.write(line)
            self._keys.add(key)
            self._lines_by_battle.setdefault(battle_id, []).append(line.encode("utf-8"))
        except Exception as exc:
            self._errors_by_battle.setdefault(battle_id, []).append(str(exc))
            raise

    def finish_battle(self, battle_id: str) -> dict:
        errors = self._errors_by_battle.get(battle_id, [])
        if errors:
            raise DecisionCaptureError(f"battle {battle_id} capture errors: {errors}")
        lines = self._lines_by_battle.get(battle_id, [])
        if not lines:
            raise DecisionCaptureError(f"battle {battle_id} has no decision rows")
        return {
            "decision_trace_count": len(lines),
            "decision_trace_sha256": hashlib.sha256(b"".join(lines)).hexdigest(),
        }


def load_decision_trace(path) -> list[dict]:
    rows = []
    with _open_text(path, "r") as fh:
        for line_number, line in enumerate(fh, 1):
            try:
                row = json.loads(line)
                validate_trace_row(row)
            except Exception as exc:
                raise DecisionCaptureError(f"{path}:{line_number}: {exc}") from exc
            rows.append(row)
    return rows
```

- [ ] **Step 5: Result-Bindungsfelder ergänzen**

In `result_jsonl.py` zu `NULLABLE_FIELDS` hinzufügen:

```python
"decision_trace_count", "decision_trace_sha256",
```

In `validate_battle_row` bei vorhandenen Werten validieren:

```python
count = row.get("decision_trace_count")
digest = row.get("decision_trace_sha256")
if (count is None) != (digest is None):
    raise ResultRowError("decision trace count and sha256 must be present together")
if count is not None and (not isinstance(count, int) or count <= 0):
    raise ResultRowError("decision_trace_count must be a positive int")
if digest is not None and (not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None):
    raise ResultRowError("decision_trace_sha256 must be lowercase sha256 hex")
```

- [ ] **Step 6: Tests grün ausführen**

Run:

```powershell
python -m pytest tests/test_decision_capture.py tests/test_result_jsonl.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add showdown_bot/src/showdown_bot/eval/decision_capture.py showdown_bot/src/showdown_bot/eval/result_jsonl.py showdown_bot/tests/test_decision_capture.py showdown_bot/tests/test_result_jsonl.py
git commit -m "feat(eval): write and bind decision trace sidecars"
```

---

### Task 4: Capture standardmäßig aus lassen und in Schedule-Runs verdrahten

**Files:**

- Modify: `showdown_bot/src/showdown_bot/client/gauntlet.py`
- Modify: `showdown_bot/src/showdown_bot/cli.py`
- Modify: `showdown_bot/tests/test_gauntlet_dispatch.py`
- Modify: `showdown_bot/tests/test_cli_run_schedule_export.py`
- Create: `showdown_bot/tests/test_cli_decision_diff.py`

- [ ] **Step 1: Failing Capture-off- und CLI-Vertragstests schreiben**

Capture-off muss denselben Dispatchpfad behalten:

```python
class _RecordingConn:
    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)


def test_capture_off_does_not_construct_decision_trace(monkeypatch, decision_fixture):
    import showdown_bot.client.gauntlet as gauntlet

    req, kw = decision_fixture
    conn = _RecordingConn()
    client = _client(conn=conn, agent="heuristic", book=kw["book"])
    monkeypatch.setattr(client, "_state_for", lambda room, request: kw["state"])
    monkeypatch.setattr(client, "_decision_deps", lambda: (None, None, None, None))
    monkeypatch.setattr(gauntlet, "agent_choose", lambda *args, **kwargs: f"/choose default|{req.rqid}")
    monkeypatch.setattr(
        gauntlet, "DecisionTrace",
        lambda: (_ for _ in ()).throw(AssertionError("capture-off built DecisionTrace")),
    )
    client.decision_trace_writer = None
    asyncio.run(client.handle_request("battle-test", req.model_dump_json(by_alias=True)))
    assert conn.sent == [f"battle-test|/choose default|{req.rqid}"]
```

CLI-Verträge:

```python
def test_schedule_trace_requires_result_out(_sched_path):
    args = argparse.Namespace(
        schedule=str(_sched_path), result_out="", decision_trace_out="trace.jsonl",
    )
    with pytest.raises(SystemExit, match="--decision-trace-out requires --result-out"):
        run_schedule(args)


def test_parser_accepts_decision_trace_out(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        sys, "argv",
        ["showdown-bot", "gauntlet", "--schedule", "s.yaml", "--result-out", "r.jsonl",
         "--decision-trace-out", "trace.jsonl.gz"],
    )
    monkeypatch.setattr(cli, "run_gauntlet", lambda args: captured.update(vars(args)))
    cli.main()
    assert captured["decision_trace_out"] == "trace.jsonl.gz"
```

- [ ] **Step 2: Tests rot ausführen**

Run:

```powershell
python -m pytest tests/test_gauntlet_dispatch.py tests/test_cli_run_schedule_export.py tests/test_cli_decision_diff.py -q
```

Expected: FAIL wegen fehlendem CLI-Argument und Clientfeldern.

- [ ] **Step 3: Writer und Battle-Kontext durch den Gauntlet fädeln**

`run_local_gauntlet` erhält zwei optionale Keywordargumente:

```python
decision_trace_writer=None,
decision_trace_context=None,
```

Wenn genau eines gesetzt ist, `ValueError` auslösen. Bei gesetztem Kontext muss `games == 1` gelten.
Nur der Hero-Client erhält Writer und Kontext; der Villain bleibt unverändert.

`_Client.__init__` speichert:

```python
self.decision_trace_writer = decision_trace_writer
self.decision_trace_context = decision_trace_context
self._decision_capture_index = 0
```

In `handle_request` vor `agent_choose`:

```python
prepared_capture = None
if self.decision_trace_writer is not None:
    from showdown_bot.eval.decision_capture import prepare_capture
    prepared_capture = prepare_capture(state, req)

needs_model_trace = (
    self._export is not None or self._shadow is not None or self.decision_trace_writer is not None
)
trace_obj = DecisionTrace() if (
    needs_model_trace and self.agent in ("heuristic", "heuristic_reranker") and state is not None
) else None
```

Vor dem bestehenden `try` werden `capture_stage_override = None` und
`capture_reason_override = None` initialisiert. Im Exception-Pfad werden sie auf
`"client_exception_default"` und `"agent_exception"` gesetzt. Direkt nach der Choice-Berechnung,
aber vor `await self.conn.send(...)`, wird die bereits bestehende Latenz einmal ermittelt:

```python
decision_latency_ms = (time.perf_counter() - start) * 1000
self.latencies.append(decision_latency_ms / 1000)
```

Nach erfolgreichem `await self.conn.send(...)`:

```python
if self.decision_trace_writer is not None:
    from showdown_bot.eval.decision_capture import build_trace_row
    row = build_trace_row(
        context=self.decision_trace_context,
        prepared=prepared_capture,
        request=req,
        choose=choose,
        trace=trace_obj,
        decision_index=self._decision_capture_index,
        decision_latency_ms=decision_latency_ms,
        selection_stage_override=capture_stage_override,
        fallback_reason_override=capture_reason_override,
    )
    self.decision_trace_writer.write(row)
    self._decision_capture_index += 1
```

Damit wird keine bereits validierte Row nachträglich mutiert und die Sidecar-Latenz entspricht exakt
dem bestehenden Entscheidungszeitfenster, nicht der WebSocket-Sendezeit.

- [ ] **Step 4: Schedule-CLI und Battle-Bindung implementieren**

Parserargument:

```python
parser.add_argument(
    "--decision-trace-out", dest="decision_trace_out", default="",
    help="Optional hero decision sidecar for gauntlet --schedule; requires --result-out.",
)
```

In `run_schedule` nach Config-/Run-Provenance:

```python
trace_out = getattr(args, "decision_trace_out", "")
trace_writer = None
if trace_out:
    if not result_out:
        raise SystemExit("--decision-trace-out requires --result-out")
    from showdown_bot.eval.decision_capture import DecisionTraceWriter
    trace_writer = DecisionTraceWriter(trace_out)
```

Vor jedem Battle Seed, Battle-ID, Config-ID/-Hash nur einmal berechnen und verwenden:

```python
seed = derive_battle_seed(base, row.seed_index)
battle_id = make_battle_id(sched.schedule_hash, row.seed_index, seed)
config_id = hero_agent
config_hash = _config_hash_for(config_id, row.format_id)
trace_context = BattleTraceContext(
    battle_id=battle_id, seed_index=row.seed_index, config_id=config_id,
    config_hash=config_hash, schedule_hash=sched.schedule_hash,
    format_id=row.format_id, git_sha=git_sha,
) if trace_writer is not None else None
```

Im `on_br` vor `BattleResultWriter.write`:

```python
trace_binding = trace_writer.finish_battle(battle_id) if trace_writer is not None else {}
writer.write({
    # bestehende Felder unverändert
    "battle_id": battle_id,
    "decision_trace_count": trace_binding.get("decision_trace_count"),
    "decision_trace_sha256": trace_binding.get("decision_trace_sha256"),
    **record,
})
```

`run_local_gauntlet(..., decision_trace_writer=trace_writer,
decision_trace_context=trace_context)` übergeben.

- [ ] **Step 5: Capture-Tests grün und bestehende Schedule-Tests ausführen**

Run:

```powershell
python -m pytest tests/test_gauntlet_dispatch.py tests/test_cli_run_schedule_export.py tests/test_cli_decision_diff.py tests/test_result_jsonl.py -q
```

Expected: PASS; Capture-off erzeugt keine Sidecar-Datei und keinen zusätzlichen Trace.

- [ ] **Step 6: Commit**

```powershell
git add showdown_bot/src/showdown_bot/client/gauntlet.py showdown_bot/src/showdown_bot/cli.py showdown_bot/tests/test_gauntlet_dispatch.py showdown_bot/tests/test_cli_run_schedule_export.py showdown_bot/tests/test_cli_decision_diff.py
git commit -m "feat(eval): capture schedule decisions in optional sidecars"
```

---

### Task 5: Sidecar-Runs gegen Result-Zeilen fail-closed validieren

**Files:**

- Create: `showdown_bot/src/showdown_bot/eval/decision_diff.py`
- Create: `showdown_bot/tests/test_decision_diff.py`

- [ ] **Step 1: Failing Run-Validierungstests schreiben**

```python
@pytest.fixture
def bound_trace_fixture(tmp_path, decision_fixture):
    req, kw = decision_fixture
    writer = DecisionTraceWriter(tmp_path / "trace.jsonl")
    results = []
    for seed_index, battle_id in enumerate(("battle-a", "battle-b")):
        context = BattleTraceContext(
            battle_id=battle_id, seed_index=seed_index, config_id="heuristic",
            config_hash="config-a", schedule_hash="schedule-a",
            format_id="gen9vgc2025regi", git_sha="a" * 40,
        )
        for decision_index in (0, 1):
            writer.write(build_trace_row(
                context=context, prepared=prepare_capture(kw["state"], req), request=req,
                choose=f"/choose move 1 1, move 2 2|{req.rqid}", trace=None,
                decision_index=decision_index, decision_latency_ms=1.0,
            ))
        results.append({
            "battle_id": battle_id, "seed_index": seed_index,
            "config_hash": "config-a", "schedule_hash": "schedule-a",
            "format_id": "gen9vgc2025regi", "git_sha": "a" * 40,
            **writer.finish_battle(battle_id),
        })
    return results, load_decision_trace(tmp_path / "trace.jsonl")


def test_validate_trace_run_accepts_bound_rows(bound_trace_fixture):
    result_rows, trace_rows = bound_trace_fixture
    run = validate_trace_run(result_rows, trace_rows)
    assert sorted(run.rows_by_battle) == ["battle-a", "battle-b"]


@pytest.mark.parametrize("mutation, message", [
    (lambda results, traces: results[0].update(decision_trace_count=99), "count mismatch"),
    (lambda results, traces: results[0].update(decision_trace_sha256="0" * 64), "sha mismatch"),
    (lambda results, traces: traces[0].update(config_hash="wrong"), "config_hash mismatch"),
    (lambda results, traces: traces[1].update(decision_index=0), "duplicate decision key"),
])
def test_validate_trace_run_refuses_corruption(bound_trace_fixture, mutation, message):
    result_rows, trace_rows = copy.deepcopy(bound_trace_fixture)
    mutation(result_rows, trace_rows)
    with pytest.raises(DecisionDiffError, match=message):
        validate_trace_run(result_rows, trace_rows)
```

Legacy-Result ohne Bindungsfelder muss im Full mode scheitern und im Outcome-only mode ohne Aufruf
dieser Funktion bleiben.

- [ ] **Step 2: Tests rot ausführen**

Run:

```powershell
python -m pytest tests/test_decision_diff.py -q
```

Expected: FAIL wegen fehlendem Modul.

- [ ] **Step 3: Run-Datentyp und Validierung implementieren**

```python
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from showdown_bot.eval.decision_capture import TRACE_SCHEMA_VERSION

class DecisionDiffError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedTraceRun:
    config_hash: str
    schedule_hash: str
    rows_by_battle: dict[str, tuple[dict, ...]]


def _trace_line(row: dict) -> bytes:
    return (json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def validate_trace_run(result_rows: list[dict], trace_rows: list[dict]) -> ValidatedTraceRun:
    by_result = {row["battle_id"]: row for row in result_rows}
    if len(by_result) != len(result_rows):
        raise DecisionDiffError("duplicate result battle_id")
    grouped = {}
    for row in trace_rows:
        if row["trace_schema_version"] != TRACE_SCHEMA_VERSION:
            raise DecisionDiffError("unknown trace schema version")
        battle_id = row["battle_id"]
        if battle_id not in by_result:
            raise DecisionDiffError(f"trace battle absent from results: {battle_id}")
        result = by_result[battle_id]
        for field in ("seed_index", "config_hash", "schedule_hash", "format_id", "git_sha"):
            if row[field] != result[field]:
                raise DecisionDiffError(f"{battle_id}: {field} mismatch")
        grouped.setdefault(battle_id, []).append(row)
    for battle_id, result in by_result.items():
        expected_count = result.get("decision_trace_count")
        expected_sha = result.get("decision_trace_sha256")
        if expected_count is None or expected_sha is None:
            raise DecisionDiffError(f"{battle_id}: missing decision trace binding")
        rows = sorted(grouped.get(battle_id, []), key=lambda row: row["decision_index"])
        indices = [row["decision_index"] for row in rows]
        if indices != list(range(len(rows))):
            raise DecisionDiffError(f"{battle_id}: non-contiguous or duplicate decision key")
        if len(rows) != expected_count:
            raise DecisionDiffError(f"{battle_id}: count mismatch")
        actual_sha = hashlib.sha256(b"".join(_trace_line(row) for row in rows)).hexdigest()
        if actual_sha != expected_sha:
            raise DecisionDiffError(f"{battle_id}: sha mismatch")
        grouped[battle_id] = tuple(rows)
    config_hashes = {row["config_hash"] for row in result_rows}
    schedule_hashes = {row["schedule_hash"] for row in result_rows}
    if len(config_hashes) != 1 or len(schedule_hashes) != 1:
        raise DecisionDiffError("run provenance is not constant")
    return ValidatedTraceRun(
        config_hash=next(iter(config_hashes)), schedule_hash=next(iter(schedule_hashes)),
        rows_by_battle={key: grouped[key] for key in sorted(grouped)},
    )
```

- [ ] **Step 4: Tests grün ausführen**

Run:

```powershell
python -m pytest tests/test_decision_diff.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add showdown_bot/src/showdown_bot/eval/decision_diff.py showdown_bot/tests/test_decision_diff.py
git commit -m "feat(eval): validate decision sidecars against result evidence"
```

---

### Task 6: Entscheidungen alignen und Divergenzen klassifizieren

**Files:**

- Modify: `showdown_bot/src/showdown_bot/eval/decision_diff.py`
- Modify: `showdown_bot/tests/test_decision_diff.py`

- [ ] **Step 1: Failing Klassifikationsmatrix schreiben**

Parametrisierte Tests müssen die feste Priorität beweisen:

```python
def action(kind, *, move_id=None, target=None, protect=False, switch_target=None, tera=False):
    if kind == "move":
        slot0 = {
            "kind": "move", "move_index": 1, "move_id": move_id,
            "target": target, "tera": tera, "is_protect": protect,
        }
    elif kind == "switch":
        slot0 = {"kind": "switch", "switch_target": switch_target}
    else:
        slot0 = {"kind": kind}
    return {"kind": "joint", "slots": [slot0, {"kind": "pass"}]}


@pytest.mark.parametrize(("baseline", "candidate", "expected"), [
    (action("move", move_id="fakeout", target=1), action("move", move_id="fakeout", target=2), "ATTACK_TARGET"),
    (action("move", move_id="fakeout", target=1), action("move", move_id="flareblitz", target=1), "ATTACK_MOVE"),
    (action("move", move_id="protect", protect=True), action("move", move_id="fakeout", target=1), "PROTECT"),
    (action("move", move_id="fakeout", target=1), action("switch", switch_target="rillaboom"), "SWITCH"),
    (action("move", move_id="fakeout", target=1), action("move", move_id="fakeout", target=1, tera=True), "TERA"),
])
def test_classify_action_diff(baseline, candidate, expected):
    assert classify_action_diff(baseline, candidate).primary == expected
```

Zusätzlich: `FALLBACK` schlägt alle anderen Klassen; gleiche Aktion plus anderer Rang wird Agreement
mit `score_rank_changed`; erste Aktionsdivergenz; spätere State-Divergenz; unterschiedlich lange
Suffixe nach Divergenz; fehlender Cross-Run-Key vor jeder Divergenz ist Fehler.

- [ ] **Step 2: Tests rot ausführen**

Run:

```powershell
python -m pytest tests/test_decision_diff.py -q
```

Expected: FAIL wegen fehlender Klassifikation/Alignment-API.

- [ ] **Step 3: Datentypen und Klassifikation implementieren**

```python
@dataclass(frozen=True)
class ActionDiff:
    primary: str
    markers: tuple[str, ...]


@dataclass(frozen=True)
class BattleDecisionDiff:
    battle_id: str
    comparable: int
    agreements: int
    direct_divergences: tuple[dict, ...]
    first_divergence: dict | None
    state_divergence_index: int | None
    baseline_suffix_count: int
    candidate_suffix_count: int


def classify_action_diff(baseline: dict, candidate: dict,
                         *, baseline_stage: str | None = None,
                         candidate_stage: str | None = None) -> ActionDiff:
    markers = []
    if baseline_stage != candidate_stage and (
        "fallback" in (baseline_stage or "") or "fallback" in (candidate_stage or "")
        or "default" in (baseline_stage or "") or "default" in (candidate_stage or "")
    ):
        return ActionDiff("FALLBACK", ("selection_stage_changed",))
    bslots = baseline.get("slots", [])
    cslots = candidate.get("slots", [])
    for marker, predicate in (
        ("tera_changed", lambda b, c: b.get("tera") != c.get("tera")),
        ("switch_changed", lambda b, c: b.get("switch_target") != c.get("switch_target") or b.get("kind") != c.get("kind")),
        ("protect_changed", lambda b, c: b.get("is_protect") != c.get("is_protect")),
        ("move_changed", lambda b, c: b.get("move_id") != c.get("move_id")),
        ("target_changed", lambda b, c: b.get("target") != c.get("target")),
    ):
        if any(predicate(b, c) for b, c in zip(bslots, cslots)):
            markers.append(marker)
    for marker, primary in (
        ("tera_changed", "TERA"),
        ("switch_changed", "SWITCH"),
        ("protect_changed", "PROTECT"),
        ("move_changed", "ATTACK_MOVE"),
        ("target_changed", "ATTACK_TARGET"),
    ):
        if marker in markers:
            return ActionDiff(primary, tuple(markers))
    return ActionDiff("OTHER_ACTION", tuple(markers))
```

- [ ] **Step 4: Alignment bis State-Divergenz implementieren**

`compare_battle_decisions(pair, baseline_rows, candidate_rows)` iteriert ab Index 0. Verbindliche
Reihenfolge pro Index:

```python
if one_side_missing:
    if first_direct_divergence is None:
        raise DecisionDiffError(f"{battle_id}: decision key missing before divergence")
    return suffix_result(...)
if baseline["observable_state_hash"] != candidate["observable_state_hash"]:
    state_divergence_index = index
    return suffix_result(...)
comparable += 1
if baseline["normalized_action"] == candidate["normalized_action"]:
    markers = ("score_rank_changed",) if baseline.get("chosen_rank") != candidate.get("chosen_rank") else ()
    agreements += 1
else:
    diff = classify_action_diff(...)
    direct = {"decision_index": index, "turn_number": baseline["turn_number"],
              "decision_phase": baseline["decision_phase"], "primary": diff.primary,
              "markers": list(diff.markers)}
    divergences.append(direct)
    first_direct_divergence = first_direct_divergence or direct
```

Wenn ein Run nach einer direkten Aktionsdivergenz endet, ist der verbleibende Suffix zulässig. Wenn
beide Runs ohne State-Divergenz und ohne fehlenden Schlüssel enden, bleibt `state_divergence_index`
`None`.

- [ ] **Step 5: Klassifikations-/Alignment-Tests grün ausführen**

Run:

```powershell
python -m pytest tests/test_decision_diff.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add showdown_bot/src/showdown_bot/eval/decision_diff.py showdown_bot/tests/test_decision_diff.py
git commit -m "feat(eval): classify first policy and state divergences"
```

---

### Task 7: Outcomes, Matchup-Buckets, Regressionen und Repeat-Identität aggregieren

**Files:**

- Modify: `showdown_bot/src/showdown_bot/eval/decision_diff.py`
- Modify: `showdown_bot/tests/test_decision_diff.py`

- [ ] **Step 1: Failing Outcome-/Bucket-/Stability-Tests schreiben**

```python
@pytest.mark.parametrize(("baseline", "candidate", "expected"), [
    ("hero", "hero", "BOTH_WIN"),
    ("villain", "villain", "BOTH_LOSS"),
    ("villain", "hero", "CANDIDATE_FLIP_TO_WIN"),
    ("hero", "villain", "CANDIDATE_REGRESSION_TO_LOSS"),
    ("tie", "hero", "NON_BINARY"),
])
def test_outcome_category(baseline, candidate, expected):
    assert outcome_category({"winner": baseline}, {"winner": candidate}) == expected


def test_bucket_under_ten_is_underpowered():
    records = [{
        "baseline_row": {"winner": "villain", "opp_policy": "max_damage",
                         "opp_team_hash": "opp-hash", "hero_team_hash": "hero-hash"},
        "candidate_row": {"winner": "hero", "opp_policy": "max_damage",
                          "opp_team_hash": "opp-hash", "hero_team_hash": "hero-hash"},
        "first_divergence": {"primary": "ATTACK_TARGET"},
        "lead": "Incineroar+Rillaboom",
    } for _ in range(9)]
    bucket = build_matchup_buckets(records, archetype_by_hash={
        "opp-hash": "rain", "hero-hash": "balance",
    })[0]
    assert bucket["n"] == 9
    assert bucket["underpowered"] is True
    assert 0.0 <= bucket["candidate_wilson_lo"] <= bucket["candidate_wilson_hi"] <= 1.0


def test_repeat_identity_ignores_only_volatile_latency(bound_trace_fixture):
    _results, trace_rows = bound_trace_fixture
    repeat = copy.deepcopy(trace_rows)
    repeat[0]["decision_latency_ms"] += 99.0
    assert compare_repeat_identity(trace_rows, repeat)["identical"] is True
    repeat[0]["normalized_action"]["slots"][0]["target"] = 2
    assert compare_repeat_identity(trace_rows, repeat)["identical"] is False
```

Zusätzlich: McNemar-Orientierung Baseline=A/Candidate=B, Candidate-only-Fallback, Losing-cell-
Regression, Lead aus erster regulärer `state_summary`, unbekannter Archetyp=`unclassified`.

- [ ] **Step 2: Tests rot ausführen**

Run:

```powershell
python -m pytest tests/test_decision_diff.py -q
```

Expected: FAIL wegen fehlender Aggregationsfunktionen.

- [ ] **Step 3: Outcome und Statistik mit vorhandenen Primitives implementieren**

```python
from showdown_bot.eval.stats import exact_binom_two_sided_p, mcnemar_counts, wilson_interval


def outcome_category(baseline_row: dict, candidate_row: dict) -> str:
    b, c = baseline_row["winner"], candidate_row["winner"]
    if b not in ("hero", "villain") or c not in ("hero", "villain"):
        return "NON_BINARY"
    if b == "hero" and c == "hero":
        return "BOTH_WIN"
    if b == "villain" and c == "villain":
        return "BOTH_LOSS"
    return "CANDIDATE_FLIP_TO_WIN" if c == "hero" else "CANDIDATE_REGRESSION_TO_LOSS"


def paired_strength_summary(pairs) -> dict:
    counts = mcnemar_counts((pair.hero_win_a, pair.hero_win_b) for pair in pairs)
    return {
        "orientation": "A=baseline,B=candidate",
        "n11": counts.n11, "n00": counts.n00,
        "n10_baseline_only_win": counts.n10,
        "n01_candidate_only_win": counts.n01,
        "n_discordant": counts.n_discordant,
        "candidate_minus_baseline_winrate": -counts.delta,
        "exact_two_sided_p": exact_binom_two_sided_p(counts.n01, counts.n_discordant),
    }
```

- [ ] **Step 4: Buckets, Regressionen und Leads implementieren**

Panelteam-Mapping über `team_hash` und `team_path`; nicht gefundene Hero-Teams erhalten
`unclassified`. Lead aus der ersten `regular_turn`-Row:

```python
def _lead(row: dict, side: str) -> str:
    slots = row.get("state_summary", {}).get("sides", {}).get(side, {})
    species = [slots.get(slot, {}).get("species") for slot in ("a", "b")]
    return "+".join(species) if all(species) else "unavailable"


def build_matchup_buckets(records: list[dict], *, archetype_by_hash: dict[str, str]) -> list[dict]:
    grouped = {}
    for record in records:
        baseline = record["baseline_row"]
        candidate = record["candidate_row"]
        key = (
            archetype_by_hash.get(baseline.get("hero_team_hash"), "unclassified"),
            archetype_by_hash.get(baseline.get("opp_team_hash"), "unclassified"),
            baseline["opp_policy"], record.get("lead", "unavailable"),
        )
        grouped.setdefault(key, []).append(record)
    buckets = []
    for (hero_arch, opp_arch, policy, lead), rows in sorted(grouped.items()):
        n = len(rows)
        bw = sum(row["baseline_row"]["winner"] == "hero" for row in rows)
        cw = sum(row["candidate_row"]["winner"] == "hero" for row in rows)
        blo, bhi = wilson_interval(bw, n)
        clo, chi = wilson_interval(cw, n)
        buckets.append({
            "hero_archetype": hero_arch, "opponent_archetype": opp_arch,
            "opponent_policy": policy, "lead": lead, "n": n,
            "baseline_wins": bw, "candidate_wins": cw,
            "baseline_win_rate": bw / n, "candidate_win_rate": cw / n,
            "baseline_wilson_lo": blo, "baseline_wilson_hi": bhi,
            "candidate_wilson_lo": clo, "candidate_wilson_hi": chi,
            "positive_flips": sum(outcome_category(row["baseline_row"], row["candidate_row"])
                                  == "CANDIDATE_FLIP_TO_WIN" for row in rows),
            "negative_flips": sum(outcome_category(row["baseline_row"], row["candidate_row"])
                                  == "CANDIDATE_REGRESSION_TO_LOSS" for row in rows),
            "underpowered": n < 10,
        })
    return buckets
```

Jeder Bucket enthält `n`, Baseline-/Candidate-Wins und -Winraten, beide Wilson-Intervalle,
positive/negative Flips, `underpowered = n < 10` und sortierte Divergenzklassen. Regressionen:

```python
regressions = {
    "candidate_regression_to_loss": negative_flips,
    "candidate_only_fallbacks": candidate_only_fallbacks,
    "candidate_only_timeouts": candidate_only_timeouts,
    "candidate_only_crashes": candidate_only_crashes,
    "latency_budget_regressions": latency_regressions,
    "winning_to_losing_cells": losing_cell_flips,
}
```

Keine dieser Diagnosen erzeugt eigenständig GO/NO-GO.

Die öffentliche Orchestrierung wird in derselben Task definiert:

```python
def analyze_decision_diff(baseline_bundle, candidate_bundle, *, panel,
                          baseline_trace: ValidatedTraceRun | None,
                          candidate_trace: ValidatedTraceRun | None,
                          outcome_only: bool,
                          baseline_repeat: list[dict] | None = None,
                          candidate_repeat: list[dict] | None = None) -> dict:
    pairs = pair_runs(baseline_bundle.rows, candidate_bundle.rows,
                      expected_rows=baseline_bundle.schedule_row_count)
    comparisons = []
    if not outcome_only:
        if baseline_trace is None or candidate_trace is None:
            raise DecisionDiffError("full mode requires validated traces")
        for pair in pairs:
            comparisons.append(compare_battle_decisions(
                pair,
                baseline_trace.rows_by_battle[pair.battle_id],
                candidate_trace.rows_by_battle[pair.battle_id],
            ))
    archetype_by_hash = {
        team.team_hash: team.archetype
        for team in (*panel.dev_teams, *panel.heldout_teams)
    }
    records = build_battle_records(pairs, comparisons, baseline_trace)
    return {
        "capability_mode": "outcome_only" if outcome_only else "full",
        "provenance": {"baseline": baseline_bundle.manifest,
                       "candidate": candidate_bundle.manifest},
        "integrity": integrity_summary(pairs, comparisons),
        "strength": paired_strength_summary(pairs),
        "outcomes": outcome_counts(records),
        "decision_differences": None if outcome_only else decision_summary(comparisons),
        "matchup_buckets": build_matchup_buckets(records, archetype_by_hash=archetype_by_hash),
        "stability": build_stability_block(
            baseline_trace, candidate_trace, baseline_repeat, candidate_repeat),
        "regressions": build_regressions(records, baseline_bundle, candidate_bundle),
        "top_positive_associations": rank_associations(records, positive=True),
        "top_negative_associations": rank_associations(records, positive=False),
    }
```

Die verwendeten Helper werden mit diesen Verträgen implementiert:

```python
def build_battle_records(pairs, comparisons, baseline_trace) -> list[dict]:
    by_battle = {item.battle_id: item for item in comparisons}
    records = []
    for pair in pairs:
        diff = by_battle.get(pair.battle_id)
        lead = "unavailable"
        if baseline_trace is not None:
            regular = next((row for row in baseline_trace.rows_by_battle[pair.battle_id]
                            if row["decision_phase"] == "regular_turn"), None)
            if regular is not None:
                lead = _lead(regular, regular["our_side"])
        records.append({
            "battle_id": pair.battle_id, "baseline_row": pair.row_a,
            "candidate_row": pair.row_b, "first_divergence": None if diff is None else diff.first_divergence,
            "decision_diff": diff, "lead": lead,
            "outcome_category": outcome_category(pair.row_a, pair.row_b),
        })
    return records


def integrity_summary(pairs, comparisons) -> dict:
    return {
        "paired_battles": len(pairs),
        "battles_with_decision_comparison": len(comparisons),
        "directly_comparable_decisions": sum(item.comparable for item in comparisons),
        "direct_agreements": sum(item.agreements for item in comparisons),
        "direct_divergences": sum(len(item.direct_divergences) for item in comparisons),
        "battles_with_state_divergence": sum(item.state_divergence_index is not None
                                             for item in comparisons),
    }


def outcome_counts(records) -> dict:
    names = ("BOTH_WIN", "BOTH_LOSS", "CANDIDATE_FLIP_TO_WIN",
             "CANDIDATE_REGRESSION_TO_LOSS", "NON_BINARY")
    return {name: sum(row["outcome_category"] == name for row in records) for name in names}


def decision_summary(comparisons) -> dict:
    classes = {}
    for comparison in comparisons:
        for item in comparison.direct_divergences:
            classes[item["primary"]] = classes.get(item["primary"], 0) + 1
    return {
        "comparable": sum(item.comparable for item in comparisons),
        "agreements": sum(item.agreements for item in comparisons),
        "divergences": sum(len(item.direct_divergences) for item in comparisons),
        "by_primary_class": dict(sorted(classes.items())),
    }


def build_stability_block(baseline_trace, candidate_trace, baseline_repeat, candidate_repeat) -> dict:
    return {
        "baseline": {"status": "not_provided"} if baseline_repeat is None else
                    compare_repeat_identity(flatten(baseline_trace), baseline_repeat),
        "candidate": {"status": "not_provided"} if candidate_repeat is None else
                     compare_repeat_identity(flatten(candidate_trace), candidate_repeat),
    }


def build_regressions(records, baseline_bundle, candidate_bundle) -> dict:
    return {
        "candidate_regression_to_loss": sum(
            row["outcome_category"] == "CANDIDATE_REGRESSION_TO_LOSS" for row in records),
        "candidate_only_fallbacks": sum(
            row["decision_diff"] is not None and
            any(item["primary"] == "FALLBACK" for item in row["decision_diff"].direct_divergences)
            for row in records),
        "candidate_only_timeouts": sum(
            bool(row["candidate_row"].get("timeouts")) and not bool(row["baseline_row"].get("timeouts"))
            for row in records),
        "candidate_only_crashes": sum(
            row["candidate_row"].get("crashes", 0) > row["baseline_row"].get("crashes", 0)
            for row in records),
        "latency_budget_regressions": sum(
            row["candidate_row"]["decision_latency_p95_ms"] > candidate_bundle.latency_budget_ms
            and row["baseline_row"]["decision_latency_p95_ms"] <= baseline_bundle.latency_budget_ms
            for row in records),
    }


def rank_associations(records, *, positive: bool) -> list[dict]:
    wanted = "CANDIDATE_FLIP_TO_WIN" if positive else "CANDIDATE_REGRESSION_TO_LOSS"
    counts = {}
    for row in records:
        first = row["first_divergence"]
        if row["outcome_category"] == wanted and first is not None:
            key = first["primary"]
            counts[key] = counts.get(key, 0) + 1
    return [
        {"primary": primary, "associated_battles": count}
        for primary, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
```

```python
def flatten(run: ValidatedTraceRun | None) -> list[dict]:
    if run is None:
        raise DecisionDiffError("repeat comparison requires the original validated trace run")
    return [
        row for battle_id in sorted(run.rows_by_battle)
        for row in run.rows_by_battle[battle_id]
    ]
```

- [ ] **Step 5: Repeat-Normalisierung implementieren**

```python
VOLATILE_TRACE_FIELDS = frozenset({"decision_latency_ms"})


def _identity_row(row: dict) -> dict:
    return {key: value for key, value in row.items() if key not in VOLATILE_TRACE_FIELDS}


def compare_repeat_identity(original: list[dict], repeat: list[dict]) -> dict:
    for field in ("trace_schema_version", "config_hash", "schedule_hash", "git_sha"):
        left_values = {row[field] for row in original}
        right_values = {row[field] for row in repeat}
        if len(left_values) != 1 or left_values != right_values:
            raise DecisionDiffError(f"repeat {field} mismatch")
    left = [_identity_row(row) for row in sorted(original, key=lambda r: (r["seed_index"], r["decision_index"]))]
    right = [_identity_row(row) for row in sorted(repeat, key=lambda r: (r["seed_index"], r["decision_index"]))]
    diffs = []
    for index in range(max(len(left), len(right))):
        a = left[index] if index < len(left) else None
        b = right[index] if index < len(right) else None
        if a != b:
            diffs.append({"index": index, "baseline": a, "repeat": b})
    return {"identical": not diffs, "n_compared": min(len(left), len(right)), "diffs": diffs}
```

Vor dem Vergleich gleiche `config_hash`, `schedule_hash`, `git_sha` und Trace-Schema-Version
verlangen.

- [ ] **Step 6: Tests grün ausführen**

Run:

```powershell
python -m pytest tests/test_decision_diff.py tests/test_eval_stats.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add showdown_bot/src/showdown_bot/eval/decision_diff.py showdown_bot/tests/test_decision_diff.py
git commit -m "feat(eval): aggregate paired decision effects and stability"
```

---

### Task 8: Deterministischen JSON-/Markdown-Report bauen

**Files:**

- Create: `showdown_bot/src/showdown_bot/eval/decision_diff_report.py`
- Create: `showdown_bot/tests/test_decision_diff_report.py`

- [ ] **Step 1: Failing Report-Strukturtests schreiben**

```python
@pytest.fixture
def analysis_fixture():
    return {
        "capability_mode": "full",
        "provenance": {"baseline": {"config_hash": "a"},
                       "candidate": {"config_hash": "b"}},
        "integrity": {"paired_battles": 2, "directly_comparable_decisions": 3},
        "strength": {"n_discordant": 2, "exact_two_sided_p": 1.0},
        "outcomes": {"BOTH_WIN": 0, "BOTH_LOSS": 0,
                     "CANDIDATE_FLIP_TO_WIN": 1,
                     "CANDIDATE_REGRESSION_TO_LOSS": 1, "NON_BINARY": 0},
        "decision_differences": {"by_primary_class": {"ATTACK_TARGET": 2}},
        "matchup_buckets": [
            {"hero_archetype": "balance", "opponent_archetype": "rain",
             "opponent_policy": "max_damage", "lead": "A+B", "n": 2,
             "candidate_win_rate": 0.5, "underpowered": True},
        ],
        "stability": {"baseline": {"status": "not_provided"},
                      "candidate": {"status": "not_provided"}},
        "regressions": {"candidate_regression_to_loss": 1},
        "top_positive_associations": [{"primary": "ATTACK_TARGET", "associated_battles": 1}],
        "top_negative_associations": [{"primary": "ATTACK_TARGET", "associated_battles": 1}],
    }


def reversed_fixture(source):
    copy_ = copy.deepcopy(source)
    copy_["matchup_buckets"] = list(reversed(copy_["matchup_buckets"]))
    return copy_


def test_report_is_verdict_first_but_not_a_new_gate(analysis_fixture):
    obj = build_report_object(analysis_fixture)
    md = render_markdown(obj)
    assert obj["report_schema_version"] == "decision-diff-report-v1"
    assert obj["strength"]["source"] == "existing paired statistics"
    assert "new_strength_verdict" not in json.dumps(obj)
    assert md.startswith("# Candidate-vs-Baseline Differential Report\n")
    assert "## Existing paired strength evidence" in md
    assert "## First direct divergences" in md
    assert "## Regressions" in md
    assert "association, not causal proof" in md


def test_report_is_deterministic(analysis_fixture):
    first = render_markdown(build_report_object(analysis_fixture))
    second = render_markdown(build_report_object(reversed_fixture(analysis_fixture)))
    assert first == second
```

Nicht endliche Zahlen müssen `DecisionDiffError` auslösen.

- [ ] **Step 2: Tests rot ausführen**

Run:

```powershell
python -m pytest tests/test_decision_diff_report.py -q
```

Expected: FAIL wegen fehlendem Renderer.

- [ ] **Step 3: Reportobjekt mit fester Struktur implementieren**

```python
REPORT_SCHEMA_VERSION = "decision-diff-report-v1"


def _bucket_sort_key(bucket: dict) -> tuple:
    return (
        bucket["hero_archetype"], bucket["opponent_archetype"],
        bucket["opponent_policy"], bucket["lead"],
    )


def validate_finite_numbers(value, path: str = "root") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise DecisionDiffError(f"non-finite report number at {path}")
    if isinstance(value, dict):
        for key, child in value.items():
            validate_finite_numbers(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            validate_finite_numbers(child, f"{path}[{index}]")


def build_report_object(analysis: dict) -> dict:
    obj = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "capability_mode": analysis["capability_mode"],
        "provenance": analysis["provenance"],
        "integrity": analysis["integrity"],
        "strength": {"source": "existing paired statistics", **analysis["strength"]},
        "outcomes": analysis["outcomes"],
        "decision_differences": analysis.get("decision_differences"),
        "matchup_buckets": sorted(analysis.get("matchup_buckets", []), key=_bucket_sort_key),
        "stability": analysis.get("stability", {"status": "not_provided"}),
        "regressions": analysis.get("regressions", {}),
        "top_positive_associations": analysis.get("top_positive_associations", []),
        "top_negative_associations": analysis.get("top_negative_associations", []),
        "limitations": [
            "first divergence is an association, not causal proof",
            "strength acceptance remains in the existing paired gate",
            "counterfactual regret is outside this report",
        ],
    }
    validate_finite_numbers(obj)
    return obj
```

- [ ] **Step 4: Markdown in fester Reihenfolge implementieren**

`render_markdown` rendert Tabellenzeilen nach festen Tupeln und Floats einheitlich mit sechs
Nachkommastellen:

```python
def render_markdown(obj: dict) -> str:
    lines = [
        "# Candidate-vs-Baseline Differential Report", "",
        f"- capability mode: `{obj['capability_mode']}`",
        f"- paired battles: {obj['integrity']['paired_battles']}",
        "- interpretation: diagnostic evidence; strength gate unchanged", "",
        "## Inputs and provenance", "",
        "```json", json.dumps(obj["provenance"], sort_keys=True, indent=2), "```", "",
        "## Integrity and coverage", "",
    ]
    for key, value in sorted(obj["integrity"].items()):
        lines.append(f"- {key}: {value}")
    lines += ["", "## Existing paired strength evidence", ""]
    for key, value in sorted(obj["strength"].items()):
        lines.append(f"- {key}: {_fmt(value)}")
    lines += ["", "## Outcome flips", ""]
    for key, value in sorted(obj["outcomes"].items()):
        lines.append(f"- {key}: {value}")
    lines += ["", "## First direct divergences", ""]
    differences = obj.get("decision_differences")
    if differences is None:
        lines.append("Unavailable in outcome-only mode.")
    else:
        for key, value in sorted(differences.items()):
            lines.append(f"- {key}: {_fmt(value)}")
    lines += ["", "## Matchup buckets", "",
              "| hero archetype | opponent archetype | policy | lead | n | candidate win rate | underpowered |",
              "| --- | --- | --- | --- | ---: | ---: | --- |"]
    for bucket in obj["matchup_buckets"]:
        lines.append(
            f"| {bucket['hero_archetype']} | {bucket['opponent_archetype']} | "
            f"{bucket['opponent_policy']} | {bucket['lead']} | {bucket['n']} | "
            f"{_fmt(bucket['candidate_win_rate'])} | {bucket['underpowered']} |"
        )
    lines += ["", "## Stability", "", "```json",
              json.dumps(obj["stability"], sort_keys=True, indent=2), "```", "",
              "## Regressions", ""]
    for key, value in sorted(obj["regressions"].items()):
        lines.append(f"- {key}: {_fmt(value)}")
    for title, key in (
        ("Positive flip associations", "top_positive_associations"),
        ("Negative flip associations", "top_negative_associations"),
    ):
        lines += ["", f"## {title}", ""]
        for item in obj[key]:
            lines.append(f"- {item['primary']}: {item['associated_battles']}")
    lines += ["", "## Limitations", ""]
    lines.extend(f"- {item}" for item in obj["limitations"])
    return "\n".join(lines) + "\n"


def _fmt(value) -> str:
    return f"{value:.6f}" if isinstance(value, float) else str(value)
```

- [ ] **Step 5: Reporttests grün ausführen**

Run:

```powershell
python -m pytest tests/test_decision_diff_report.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add showdown_bot/src/showdown_bot/eval/decision_diff_report.py showdown_bot/tests/test_decision_diff_report.py
git commit -m "feat(eval): render deterministic decision differential reports"
```

---

### Task 9: `decision-diff` CLI und expliziten Outcome-only-Modus ergänzen

**Files:**

- Modify: `showdown_bot/src/showdown_bot/cli.py`
- Modify: `showdown_bot/tests/test_cli_decision_diff.py`

- [ ] **Step 1: Failing CLI-Matrix schreiben**

Tests für:

```python
def _args(tmp_path, *, outcome_only=False):
    return argparse.Namespace(
        baseline_run="baseline.jsonl", baseline_seedlog="baseline-seeds.jsonl",
        baseline_trace="", baseline_repeat_trace="", baseline_room_raw="",
        candidate_run="candidate.jsonl", candidate_seedlog="candidate-seeds.jsonl",
        candidate_trace="", candidate_repeat_trace="", candidate_room_raw="",
        schedule="schedule.yaml", panel="panel.yaml", teams_root=".",
        out=str(tmp_path), outcome_only=outcome_only,
    )


def _minimal_analysis(mode):
    return {
        "capability_mode": mode, "provenance": {},
        "integrity": {"paired_battles": 1}, "strength": {}, "outcomes": {},
        "decision_differences": None if mode == "outcome_only" else {},
        "matchup_buckets": [], "stability": {}, "regressions": {},
        "top_positive_associations": [], "top_negative_associations": [],
    }


def test_full_mode_requires_both_traces(tmp_path):
    with pytest.raises(SystemExit, match="full mode requires --baseline-trace and --candidate-trace"):
        run_decision_diff(_args(tmp_path))


def test_outcome_only_refuses_trace_claims(monkeypatch, tmp_path):
    monkeypatch.setattr(report.RunBundle, "load", classmethod(
        lambda cls, *a, **kw: types.SimpleNamespace(rows=[])))
    monkeypatch.setattr(panel, "load_panel", lambda *a, **kw: object())
    monkeypatch.setattr(decision_diff, "analyze_decision_diff",
                        lambda *a, **kw: _minimal_analysis("outcome_only"))
    run_decision_diff(_args(tmp_path, outcome_only=True))
    obj = json.loads((tmp_path / "report.json").read_text())
    assert obj["capability_mode"] == "outcome_only"
    assert obj["decision_differences"] is None


def test_full_mode_writes_deterministic_outputs(monkeypatch, tmp_path):
    args = _args(tmp_path)
    args.baseline_trace = "baseline-trace.jsonl"
    args.candidate_trace = "candidate-trace.jsonl"
    monkeypatch.setattr(report.RunBundle, "load", classmethod(
        lambda cls, *a, **kw: types.SimpleNamespace(rows=[])))
    monkeypatch.setattr(panel, "load_panel", lambda *a, **kw: object())
    monkeypatch.setattr(decision_capture, "load_decision_trace", lambda path: [])
    monkeypatch.setattr(decision_diff, "validate_trace_run", lambda rows, trace: object())
    monkeypatch.setattr(decision_diff, "analyze_decision_diff",
                        lambda *a, **kw: _minimal_analysis("full"))
    run_decision_diff(args)
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "report.json").exists()
```

- [ ] **Step 2: Tests rot ausführen**

Run:

```powershell
python -m pytest tests/test_cli_decision_diff.py -q
```

Expected: FAIL wegen fehlendem Command/Handler.

- [ ] **Step 3: Eindeutige Baseline-/Candidate-Argumente ergänzen**

Command-Choice um `decision-diff` erweitern. Neue Argumente:

```python
--baseline-run
--baseline-seedlog
--baseline-trace
--baseline-repeat-trace
--baseline-room-raw
--candidate-run
--candidate-seedlog
--candidate-trace
--candidate-repeat-trace
--candidate-room-raw
--outcome-only
```

`--schedule`, `--panel`, `--teams-root` und `--out` wiederverwenden. Keine `run-a/run-b`-Semantik:
Die neue CLI benennt die Orientierung ausdrücklich.

- [ ] **Step 4: Handler implementieren**

```python
def _run_decision_diff_impl(args) -> None:
    from showdown_bot.eval.decision_capture import load_decision_trace
    from showdown_bot.eval.decision_diff import analyze_decision_diff, validate_trace_run
    from showdown_bot.eval.decision_diff_report import build_report_object, render_markdown
    from showdown_bot.eval.panel import load_panel
    from showdown_bot.eval.report import RunBundle

    required = ("baseline_run", "baseline_seedlog", "candidate_run", "candidate_seedlog",
                "schedule", "panel", "out")
    missing = [name for name in required if not getattr(args, name, "")]
    if missing:
        raise SystemExit(f"decision-diff missing required inputs: {missing}")
    if not args.outcome_only and (not args.baseline_trace or not args.candidate_trace):
        raise SystemExit("full mode requires --baseline-trace and --candidate-trace")

    baseline = RunBundle.load(
        args.baseline_run, args.baseline_seedlog, args.schedule, args.panel,
        teams_root=args.teams_root, room_raw_dir=args.baseline_room_raw or None,
    )
    candidate = RunBundle.load(
        args.candidate_run, args.candidate_seedlog, args.schedule, args.panel,
        teams_root=args.teams_root, room_raw_dir=args.candidate_room_raw or None,
    )
    baseline_trace = candidate_trace = None
    if not args.outcome_only:
        baseline_trace = validate_trace_run(baseline.rows, load_decision_trace(args.baseline_trace))
        candidate_trace = validate_trace_run(candidate.rows, load_decision_trace(args.candidate_trace))
    panel = load_panel(args.panel, teams_root=args.teams_root)
    analysis = analyze_decision_diff(
        baseline, candidate, panel=panel,
        baseline_trace=baseline_trace, candidate_trace=candidate_trace,
        outcome_only=args.outcome_only,
        baseline_repeat=load_decision_trace(args.baseline_repeat_trace) if args.baseline_repeat_trace else None,
        candidate_repeat=load_decision_trace(args.candidate_repeat_trace) if args.candidate_repeat_trace else None,
    )
    obj = build_report_object(analysis)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(render_markdown(obj), encoding="utf-8", newline="\n")
    (out / "report.json").write_text(
        json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )


def run_decision_diff(args) -> None:
    from showdown_bot.eval.decision_capture import DecisionCaptureError
    from showdown_bot.eval.decision_diff import DecisionDiffError
    from showdown_bot.eval.pairing import PairingError
    from showdown_bot.eval.report import LogIntegrityError, ReportInputError

    try:
        _run_decision_diff_impl(args)
    except (PairingError, ReportInputError, LogIntegrityError,
            DecisionCaptureError, DecisionDiffError) as exc:
        print(f"decision-diff: input/integrity failure: {exc}")
        raise SystemExit(1) from exc
```

Damit entsteht bei Integritätsfehlern kein Teilreport.

- [ ] **Step 5: CLI- und Offline-Integrationstests grün ausführen**

Run:

```powershell
python -m pytest tests/test_cli_decision_diff.py tests/test_decision_diff.py tests/test_decision_diff_report.py tests/test_cli_eval_report.py -q
```

Expected: PASS; bestehendes `eval-report` bleibt unverändert.

- [ ] **Step 6: Commit**

```powershell
git add showdown_bot/src/showdown_bot/cli.py showdown_bot/tests/test_cli_decision_diff.py
git commit -m "feat(eval): add candidate-vs-baseline differential CLI"
```

---

### Task 10: Gesamtverifikation und Dokumentation

**Files:**

- Modify: `README.md`
- Create: `reports/2026-07-11-candidate-vs-baseline-diff-smoke.md`

- [ ] **Step 1: README-Nutzung dokumentieren**

Unter Eval-Harness ein kompaktes Beispiel ergänzen:

```powershell
python -m showdown_bot.cli gauntlet --schedule ../config/eval/schedules/t4_smoke_v001.yaml `
  --result-out /tmp/baseline.jsonl --decision-trace-out /tmp/baseline-trace.jsonl.gz

python -m showdown_bot.cli decision-diff `
  --baseline-run /tmp/baseline.jsonl --baseline-seedlog /tmp/baseline-seeds.jsonl `
  --baseline-trace /tmp/baseline-trace.jsonl.gz `
  --candidate-run /tmp/candidate.jsonl --candidate-seedlog /tmp/candidate-seeds.jsonl `
  --candidate-trace /tmp/candidate-trace.jsonl.gz `
  --schedule ../config/eval/schedules/t4_smoke_v001.yaml `
  --panel ../config/eval/panels/panel_v001.yaml --out /tmp/decision-diff
```

Direkt darunter: „diagnostic only; strength verdict remains `eval-report`; no held-out access is
performed by this command.“

- [ ] **Step 2: Format-, Placeholder- und Diff-Prüfung ausführen**

Run:

```powershell
git diff --check
rg -n "T[B]D|T[O]DO|F[I]XME|P[L]ACEHOLDER" showdown_bot/src/showdown_bot/eval/decision_capture.py showdown_bot/src/showdown_bot/eval/decision_diff.py showdown_bot/src/showdown_bot/eval/decision_diff_report.py README.md
```

Expected: `git diff --check` exit 0; `rg` exit 1 ohne Treffer.

- [ ] **Step 3: Alle betroffenen Tests ausführen**

Run:

```powershell
python -m pytest tests/test_decision_trace.py tests/test_actions_force_phase.py tests/test_reranker_override.py tests/test_decision_capture.py tests/test_decision_diff.py tests/test_decision_diff_report.py tests/test_cli_decision_diff.py tests/test_cli_run_schedule_export.py tests/test_result_jsonl.py tests/test_eval_pairing.py tests/test_eval_stats.py tests/test_cli_eval_report.py -q
```

Expected: PASS, 0 failures.

- [ ] **Step 4: Vollständige Suite ausführen**

Vorher im frischen Klon:

```powershell
npm ci --prefix tools/calc
python -m pytest -q
```

Expected: 0 failures; der bekannte Strict-Xfail darf weiter als xfailed erscheinen.

- [ ] **Step 5: Reinen Fixture-Smoke-Report erzeugen**

Mit den in `test_cli_decision_diff.py` verwendeten kleinen Fixture-Runs die echte CLI in einem
temporären Verzeichnis aufrufen und die resultierenden JSON-/Markdown-Dateien nach
`reports/2026-07-11-candidate-vs-baseline-diff-smoke.md` zusammenfassen. Der Report enthält:

- verwendete Fixture-Dateien und Hashes,
- Full-mode Integrity/Coverage,
- eine positive und eine negative Flip-Kategorie,
- mindestens eine direkte Divergenz und einen späteren State-Suffix,
- den expliziten Hinweis „fixture smoke, not strength evidence“.

Keine Battles starten.

- [ ] **Step 6: Abschlusscommit**

```powershell
git add README.md reports/2026-07-11-candidate-vs-baseline-diff-smoke.md
git commit -m "docs(eval): document decision differential workflow"
```

- [ ] **Step 7: Abschlusszustand prüfen**

Run:

```powershell
git status --short
git log --oneline --decorate -10
```

Expected: leerer Status; die Task-Commits erscheinen in der geplanten Reihenfolge.

---

## Plan-Selbstprüfung

- Spec §3/4, bestehende Pairing-/Result-/DecisionTrace-Bausteine: Tasks 1, 4, 5 und 9.
- Spec §5, sichtbarer Sidecar-Vertrag und Leakage-Schutz: Tasks 2 und 3.
- Spec §6, feste Divergenzklassen und Score-Rang-Marker: Task 6.
- Spec §7/8, Outcomes, McNemar, Buckets und Regressionen: Task 7.
- Spec §9, Wiederholungsidentität mit Ausschluss nur volatiler Latenz: Task 7 und optionale CLI-
  Repeat-Inputs in Task 9.
- Spec §10, deterministische JSON-/Markdown-Ausgabe: Task 8.
- Spec §11/12, Outcome-only und fail-closed Fehlerpfade: Tasks 5 und 9.
- Spec §13/14, Tests und Abnahmekriterien: Tasks 1–10.
- Spec §15/16, keine neue Strength-Logik, kein Held-out und keine Counterfactual-Simulation: im
  Analyzer, Renderer, README und Smoke-Report explizit abgesichert.
- Unterschiedlich lange Suffixe sind erst nach State-Divergenz oder terminaler direkter
  Aktionsdivergenz erlaubt; vorherige Lücken bleiben Fehler.
- Capture-off baut keinen zusätzlichen `DecisionTrace`, erzeugt keine Datei und ändert keine
  Choice-Strings.
- Keine Platzhalter oder offenen Funktionsnamen; alle später verwendeten APIs werden in früheren
  Tasks definiert.
