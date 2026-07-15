from __future__ import annotations

import copy

import pytest

from showdown_bot.battle.actions import JointAction, enumerate_my_actions
from showdown_bot.battle.mega_scoring import (
    MegaEvaluationContext,
    MegaScoreRecord,
    build_own_mega_contexts,
    score_evaluated_variants,
)
from showdown_bot.battle.mega_variants import ScoredMegaVariant
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.engine.belief.hypotheses import SpreadBook
from showdown_bot.engine.calc.client import SubprocessCalcBackend
from showdown_bot.engine.calc.models import CalcMon
from showdown_bot.engine.species_meta import species_meta_table
from showdown_bot.engine.state import BattleState, PokemonState, to_id
from showdown_bot.models.request import BattleRequest

# ---------------------------------------------------------------------------
# I7a-B Task 2: MegaEvaluationContext + post-Mega plan speed
# ---------------------------------------------------------------------------


def _build_req(
    *, a_species: str, a_item: str, a_moves: list[str], a_can_mega: bool,
    b_species: str, b_moves: list[str],
) -> BattleRequest:
    return BattleRequest.model_validate({
        "active": [
            {
                "moves": [
                    {
                        "move": name, "id": to_id(name), "pp": 8, "maxpp": 8,
                        "target": "normal", "disabled": False,
                    }
                    for name in a_moves
                ],
                "canMegaEvo": a_can_mega,
            },
            {
                "moves": [
                    {
                        "move": name, "id": to_id(name), "pp": 8, "maxpp": 8,
                        "target": "normal", "disabled": False,
                    }
                    for name in b_moves
                ],
                "canMegaEvo": False,
            },
        ],
        "side": {
            "name": "Player1",
            "id": "p1",
            "pokemon": [
                {
                    "ident": f"p1: {a_species}",
                    "details": f"{a_species}, L50",
                    "condition": "100/100",
                    "active": True,
                    "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
                    "moves": [to_id(n) for n in a_moves],
                    "baseTypes": ["Normal"],
                    "item": a_item,
                },
                {
                    "ident": f"p1: {b_species}",
                    "details": f"{b_species}, L50",
                    "condition": "100/100",
                    "active": True,
                    "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
                    "moves": [to_id(n) for n in b_moves],
                    "baseTypes": ["Normal"],
                },
            ],
        },
        "rqid": 1,
    })


def _build_state(a_species: str, a_item: str, b_species: str, foe_species: str) -> BattleState:
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(
        species=a_species, base_species_id=to_id(a_species), item=a_item,
        types=["Normal"], hp=100, max_hp=100,
    )
    st.sides["p1"]["b"] = PokemonState(
        species=b_species, base_species_id=to_id(b_species),
        types=["Normal"], hp=100, max_hp=100,
    )
    st.sides["p2"]["a"] = PokemonState(
        species=foe_species, base_species_id=to_id(foe_species),
        types=["Normal"], hp=100, max_hp=100,
    )
    return st


@pytest.fixture
def speed_oracle(calc_profile):
    from showdown_bot.engine.speed import SpeedOracle

    return SpeedOracle(stats_backend=SubprocessCalcBackend(), profile=calc_profile)


def _build_aerodactyl_contexts(speed_oracle, aerodactyl_spreads, calc_profile):
    req = _build_req(
        a_species="Aerodactyl", a_item="Aerodactylite", a_moves=["Rock Slide"],
        a_can_mega=True, b_species="Whimsicott", b_moves=["Moonblast"],
    )
    state = _build_state("Aerodactyl", "Aerodactylite", "Whimsicott", "Incineroar")
    spreads = {"aerodactyl": aerodactyl_spreads, "whimsicott": aerodactyl_spreads}
    book = SpreadBook(default=aerodactyl_spreads)
    oracle = DamageOracle()
    my_actions = enumerate_my_actions(req)
    contexts = build_own_mega_contexts(
        req, state, our_side="p1", opp_side="p2", book=book, oracle=oracle,
        speed_oracle=speed_oracle, species_meta=species_meta_table(),
        our_spreads=spreads, opp_sets=None, calc_profile=calc_profile,
        my_actions=my_actions,
    )
    return req, state, contexts


