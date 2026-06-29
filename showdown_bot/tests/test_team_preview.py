from showdown_bot.battle.team_preview import pick_team_preview_default
from showdown_bot.models.request import BattleRequest, PokemonSlot, SideInfo

# The fixed team's movesets (ids), in team-sheet order.
_TEAM = [
    ("Incineroar", ["fakeout", "flareblitz", "knockoff", "protect"]),
    ("Rillaboom", ["fakeout", "grassyglide", "woodhammer", "protect"]),
    ("Flutter Mane", ["moonblast", "shadowball", "dazzlinggleam", "protect"]),
    ("Landorus-Therian", ["earthpower", "sludgebomb", "uturn", "protect"]),
    ("Tornadus", ["tailwind", "bleakwindstorm", "taunt", "protect"]),  # slot 5 = speed control
    ("Urshifu-Rapid-Strike", ["closecombat", "surgingstrikes", "aquajet", "protect"]),
]


def _preview_req(with_moves=True) -> BattleRequest:
    pokemon = [
        PokemonSlot(
            ident=f"p1: {name}", details=f"{name}, L50", condition="100/100",
            active=False, moves=(moves if with_moves else []),
        )
        for name, moves in _TEAM
    ]
    return BattleRequest(team_preview=True, side=SideInfo(id="p1", pokemon=pokemon), rqid=1)


def test_preview_brings_speed_control_and_leads_tempo():
    chosen = pick_team_preview_default(_preview_req())
    assert len(chosen) == 4
    assert len(set(chosen)) == 4  # no duplicates
    # Tornadus (Tailwind, slot 5) is the team's only speed control -> must be brought.
    assert 5 in chosen
    # Leads (first two) are tempo mons (Fake Out users 1/2 or the Tailwind setter 5).
    assert set(chosen[:2]) <= {1, 2, 5}
    assert 1 in chosen[:2] or 2 in chosen[:2]  # at least one Fake Out lead


def test_preview_falls_back_when_no_move_info():
    chosen = pick_team_preview_default(_preview_req(with_moves=False))
    assert chosen == [1, 2, 3, 4]
