from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "formats"


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
    meta_paths: dict[str, Path] = field(default_factory=dict)
    source_path: Path | None = None

    def meta_path(self, key: str) -> Path:
        try:
            return self.meta_paths[key]
        except KeyError as exc:
            raise KeyError(f"format '{self.format_id}' has no meta path '{key}'") from exc


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
        meta_paths=meta_paths,
        source_path=path,
    )
