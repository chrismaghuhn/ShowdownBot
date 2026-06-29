import json
from pathlib import Path

import yaml

from showdown_bot.engine.items import get_item_meta

CONFIG = Path(__file__).resolve().parents[1] / "config"

KNOWN_ITEM_CLASSES = {
    "residual_heal",
    "threshold_heal",
    "status_cure",
    "pinch_trigger",
    "speed",
    "damage_stat",
    "residual_self",
    "activation_item",
    "effect_block",
    "contact_punish",
}


def test_item_meta_classes():
    lo = get_item_meta("Life Orb")
    assert "damage_stat" in lo.classes
    assert lo.params.get("recoil") == 0.1
    s = get_item_meta("Sitrus Berry")
    assert "threshold_heal" in s.classes
    assert s.params["frac"] == 0.25
    assert s.is_berry
    sc = get_item_meta("Choice Scarf")
    assert "speed" in sc.classes
    assert sc.params["mult"] == 1.5
    assert sc.is_choice


def test_unknown_item_has_no_classes():
    m = get_item_meta("Nonexistent Item")
    assert m.classes == ()


def test_item_effect_classes_schema():
    items = json.loads((CONFIG / "items" / "itemdata.json").read_text(encoding="utf-8"))["items"]
    ec = yaml.safe_load((CONFIG / "items" / "item_effect_classes.yaml").read_text(encoding="utf-8"))
    for iid, entry in ec.items():
        assert iid in items, f"item_effect_classes.yaml references unknown item id: {iid}"
        for c in entry.get("classes", []):
            assert c in KNOWN_ITEM_CLASSES, f"{iid}: unknown item class {c!r}"