def test_build_own_mega_contexts_returns_none_and_mega_slot_branches(
    speed_oracle, aerodactyl_spreads, calc_profile,
):
    req, state, contexts = _build_aerodactyl_contexts(speed_oracle, aerodactyl_spreads, calc_profile)

    slots = {c.own_mega_slot for c in contexts}
    assert slots == {None, 0}
    for c in contexts:
        assert c.foe_mega_slot is None
        assert c.branch_weight == 1.0
        assert c.activation_order is None
        assert c.projected_state is not state
        assert c.plans  # at least one candidate joint action was planned

    mega_ctx = next(c for c in contexts if c.own_mega_slot == 0)
    assert mega_ctx.projected_state.sides["p1"]["a"].species == "Aerodactyl-Mega"

    none_ctx = next(c for c in contexts if c.own_mega_slot is None)
    assert none_ctx.projected_state.sides["p1"]["a"].species == "Aerodactyl"


def test_mega_context_damage_model_hyps_use_projected_species_and_ability(
    speed_oracle, aerodactyl_spreads, calc_profile,
):
    _req, _state, contexts = _build_aerodactyl_contexts(speed_oracle, aerodactyl_spreads, calc_profile)

    mega_ctx = next(c for c in contexts if c.own_mega_slot == 0)
    hyp = mega_ctx.damage_model.hyps[("p1", "a")]
    assert hyp.species == "Aerodactyl-Mega"
    assert hyp.ability == "Tough Claws"

    none_ctx = next(c for c in contexts if c.own_mega_slot is None)
    hyp0 = none_ctx.damage_model.hyps[("p1", "a")]
    assert hyp0.species == "Aerodactyl"


def test_build_own_mega_contexts_does_not_mutate_live_state_or_request(
    speed_oracle, aerodactyl_spreads, calc_profile,
):
    req = _build_req(
        a_species="Aerodactyl", a_item="Aerodactylite", a_moves=["Rock Slide"],
        a_can_mega=True, b_species="Whimsicott", b_moves=["Moonblast"],
    )
    state = _build_state("Aerodactyl", "Aerodactylite", "Whimsicott", "Incineroar")
    spreads = {"aerodactyl": aerodactyl_spreads, "whimsicott": aerodactyl_spreads}
    book = SpreadBook(default=aerodactyl_spreads)
    oracle = DamageOracle()
    my_actions = enumerate_my_actions(req)

    before_sides = copy.deepcopy(state.sides)
    before_field = copy.deepcopy(state.field)
    before_mega_spent = copy.deepcopy(state.side_mega_spent)
    before_req = req.model_copy(deep=True)

    contexts = build_own_mega_contexts(
        req, state, our_side="p1", opp_side="p2", book=book, oracle=oracle,
        speed_oracle=speed_oracle, species_meta=species_meta_table(),
        our_spreads=spreads, opp_sets=None, calc_profile=calc_profile,
        my_actions=my_actions,
    )

    assert state.sides == before_sides
    assert state.field == before_field
    assert state.side_mega_spent == before_mega_spent
    assert req == before_req
    for ctx in contexts:
        assert ctx.projected_state is not state
        assert ctx.projected_state.sides is not state.sides


def test_mega_context_plan_speed_overrides_to_projected_222(
    speed_oracle, aerodactyl_spreads, calc_profile,
):
    # Ground truth: BASE (non-Mega) Aerodactyl's request speed at the same
    # spread used for the projected Mega form (already pinned at 222 by
    # test_i7a_foundation.test_aerodactyl_gen0_speed_222).
    mega_calc_mon = CalcMon(
        species="Aerodactyl", level=50, nature="Jolly",
        evs={"atk": 32, "spe": 32, "hp": 2}, ivs={"spe": 31},
    )
    backend = SubprocessCalcBackend()
    base_stats = backend.stats_batch([mega_calc_mon], gen=0)
    assert base_stats[0]["spe"] == 200

    req = _build_req(
        a_species="Aerodactyl", a_item="Aerodactylite", a_moves=["Rock Slide"],
        a_can_mega=True, b_species="Whimsicott", b_moves=["Moonblast"],
    )
    state = _build_state("Aerodactyl", "Aerodactylite", "Whimsicott", "Incineroar")
    spreads = {"aerodactyl": aerodactyl_spreads, "whimsicott": aerodactyl_spreads}
    book = SpreadBook(default=aerodactyl_spreads)
    oracle = DamageOracle()
    my_actions = enumerate_my_actions(req)

    before_state = copy.deepcopy(state)
    before_req_stats = copy.deepcopy(req.side.pokemon[0].stats)

    contexts = build_own_mega_contexts(
        req, state, our_side="p1", opp_side="p2", book=book, oracle=oracle,
        speed_oracle=speed_oracle, species_meta=species_meta_table(),
        our_spreads=spreads, opp_sets=None, calc_profile=calc_profile,
        my_actions=my_actions,
    )

    mega_ctx = next(c for c in contexts if c.own_mega_slot == 0)
    plan = next(iter(mega_ctx.plans.values()))
    slot_a_plan = next(p for p in plan if p.slot == "a")
    assert slot_a_plan.speed == 222

    assert state.sides == before_state.sides
    assert req.side.pokemon[0].stats == before_req_stats


