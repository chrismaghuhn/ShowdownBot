"""I7a-B Task 1: candidate-key v2 and decision-trace v3 (identity/schema layer only).

The non-Mega decision path is migrated to key-v2/trace-v3 bookkeeping, and the
v3 validators are exercised directly against literal/constructed rows. See
``docs/superpowers/specs/2026-07-14-champions-mega-i7-design.md`` Sec.13 for
the authoritative schema.

I7a-B Task 4 adds real Mega-branch trace population tests (T50, plus the
mutual-exclusion smoke) further down in this file -- those DO exercise real
Mega ranking/scoring through ``_choose_best_mega``.
"""
from __future__ import annotations

import copy
import dataclasses
import json

import pytest


@pytest.fixture
def capture_fixture(decision_fixture):
    req, kw = decision_fixture
    return req, copy.deepcopy(kw["state"])

from showdown_bot.battle.actions import JointAction, enumerate_my_actions
from showdown_bot.battle.candidate_identity import (
    ChosenCandidateResolutionError,
    joint_action_key_v2,
    resolve_chosen_candidate,
)
from showdown_bot.battle.decision_trace import CandidateTrace, DecisionTrace
from showdown_bot.battle.evaluate import OutcomeBreakdown
from showdown_bot.eval.decision_capture import (
    DecisionCaptureError,
    SUPPORTED_TRACE_SCHEMA_VERSIONS,
    TRACE_SCHEMA_VERSION,
    TRACE_SCHEMA_VERSION_V1,
    TRACE_SCHEMA_VERSION_V2,
    TRACE_SCHEMA_VERSION_V3,
    normalize_choose,
    validate_trace_row,
)
from showdown_bot.models.actions import SlotAction


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_supported_schema_versions_include_v3():
    assert SUPPORTED_TRACE_SCHEMA_VERSIONS == frozenset({
        TRACE_SCHEMA_VERSION_V1, TRACE_SCHEMA_VERSION_V2, TRACE_SCHEMA_VERSION_V3,
    })
    assert TRACE_SCHEMA_VERSION == TRACE_SCHEMA_VERSION_V3


# ---------------------------------------------------------------------------
# /choose normalization: mega overlay token
# ---------------------------------------------------------------------------

def test_normalize_choose_accepts_mega_overlay_token(capture_fixture):
    request, _state = capture_fixture
    action = normalize_choose("/choose move 1 1 mega, pass|7", request)
    assert action["kind"] == "joint"
    assert action["slots"][0]["mega"] is True
    assert action["slots"][0]["tera"] is False


def test_normalize_choose_rejects_dual_overlay_token(capture_fixture):
    request, _state = capture_fixture
    with pytest.raises(DecisionCaptureError):
        normalize_choose("/choose move 1 1 terastallize mega, pass|7", request)


# ---------------------------------------------------------------------------
# _label_ja: mega suffix (labels are diagnostic only)
# ---------------------------------------------------------------------------

def test_label_ja_adds_mega_suffix(decision_fixture):
    from showdown_bot.battle.decision import _label_ja

    req, _kw = decision_fixture
    ja = JointAction(
        slot0=SlotAction(kind="move", move_index=1, target=1, mega_evolve=True),
        slot1=SlotAction(kind="pass"),
    )
    label = _label_ja(req, ja)
    assert label.startswith("(")
    assert " mega" in label.split(",")[0]


# ---------------------------------------------------------------------------
# decision.py candidate population uses key-v2 (no v1 keys leak into v3 rows)
# ---------------------------------------------------------------------------

def test_heuristic_decision_populates_v2_candidate_keys(decision_fixture):
    from showdown_bot.battle.decision import heuristic_choose_for_request

    req, kw = decision_fixture
    trace = DecisionTrace()
    heuristic_choose_for_request(req, trace=trace, **kw)

    assert trace.candidates, "expected at least one traced candidate"
    for cand in trace.candidates:
        payload = json.loads(cand.candidate_key)
        assert payload["version"] == 2
        for slot in payload["slots"]:
            assert "mega_evolve" in slot

    chosen_payload = json.loads(trace.chosen_candidate_key)
    assert chosen_payload["version"] == 2
    assert trace.chosen_mega_slot is None


