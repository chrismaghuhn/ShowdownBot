from __future__ import annotations

import copy
import json

import pytest

from showdown_bot.engine import items as items_mod
from showdown_bot.engine import species_meta as species_meta_mod
from showdown_bot.engine.items import ItemMeta, _item_table, get_item_meta, to_id
from showdown_bot.engine.mega_form import mega_form_for
from showdown_bot.engine.species_meta import (
    SpeciesMetaStaleError,
    get_species_form_meta,
    species_meta_table,
)
from showdown_bot.engine.state import PokemonState
from showdown_bot.engine.spread_lookup import lookup_our_spreads, spread_lookup_key


# ---------------------------------------------------------------------------
# Task 2: metadata loaders, form resolution, hash verification
# ---------------------------------------------------------------------------


def test_charizardite_y_mega_stone_metadata():
    meta = get_item_meta("Charizardite Y")
    assert meta.mega_stone == {"charizard": "Charizard-Mega-Y"}


def test_mega_form_for_charizard_y():
    form = mega_form_for("Charizard", "Charizardite Y")
    assert form is not None
    assert form.base_species_id == "charizard"
    assert form.form_species_id == "charizardmegay"
    assert form.form_species_name == "Charizard-Mega-Y"
    assert form.stone_item_id == "charizarditey"


def test_mega_form_for_wrong_base_species_returns_none():
    assert mega_form_for("Blastoise", "Charizardite Y") is None


def test_tatsugirinite_preserves_all_base_form_mappings():
    meta = get_item_meta("Tatsugirinite")
    assert meta.mega_stone == {
        "tatsugiri": "Tatsugiri-Curly-Mega",
        "tatsugiridroopy": "Tatsugiri-Droopy-Mega",
        "tatsugiristretchy": "Tatsugiri-Stretchy-Mega",
    }
    assert mega_form_for("Tatsugiri", "Tatsugirinite").form_species_name == "Tatsugiri-Curly-Mega"
    assert mega_form_for("Tatsugiri-Droopy", "Tatsugirinite").form_species_name == "Tatsugiri-Droopy-Mega"
    assert mega_form_for("Tatsugiri-Stretchy", "Tatsugirinite").form_species_name == "Tatsugiri-Stretchy-Mega"


def test_get_species_form_meta_charizard_mega_y():
    form = get_species_form_meta("Charizard-Mega-Y")
    assert form is not None
    assert form.base_species_name == "Charizard"
    assert form.ability_slot0 == "Drought"
    assert form.types == ("Fire", "Flying")


def test_itemdata_stale_hash_raises_after_cache_clear(tmp_path, monkeypatch):
    raw = json.loads(items_mod._ITEMDATA.read_text(encoding="utf-8"))
    raw["data_hash"] = "deadbeef00000000"
    p = tmp_path / "itemdata.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(items_mod, "_ITEMDATA", p)
    _item_table.cache_clear()
    with pytest.raises(items_mod.ItemdataStaleError):
        _item_table()


def test_speciesdata_stale_hash_raises_after_cache_clear(tmp_path, monkeypatch):
    raw = json.loads(species_meta_mod._SPECIESDATA.read_text(encoding="utf-8"))
    raw["data_hash"] = "deadbeef00000000"
    p = tmp_path / "speciesdata.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(species_meta_mod, "_SPECIESDATA", p)
    species_meta_mod.species_meta_table.cache_clear()
    with pytest.raises(SpeciesMetaStaleError):
        species_meta_mod.species_meta_table()


# ---------------------------------------------------------------------------
# Task 3: base_species_id spread identity
# ---------------------------------------------------------------------------


def test_projected_species_uses_base_species_spread_key():
    mon = PokemonState(species="Aerodactyl-Mega", base_species_id="aerodactyl")
    spreads = {"aerodactyl": object(), "Aerodactyl": object()}
    assert lookup_our_spreads(spreads, mon) is spreads["aerodactyl"]


def test_legacy_state_backfills_base_species_id():
    assert PokemonState(species="Aerodactyl").base_species_id == "aerodactyl"


def test_spread_lookup_key_prefers_base_species_id():
    mon = PokemonState(species="Charizard-Mega-Y", base_species_id="charizard")
    assert spread_lookup_key(mon) == "charizard"


# ---------------------------------------------------------------------------
# Task 4: projection, speed, weather (imported below after modules exist)
# ---------------------------------------------------------------------------

from showdown_bot.engine.calc.client import SubprocessCalcBackend
from showdown_bot.engine.calc_profile import calc_profile_from_config
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.mega_form import MegaForm
from showdown_bot.engine.mega_projection import (
    UnsupportedMegaAbilityError,
    copy_battle_state,
    project_mega,
)
from showdown_bot.engine.speed import MissingMegaSpreadError, SpeedOracle
from showdown_bot.engine.state import BattleState


