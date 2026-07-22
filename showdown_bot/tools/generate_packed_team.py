"""One-off helper — requires poke-env (not a runtime dependency).

Packs a Showdown paste (`.txt`) into its single-line `.packed` sibling, using poke-env's own
`Teambuilder` — the same mechanism every existing `.packed` file in this repo was produced with.

Usage:

    python showdown_bot/tools/generate_packed_team.py                  # the default fixed_team
    python showdown_bot/tools/generate_packed_team.py PATH.txt [...]   # explicit paste paths

With no arguments the historical behaviour is preserved exactly (`teams/fixed_team.txt` ->
`teams/fixed_team.packed`), so existing callers and docs keep working. Paths given explicitly are
resolved as-is; each writes its `.packed` sibling. The transformation is deterministic: packing the
same `.txt` twice yields byte-identical output.
"""
from pathlib import Path
import sys

from poke_env.teambuilder.teambuilder import Teambuilder

ROOT = Path(__file__).resolve().parents[1]


def pack_team(paste_path: Path) -> Path:
    """Write ``paste_path``'s ``.packed`` sibling and return it."""
    packed_path = paste_path.with_suffix(".packed")
    packed = Teambuilder.join_team(
        Teambuilder.parse_showdown_team(paste_path.read_text(encoding="utf-8"))
    )
    packed_path.write_text(packed, encoding="utf-8", newline="")
    return packed_path


def main(argv: list[str]) -> None:
    paths = [Path(a) for a in argv] or [ROOT / "teams" / "fixed_team.txt"]
    for paste_path in paths:
        packed_path = pack_team(paste_path)
        print(f"wrote {packed_path} ({len(packed_path.read_text(encoding='utf-8'))} chars)")


if __name__ == "__main__":
    main(sys.argv[1:])
