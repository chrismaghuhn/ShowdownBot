"""I7a-C Task 3: bind Mega metadata (itemdata.json/speciesdata.json) to run provenance.

Mega depends on BOTH itemdata.json (megaStone mapping, is_choice/is_berry classes) and
speciesdata.json (required_item, base species). ``config_provenance_for_format`` must
expose content hashes for both so two runs on different Mega-relevant data never share a
config_hash lineage. Both hashes are FAIL-CLOSED: a stale embedded generator hash raises
the typed error (``ItemdataStaleError``/``SpeciesMetaStaleError``) straight out of
``config_provenance_for_format`` -- no raw-file-SHA fallback.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from showdown_bot.eval.config_env import build_config_manifest, config_provenance_for_format
from showdown_bot.eval.result_jsonl import make_config_hash

REPO_ROOT = Path(__file__).resolve().parents[2]
FORMAT_ID = "gen9championsvgc2026regma"


def _manifest(**overrides):
    base = build_config_manifest(
        agent="heuristic",
        format_id=FORMAT_ID,
        priors_hash="p",
        spreads_hash="s",
        env={},
    )
    base.update(overrides)
    return base


# --- config_provenance_for_format returns both hashes ------------------------------------

def test_config_provenance_includes_itemdata_and_speciesdata_hashes():
    provenance = config_provenance_for_format(FORMAT_ID)
    assert provenance["itemdata_hash"]
    assert isinstance(provenance["itemdata_hash"], str)
    assert provenance["speciesdata_hash"]
    assert isinstance(provenance["speciesdata_hash"], str)


def test_config_provenance_itemdata_hash_matches_direct_call():
    from showdown_bot.engine.items import itemdata_content_hash

    provenance = config_provenance_for_format(FORMAT_ID)
    assert provenance["itemdata_hash"] == itemdata_content_hash()


def test_config_provenance_speciesdata_hash_matches_direct_call():
    from showdown_bot.engine.species_meta import speciesdata_content_hash

    provenance = config_provenance_for_format(FORMAT_ID)
    assert provenance["speciesdata_hash"] == speciesdata_content_hash()


# --- build_config_manifest wires both optional kwargs -------------------------------------

def test_build_config_manifest_includes_itemdata_hash_when_provided():
    manifest = build_config_manifest(
        agent="a", format_id="f", priors_hash="p", spreads_hash="s", env={},
        itemdata_hash="deadbeef",
    )
    assert manifest["itemdata_hash"] == "deadbeef"


def test_build_config_manifest_includes_speciesdata_hash_when_provided():
    manifest = build_config_manifest(
        agent="a", format_id="f", priors_hash="p", spreads_hash="s", env={},
        speciesdata_hash="cafef00d",
    )
    assert manifest["speciesdata_hash"] == "cafef00d"


def test_build_config_manifest_omits_item_species_hashes_when_absent():
    manifest = build_config_manifest(
        agent="a", format_id="f", priors_hash="p", spreads_hash="s", env={},
    )
    assert "itemdata_hash" not in manifest
    assert "speciesdata_hash" not in manifest


# --- config_hash changes when either hash changes ------------------------------------------

def test_config_hash_changes_when_itemdata_hash_changes():
    m1 = _manifest(itemdata_hash="aaaaaaaaaaaaaaaa", speciesdata_hash="zzzzzzzzzzzzzzzz")
    m2 = _manifest(itemdata_hash="bbbbbbbbbbbbbbbb", speciesdata_hash="zzzzzzzzzzzzzzzz")
    assert make_config_hash(m1) != make_config_hash(m2)


def test_config_hash_changes_when_speciesdata_hash_changes():
    m1 = _manifest(itemdata_hash="aaaaaaaaaaaaaaaa", speciesdata_hash="zzzzzzzzzzzzzzzz")
    m2 = _manifest(itemdata_hash="aaaaaaaaaaaaaaaa", speciesdata_hash="yyyyyyyyyyyyyyyy")
    assert make_config_hash(m1) != make_config_hash(m2)


def test_config_hash_stable_when_neither_hash_changes():
    m1 = _manifest(itemdata_hash="aaaaaaaaaaaaaaaa", speciesdata_hash="zzzzzzzzzzzzzzzz")
    m2 = _manifest(itemdata_hash="aaaaaaaaaaaaaaaa", speciesdata_hash="zzzzzzzzzzzzzzzz")
    assert make_config_hash(m1) == make_config_hash(m2)


# --- fail-closed: no fallback to raw file SHA on stale embedded generator hash --------------

def test_config_provenance_propagates_stale_itemdata_error(monkeypatch):
    from showdown_bot.engine import items as items_mod

    def _boom():
        raise items_mod.ItemdataStaleError("itemdata.json embedded data_hash stale")

    monkeypatch.setattr(items_mod, "itemdata_content_hash", _boom)
    with pytest.raises(items_mod.ItemdataStaleError):
        config_provenance_for_format(FORMAT_ID)


def test_config_provenance_propagates_stale_speciesdata_error(monkeypatch):
    from showdown_bot.engine import species_meta as species_meta_mod

    def _boom():
        raise species_meta_mod.SpeciesMetaStaleError("speciesdata.json embedded data_hash stale")

    monkeypatch.setattr(species_meta_mod, "speciesdata_content_hash", _boom)
    with pytest.raises(species_meta_mod.SpeciesMetaStaleError):
        config_provenance_for_format(FORMAT_ID)


# --- every real production build_config_manifest caller wires both hashes ------------------
#
# I7a-C P1.4: cli.py no longer calls build_config_manifest(...) directly -- it calls the
# shared eval.config_env.effective_config_manifest(...), which is the ONE place that wires
# itemdata_hash/speciesdata_hash from its own config_provenance_for_format(...) call (see
# test_config_env.py's test_effective_config_manifest_* tests for that wiring). The two
# scripts below still assemble the manifest inline (pre-existing, out of scope for P1.4;
# migrating them to effective_config_manifest is a documented follow-up, not done here).

_CALLER_FILES = [
    REPO_ROOT / "scripts" / "run_accuracy_baseline_freeze.py",
    REPO_ROOT / "scripts" / "run_cap_action_capture.py",
]


def test_cli_uses_shared_effective_config_manifest_not_a_direct_call():
    """Regression guard for P1.4: cli.py must call the shared effective_config_manifest(...)
    (config_env.py) rather than re-deriving priors/spreads/movedata/provenance hashes and
    calling build_config_manifest(...) itself -- that duplication is exactly what let the
    CLI's live config_hash and a future freeze helper silently drift apart."""
    src = (REPO_ROOT / "src" / "showdown_bot" / "cli.py").read_text(encoding="utf-8")
    assert "effective_config_manifest(" in src
    assert "build_config_manifest(" not in src


