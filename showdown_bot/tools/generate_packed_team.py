"""One-off helper — requires poke-env (not a runtime dependency)."""
from pathlib import Path

from poke_env.teambuilder.teambuilder import Teambuilder

ROOT = Path(__file__).resolve().parents[1]
paste_path = ROOT / "teams" / "fixed_team.txt"
packed_path = ROOT / "teams" / "fixed_team.packed"

packed = Teambuilder.join_team(Teambuilder.parse_showdown_team(paste_path.read_text(encoding="utf-8")))
packed_path.write_text(packed, encoding="utf-8")
print(f"wrote {packed_path} ({len(packed)} chars)")