def test_mega_sol_fire_boosted_water_weakened_partner_and_foe_unchanged(
    speed_oracle, aerodactyl_spreads, calc_profile,
):
    """T28: projected Mega Sol boosts Meganium-Mega's own Fire move and weakens
    its own Water move vs. a neutral (ability-blanked) baseline. Partner and
    foe moves are untouched (Mega Sol never sets global weather -- it's a
    per-attacker check in the calc, not a field effect)."""
    from showdown_bot.battle.resolve import PlannedAction
    from showdown_bot.battle.evaluate import DamageModel
    from showdown_bot.engine.moves import get_move_meta

    req = _build_req(
        a_species="Meganium", a_item="Meganiumite", a_moves=["Overheat", "Hydro Pump"],
        a_can_mega=True, b_species="Whimsicott", b_moves=["Moonblast"],
    )
    state = _build_state("Meganium", "Meganiumite", "Whimsicott", "Incineroar")
    spreads = {
        "meganium": aerodactyl_spreads, "whimsicott": aerodactyl_spreads,
        "incineroar": aerodactyl_spreads,
    }
    book = SpreadBook(default=aerodactyl_spreads)
    oracle = DamageOracle()
    my_actions = enumerate_my_actions(req)

    contexts = build_own_mega_contexts(
        req, state, our_side="p1", opp_side="p2", book=book, oracle=oracle,
        speed_oracle=speed_oracle, species_meta=species_meta_table(),
        our_spreads=spreads, opp_sets=None, calc_profile=calc_profile,
        my_actions=my_actions,
    )
    mega_context = next(c for c in contexts if c.own_mega_slot == 0)
    assert mega_context.projected_state.field.weather is None

    mega_model = mega_context.damage_model

    neutral_state = copy.deepcopy(mega_context.projected_state)
    # An empty-string ability is falsy on the calc side and falls back to the
    # species' declared default ability (which for Meganium-Mega IS "Mega
    # Sol") -- use a real, different ability so the payload actually diverges.
    neutral_state.sides["p1"]["a"].ability = "Overgrow"
    neutral_model = DamageModel(
        neutral_state, "p1", "p2", book=book, oracle=oracle,
        field=neutral_state.field, our_spreads=spreads, opp_sets=None,
        calc_profile=calc_profile,
    )

    our_fire_action = PlannedAction(
        "p1", "a", "move", speed=222, move=get_move_meta("Overheat"),
        target=("p2", "a"), is_ours=True, is_mega=True,
    )
    our_water_action = PlannedAction(
        "p1", "a", "move", speed=222, move=get_move_meta("Hydro Pump"),
        target=("p2", "a"), is_ours=True, is_mega=True,
    )
    partner_action = PlannedAction(
        "p1", "b", "move", speed=100, move=get_move_meta("Moonblast"),
        target=("p2", "a"), is_ours=True,
    )
    foe_action = PlannedAction(
        "p2", "a", "move", speed=100, move=get_move_meta("Knock Off"),
        target=("p1", "a"), is_ours=False,
    )

    foe_target = mega_context.projected_state.sides["p2"]["a"]
    our_target = mega_context.projected_state.sides["p1"]["a"]

    action_groups = [
        [our_fire_action, our_water_action, partner_action],
        [foe_action],
    ]
    mega_model.enqueue(action_groups)
    neutral_model.enqueue(action_groups)
    oracle.flush()

    fire_mega = mega_model.damage_fn(our_fire_action, foe_target)
    fire_neutral = neutral_model.damage_fn(our_fire_action, foe_target)
    water_mega = mega_model.damage_fn(our_water_action, foe_target)
    water_neutral = neutral_model.damage_fn(our_water_action, foe_target)

    assert fire_mega > fire_neutral
    assert water_mega < water_neutral
    assert mega_model.damage_fn(partner_action, foe_target) == neutral_model.damage_fn(
        partner_action, foe_target
    )
    assert mega_model.damage_fn(foe_action, our_target) == neutral_model.damage_fn(
        foe_action, our_target
    )
    assert mega_context.projected_state.field.weather is None


