from showdown_bot.models.request import BattleRequest

_BASE = {
    "rqid": 1,
    "side": {"name": "P1", "id": "p1", "pokemon": [
        {"ident": "p1: Landorus", "details": "Landorus-Therian, L50, M",
         "condition": "179/179", "active": True,
         "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
         "moves": ["earthpower"], "baseTypes": ["Ground", "Flying"], "item": "choicescarf"},
    ]},
}


def test_item_present_nonempty():
    req = BattleRequest.model_validate(_BASE)
    assert req.side.pokemon[0].item == "choicescarf"


def test_item_present_empty_vs_missing():
    empty = {**_BASE, "side": {**_BASE["side"], "pokemon": [{**_BASE["side"]["pokemon"][0], "item": ""}]}}
    missing = {**_BASE, "side": {**_BASE["side"], "pokemon": [{k: v for k, v in _BASE["side"]["pokemon"][0].items() if k != "item"}]}}
    assert BattleRequest.model_validate(empty).side.pokemon[0].item == ""      # present-empty
    assert BattleRequest.model_validate(missing).side.pokemon[0].item is None  # missing