def test_build_trace_row_from_real_decision_is_v3(trace_context, prepared, capture_fixture, decision_fixture):
    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.eval.decision_capture import build_trace_row

    request, kw = decision_fixture
    trace = DecisionTrace()
    choose = heuristic_choose_for_request(request, trace=trace, **kw)
    row = build_trace_row(
        context=trace_context, prepared=prepared, request=request,
        choose=choose, trace=trace, decision_index=0, decision_latency_ms=1.0,
    )
    assert row["trace_schema_version"] == TRACE_SCHEMA_VERSION_V3
    assert row["chosen_mega_slot"] is None
    validate_trace_row(row)


# ---------------------------------------------------------------------------
# I7a-B merge-blocker follow-up (Task 5): pre-Tera key / post-Tera label.
# ---------------------------------------------------------------------------


def test_build_trace_row_regression_for_actually_chosen_tera_action(
    trace_context, prepared, capture_fixture,
):
    """``chosen_candidate_key`` stays PRE-Tera while ``chosen_candidate_id``
    may carry the POST-Tera ``' tera'`` label -- decision.py always sets
    ``trace.chosen_candidate_key = joint_action_key_v2(pre_tera_ja)`` and
    ``trace.chosen_candidate_id = _label_ja(req, best_ja)`` where ``best_ja``
    is POST-Tera (see ``_populate_legacy_decision_trace`` /
    ``_populate_mega_decision_trace``), while every traced candidate's own
    ``candidate_id``/``candidate_key`` is PRE-Tera (Tera is an overlay applied
    only to the winner, never enumerated as its own candidate). This is a
    real, structural split -- not a hypothetical -- so ``build_trace_row``'s
    own validators must accept it for a genuinely chosen Tera action: the key
    stays authoritative (resolves the candidate), and label consistency is
    checked Tera-STRIPPED, without introducing a first-match/fuzzy fallback
    (the candidate is still found via the exact key match; stripping is only
    used to compare the already-resolved candidate's label against the
    chosen post-Tera label)."""
    from showdown_bot.battle.candidate_identity import joint_action_key_v2
    from showdown_bot.battle.decision import _label_ja
    from showdown_bot.eval.decision_capture import build_trace_row

    request, _state = capture_fixture
    move_index = 1
    assert request.active[0].moves, "fixture request must have at least one move"

    pre_tera_ja = JointAction(
        slot0=SlotAction(kind="move", move_index=move_index, target=1),
        slot1=SlotAction(kind="pass"),
    )
    post_tera_ja = JointAction(
        slot0=SlotAction(kind="move", move_index=move_index, target=1, terastallize=True),
        slot1=SlotAction(kind="pass"),
    )

    pre_key = joint_action_key_v2(pre_tera_ja)
    pre_label = _label_ja(request, pre_tera_ja)
    post_label = _label_ja(request, post_tera_ja)
    assert " tera" not in pre_label
    assert " tera" in post_label

    trace = DecisionTrace(
        game_mode="NEUTRAL",
        chosen_candidate_key=pre_key,
        chosen_candidate_id=post_label,
        chosen_tera_slot=0,
        chosen_mega_slot=None,
        candidates=[
            CandidateTrace(
                candidate_id=pre_label, joint_action=pre_tera_ja, rank=0,
                aggregate_score=1.0, score_vector=[1.0],
                outcome_breakdowns=[OutcomeBreakdown()],
                aggregate_breakdown=OutcomeBreakdown(),
                candidate_key=pre_key,
            ),
        ],
    )
    choose = f"/choose move {move_index} 1 terastallize, pass|{request.rqid}"

    row = build_trace_row(
        context=trace_context, prepared=prepared, request=request,
        choose=choose, trace=trace, decision_index=0, decision_latency_ms=1.0,
    )
    assert row["chosen_candidate_key"] == pre_key
    assert row["chosen_candidate_id"] == post_label
    assert row["chosen_tera_slot"] == 0
    assert row["chosen_rank"] == 0
    validate_trace_row(row)  # must not raise


