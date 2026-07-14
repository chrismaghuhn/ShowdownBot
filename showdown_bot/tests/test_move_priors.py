from pathlib import Path

from showdown_bot.engine.belief.move_priors import load_move_priors, load_move_priors_for_format


def test_missing_file_returns_empty(tmp_path):
    assert load_move_priors(tmp_path / "nope.yaml") == {}


def test_keys_and_moves_are_to_id_normalized(tmp_path):
    p = tmp_path / "mp.yaml"
    p.write_text("species:\n  Flutter Mane:\n    - Moonblast\n    - Shadow Ball\n", encoding="utf-8")
    out = load_move_priors(p)
    assert out == {"fluttermane": ["moonblast", "shadowball"]}


def test_duplicate_moves_deduped_in_order(tmp_path):
    p = tmp_path / "mp.yaml"
    p.write_text("species:\n  Incineroar:\n    - Fake Out\n    - Fake Out\n    - Knock Off\n", encoding="utf-8")
    assert load_move_priors(p) == {"incineroar": ["fakeout", "knockoff"]}


def test_load_for_format_delegates_and_missing_is_empty(tmp_path, monkeypatch):
    # Mirror how load_opp_sets_for_format imports load_format_config locally.
    # The function does: from showdown_bot.engine.format_config import load_format_config
    # inside its body — so monkeypatch the name as it lives in the move_priors module.
    import showdown_bot.engine.belief.move_priors as mod

    class _FakeConfig:
        def meta_path(self, key):
            # point at a file that definitely does not exist
            return tmp_path / "missing_move_priors.yaml"

    monkeypatch.setattr(mod, "load_format_config", lambda fmt: _FakeConfig())

    assert load_move_priors_for_format("gen9vgc2024regg") == {}


def test_champions_missing_move_priors_degrades_to_empty():
    assert load_move_priors_for_format("gen9championsvgc2026regma") == {}