@pytest.mark.parametrize("path", _CALLER_FILES, ids=lambda p: p.name)
def test_every_manifest_caller_wires_item_and_species_hashes(path: Path):
    """Every real ``build_config_manifest(`` call site (re-verified via
    ``rg -n "build_config_manifest\\(" src scripts -g "*.py"``) must pass
    ``itemdata_hash=`` and ``speciesdata_hash=`` sourced from the caller's own
    ``config_provenance_for_format(...)`` result -- not a fresh/duplicate call."""
    src = path.read_text(encoding="utf-8")
    assert "config_provenance_for_format(" in src, f"{path} lost its provenance call"
    assert "build_config_manifest(" in src
    assert 'itemdata_hash=provenance["itemdata_hash"]' in src, (
        f"{path} does not wire itemdata_hash from its provenance dict"
    )
    assert 'speciesdata_hash=provenance["speciesdata_hash"]' in src, (
        f"{path} does not wire speciesdata_hash from its provenance dict"
    )


def test_manifest_caller_files_are_exactly_the_rg_result():
    """Ground truth: re-derive the caller list the same way the plan's Step 2 does, and
    assert it is exactly the parametrized set above (no missed / no invented caller)."""
    import re as _re

    found: set[Path] = set()
    for base in (REPO_ROOT / "src", REPO_ROOT / "scripts"):
        for path in base.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if _re.search(r"build_config_manifest\(", text):
                # Exclude the definition site itself (src/showdown_bot/eval/config_env.py),
                # which matches the def signature, not a call.
                if path.name == "config_env.py":
                    continue
                found.add(path)
    assert found == set(_CALLER_FILES)
