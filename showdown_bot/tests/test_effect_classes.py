import json
from pathlib import Path

import yaml

from showdown_bot.engine.moves import get_move_meta

CONFIG = Path(__file__).resolve().parents[1] / "config"

KNOWN_CLASSES = {
    "speed_control",
    "status_infliction",
    "setup_self",
    "debuff_foe",
    "protect",
    "redirect",
    "pivot",
    "field_setter",
    "disruption",
    "recovery",
    "damage_modifier",
    "volatile_inflict",
}


def _effect_classes() -> dict:
    return yaml.safe_load((CONFIG / "moves" / "effect_classes.yaml").read_text(encoding="utf-8"))


def test_effect_classes_reference_real_moves_and_known_classes():
    """Schema guard: every curated id exists in movedata, every class is known."""
    data = json.loads((CONFIG / "moves" / "movedata.json").read_text(encoding="utf-8"))["moves"]
    ec = _effect_classes()
    for mid, entry in ec.items():
        assert mid in data, f"effect_classes.yaml references unknown move id: {mid}"
        classes = entry.get("classes", [])
        assert isinstance(classes, list), f"{mid}: classes must be a list"
        for c in classes:
            assert c in KNOWN_CLASSES, f"{mid}: unknown effect class {c!r}"


def test_move_meta_carries_effect_classes():
    tw = get_move_meta("Tailwind")
    assert "speed_control" in tw.effect_classes
    assert tw.effect_params.get("duration") == 4
    wow = get_move_meta("Will-O-Wisp")
    assert "status_infliction" in wow.effect_classes
    assert wow.effect_params.get("status") == "brn"
    # unlisted move -> no semantic class, but still valid raw mechanics
    tackle = get_move_meta("Tackle")
    assert tackle.effect_classes == ()