# ---------------------------------------------------------------------------
# I7a-B Task 3: score_evaluated_variants (batching, K-world weight
# separation, depth-2 context binding)
# ---------------------------------------------------------------------------


class _CountingOracle:
    """Fake ``DamageOracle`` that counts ``flush()`` calls and records whether
    ``get()`` was ever called before the first ``flush()`` -- proves the "all
    contexts for a world enqueue before exactly one flush()" batching
    invariant without needing a real Node calc subprocess."""

    def __init__(self):
        self.flush_calls = 0
        self.get_calls_before_any_flush = 0
        self.requested = []

    def request(self, req):
        key = (req.attacker.species, req.move, req.defender.species, id(req))
        self.requested.append(key)
        return key

    def flush(self):
        self.flush_calls += 1

    def get(self, key):
        if self.flush_calls == 0:
            self.get_calls_before_any_flush += 1
        from showdown_bot.engine.calc.models import DamageResult

        return DamageResult(min_damage=20, max_damage=35, max_hp=150)

    def damage(self, req):
        return self.get(self.request(req))


def _basic_state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Aerodactyl", base_species_id="aerodactyl", hp=100, max_hp=100)
    st.sides["p1"]["b"] = PokemonState(species="Whimsicott", base_species_id="whimsicott", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Incineroar", base_species_id="incineroar", hp=100, max_hp=100)
    return st


def _attack_plan(target_side="p2", target_slot="a"):
    from showdown_bot.battle.resolve import PlannedAction
    from showdown_bot.engine.moves import get_move_meta

    return [
        PlannedAction(
            "p1", "a", "move", speed=100, move=get_move_meta("Tackle"),
            target=(target_side, target_slot), is_ours=True,
        ),
        PlannedAction("p1", "b", "pass", speed=100, is_ours=True),
    ]


def _opp_response(label="atk", weight=1.0):
    from showdown_bot.battle.opponent import OppResponse
    from showdown_bot.battle.resolve import PlannedAction
    from showdown_bot.engine.moves import get_move_meta

    return OppResponse(
        actions=[
            PlannedAction(
                "p2", "a", "move", speed=50, move=get_move_meta("Tackle"),
                target=("p1", "a"), is_ours=False,
            )
        ],
        label=label,
        weight=weight,
    )


def _score_kwargs(**overrides):
    from showdown_bot.battle.evaluate import EvalWeights
    from showdown_bot.engine.belief.game_mode import GameMode

    base = dict(
        req=None, state=_basic_state(), book=SpreadBook(default=None), our_side="p1",
        opp_side="p2", calc=None, speed_oracle=None, dex=None, priors=None,
        weights=EvalWeights(), mode=GameMode.NEUTRAL, risk_lambda=0.5, rollout_horizon=0,
        our_spreads=None, opp_sets=None, calc_profile=None, accuracy_mode=False,
        accuracy_branch_cap=6, endgame=False, fast_board=False,
    )
    base.update(overrides)
    return base


def _minimal_context(own_mega_slot, joints):
    st = _basic_state()
    return MegaEvaluationContext(
        context_id=f"own_mega:{own_mega_slot}", projected_state=st,
        own_mega_slot=own_mega_slot, foe_mega_slot=None, branch_weight=1.0,
        activation_order=None, field=st.field,
        plans={ja: _attack_plan() for ja in joints}, damage_model=None,
    )


def _pass_joint(tag: int) -> JointAction:
    from showdown_bot.models.actions import SlotAction

    # target distinguishes otherwise-identical JointActions across contexts
    # (frozen dataclass -> hashable dict key).
    return JointAction(
        slot0=SlotAction(kind="move", move_index=1, target=tag),
        slot1=SlotAction(kind="pass"),
    )


def test_score_evaluated_variants_batches_all_contexts_before_one_flush(monkeypatch):
    """A counting fake oracle proves EVERY context's plan + opponent-response
    calcs are enqueued before exactly one ``flush()`` -- never per-context,
    never per-candidate (I7a-B Task 3 batching invariant)."""
    import showdown_bot.battle.mega_scoring as mega_scoring

    monkeypatch.setattr(mega_scoring, "predict_responses", lambda *a, **k: [_opp_response()])

    ja_none = _pass_joint(1)
    ja_mega = _pass_joint(2)
    ctx_none = _minimal_context(None, [ja_none])
    ctx_mega = _minimal_context(0, [ja_mega])
    variants = [
        ScoredMegaVariant(joint=ja_none, own_mega_slot=None),
        ScoredMegaVariant(joint=ja_mega, own_mega_slot=0),
    ]

    oracle = _CountingOracle()
    records = score_evaluated_variants(
        variants, [ctx_none, ctx_mega], oracle=oracle, **_score_kwargs()
    )

    assert oracle.flush_calls == 1
    assert oracle.get_calls_before_any_flush == 0
    assert len(oracle.requested) > 0  # both contexts' Tackle calcs really enqueued
    assert len(records) == 2
    assert {r.variant.own_mega_slot for r in records} == {None, 0}
    for r in records:
        assert len(r.score_vector) == 1  # one opponent response, one world
        assert r.score_weights == [1.0]


def test_score_evaluated_variants_k_world_pools_but_diagnostics_are_world0_only(monkeypatch):
    """Two-world fixture with unequal world weights (0.7 / 0.3) and DIFFERENT
    per-world response counts (2 vs 3): pooled ``score_vector``/``score_weights``
    cover both worlds (length 5) while ``diagnostic_details``/``diagnostic_
    weights`` cover only world 0 (length 2) -- and the two weight arrays' own
    totals genuinely differ (2.0 vs 2.3), so an aggregate-breakdown computation
    that divided by the WRONG (pooled) total instead of ``diagnostic_weights``'
    own total would silently produce a different, wrong number."""
    import showdown_bot.battle.mega_scoring as mega_scoring

    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "2")

    def _fake_predict_responses(state, our_side, opp_side, *, opp_sets=None, **_kw):
        n = 3 if opp_sets else 2  # world1's merged_sets marker -> 3 responses
        return [_opp_response(label=f"r{i}") for i in range(n)]

    from showdown_bot.engine.belief.hypotheses import SpreadPreset, SpeciesSpreads

    world1_preset = SpeciesSpreads(
        offense=SpreadPreset(nature="Hardy", evs={}),
        defense=SpreadPreset(nature="Hardy", evs={}),
    )

    monkeypatch.setattr(mega_scoring, "predict_responses", _fake_predict_responses)
    monkeypatch.setattr(mega_scoring, "build_world_dist", lambda *a, **k: {"incineroar": [(world1_preset, 1.0)]})
    monkeypatch.setattr(
        mega_scoring, "sample_worlds",
        lambda *a, **k: [({}, 0.7), ({"incineroar": world1_preset}, 0.3)],
    )

    ja = _pass_joint(1)
    ctx = _minimal_context(None, [ja])
    variants = [ScoredMegaVariant(joint=ja, own_mega_slot=None)]

    oracle = _CountingOracle()
    records = score_evaluated_variants(
        variants, [ctx], oracle=oracle,
        **_score_kwargs(),
    )

    rec = records[0]
    assert len(rec.score_vector) == 5  # 2 (world0) + 3 (world1)
    assert len(rec.score_weights) == 5
    assert rec.score_weights == [0.7, 0.7, 0.3, 0.3, 0.3]

    assert len(rec.diagnostic_details) == 2  # world0 only
    assert len(rec.diagnostic_weights) == 2
    assert rec.diagnostic_weights == [1.0, 1.0]  # RAW (no priors) -- not world_w-scaled

    diagnostic_total = sum(rec.diagnostic_weights)
    pooled_total = sum(rec.score_weights)
    assert diagnostic_total == 2.0
    assert pooled_total == 2.3
    assert diagnostic_total != pooled_total  # the two denominators are NOT interchangeable

    correct_mean = sum(
        d.score * w for d, w in zip(rec.diagnostic_details, rec.diagnostic_weights)
    ) / diagnostic_total
    wrong_mean = sum(
        d.score * w for d, w in zip(rec.diagnostic_details, rec.diagnostic_weights)
    ) / pooled_total
    assert correct_mean != wrong_mean


