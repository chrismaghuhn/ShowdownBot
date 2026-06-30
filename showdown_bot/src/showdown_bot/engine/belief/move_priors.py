from __future__ import annotations

from pathlib import Path

import yaml

from showdown_bot.engine.format_config import load_format_config


def load_move_priors(path: Path) -> dict[str, list[str]]:
    """Curated per-species move priors. Returns {to_id(species): [to_id(move), ...]}
    with deterministic dedupe (first occurrence wins). Missing file -> {}.
    SEPARATE from likely_sets (which carries spreads); move_priors carries only
    ordered move ids."""
    from showdown_bot.engine.state import to_id

    if not Path(path).exists():
        return {}
    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    out: dict[str, list[str]] = {}
    for name, moves in (data.get("species") or {}).items():
        seen: set[str] = set()
        ordered: list[str] = []
        for m in moves or []:
            mid = to_id(m)
            if mid not in seen:
                seen.add(mid)
                ordered.append(mid)
        out[to_id(name)] = ordered
    return out


def load_move_priors_for_format(format_id: str) -> dict[str, list[str]]:
    """Load curated move priors for a format via meta_path('move_priors').
    Mirror of load_opp_sets_for_format: missing file or any error -> {}.
    No species validator (moves are plain strings, no calc backend needed)."""
    try:
        path = load_format_config(format_id).meta_path("move_priors")
        return load_move_priors(path)
    except Exception:  # noqa: BLE001 - missing/invalid file -> off
        return {}