# ---------------------------------------------------------------------------
# Fixtures: trace_context / prepared / capture_fixture are provided by the
# top-level tests/conftest.py.
# ---------------------------------------------------------------------------

@pytest.fixture
def trace_context():
    from showdown_bot.eval.decision_capture import BattleTraceContext

    return BattleTraceContext(
        battle_id="battle-i7a", seed_index=0, config_id="heuristic",
        config_hash="config-a", schedule_hash="schedule-a",
        format_id="gen9vgc2025regi", git_sha="a" * 40,
    )


@pytest.fixture
def prepared(capture_fixture):
    from showdown_bot.eval.decision_capture import prepare_capture

    request, state = capture_fixture
    return prepare_capture(state, request)


# ---------------------------------------------------------------------------
# T33/T34/T35: mega vs tera chosen-slot semantics
# ---------------------------------------------------------------------------

def _minimal_v3_row(*, key_mega_evolve_slot0: bool, chosen_mega_slot,
                    chosen_tera_slot=None, normalized_mega_slot0: bool):
    """Build a minimal literal v3 row with exactly one candidate (the chosen
    one), so the mega-key-consistency and normalized-action-consistency checks
    can be exercised independently of a real decision/request."""
    ja = JointAction(
        slot0=SlotAction(kind="move", move_index=1, target=1, mega_evolve=key_mega_evolve_slot0),
        slot1=SlotAction(kind="pass"),
    )
    key = joint_action_key_v2(ja)
    return {
        "trace_schema_version": TRACE_SCHEMA_VERSION_V3,
        "battle_id": "b", "seed_index": 0, "decision_index": 0, "turn_number": 1,
        "our_side": "p1", "config_id": "heuristic", "config_hash": "c" * 64,
        "schedule_hash": "s" * 64, "format_id": "gen9vgc2025regi", "git_sha": "a" * 40,
        "observable_state_hash": "0" * 64, "request_hash": "1" * 64,
        "decision_phase": "regular_turn", "state_summary": {"turn": 1, "field": {}, "sides": {}},
        "actual_choose_string": "/choose move 1 1 mega, pass|1",
        "normalized_action": {
            "kind": "joint",
            "slots": [
                {
                    "kind": "move", "move_index": 1, "move_id": "flamethrower", "target": 1,
                    "tera": False, "mega": normalized_mega_slot0, "is_protect": False,
                },
                {"kind": "pass"},
            ],
        },
        "chosen_candidate_id": "(Flamethrower->1 mega, pass)",
        "chosen_candidate_key": key,
        "chosen_tera_slot": chosen_tera_slot,
        "chosen_mega_slot": chosen_mega_slot,
        "chosen_rank": 0,
        "candidates": [{
            "candidate_id": "(Flamethrower->1 mega, pass)",
            "candidate_key": key,
            "rank": 0,
            "aggregate_score": 1.0,
        }],
        "decision_latency_ms": 1.0,
    }


def test_v3_valid_mega_row_validates():
    row = _minimal_v3_row(
        key_mega_evolve_slot0=True, chosen_mega_slot=0,
        chosen_tera_slot=None, normalized_mega_slot0=True,
    )
    validate_trace_row(row)


# T33: both chosen_mega_slot and chosen_tera_slot set -> reject.
def test_v3_rejects_both_mega_and_tera_slot_set():
    row = _minimal_v3_row(
        key_mega_evolve_slot0=True, chosen_mega_slot=0,
        chosen_tera_slot=1, normalized_mega_slot0=True,
    )
    with pytest.raises(DecisionCaptureError):
        validate_trace_row(row)