def test_score_evaluated_variants_raises_for_variant_without_matching_context():
    ja = _pass_joint(1)
    variants = [ScoredMegaVariant(joint=ja, own_mega_slot=0)]
    ctx_none = _minimal_context(None, [])

    with pytest.raises(ValueError):
        score_evaluated_variants(
            variants, [ctx_none], oracle=_CountingOracle(), **_score_kwargs()
        )


# ---------------------------------------------------------------------------
# I7a-B Task 3: depth-2 context binding (search.depth2_value_for_mega_context)
# ---------------------------------------------------------------------------


def test_depth2_value_for_mega_context_binds_to_matching_context_never_another(monkeypatch):
    """Spy on ``search.depth2_value``: calling ``depth2_value_for_mega_context``
    for two DIFFERENT contexts must pass each call the MATCHING context's own
    ``projected_state`` (proven via species) and ``damage_model.oracle`` (a
    distinct sentinel per context) -- never the other context's, never a bare
    unprojected state."""
    from showdown_bot.battle import search
    from showdown_bot.battle.resolve import TurnOutcome
    from showdown_bot.engine.belief.game_mode import GameMode

    calls = []
    monkeypatch.setattr(search, "depth2_value", lambda *a, **k: calls.append((a, k)) or -1.0)

    st_none = BattleState()
    st_none.sides["p1"]["a"] = PokemonState(species="Aerodactyl", hp=100, max_hp=100)
    sentinel_none = object()
    ctx_none = MegaEvaluationContext(
        context_id="own_mega:none", projected_state=st_none, own_mega_slot=None,
        foe_mega_slot=None, branch_weight=1.0, activation_order=None, field=st_none.field,
        plans={}, damage_model=type("DM", (), {"oracle": sentinel_none})(),
    )

    st_mega = BattleState()
    st_mega.sides["p1"]["a"] = PokemonState(species="Aerodactyl-Mega", hp=100, max_hp=100)
    sentinel_mega = object()
    ctx_mega = MegaEvaluationContext(
        context_id="own_mega:0", projected_state=st_mega, own_mega_slot=0,
        foe_mega_slot=None, branch_weight=1.0, activation_order=None, field=st_mega.field,
        plans={}, damage_model=type("DM", (), {"oracle": sentinel_mega})(),
    )

    outcome = TurnOutcome(hp_delta={("p2", "a"): -0.5})

    v_none = search.depth2_value_for_mega_context(
        ctx_none, outcome, our_side="p1", mode=GameMode.NEUTRAL, risk_lambda=0.5,
        top_m=2, book=None,
    )
    v_mega = search.depth2_value_for_mega_context(
        ctx_mega, outcome, our_side="p1", mode=GameMode.NEUTRAL, risk_lambda=0.5,
        top_m=2, book=None,
    )

    assert v_none == -1.0 and v_mega == -1.0
    assert len(calls) == 2

    (args0, kwargs0), (args1, kwargs1) = calls
    assert args0[0] is st_none
    assert args0[0].sides["p1"]["a"].species == "Aerodactyl"
    assert kwargs0["oracle"] is sentinel_none

    assert args1[0] is st_mega
    assert args1[0].sides["p1"]["a"].species == "Aerodactyl-Mega"
    assert kwargs1["oracle"] is sentinel_mega

    # Never the base/unprojected state, never cross-wired between contexts.
    assert args0[0] is not st_mega
    assert args1[0] is not st_none
    assert kwargs0["oracle"] is not sentinel_mega
    assert kwargs1["oracle"] is not sentinel_none
