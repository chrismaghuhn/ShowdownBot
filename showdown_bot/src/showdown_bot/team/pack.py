from __future__ import annotations

from pathlib import Path


def load_packed_team(team_path: Path | str) -> str:
    """Load a single-line packed team for |/utm."""
    packed_path = Path(team_path).with_suffix(".packed")
    if not packed_path.exists():
        raise FileNotFoundError(
            f"Missing {packed_path}. Generate it from the paste team "
            f"(see tools/generate_packed_team.py)."
        )
    packed = packed_path.read_text(encoding="utf-8").strip()
    if "\n" in packed:
        raise ValueError(f"packed team must be one line: {packed_path}")
    return packed