# T34: chosen_mega_slot points at a slot whose candidate_key mega_evolve flag
# doesn't match -> reject.
def test_v3_rejects_chosen_mega_key_mismatch():
    row = _minimal_v3_row(
        key_mega_evolve_slot0=False, chosen_mega_slot=0,
        chosen_tera_slot=None, normalized_mega_slot0=True,
    )
    with pytest.raises(DecisionCaptureError):
        validate_trace_row(row)


# T35: normalized_action's mega marker disagrees with chosen_mega_slot -> reject.
def test_v3_rejects_normalized_mega_mismatch():
    row = _minimal_v3_row(
        key_mega_evolve_slot0=True, chosen_mega_slot=0,
        chosen_tera_slot=None, normalized_mega_slot0=False,
    )
    with pytest.raises(DecisionCaptureError):
        validate_trace_row(row)


# ---------------------------------------------------------------------------
# resolve_chosen_candidate: v2 keys distinguish mega/non-mega candidates and
# resolve exactly once.
# ---------------------------------------------------------------------------

def _ct(*, candidate_key: str, rank: int) -> CandidateTrace:
    return CandidateTrace(
        candidate_id="x", joint_action=None, rank=rank, aggregate_score=1.0,
        score_vector=[1.0], outcome_breakdowns=[OutcomeBreakdown()],
        aggregate_breakdown=OutcomeBreakdown(), candidate_key=candidate_key,
    )


def test_resolve_chosen_candidate_v2_mega_key_resolves_exactly_once():
    ja_plain = JointAction(SlotAction(kind="move", move_index=1, target=1), SlotAction(kind="pass"))
    ja_mega = ja_plain.with_mega(0)
    key_plain, key_mega = joint_action_key_v2(ja_plain), joint_action_key_v2(ja_mega)
    assert key_plain != key_mega

    trace = DecisionTrace(
        chosen_candidate_key=key_mega, chosen_mega_slot=0,
        candidates=[_ct(candidate_key=key_plain, rank=1), _ct(candidate_key=key_mega, rank=0)],
    )
    resolved = resolve_chosen_candidate(trace)
    assert resolved.candidate_key == key_mega
    assert resolved.rank == 0


def test_resolve_chosen_candidate_v2_key_ambiguous_raises():
    dup = joint_action_key_v2(JointAction(SlotAction(kind="move", move_index=1, target=1), SlotAction(kind="pass")))
    trace = DecisionTrace(
        chosen_candidate_key=dup,
        candidates=[_ct(candidate_key=dup, rank=0), _ct(candidate_key=dup, rank=1)],
    )
    with pytest.raises(ChosenCandidateResolutionError, match="ambiguous"):
        resolve_chosen_candidate(trace)


# ---------------------------------------------------------------------------
# I7a-B Task 4: Mega-branch trace population (T50) + Mega/Tera mutual
# exclusion. Self-contained fixtures/helpers (no cross-import from
# test_i7a_decision.py) mirroring that file's T17/T31 fixtures.
# ---------------------------------------------------------------------------


def _mega_trace_req(*, a_moves, a_can_mega, a_can_tera=False, b_moves=("Moonblast",)):
    from showdown_bot.engine.state import to_id
    from showdown_bot.models.request import BattleRequest

    active0 = {
        "moves": [
            {"move": n, "id": to_id(n), "pp": 8, "maxpp": 8, "target": "normal", "disabled": False}
            for n in a_moves
        ],
        "canMegaEvo": a_can_mega,
    }
    if a_can_tera:
        active0["canTerastallize"] = "Fire"
    return BattleRequest.model_validate({
        "active": [
            active0,
            {
                "moves": [
                    {"move": n, "id": to_id(n), "pp": 8, "maxpp": 8, "target": "normal", "disabled": False}
                    for n in b_moves
                ],
                "canMegaEvo": False,
            },
        ],
        "side": {
            "name": "Player1", "id": "p1",
            "pokemon": [
                {
                    "ident": "p1: Aerodactyl", "details": "Aerodactyl, L50",
                    "condition": "100/100", "active": True,
                    "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
                    "moves": [to_id(n) for n in a_moves], "baseTypes": ["Normal"],
                    "item": "Aerodactylite",
                },
                {
                    "ident": "p1: Whimsicott", "details": "Whimsicott, L50",
                    "condition": "100/100", "active": True,
                    "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
                    "moves": [to_id(n) for n in b_moves], "baseTypes": ["Normal"],
                },
            ],
        },
        "rqid": 1,
    })