PANEL_ROWS: list[tuple[str, str, str, str]] = [
    ("scovillainite", "Scovillain", "Scovillain-Mega", "Spicy Spray"),
    ("aerodactylite", "Aerodactyl", "Aerodactyl-Mega", "Tough Claws"),
    ("lucarionite", "Lucario", "Lucario-Mega", "Adaptability"),
    ("delphoxite", "Delphox", "Delphox-Mega", "Levitate"),
    ("meganiumite", "Meganium", "Meganium-Mega", "Mega Sol"),
    ("froslassite", "Froslass", "Froslass-Mega", "Snow Warning"),
    ("tyranitarite", "Tyranitar", "Tyranitar-Mega", "Sand Stream"),
]


@pytest.fixture
def speed_oracle(calc_profile):
    return SpeedOracle(stats_backend=SubprocessCalcBackend(), profile=calc_profile)


def _panel_state(stone_id: str, base_species: str, *, side: str = "p1", slot: str = "a") -> BattleState:
    st = BattleState()
    st.sides[side][slot] = PokemonState(
        species=base_species,
        base_species_id=to_id(base_species),
        item=stone_id,
        types=["Normal"],
    )
    return st


def test_t5_projection_does_not_mutate_live_state(speed_oracle, aerodactyl_spreads, calc_profile):
    state = _panel_state("aerodactylite", "Aerodactyl")
    before = copy.deepcopy(state)
    form = mega_form_for("Aerodactyl", "Aerodactylite")
    spreads = {"aerodactyl": aerodactyl_spreads}
    project_mega(
        state,
        "p1",
        "a",
        form,
        species_meta=species_meta_table(),
        speed_oracle=speed_oracle,
        spread_lookup=spreads,
        calc_profile=calc_profile,
    )
    assert state.sides == before.sides
    assert state.field.weather == before.field.weather
    assert state.side_mega_spent == before.side_mega_spent


def test_t6_charizard_y_gt_projection(charizard_y_gt, speed_oracle, calc_profile):
    from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadPreset

    gt = charizard_y_gt
    state = BattleState()
    state.sides["p1"]["a"] = PokemonState(
        species="Charizard",
        base_species_id="charizard",
        item="Charizardite Y",
        types=["Fire", "Flying"],
    )
    spreads = {
        "charizard": SpeciesSpreads(
            offense=SpreadPreset(nature=gt["spread"]["nature"], evs=gt["spread"]["evs"]),
            defense=SpreadPreset(nature=gt["spread"]["nature"], evs=gt["spread"]["evs"]),
        )
    }
    form = mega_form_for("Charizard", "Charizardite Y")
    result = project_mega(
        state,
        "p1",
        "a",
        form,
        species_meta=species_meta_table(),
        speed_oracle=speed_oracle,
        spread_lookup=spreads,
        calc_profile=calc_profile,
    )
    mon = result.projected_state.sides["p1"]["a"]
    assert mon.species == gt["post_mega"]["species"]
    assert mon.ability == gt["post_mega"]["ability"]
    assert mon.types == gt["post_mega"]["types"]
    assert mon.item == "Charizardite Y"
    assert mon.base_species_id == "charizard"
    assert result.effective_speed == gt["post_mega"]["effective_speed"]
    assert result.projected_state.field.weather == gt["post_mega"]["weather"]


@pytest.mark.parametrize("stone_id,base_species,form_name,ability", PANEL_ROWS)
def test_t7_panel_mega_metadata(stone_id, base_species, form_name, ability):
    form = mega_form_for(base_species, stone_id)
    assert form is not None
    meta = get_species_form_meta(form.form_species_name)
    assert meta.ability_slot0 == ability
    assert meta.form_species_name == form_name


@pytest.mark.parametrize(
    "stone_id,base_species,weather",
    [
        ("charizarditey", "Charizard", "sunnyday"),
        ("tyranitarite", "Tyranitar", "sandstorm"),
        ("froslassite", "Froslass", "snowscape"),
    ],
)
def test_weather_hooks_on_projection(
    stone_id, base_species, weather, speed_oracle, aerodactyl_spreads, calc_profile
):
    state = _panel_state(stone_id, base_species)
    spreads = {to_id(base_species): aerodactyl_spreads}
    form = mega_form_for(base_species, stone_id)
    result = project_mega(
        state,
        "p1",
        "a",
        form,
        species_meta=species_meta_table(),
        speed_oracle=speed_oracle,
        spread_lookup=spreads,
        calc_profile=calc_profile,
    )
    assert result.projected_state.field.weather == weather


