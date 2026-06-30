from __future__ import annotations

from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.engine.calc.models import CalcMon, DamageRequest, DamageResult


class FakeClient:
    """Stand-in CalcClient that counts batch calls and returns deterministic
    results keyed by request order."""

    def __init__(self):
        self.batch_calls = 0
        self.total_requests = 0

    def damage_batch(self, requests):
        self.batch_calls += 1
        self.total_requests += len(requests)
        out = []
        for r in requests:
            out.append(
                DamageResult(
                    rolls=[100] * 16, min_damage=100, max_damage=100, max_hp=200, id=r.id
                )
            )
        return out


def _req(move="Moonblast", defender_item=None):
    return DamageRequest(
        attacker=CalcMon(species="Flutter Mane", move=move),
        defender=CalcMon(species="Incineroar", item=defender_item),
        move=move,
    )


def test_dedupes_identical_requests():
    oracle = DamageOracle(client=FakeClient())
    k1 = oracle.request(_req())
    k2 = oracle.request(_req())
    assert k1 == k2
    assert len(oracle._pending) == 1


def test_single_batch_per_turn():
    fake = FakeClient()
    oracle = DamageOracle(client=fake)
    keys = [
        oracle.request(_req("Moonblast")),
        oracle.request(_req("Shadow Ball")),
        oracle.request(_req("Moonblast")),  # dup
    ]
    oracle.flush()
    assert fake.batch_calls == 1
    assert fake.total_requests == 2  # dup collapsed
    for k in keys:
        assert oracle.get(k).max_hp == 200


def test_get_autoflushes():
    fake = FakeClient()
    oracle = DamageOracle(client=fake)
    k = oracle.request(_req())
    res = oracle.get(k)  # triggers flush
    assert res.min_damage == 100
    assert fake.batch_calls == 1


def test_distinct_field_makes_distinct_key():
    oracle = DamageOracle(client=FakeClient())
    a = _req()
    b = _req(defender_item="Assault Vest")  # changes defender payload
    assert oracle._key(a) != oracle._key(b)


def test_cached_results_no_extra_batch():
    fake = FakeClient()
    oracle = DamageOracle(client=fake)
    k = oracle.request(_req())
    oracle.flush()
    # second request of same calc should hit cache, not re-enqueue
    k2 = oracle.request(_req())
    assert k == k2
    assert len(oracle._pending) == 0
    oracle.get(k2)
    assert fake.batch_calls == 1


# --- prefetch guarantees a single batch even with spread/redirect/retarget ---

def _twov2_state():
    from showdown_bot.engine.state import BattleState, PokemonState

    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=100, max_hp=100)
    st.sides["p2"]["b"] = PokemonState(species="Amoonguss", hp=100, max_hp=100)
    return st


def _model_with_real_oracle(st):
    from showdown_bot.battle.evaluate import DamageModel
    from showdown_bot.engine.belief.hypotheses import load_spread_book
    from showdown_bot.engine.format_config import load_format_config

    cfg = load_format_config("gen9vgc2025regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    oracle = DamageOracle(client=FakeClient())
    model = DamageModel(st, "p1", "p2", book=book, oracle=oracle)
    return model, oracle


def test_prefetch_covers_spread_move_single_batch():
    from showdown_bot.battle.resolve import PlannedAction, resolve_turn
    from showdown_bot.engine.moves import get_move_meta

    st = _twov2_state()
    model, oracle = _model_with_real_oracle(st)
    heat = get_move_meta("Heat Wave")  # allAdjacentFoes -> hits p2a AND p2b
    a = PlannedAction("p1", "a", "move", speed=100, move=heat, target=("p2", "a"), is_ours=True)

    model.prefetch([[a]])
    assert oracle.batch_calls == 1

    out = resolve_turn(st, [a], model.damage_fn, our_side="p1")
    # second foe slot resolved without forcing a new Node round trip
    assert oracle.batch_calls == 1
    assert out.hp_delta[("p2", "a")] < 0
    assert out.hp_delta[("p2", "b")] < 0


def test_prefetch_covers_redirect_single_batch():
    from showdown_bot.battle.resolve import PlannedAction, resolve_turn
    from showdown_bot.engine.moves import get_move_meta

    st = _twov2_state()
    model, oracle = _model_with_real_oracle(st)
    moon = get_move_meta("Moonblast")
    rage = get_move_meta("Rage Powder")
    mine = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)
    redir = PlannedAction("p2", "b", "move", speed=150, move=rage, is_ours=False)

    model.prefetch([[mine], [redir]])
    assert oracle.batch_calls == 1

    out = resolve_turn(st, [mine, redir], model.damage_fn, our_side="p1")
    assert oracle.batch_calls == 1  # redirected target p2b was prefetched
    assert any(r.new_target == ("p2", "b") for r in out.redirected_hits)


def test_prefetch_covers_retarget_single_batch():
    from showdown_bot.battle.resolve import PlannedAction, resolve_turn
    from showdown_bot.engine.moves import get_move_meta

    st = _twov2_state()
    st.sides["p2"]["a"].fainted = True  # original target gone -> must retarget to p2b
    model, oracle = _model_with_real_oracle(st)
    moon = get_move_meta("Moonblast")
    mine = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)

    model.prefetch([[mine]])
    assert oracle.batch_calls == 1

    out = resolve_turn(st, [mine], model.damage_fn, our_side="p1")
    assert oracle.batch_calls == 1  # retargeted slot p2b was prefetched
    assert "retarget" in out.flags