def _mega_trace_state():
    from showdown_bot.engine.state import BattleState, PokemonState

    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(
        species="Aerodactyl", base_species_id="aerodactyl", item="Aerodactylite",
        types=["Normal"], hp=100, max_hp=100,
    )
    st.sides["p1"]["b"] = PokemonState(
        species="Whimsicott", base_species_id="whimsicott", types=["Normal"], hp=100, max_hp=100,
    )
    st.sides["p2"]["a"] = PokemonState(
        species="Incineroar", base_species_id="incineroar", types=["Normal"], hp=100, max_hp=100,
    )
    return st


class _MegaTraceCalc:
    """Same controlled-damage design as test_i7a_decision.py's _T17Calc:
    B(Pound) beats A(Tackle) only once Mega evolved, so the winner is
    deterministically B+Mega -- lets these trace tests assert on a known,
    stable chosen_mega_slot."""

    backend = None
    _TABLE = {
        ("Aerodactyl", "Tackle"): (90, 97),
        ("Aerodactyl", "Pound"): (45, 52),
        ("Aerodactyl-Mega", "Tackle"): (97, 105),
        ("Aerodactyl-Mega", "Pound"): (135, 142),
    }

    def damage_batch(self, requests):
        from showdown_bot.engine.calc.models import DamageResult

        out = []
        for req in requests:
            key = (req.attacker.species, req.move)
            if key in self._TABLE:
                mn, mx = self._TABLE[key]
                out.append(DamageResult(min_damage=mn, max_damage=mx, max_hp=150))
            else:
                out.append(DamageResult(min_damage=20, max_damage=35, max_hp=150))
        return out


@pytest.fixture
def mega_trace_speed_oracle(calc_profile):
    from showdown_bot.engine.calc.client import SubprocessCalcBackend
    from showdown_bot.engine.speed import SpeedOracle

    return SpeedOracle(stats_backend=SubprocessCalcBackend(), profile=calc_profile)


def test_mega_decision_populates_trace_with_chosen_mega_slot_and_full_candidates(
    champions_cfg, calc_profile, aerodactyl_spreads, mega_trace_speed_oracle,
):
    """A real Mega-enabled decision (T17's B+Mega-wins fixture) populates
    DecisionTrace fully through _choose_best_mega: chosen_mega_slot set,
    chosen_tera_slot None (Champions has tera=False anyway), every evaluated
    variant present exactly once in trace.candidates (no TOP_K truncation),
    and every candidate key is a valid v2 key with a mega_evolve flag."""
    from showdown_bot.battle.decision import _choose_best
    from showdown_bot.battle.mega_scoring import build_own_mega_contexts
    from showdown_bot.battle.mega_variants import ScoredMegaVariant
    from showdown_bot.battle.oracle import DamageOracle
    from showdown_bot.engine.belief.hypotheses import SpreadBook
    from showdown_bot.engine.species_meta import species_meta_table

    req = _mega_trace_req(a_moves=["Tackle", "Pound"], a_can_mega=True)
    state = _mega_trace_state()
    spreads = {
        "aerodactyl": aerodactyl_spreads, "whimsicott": aerodactyl_spreads,
        "incineroar": aerodactyl_spreads,
    }
    book = SpreadBook(default=aerodactyl_spreads)
    calc = _MegaTraceCalc()

    # Independently recompute the expected evaluated-variant set (same
    # expand+filter pipeline the production code uses) so the trace assertion
    # doesn't just trust decision.py's own internal bookkeeping.
    expected_contexts, _expected_evaluated = build_own_mega_contexts(
        req, state, our_side="p1", opp_side="p2", book=book, oracle=DamageOracle(_MegaTraceCalc()),
        speed_oracle=mega_trace_speed_oracle, species_meta=species_meta_table(),
        our_spreads=spreads, opp_sets=None, calc_profile=calc_profile,
        my_actions=enumerate_my_actions(req),
    )
    expected_keys = {
        joint_action_key_v2(ja)
        for ctx in expected_contexts
        for ja in ctx.plans
    }

    trace = DecisionTrace()
    best_ja, best_val = _choose_best(
        req, state=state, book=book, our_side="p1", calc=calc, oracle=DamageOracle(calc),
        speed_oracle=mega_trace_speed_oracle, dex=None, our_spreads=spreads,
        format_config=champions_cfg, risk_lambda=0.0, trace=trace,
    )

    assert best_ja.slot0.mega_evolve is True
    assert trace.chosen_mega_slot == 0
    assert trace.chosen_tera_slot is None
    assert trace.game_mode

    trace_keys = [c.candidate_key for c in trace.candidates]
    assert len(trace_keys) == len(expected_keys)
    assert set(trace_keys) == expected_keys
    assert len(trace_keys) == len(set(trace_keys))  # every variant exactly once

    for cand in trace.candidates:
        payload = json.loads(cand.candidate_key)
        assert payload["version"] == 2
        for slot in payload["slots"]:
            assert "mega_evolve" in slot

    resolved = resolve_chosen_candidate(trace)
    assert resolved.candidate_key == trace.chosen_candidate_key


