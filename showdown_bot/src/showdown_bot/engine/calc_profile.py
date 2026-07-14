"""Calc engine profile + SpeedOracle factory (I4 §6)."""
from __future__ import annotations

from dataclasses import dataclass

from showdown_bot.engine.format_config import (
    DEFAULT_STAT_INVESTMENT,
    FormatConfig,
)


@dataclass(frozen=True)
class CalcProfile:
    generation: int
    max_spe_investment: int


DEFAULT_CALC_PROFILE = CalcProfile(
    generation=9,
    max_spe_investment=DEFAULT_STAT_INVESTMENT.max_per_stat,
)


def calc_profile_from_config(cfg: FormatConfig | None) -> CalcProfile:
    if cfg is None:
        return DEFAULT_CALC_PROFILE
    return CalcProfile(
        generation=cfg.calc_generation,
        max_spe_investment=cfg.stat_investment.max_per_stat,
    )


def build_speed_oracle(stats_backend, profile: CalcProfile | None = None):
    from showdown_bot.engine.speed import SpeedOracle

    return SpeedOracle(stats_backend=stats_backend, profile=profile or DEFAULT_CALC_PROFILE)