def test_mega_sol_leaves_global_weather_unchanged(speed_oracle, aerodactyl_spreads, calc_profile):
    state = _panel_state("meganiumite", "Meganium")
    state.field.weather = "raindance"
    spreads = {"meganium": aerodactyl_spreads}
    form = mega_form_for("Meganium", "Meganiumite")
    result = project_mega(
        state,
        "p1",
        "a",
        form,
        species_meta=species_meta_table(),
        speed_oracle=speed_oracle,
        spread_lookup=spreads,
        calc_profile=calc_profile,
    )
    assert result.projected_state.field.weather == "raindance"


def test_t18_side_mega_spent_and_stone_held(speed_oracle, aerodactyl_spreads, calc_profile):
    state = _panel_state("aerodactylite", "Aerodactyl")
    form = mega_form_for("Aerodactyl", "Aerodactylite")
    spreads = {"aerodactyl": aerodactyl_spreads}
    result = project_mega(
        state,
        "p1",
        "a",
        form,
        species_meta=species_meta_table(),
        speed_oracle=speed_oracle,
        spread_lookup=spreads,
        calc_profile=calc_profile,
    )
    assert result.projected_state.side_mega_spent["p1"] is True
    assert result.projected_state.sides["p1"]["a"].item == state.sides["p1"]["a"].item


def test_aerodactyl_gen0_speed_222(speed_oracle, aerodactyl_spreads, calc_profile):
    state = _panel_state("aerodactylite", "Aerodactyl")
    form = mega_form_for("Aerodactyl", "Aerodactylite")
    spreads = {"aerodactyl": aerodactyl_spreads}
    result = project_mega(
        state,
        "p1",
        "a",
        form,
        species_meta=species_meta_table(),
        speed_oracle=speed_oracle,
        spread_lookup=spreads,
        calc_profile=calc_profile,
    )
    assert result.effective_speed == 222


def test_spicy_spray_fail_closed(speed_oracle, aerodactyl_spreads, calc_profile):
    state = _panel_state("scovillainite", "Scovillain")
    spreads = {"scovillain": aerodactyl_spreads}
    form = mega_form_for("Scovillain", "Scovillainite")
    with pytest.raises(UnsupportedMegaAbilityError):
        project_mega(
            state,
            "p1",
            "a",
            form,
            species_meta=species_meta_table(),
            speed_oracle=speed_oracle,
            spread_lookup=spreads,
            calc_profile=calc_profile,
        )


def test_speed_oracle_profile_must_match_calc_profile(speed_oracle, aerodactyl_spreads):
    cfg = load_format_config("gen9vgc2025regi")
    wrong_profile = calc_profile_from_config(cfg)
    state = _panel_state("aerodactylite", "Aerodactyl")
    form = mega_form_for("Aerodactyl", "Aerodactylite")
    spreads = {"aerodactyl": aerodactyl_spreads}
    with pytest.raises(ValueError, match="calc_profile"):
        project_mega(
            state,
            "p1",
            "a",
            form,
            species_meta=species_meta_table(),
            speed_oracle=speed_oracle,
            spread_lookup=spreads,
            calc_profile=wrong_profile,
        )


def test_copy_battle_state_deep_copies_side_mega_spent():
    state = BattleState()
    state.side_mega_spent["p1"] = True
    copied = copy_battle_state(state)
    copied.side_mega_spent["p1"] = False
    assert state.side_mega_spent["p1"] is True


# ---------------------------------------------------------------------------
# Task 5: protocol legality and variant expansion
# ---------------------------------------------------------------------------

from showdown_bot.battle.actions import JointAction, enumerate_my_actions
from showdown_bot.battle.legal_actions import enumerate_slot_pairs
from showdown_bot.battle.mega_variants import (
    ScoredMegaVariant,
    expand_mega_variants,
    filter_projectable_variants,
)
from showdown_bot.models.actions import SlotAction
from showdown_bot.models.request import BattleRequest
from showdown_bot.protocol.encoder import encode_choose, format_slot_action


def test_t1_parse_can_mega_evo(scovillain_mega_request):
    assert scovillain_mega_request.active[0].can_mega_evo is True
    assert scovillain_mega_request.active[1].can_mega_evo is False


def test_t2_encoder_move_with_mega_token():
    action = SlotAction(kind="move", move_index=1, target=1, mega_evolve=True)
    assert format_slot_action(action) == "move 1 1 mega"


