import json
from dataclasses import asdict

from showdown_bot.engine.conditions import ConditionInstance, ConditionState, MonConditions
from showdown_bot.battle.rollout import (
    RolloutActor,
    RolloutBudget,
    rollout,
)

A = ("p1", "a")
B = ("p2", "a")


def test_rollout_horizon_zero_is_noop():
    """Additivity hook (spec I-7): H=0 contributes nothing."""
    res = rollout([], ConditionState(), {A: 1.0, B: 1.0}, our_side="p1",
                  budget=RolloutBudget(horizon=0))
    assert res.value == 0.0
    assert res.trace == []


def test_burn_residual_accumulates_as_value():
    cs = ConditionState(mons={B: MonConditions(status="brn")})
    res = rollout([], cs, {A: 1.0, B: 1.0}, our_side="p1",
                  budget=RolloutBudget(horizon=2, gamma=0.7))
    # opponent burned -> chips 1/16 per turn -> positive value for us (dmg dealt)
    assert res.value > 0
    assert abs(res.final_hp[B] - (1.0 - 2 / 16)) < 1e-9
    assert len(res.trace) == 2
    # caller's inputs are not mutated (rollout is a lookahead)
    assert cs.mons[B].status == "brn"


def test_rollout_does_not_mutate_caller_hp():
    hp = {A: 1.0, B: 1.0}
    cs = ConditionState(mons={A: MonConditions(status="brn")})
    rollout([], cs, hp, our_side="p1", budget=RolloutBudget(horizon=2))
    assert hp == {A: 1.0, B: 1.0}


def test_tailwind_speed_flip_secures_ko_before_act():
    """The spec's core claim: Tailwind's value is emergent. Same actors, only
    the condition state differs; the speed flip lets our slower mon KO first."""
    actors = [
        RolloutActor(key=A, target=B, base_damage=1.0, base_speed=80, category="physical"),
        RolloutActor(key=B, target=A, base_damage=1.0, base_speed=100, category="physical"),
    ]
    no_tw = rollout(actors, ConditionState(), {A: 1.0, B: 1.0}, our_side="p1",
                    budget=RolloutBudget(horizon=1))
    tw = ConditionState(sides={"p1": {"tailwind": ConditionInstance("tailwind", 4)}})
    with_tw = rollout(actors, tw, {A: 1.0, B: 1.0}, our_side="p1",
                      budget=RolloutBudget(horizon=1))

    assert with_tw.value > no_tw.value
    assert B in with_tw.trace[0].kos      # tailwind: we KO the opponent first
    assert A in no_tw.trace[0].kos        # no tailwind: our mon faints first


def test_paralysis_scales_expected_damage():
    actor = RolloutActor(key=A, target=B, base_damage=0.4, base_speed=100, category="physical")
    healthy = rollout([actor], ConditionState(), {A: 1.0, B: 1.0}, our_side="p1",
                      budget=RolloutBudget(horizon=1))
    par = ConditionState(mons={A: MonConditions(status="par")})
    paralyzed = rollout([actor], par, {A: 1.0, B: 1.0}, our_side="p1",
                        budget=RolloutBudget(horizon=1))
    assert abs(healthy.final_hp[B] - 0.6) < 1e-9          # full 0.4 hit
    assert abs(paralyzed.final_hp[B] - 0.7) < 1e-9         # 0.75 * 0.4 = 0.3 expected


def test_rollout_deterministic():
    def actors():
        return [
            RolloutActor(A, B, 0.3, 100, "physical"),
            RolloutActor(B, A, 0.25, 90, "physical"),
        ]

    def cs():
        return ConditionState(mons={A: MonConditions(status="brn")})

    r1 = rollout(actors(), cs(), {A: 1.0, B: 1.0}, our_side="p1", budget=RolloutBudget(horizon=3))
    r2 = rollout(actors(), cs(), {A: 1.0, B: 1.0}, our_side="p1", budget=RolloutBudget(horizon=3))
    assert r1.value == r2.value
    assert [t.hp for t in r1.trace] == [t.hp for t in r2.trace]


def test_rollout_trace_is_json_serializable():
    res = rollout(
        [RolloutActor(A, B, 0.5, 100)],
        ConditionState(mons={B: MonConditions(status="brn")}),
        {A: 1.0, B: 1.0},
        our_side="p1",
        budget=RolloutBudget(horizon=2),
    )
    payload = json.dumps([asdict(t) for t in res.trace])
    assert "score" in payload and "turn" in payload
