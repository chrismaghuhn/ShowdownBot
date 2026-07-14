from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "formats"

_STAT_INVESTMENT_KINDS = frozenset({"ev", "stat_points"})


@dataclass(frozen=True)
class StatInvestment:
    """Format stat-budget rules for spread books and future validators.

    ``evs`` keys in spread yaml always hold per-stat investment counts; this
    block documents whether those counts are Reg-style EVs or Champions Stat Points.
    """

    kind: str
    total: int
    max_per_stat: int
    iv_policy: str | None = None


DEFAULT_STAT_INVESTMENT = StatInvestment(
    kind="ev",
    total=510,
    max_per_stat=252,
    iv_policy="flexible",
)


@dataclass(frozen=True)
class FormatConfig:
    """Static, format-specific configuration (regulation rules + meta paths).

    `format_id` selects which config/spreads to load; it is NOT passed to
    @smogon/calc, which derives mechanics from the generation + field instead.
    """

    format_id: str
    level: int
    game_type: str
    restricted_limit: int
    tera: bool
    mega: bool
    stat_investment: StatInvestment
    meta_paths: dict[str, Path] = field(default_factory=dict)
    source_path: Path | None = None

    def meta_path(self, key: str) -> Path:
        try:
            return self.meta_paths[key]
        except KeyError as exc:
            raise KeyError(f"format '{self.format_id}' has no meta path '{key}'") from exc


def _parse_stat_investment(raw: object) -> StatInvestment:
    if raw is None:
        return DEFAULT_STAT_INVESTMENT
    if not isinstance(raw, dict):
        raise ValueError("stat_investment must be a mapping")

    kind = raw.get("kind", DEFAULT_STAT_INVESTMENT.kind)
    if kind not in _STAT_INVESTMENT_KINDS:
        allowed = ", ".join(sorted(_STAT_INVESTMENT_KINDS))
        raise ValueError(f"stat_investment.kind must be one of {{{allowed}}}, got {kind!r}")

    total = int(raw.get("total", DEFAULT_STAT_INVESTMENT.total))
    max_per_stat = int(raw.get("max_per_stat", DEFAULT_STAT_INVESTMENT.max_per_stat))
    if total <= 0:
        raise ValueError(f"stat_investment.total must be positive, got {total}")
    if max_per_stat <= 0:
        raise ValueError(f"stat_investment.max_per_stat must be positive, got {max_per_stat}")

    iv_raw = raw.get("iv_policy", DEFAULT_STAT_INVESTMENT.iv_policy)
    iv_policy = None if iv_raw is None else str(iv_raw)

    return StatInvestment(
        kind=kind,
        total=total,
        max_per_stat=max_per_stat,
        iv_policy=iv_policy,
    )


def load_format_config(format_id: str, *, config_dir: Path | None = None) -> FormatConfig:
    base = config_dir or DEFAULT_CONFIG_DIR
    path = base / f"{format_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"format config not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    raw_meta = data.get("meta_paths", {}) or {}
    meta_paths = {key: (path.parent / rel).resolve() for key, rel in raw_meta.items()}

    return FormatConfig(
        format_id=data["format_id"],
        level=int(data["level"]),
        game_type=data["game_type"],
        restricted_limit=int(data.get("restricted_limit", 0)),
        tera=bool(data.get("tera", False)),
        mega=bool(data.get("mega", False)),
        stat_investment=_parse_stat_investment(data.get("stat_investment")),
        meta_paths=meta_paths,
        source_path=path,
    )