def test_t50_scovillain_absent_from_full_decision_ranking_and_trace(
    scovillain_mega_request, champions_cfg, calc_profile, aerodactyl_spreads,
):
    """T50 (design spec Sec.3.6): Scovillainite's raw Mega variant (Spicy
    Spray, fail-closed) exists in expand_mega_variants' output but must be
    absent from evaluated_variants, ranking, AND trace -- and every ACTUALLY
    evaluated variant must appear exactly once in trace.candidates."""
    from showdown_bot.battle.decision import _choose_best
    from showdown_bot.battle.mega_scoring import build_own_mega_contexts
    from showdown_bot.battle.mega_variants import expand_mega_variants
    from showdown_bot.battle.oracle import DamageOracle
    from showdown_bot.engine.belief.hypotheses import SpreadBook
    from showdown_bot.engine.species_meta import species_meta_table
    from showdown_bot.engine.state import BattleState, PokemonState

    state = BattleState()
    state.sides["p1"]["a"] = PokemonState(
        species="Scovillain", base_species_id="scovillain", item="Scovillainite",
        types=["Grass", "Fire"], hp=155, max_hp=155,
    )
    state.sides["p1"]["b"] = PokemonState(
        species="Whimsicott", base_species_id="whimsicott",
        types=["Grass", "Fairy"], hp=140, max_hp=140,
    )
    state.sides["p2"]["a"] = PokemonState(
        species="Incineroar", base_species_id="incineroar",
        types=["Fire", "Dark"], hp=180, max_hp=180,
    )

    class _T50Speed:
        def __init__(self, profile):
            self.profile = profile

        def our_speed(self, base, mon, field, side):
            return base or 100

        def opponent_range(self, mon, field, side, *, book):
            from showdown_bot.engine.speed import SpeedRange

            return SpeedRange(min=80, likely=110, max=150)

    class _T50Calc:
        backend = None

        def damage_batch(self, requests):
            from showdown_bot.engine.calc.models import DamageResult

            return [DamageResult(min_damage=20, max_damage=35, max_hp=150) for _ in requests]

    base_joints = enumerate_my_actions(scovillain_mega_request)
    raw_variants = expand_mega_variants(base_joints, scovillain_mega_request, state, "p1")
    assert any(v.own_mega_slot == 0 for v in raw_variants)  # raw variant exists

    book = SpreadBook(default=aerodactyl_spreads)
    spreads = {
        "scovillain": aerodactyl_spreads, "whimsicott": aerodactyl_spreads,
        "incineroar": aerodactyl_spreads,
    }
    calc = _T50Calc()
    speed_oracle = _T50Speed(calc_profile)

    expected_contexts, _expected_evaluated = build_own_mega_contexts(
        scovillain_mega_request, state, our_side="p1", opp_side="p2", book=book,
        oracle=DamageOracle(_T50Calc()), speed_oracle=speed_oracle,
        species_meta=species_meta_table(), our_spreads=spreads, opp_sets=None,
        calc_profile=calc_profile, my_actions=base_joints,
    )
    expected_keys = {
        joint_action_key_v2(ja) for ctx in expected_contexts for ja in ctx.plans
    }
    assert not any(ctx.own_mega_slot == 0 for ctx in expected_contexts)  # fail-closed

    trace = DecisionTrace()
    best_ja, _best_val = _choose_best(
        scovillain_mega_request, state=state, book=book, our_side="p1", calc=calc,
        oracle=DamageOracle(calc), speed_oracle=speed_oracle, dex=None,
        our_spreads=spreads, format_config=champions_cfg, risk_lambda=0.0, trace=trace,
    )

    assert best_ja.slot0.mega_evolve is False
    assert trace.chosen_mega_slot is None

    trace_keys = [c.candidate_key for c in trace.candidates]
    assert len(trace_keys) == len(expected_keys)
    assert set(trace_keys) == expected_keys
    assert len(trace_keys) == len(set(trace_keys))  # every evaluated variant exactly once
    for key in trace_keys:
        payload = json.loads(key)
        assert payload["slots"][0]["mega_evolve"] is False  # Scovillain slot never mega'd


