import json
import shutil
import subprocess
from pathlib import Path

import pytest

CONFIG = Path(__file__).resolve().parents[1] / "config"


def _load(name: str) -> dict:
    return json.loads((CONFIG / name).read_text(encoding="utf-8"))


def test_movedata_has_version_and_known_moves():
    data = _load("moves/movedata.json")
    assert data["generation"] == 9
    assert data["data_hash"]
    assert data["source_version"]
    moves = data["moves"]
    assert len(moves) > 800
    # semantic fields the effect-class layer relies on
    assert moves["willowisp"]["status"] == "brn"
    assert moves["tailwind"]["sideCondition"] == "tailwind"
    assert moves["swordsdance"]["boosts"] == {"atk": 2}
    assert moves["grassyterrain"]["terrain"] == "grassyterrain"
    # synthetic flinch flag preserved for the resolver's backward-compat contract
    assert "flinch" in moves["fakeout"]["flags"]
    assert moves["fakeout"]["priority"] == 3


def test_itemdata_known_items():
    items = _load("items/itemdata.json")["items"]
    assert len(items) > 400
    assert items["leftovers"]["name"] == "Leftovers"
    assert items["choicescarf"]["isChoice"] is True
    assert items["sitrusberry"]["isBerry"] is True


def test_itemdata_exposes_mega_stone_target():
    items = _load("items/itemdata.json")["items"]
    assert items["aerodactylite"]["megaStone"] == {
        "Aerodactyl": "Aerodactyl-Mega",
    }


def test_speciesdata_exposes_mega_form_metadata():
    row = _load("species/speciesdata.json")["species"]["aerodactylmega"]
    assert row["baseSpecies"] == "Aerodactyl"
    assert row["baseStats"]["spe"] == 150
    assert row["abilities"]["0"] == "Tough Claws"
    assert row["requiredItem"] == "Aerodactylite"


def test_generated_data_is_fresh():
    """Re-run the generator in --check mode; fail if checked-in JSON is stale."""
    if shutil.which("node") is None:
        pytest.skip("node not available")
    gen_dir = CONFIG.parent / "tools" / "gen"
    if not (gen_dir / "node_modules").exists():
        pytest.skip("generator deps not installed (run: npm install in tools/gen)")
    result = subprocess.run(
        ["node", "gen_movedata.mjs", "--check"],
        cwd=gen_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"generated data is stale:\n{result.stdout}\n{result.stderr}"