def test_t3_double_mega_rejected_by_enumerate_slot_pairs():
    req = BattleRequest.model_validate(
        {
            "active": [
                {
                    "moves": [
                        {
                            "move": "Flamethrower",
                            "id": "flamethrower",
                            "pp": 24,
                            "maxpp": 24,
                            "target": "normal",
                            "disabled": False,
                        }
                    ],
                    "canMegaEvo": True,
                },
                {
                    "moves": [
                        {
                            "move": "Moonblast",
                            "id": "moonblast",
                            "pp": 24,
                            "maxpp": 24,
                            "target": "normal",
                            "disabled": False,
                        }
                    ],
                    "canMegaEvo": True,
                },
            ],
            "side": {
                "id": "p1",
                "pokemon": [
                    {
                        "ident": "p1: Charizard",
                        "details": "Charizard, L50",
                        "condition": "150/150",
                        "active": True,
                        "moves": ["flamethrower"],
                        "baseTypes": ["Fire", "Flying"],
                        "item": "Charizardite Y",
                    },
                    {
                        "ident": "p1: Lucario",
                        "details": "Lucario, L50",
                        "condition": "150/150",
                        "active": True,
                        "moves": ["moonblast"],
                        "baseTypes": ["Fighting", "Steel"],
                        "item": "Lucarionite",
                    },
                ],
            },
            "rqid": 1,
        }
    )
    pairs = enumerate_slot_pairs(req)
    assert pairs
    assert not any(p.slot0.mega_evolve and p.slot1.mega_evolve for p in pairs)


def test_t4_mega_and_tera_same_slot_rejected():
    action = SlotAction(kind="move", move_index=1, target=1, mega_evolve=True, terastallize=True)
    with pytest.raises(ValueError, match="dual overlay"):
        format_slot_action(action)


def test_enumerate_my_actions_strips_mega(scovillain_mega_request):
    acts = enumerate_my_actions(scovillain_mega_request)
    assert acts
    for ja in acts:
        assert not ja.slot0.mega_evolve
        assert not ja.slot1.mega_evolve


def test_joint_action_with_mega():
    ja = JointAction(
        slot0=SlotAction(kind="move", move_index=1, target=1),
        slot1=SlotAction(kind="move", move_index=2, target=1),
    )
    mega = ja.with_mega(0)
    assert mega.slot0.mega_evolve is True
    assert mega.slot1.mega_evolve is False


def test_t23_unresolved_form_fail_closed(
    scovillain_mega_request, scovillain_hero_state, calc_profile, aerodactyl_spreads
):
    scovillain_hero_state.sides["p1"]["a"].item = "Unknown Stone"
    base = enumerate_my_actions(scovillain_mega_request)
    raw = expand_mega_variants(base, scovillain_mega_request, scovillain_hero_state, "p1")
    oracle = SpeedOracle(stats_backend=SubprocessCalcBackend(), profile=calc_profile)
    evaluated = filter_projectable_variants(
        raw,
        scovillain_mega_request,
        scovillain_hero_state,
        "p1",
        species_meta=species_meta_table(),
        speed_oracle=oracle,
        our_spreads={"scovillain": aerodactyl_spreads},
        calc_profile=calc_profile,
    )
    mega_slots = [v.own_mega_slot for v in evaluated if v.own_mega_slot is not None]
    assert mega_slots == []


def test_t50_scovillain_in_raw_not_in_evaluated(
    scovillain_mega_request,
    scovillain_hero_state,
    scovillain_base_joints,
    calc_profile,
    aerodactyl_spreads,
):
    raw = expand_mega_variants(
        scovillain_base_joints, scovillain_mega_request, scovillain_hero_state, "p1"
    )
    assert any(v.own_mega_slot == 0 for v in raw)
    oracle = SpeedOracle(stats_backend=SubprocessCalcBackend(), profile=calc_profile)
    evaluated = filter_projectable_variants(
        raw,
        scovillain_mega_request,
        scovillain_hero_state,
        "p1",
        species_meta=species_meta_table(),
        speed_oracle=oracle,
        our_spreads={"scovillain": aerodactyl_spreads},
        calc_profile=calc_profile,
    )
    assert not any(v.own_mega_slot == 0 for v in evaluated)
    assert any(v.own_mega_slot is None for v in evaluated)


def test_t27_variant_count_and_order(
    scovillain_mega_request, scovillain_hero_state, scovillain_base_joints
):
    state = scovillain_hero_state
    state.sides["p1"]["a"].item = "Aerodactylite"
    state.sides["p1"]["a"].species = "Aerodactyl"
    state.sides["p1"]["a"].base_species_id = "aerodactyl"
    raw = expand_mega_variants(
        scovillain_base_joints[:1], scovillain_mega_request, state, "p1"
    )
    assert len(raw) == 2
    assert raw[0].own_mega_slot is None
    assert raw[1].own_mega_slot == 0
    keys = [id(v.joint) for v in raw]
    assert len(keys) == len(set(keys))


def test_planned_action_has_is_mega_field():
    from showdown_bot.battle.resolve import PlannedAction

    pa = PlannedAction(side="p1", slot="a", kind="move")
    assert hasattr(pa, "is_mega")
    assert pa.is_mega is False
