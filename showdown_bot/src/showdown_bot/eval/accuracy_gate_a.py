"""Gate A: a smoke test sweeping a small number of fixed boards across 7 field-bucket variants,
comparing SHOWDOWN_ACCURACY_MODE off vs on via direct heuristic_choose_for_request calls, no
server. Explicitly a smoke test (spec Sec.1) -- cannot license anything on its own.

Board/field construction is verified against real source (not fixtures/assumptions): the
primary board reproduces scratchpad/bench_accuracy_latency.py's make_state() (p1
Incineroar+Rillaboom vs p2 Flutter Mane+Tornadus, exercising accuracy<100 spread moves on both
sides), and FieldState (engine/state.py) is a plain dataclass whose 7 variants are constructed
directly here.
"""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from pathlib import Path

from showdown_bot.battle.decision import heuristic_choose_for_request
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.battle.opponent import SpeciesDex
from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.calc.client import CalcClient
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.speed import SpeedOracle
from showdown_bot.engine.state import BattleState, FieldState, PokemonState
from showdown_bot.models.request import BattleRequest

_FIXTURE_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures"

FIELD_VARIANTS = ["neutral", "tailwind_both", "tailwind_p1", "tailwind_p2", "trick_room", "sun", "rain"]


def _make_field(variant: str) -> FieldState:
    if variant == "neutral":
        return FieldState()
    if variant == "tailwind_both":
        return FieldState(tailwind={"p1": True, "p2": True})
    if variant == "tailwind_p1":
        return FieldState(tailwind={"p1": True, "p2": False})
    if variant == "tailwind_p2":
        return FieldState(tailwind={"p1": False, "p2": True})
    if variant == "trick_room":
        return FieldState(trick_room=True)
    if variant == "sun":
        return FieldState(weather="Sun")
    if variant == "rain":
        return FieldState(weather="Rain")
    raise ValueError(f"unknown field variant: {variant!r}")


def _make_primary_state() -> BattleState:
    # Verbatim reproduction of scratchpad/bench_accuracy_latency.py's make_state(): p1
    # Incineroar+Rillaboom (Heat Wave 90% spread) vs p2 FlutterMane+Tornadus (Bleakwind Storm
    # 80% spread) -- exercises accuracy branching on both sides.
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=155, max_hp=155)
    fm = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    fm.move_names = {"Moonblast", "Shadow Ball"}
    tor = PokemonState(species="Tornadus", hp=140, max_hp=140)
    # Bleakwind Storm (80% acc, allAdjacentFoes) supplies the p2-side accuracy<100 spread move.
    tor.move_names = {"Tailwind", "Bleakwind Storm"}
    st.sides["p2"]["a"] = fm
    st.sides["p2"]["b"] = tor
    return st


def _make_single_target_state() -> BattleState:
    # A second board with a single-target (not spread) <100%-accuracy move, so Gate A's smoke
    # test isn't only exercising spread-move accuracy branching -- Focus Blast (70% acc).
    st = BattleState()
    gar = PokemonState(species="Gholdengo", hp=133, max_hp=133)
    gar.move_names = {"Shadow Ball", "Focus Blast"}
    st.sides["p1"]["a"] = gar
    st.sides["p1"]["b"] = PokemonState(species="Landorus-Therian", hp=155, max_hp=155)
    st.sides["p2"]["a"] = PokemonState(species="Amoonguss", hp=176, max_hp=176)
    st.sides["p2"]["b"] = PokemonState(species="Urshifu", hp=139, max_hp=139)
    return st


_BOARDS = {
    "primary": _make_primary_state,
    "single_target": _make_single_target_state,
}

_REQ = BattleRequest.model_validate(
    json.loads((_FIXTURE_DIR / "request_doubles_moves.json").read_text(encoding="utf-8"))
)
_BOOK = load_spread_book(load_format_config("gen9vgc2025regi").meta_path("default_spreads"))
_CALC = CalcClient()
_SPEED = SpeedOracle(stats_backend=_CALC.backend)
_DEX = SpeciesDex(_CALC.backend)


@dataclass(frozen=True)
class GateARow:
    board: str
    field_variant: str
    off_chosen_action: str
    on_chosen_action: str
    action_changed: bool
    exception: str | None


@dataclass(frozen=True)
class GateAResult:
    rows: list[GateARow]

    @property
    def diff_count(self) -> int:
        return sum(1 for r in self.rows if r.action_changed)

    @property
    def exception_count(self) -> int:
        return sum(1 for r in self.rows if r.exception is not None)


def _decide(board_name: str, field: FieldState, *, accuracy_on: bool) -> str:
    st = copy.deepcopy(_BOARDS[board_name]())
    st.field = field
    if accuracy_on:
        os.environ["SHOWDOWN_ACCURACY_MODE"] = "1"
    else:
        os.environ.pop("SHOWDOWN_ACCURACY_MODE", None)
    oracle = DamageOracle(_CALC)
    return heuristic_choose_for_request(
        _REQ, state=st, book=_BOOK, our_side="p1",
        calc=_CALC, oracle=oracle, speed_oracle=_SPEED, dex=_DEX,
    )


def run_gate_a(
    *, board_names: list[str] | None = None, field_variants: list[str] = FIELD_VARIANTS,
) -> GateAResult:
    board_names = board_names if board_names is not None else list(_BOARDS)
    rows: list[GateARow] = []
    try:
        for board in board_names:
            for variant in field_variants:
                field = _make_field(variant)
                try:
                    off_action = _decide(board, field, accuracy_on=False)
                    on_action = _decide(board, field, accuracy_on=True)
                    rows.append(GateARow(
                        board=board, field_variant=variant,
                        off_chosen_action=off_action, on_chosen_action=on_action,
                        action_changed=(off_action != on_action), exception=None,
                    ))
                except Exception as exc:  # noqa: BLE001
                    rows.append(GateARow(
                        board=board, field_variant=variant,
                        off_chosen_action="", on_chosen_action="",
                        action_changed=False, exception=str(exc),
                    ))
    finally:
        os.environ.pop("SHOWDOWN_ACCURACY_MODE", None)  # never leak state into other test runs
    return GateAResult(rows=rows)
