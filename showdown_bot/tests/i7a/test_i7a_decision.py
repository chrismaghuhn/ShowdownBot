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
    b_species: str, b_moves: list[str], a_can_tera: bool = False,
) -> BattleRequest:
    active0: dict = {
        "moves": [
            {
                "move": name, "id": to_id(name), "pp": 8, "maxpp": 8,
                "target": "normal", "disabled": False,
            }
            for name in a_moves
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
    contexts, _evaluated = build_own_mega_contexts(
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

    contexts, _evaluated = build_own_mega_contexts(
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

    contexts, _evaluated = build_own_mega_contexts(
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

    contexts, _evaluated = build_own_mega_contexts(
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


# ---------------------------------------------------------------------------
# I7a-B Task 4: full-grid ranking counterproof (T17) + Scovillain fail-closed
# smoke through the full decision (T31)
# ---------------------------------------------------------------------------


class _T17Calc:
    """Fully controlled damage: keyed by (attacker species, move) so the
    ranking counterproof is deterministic and independent of real @pkmn/calc
    numbers. Anything not in the table (the opponent's fallback Tackle, any
    game_mode/KO-threat calc call) gets the same safe non-KO default used by
    tests/conftest.py's _FakeCalc (keeps classify_game_mode NEUTRAL)."""

    backend = None
    _TABLE = {
        ("Aerodactyl", "Tackle"): (90, 97),        # base A: 60% of 150
        ("Aerodactyl", "Pound"): (45, 52),         # base B: 30% of 150
        ("Aerodactyl-Mega", "Tackle"): (97, 105),  # A+mega: ~65% of 150
        ("Aerodactyl-Mega", "Pound"): (135, 142),  # B+mega: 90% of 150
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


def test_t17_full_grid_counterproof_beats_score_base_then_overlay(
    speed_oracle, aerodactyl_spreads, calc_profile,
):
    """T17 (design spec Sec.7.1): base action A (Tackle) beats base action B
    (Pound) when neither Mega evolves, but B+Mega beats A once the fail-closed
    "score best base then overlay Mega" shortcut is replaced by scoring the
    full variant grid. A naive "rank base actions, then only try Mega on the
    already-chosen winner" implementation would pick base A and never
    discover B+Mega -- this proves the full grid is actually scored."""
    from showdown_bot.battle.evaluate import EvalWeights
    from showdown_bot.engine.belief.game_mode import GameMode

    req = _build_req(
        a_species="Aerodactyl", a_item="Aerodactylite", a_moves=["Tackle", "Pound"],
        a_can_mega=True, b_species="Whimsicott", b_moves=["Moonblast"],
    )
    state = _build_state("Aerodactyl", "Aerodactylite", "Whimsicott", "Incineroar")
    spreads = {
        "aerodactyl": aerodactyl_spreads, "whimsicott": aerodactyl_spreads,
        "incineroar": aerodactyl_spreads,
    }
    book = SpreadBook(default=aerodactyl_spreads)
    calc = _T17Calc()
    oracle = DamageOracle(calc)
    my_actions = enumerate_my_actions(req)

    contexts, evaluated = build_own_mega_contexts(
        req, state, our_side="p1", opp_side="p2", book=book, oracle=oracle,
        speed_oracle=speed_oracle, species_meta=species_meta_table(),
        our_spreads=spreads, opp_sets=None, calc_profile=calc_profile,
        my_actions=my_actions,
    )
    records = score_evaluated_variants(
        evaluated, contexts, req=req, state=state, book=book, our_side="p1",
        opp_side="p2", calc=calc, oracle=oracle, speed_oracle=speed_oracle,
        dex=None, priors=None, weights=EvalWeights(), mode=GameMode.NEUTRAL,
        risk_lambda=0.0, rollout_horizon=0, our_spreads=spreads, opp_sets=None,
        calc_profile=calc_profile, accuracy_mode=False, accuracy_branch_cap=6,
        endgame=False, fast_board=False,
    )

    def _rec_for(move_name: str, mega_slot):
        for r in records:
            if r.variant.own_mega_slot != mega_slot:
                continue
            idx = r.variant.joint.slot0.move_index
            if idx and req.active[0].moves[idx - 1].move == move_name:
                return r
        raise AssertionError(f"no record for move={move_name!r} mega_slot={mega_slot!r}")

    a_base = _rec_for("Tackle", None)
    b_base = _rec_for("Pound", None)
    b_mega = _rec_for("Pound", 0)

    # Base-only: A beats B.
    assert a_base.aggregate_score > b_base.aggregate_score
    # Full grid: B+Mega beats base A (the counterproof).
    assert b_mega.aggregate_score > a_base.aggregate_score

    best = max(records, key=lambda r: r.aggregate_score)
    assert best is b_mega
    assert best.variant.own_mega_slot == 0
    assert best.variant.joint.slot0.mega_evolve is True


# ---------------------------------------------------------------------------
# I7a-B Task 1 (merge-blocker follow-up): depth-2 must be wired into the real
# Mega decision path, not just exist as an isolated helper
# (search.depth2_value_for_mega_context, see the binding-rule test above).
# ---------------------------------------------------------------------------


def test_choose_best_mega_depth2_wraps_top_n_top_m_frontier(
    speed_oracle, aerodactyl_spreads, calc_profile, monkeypatch,
):
    """At SHOWDOWN_SEARCH_DEPTH=2 the Mega path must actually call
    ``search.depth2_value_for_mega_context`` to refine the top-N/top-M
    frontier -- driven through the real ``_choose_best`` -> ``_choose_best_mega``
    -> ``mega_scoring.score_evaluated_variants`` production path. An isolated
    ``depth2_value_for_mega_context`` unit test (see
    ``test_depth2_value_for_mega_context_binds_to_matching_context_never_another``
    above) is NOT sufficient -- that helper existing and being unit-tested in
    isolation, with zero real callers, is exactly the Codex I7a-B merge-blocker
    this test guards against."""
    import showdown_bot.battle.mega_scoring as mega_scoring_mod
    from showdown_bot.battle.decision import _choose_best

    for var in ("SHOWDOWN_SEARCH_TOPN", "SHOWDOWN_SEARCH_TOPM", "SHOWDOWN_WORLD_SAMPLES"):
        monkeypatch.delenv(var, raising=False)

    def _fresh_req_state():
        req = _build_req(
            a_species="Aerodactyl", a_item="Aerodactylite", a_moves=["Tackle", "Pound"],
            a_can_mega=True, b_species="Whimsicott", b_moves=["Moonblast"],
        )
        state = _build_state("Aerodactyl", "Aerodactylite", "Whimsicott", "Incineroar")
        return req, state

    spreads = {
        "aerodactyl": aerodactyl_spreads, "whimsicott": aerodactyl_spreads,
        "incineroar": aerodactyl_spreads,
    }
    book = SpreadBook(default=aerodactyl_spreads)
    calc = _T17Calc()
    real_score_evaluated_variants = mega_scoring_mod.score_evaluated_variants

    def _run(*, capture: dict | None, depth2_spy=None):
        if depth2_spy is not None:
            monkeypatch.setattr(mega_scoring_mod, "depth2_value_for_mega_context", depth2_spy)
        if capture is not None:
            def _capturing(*a, **k):
                records = real_score_evaluated_variants(*a, **k)
                capture.update({r.variant.joint: list(r.score_vector) for r in records})
                return records
            monkeypatch.setattr(mega_scoring_mod, "score_evaluated_variants", _capturing)
        req, state = _fresh_req_state()
        result = _choose_best(
            req, state=state, book=book, our_side="p1", calc=calc,
            oracle=DamageOracle(calc), speed_oracle=speed_oracle, dex=None,
            our_spreads=spreads, format_config=_champions_mega_cfg(), risk_lambda=0.0,
        )
        monkeypatch.setattr(mega_scoring_mod, "score_evaluated_variants", real_score_evaluated_variants)
        return result

    # --- baseline: depth=1, capture every candidate's 1-ply score vector ---
    monkeypatch.delenv("SHOWDOWN_SEARCH_DEPTH", raising=False)
    baseline_records: dict = {}
    _run(capture=baseline_records)

    # --- depth=2 run: spy on depth2_value_for_mega_context + capture final vectors ---
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    calls = []
    import showdown_bot.battle.search as search_mod
    real_d2 = search_mod.depth2_value_for_mega_context

    def _spy(*a, **k):
        calls.append((a, k))
        return real_d2(*a, **k)

    d2_records: dict = {}
    best_ja, best_val = _run(capture=d2_records, depth2_spy=_spy)

    assert calls, "depth2_value_for_mega_context was never invoked from the real decision path"
    import math
    assert math.isfinite(best_val)
    assert best_ja in d2_records

    # Frontier bound: exactly N(=2, default SHOWDOWN_SEARCH_TOPN) records get
    # refined, each contributing at most M(=2, default SHOWDOWN_SEARCH_TOPM)
    # depth2_value_for_mega_context calls.
    changed = {ja for ja, vec in d2_records.items() if vec != baseline_records.get(ja)}
    assert 0 < len(changed) <= 2
    assert len(calls) <= 4
    assert len(calls) >= len(changed)

    # At least one non-selected candidate's vector is byte-unchanged from its
    # 1-ply baseline value (the depth-2 wrap must not touch every candidate).
    unselected = [ja for ja in d2_records if ja not in changed]
    assert unselected, "expected at least one candidate left outside the depth-2 frontier"
    for ja in unselected:
        assert d2_records[ja] == baseline_records[ja]


def test_choose_best_mega_depth2_suppressed_when_world_sampling_active(
    speed_oracle, aerodactyl_spreads, calc_profile, monkeypatch,
):
    """INV-orthogonal (mirrors the non-Mega
    ``test_depth2_suppressed_when_world_sampling_active``): the Mega depth-2
    wrap is guarded by ``world_samples() <= 1``, so with
    ``SHOWDOWN_WORLD_SAMPLES=2`` it must NOT run even when
    ``SHOWDOWN_SEARCH_DEPTH=2`` -- the K-world +Sampling path owns that turn."""
    import showdown_bot.battle.mega_scoring as mega_scoring_mod
    from showdown_bot.battle.decision import _choose_best

    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "2")

    calls = []
    monkeypatch.setattr(
        mega_scoring_mod, "depth2_value_for_mega_context",
        lambda *a, **k: (calls.append(1), -1.0)[1],
    )

    req = _build_req(
        a_species="Aerodactyl", a_item="Aerodactylite", a_moves=["Tackle", "Pound"],
        a_can_mega=True, b_species="Whimsicott", b_moves=["Moonblast"],
    )
    state = _build_state("Aerodactyl", "Aerodactylite", "Whimsicott", "Incineroar")
    spreads = {
        "aerodactyl": aerodactyl_spreads, "whimsicott": aerodactyl_spreads,
        "incineroar": aerodactyl_spreads,
    }
    book = SpreadBook(default=aerodactyl_spreads)
    calc = _T17Calc()

    best_ja, best_val = _choose_best(
        req, state=state, book=book, our_side="p1", calc=calc,
        oracle=DamageOracle(calc), speed_oracle=speed_oracle, dex=None,
        our_spreads=spreads, format_config=_champions_mega_cfg(), risk_lambda=0.0,
    )

    assert calls == []
    import math
    assert math.isfinite(best_val)


class _TieCalc:
    """Fully controlled damage table for the Codex I7a-B merge-blocker
    regression: variant order preservation. ``Aerodactyl-Mega``'s Tackle
    is deliberately pinned to the SAME (min, max) table entry as base
    ``Aerodactyl``'s Pound, so ``A+Mega`` (Tackle, own_mega_slot=0) and
    ``B`` (Pound, own_mega_slot=None) score EXACTLY equal -- a genuine tie,
    not an approximate one. In the true ``expand_mega_variants`` order the
    joints come out interleaved per base joint: ``[A, A+Mega, B, B+Mega]``
    (A's own Mega variant is enumerated immediately after A, before B), so
    the strict first-wins tie-break must pick ``A+Mega``. A buggy
    "grouped by own_mega_slot" reconstruction would instead see
    ``[A, B, A+Mega, B+Mega]`` (every non-Mega variant first, then every
    Mega variant) and pick ``B`` instead -- exactly the bug this test
    guards against."""

    backend = None
    _TABLE = {
        ("Aerodactyl", "Tackle"): (20, 25),         # A base: deliberately the WEAKEST
        ("Aerodactyl", "Pound"): (90, 97),          # B base -- the tie value
        ("Aerodactyl-Mega", "Tackle"): (90, 97),    # A+Mega -- SAME table as B base
        ("Aerodactyl-Mega", "Pound"): (50, 55),     # B+Mega: below the tie, never wins
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


def _tie_break_fixture(speed_oracle, aerodactyl_spreads, calc_profile):
    req = _build_req(
        a_species="Aerodactyl", a_item="Aerodactylite", a_moves=["Tackle", "Pound"],
        a_can_mega=True, b_species="Whimsicott", b_moves=["Moonblast"],
    )
    state = _build_state("Aerodactyl", "Aerodactylite", "Whimsicott", "Incineroar")
    spreads = {
        "aerodactyl": aerodactyl_spreads, "whimsicott": aerodactyl_spreads,
        "incineroar": aerodactyl_spreads,
    }
    book = SpreadBook(default=aerodactyl_spreads)
    calc = _TieCalc()
    return req, state, spreads, book, calc


def test_choose_best_mega_tie_break_prefers_expand_order_a_mega_beats_b(
    speed_oracle, aerodactyl_spreads, calc_profile,
):
    """Codex merge-blocker regression (variant order preservation): on a
    genuine tie between A+Mega and B, the decision must pick A+Mega -- the
    winner determined by expand_mega_variants' own interleaved enumeration
    order, never a grouped-by-own_mega_slot reconstruction. Driven through
    the real ``_choose_best`` -> ``_choose_best_mega`` production path."""
    from showdown_bot.battle.decision import _choose_best
    from showdown_bot.battle.evaluate import EvalWeights
    from showdown_bot.engine.belief.game_mode import GameMode

    req, state, spreads, book, calc = _tie_break_fixture(speed_oracle, aerodactyl_spreads, calc_profile)

    # Independently recompute the two records to prove the tie is genuine
    # (not "A+Mega just happens to score higher") before trusting the
    # decision's winner selection.
    my_actions = enumerate_my_actions(req)
    verify_oracle = DamageOracle(calc)
    contexts, evaluated = build_own_mega_contexts(
        req, state, our_side="p1", opp_side="p2", book=book, oracle=verify_oracle,
        speed_oracle=speed_oracle, species_meta=species_meta_table(),
        our_spreads=spreads, opp_sets=None, calc_profile=calc_profile,
        my_actions=my_actions,
    )
    records = score_evaluated_variants(
        evaluated, contexts, req=req, state=state, book=book, our_side="p1",
        opp_side="p2", calc=calc, oracle=verify_oracle, speed_oracle=speed_oracle,
        dex=None, priors=None, weights=EvalWeights(), mode=GameMode.NEUTRAL,
        risk_lambda=0.0, rollout_horizon=0, our_spreads=spreads, opp_sets=None,
        calc_profile=calc_profile, accuracy_mode=False, accuracy_branch_cap=6,
        endgame=False, fast_board=False,
    )

    def _rec_for(move_name: str, mega_slot):
        for r in records:
            if r.variant.own_mega_slot != mega_slot:
                continue
            idx = r.variant.joint.slot0.move_index
            if idx and req.active[0].moves[idx - 1].move == move_name:
                return r
        raise AssertionError(f"no record for move={move_name!r} mega_slot={mega_slot!r}")

    a_mega = _rec_for("Tackle", 0)
    b_base = _rec_for("Pound", None)
    a_base = _rec_for("Tackle", None)
    b_mega = _rec_for("Pound", 0)

    # Precondition: a genuine, exact tie -- and A+Mega/B both strictly beat
    # the other two candidates (so the tie-break, not a raw score difference,
    # is what decides the winner).
    assert a_mega.aggregate_score == b_base.aggregate_score
    assert a_mega.aggregate_score > a_base.aggregate_score
    assert a_mega.aggregate_score > b_mega.aggregate_score

    # Precondition: evaluated_variants really is the interleaved expand
    # order (A+Mega before B), not grouped by own_mega_slot.
    idx_a_mega = evaluated.index(a_mega.variant)
    idx_b_base = evaluated.index(b_base.variant)
    assert idx_a_mega < idx_b_base

    # The real decision must pick A+Mega.
    best_ja, _best_val = _choose_best(
        req, state=state, book=book, our_side="p1", calc=calc,
        oracle=DamageOracle(calc), speed_oracle=speed_oracle, dex=None,
        our_spreads=spreads, format_config=_champions_mega_cfg(), risk_lambda=0.0,
    )
    assert best_ja.slot0.mega_evolve is True
    chosen_move = req.active[0].moves[best_ja.slot0.move_index - 1].move
    assert chosen_move == "Tackle"


def _champions_mega_cfg():
    from showdown_bot.engine.format_config import load_format_config

    return load_format_config("gen9championsvgc2026regma")


def test_max_damage_choice_mega_iterates_evaluated_variants_order_not_contexts_grouping(
    speed_oracle, aerodactyl_spreads, calc_profile, monkeypatch,
):
    """Same Codex merge-blocker regression for the ``max_damage`` baseline's
    Mega branch, via a spy/instrumented ``build_own_mega_contexts`` double
    rather than a real controlled-damage tie.

    A REAL end-to-end A+Mega vs B tie through ``_max_damage_choice_mega``
    driven by a real spread lookup is exercised separately by
    ``test_max_damage_choice_threads_our_spreads_lets_legal_mega_context_survive_and_win``
    below (the ``our_spreads`` threading gap this docstring used to describe
    -- "Fix #2" -- is closed; that test proves a Mega context now survives
    ``filter_projectable_variants`` and can win on damage).

    This test proves the narrower, still load-bearing claim directly:
    ``_max_damage_choice_mega`` walks ``build_own_mega_contexts``'s returned
    ``evaluated_variants`` list in order (never a
    contexts-grouped-by-``own_mega_slot`` reconstruction) by faking that
    return value with a genuine tie whose winner depends on which order is
    used, then asserting the real function picks the tie-breaking winner
    that the TRUE expand order (A, A+Mega, B, B+Mega) implies -- A+Mega --
    not the winner a grouped-by-slot order (A, B, A+Mega, B+Mega) would
    imply -- B.
    """
    import showdown_bot.battle.mega_scoring as mega_scoring_mod
    from showdown_bot.battle.baselines import _max_damage_choice_mega
    from showdown_bot.battle.resolve import PlannedAction
    from showdown_bot.engine.moves import get_move_meta
    from showdown_bot.models.actions import SlotAction

    def _joint(tag: int, *, mega: bool) -> JointAction:
        return JointAction(
            slot0=SlotAction(kind="move", move_index=1, target=tag, mega_evolve=mega),
            slot1=SlotAction(kind="pass"),
        )

    ja_a = _joint(1, mega=False)        # A (base) -- lowest, sets an initial best
    ja_a_mega = _joint(2, mega=True)    # A+Mega -- tied top score, FIRST in true expand order
    ja_b = _joint(3, mega=False)        # B (base) -- tied top score, AFTER A+Mega in true order
    ja_b_mega = _joint(4, mega=True)    # B+Mega -- below the tie, never wins

    by_action_id: dict[int, float] = {}

    class _FakeDamageModel:
        def damage_fn(self, action, _target_mon):
            return by_action_id.get(id(action), 0.0)

    fake_model = _FakeDamageModel()

    def _plan_for(score: float):
        atk = PlannedAction(
            "p1", "a", "move", speed=100, move=get_move_meta("Tackle"),
            target=("p2", "a"), is_ours=True,
        )
        by_action_id[id(atk)] = score
        return [atk, PlannedAction("p1", "b", "pass", speed=100, is_ours=True)]

    st = _basic_state()
    none_ctx = MegaEvaluationContext(
        context_id="own_mega:none", projected_state=st, own_mega_slot=None,
        foe_mega_slot=None, branch_weight=1.0, activation_order=None, field=st.field,
        plans={ja_a: _plan_for(0.2), ja_b: _plan_for(0.9)}, damage_model=fake_model,
    )
    mega_ctx = MegaEvaluationContext(
        context_id="own_mega:0", projected_state=st, own_mega_slot=0,
        foe_mega_slot=None, branch_weight=1.0, activation_order=None, field=st.field,
        plans={ja_a_mega: _plan_for(0.9), ja_b_mega: _plan_for(0.5)}, damage_model=fake_model,
    )
    fake_contexts = [none_ctx, mega_ctx]
    fake_evaluated = [
        ScoredMegaVariant(joint=ja_a, own_mega_slot=None),
        ScoredMegaVariant(joint=ja_a_mega, own_mega_slot=0),
        ScoredMegaVariant(joint=ja_b, own_mega_slot=None),
        ScoredMegaVariant(joint=ja_b_mega, own_mega_slot=0),
    ]

    monkeypatch.setattr(
        mega_scoring_mod, "build_own_mega_contexts",
        lambda *a, **k: (fake_contexts, fake_evaluated),
    )

    req = _build_req(
        a_species="Aerodactyl", a_item="Aerodactylite", a_moves=["Tackle"],
        a_can_mega=True, b_species="Whimsicott", b_moves=["Moonblast"],
    )

    def _no_fallback(_req):
        raise AssertionError("max_damage tie-break test must not hit the fallback path")

    class _FlushOnlyOracle:
        def flush(self):
            pass

    out = _max_damage_choice_mega(
        req, state=st, book=None, our_side="p1", opp_side="p2",
        oracle=_FlushOnlyOracle(), speed_oracle=speed_oracle, calc_profile=calc_profile,
        my_actions=[ja_a, ja_b], fallback=_no_fallback,
    )

    slot0_part = out[len("/choose "):].split(", ")[0]
    assert slot0_part.startswith("move 1 2"), out  # ja_a_mega's tag=2
    assert "mega" in slot0_part, out


class _BigMegaCalc:
    """Aerodactyl-Mega's Tackle deals dramatically more damage than base
    Aerodactyl's Tackle -- a pure-outgoing-damage baseline (max_damage never
    weighs incoming damage) MUST pick the Mega variant once its context
    actually exists in the evaluated set."""

    backend = None
    _TABLE = {
        ("Aerodactyl", "Tackle"): (20, 25),
        ("Aerodactyl-Mega", "Tackle"): (140, 150),
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


def test_max_damage_choice_threads_our_spreads_lets_legal_mega_context_survive_and_win(
    speed_oracle, aerodactyl_spreads, calc_profile,
):
    """I7a-B Task 2: ``max_damage_choice`` must accept ``our_spreads``
    explicitly and thread it all the way into
    ``build_own_mega_contexts``/``_max_damage_choice_mega`` (never hardcode
    ``our_spreads=None``) -- otherwise ``project_mega`` always raises
    ``MissingMegaSpreadError`` and ``filter_projectable_variants`` fail-closes
    every own-Mega variant before any scoring happens, so a Mega candidate
    can never even exist in the evaluated set, regardless of how much more
    damage it would deal (Codex I7a-B merge-blocker #2).

    Counterexample: Aerodactyl-Mega's Tackle deals ~5x base Aerodactyl's
    Tackle. With ``our_spreads`` correctly threaded through, a legal Mega
    context survives ``filter_projectable_variants`` and wins on pure
    outgoing damage. Without it (``our_spreads=None``), the Mega candidate
    never exists at all and the baseline is stuck on the base action despite
    it doing far less damage -- proving the gap this fix closes, not just
    the fixed behavior in isolation.
    """
    from showdown_bot.battle.baselines import max_damage_choice

    req = _build_req(
        a_species="Aerodactyl", a_item="Aerodactylite", a_moves=["Tackle"],
        a_can_mega=True, b_species="Whimsicott", b_moves=["Moonblast"],
    )
    state = _build_state("Aerodactyl", "Aerodactylite", "Whimsicott", "Incineroar")
    spreads = {
        "aerodactyl": aerodactyl_spreads, "whimsicott": aerodactyl_spreads,
        "incineroar": aerodactyl_spreads,
    }
    book = SpreadBook(default=aerodactyl_spreads)
    calc = _BigMegaCalc()

    out = max_damage_choice(
        req, state=state, book=book, our_side="p1", calc=calc,
        oracle=DamageOracle(calc), speed_oracle=speed_oracle,
        our_spreads=spreads, format_config=_champions_mega_cfg(),
    )
    slot0_part = out[len("/choose "):].split(", ")[0]
    assert "mega" in slot0_part, out

    # Counterexample: without our_spreads threaded, the Mega candidate never
    # exists (MissingMegaSpreadError fail-closes it out upstream) -- the
    # baseline is stuck on the base action despite it doing far less damage.
    out_no_spreads = max_damage_choice(
        req, state=state, book=book, our_side="p1", calc=calc,
        oracle=DamageOracle(calc), speed_oracle=speed_oracle,
        our_spreads=None, format_config=_champions_mega_cfg(),
    )
    slot0_no_spreads = out_no_spreads[len("/choose "):].split(", ")[0]
    assert "mega" not in slot0_no_spreads, out_no_spreads


class _T31Speed:
    """Self-contained speed stub (no subprocess): Scovillain's ability fails
    closed inside project_mega before any real speed lookup would matter."""

    def __init__(self, profile):
        self.profile = profile

    def our_speed(self, base, mon, field, side):
        return base or 100

    def opponent_range(self, mon, field, side, *, book):
        from showdown_bot.engine.speed import SpeedRange

        return SpeedRange(min=80, likely=110, max=150)


class _T31Calc:
    """Non-KO damage regardless of request (keeps game_mode NEUTRAL) -- T31
    only cares about which action is chosen, not damage numbers."""

    backend = None

    def damage_batch(self, requests):
        from showdown_bot.engine.calc.models import DamageResult

        return [DamageResult(min_damage=20, max_damage=35, max_hp=150) for _ in requests]


def test_t31_scovillain_mega_path_unavailable_not_silent_base_scoring(
    scovillain_mega_request, champions_cfg, calc_profile, aerodactyl_spreads,
):
    """T31 (design spec Sec.11.3): the default hero's Scovillainite must show
    the Scovillain-Mega path as UNAVAILABLE (fail-closed, Spicy Spray is
    unsupported) -- not silently scored as if it were a normal base-form
    action. Scovillain's active slot is looked up from state.side(our_side)
    rather than hardcoded, so this holds regardless of which slot it's in."""
    from showdown_bot.battle.decision import _choose_best
    from showdown_bot.battle.mega_variants import expand_mega_variants
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

    scovillain_slot = next(
        slot for slot, mon in state.side("p1").items()
        if mon is not None and mon.species == "Scovillain"
    )
    assert scovillain_slot == "a"

    base_joints = enumerate_my_actions(scovillain_mega_request)
    raw_variants = expand_mega_variants(base_joints, scovillain_mega_request, state, "p1")
    assert any(v.own_mega_slot == 0 for v in raw_variants), "raw Mega variant must exist"

    book = SpreadBook(default=aerodactyl_spreads)
    spreads = {
        "scovillain": aerodactyl_spreads, "whimsicott": aerodactyl_spreads,
        "incineroar": aerodactyl_spreads,
    }
    calc = _T31Calc()
    oracle = DamageOracle(calc)
    speed_oracle = _T31Speed(calc_profile)

    best_ja, _best_val = _choose_best(
        scovillain_mega_request,
        state=state, book=book, our_side="p1", calc=calc, oracle=oracle,
        speed_oracle=speed_oracle, dex=None, our_spreads=spreads,
        format_config=champions_cfg, risk_lambda=0.0,
    )

    assert best_ja.slot0.mega_evolve is False
    assert best_ja.slot1.mega_evolve is False