def test_mega_tera_mutual_exclusion_never_calls_maybe_tera_for_mega_winner(
    champions_cfg, calc_profile, aerodactyl_spreads, mega_trace_speed_oracle, monkeypatch,
):
    """Synthetic config with BOTH mega=True and tera=True (Champions itself
    has tera=False, so this needs a synthetic config to actually exercise the
    overlay-attempt path): a chosen Mega winner must never enter _maybe_tera
    (design spec Sec.7.2 mutual exclusion). Proven by spying on
    decision._maybe_tera and asserting zero calls, using a fixture where the
    Mega-capable slot ALSO has can_terastallize=True so a buggy
    implementation that forgot the mutual-exclusion guard would actually try
    to overlay Tera onto the Mega winner."""
    import showdown_bot.battle.decision as decision_mod
    from showdown_bot.battle.oracle import DamageOracle
    from showdown_bot.engine.belief.hypotheses import SpreadBook

    synthetic_cfg = dataclasses.replace(champions_cfg, mega=True, tera=True)

    req = _mega_trace_req(a_moves=["Tackle", "Pound"], a_can_mega=True, a_can_tera=True)
    state = _mega_trace_state()
    spreads = {
        "aerodactyl": aerodactyl_spreads, "whimsicott": aerodactyl_spreads,
        "incineroar": aerodactyl_spreads,
    }
    book = SpreadBook(default=aerodactyl_spreads)
    calc = _MegaTraceCalc()

    calls = []
    real_maybe_tera = decision_mod._maybe_tera

    def _spy(*args, **kwargs):
        calls.append((args, kwargs))
        return real_maybe_tera(*args, **kwargs)

    monkeypatch.setattr(decision_mod, "_maybe_tera", _spy)

    trace = DecisionTrace()
    best_ja, _best_val = decision_mod._choose_best(
        req, state=state, book=book, our_side="p1", calc=calc, oracle=DamageOracle(calc),
        speed_oracle=mega_trace_speed_oracle, dex=None, our_spreads=spreads,
        format_config=synthetic_cfg, risk_lambda=0.0, trace=trace,
    )

    assert best_ja.slot0.mega_evolve is True
    assert trace.chosen_mega_slot == 0
    assert trace.chosen_tera_slot is None
    assert calls == []  # the Mega winner never entered _maybe_tera
