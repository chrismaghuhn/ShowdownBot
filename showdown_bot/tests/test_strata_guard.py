# showdown_bot/tests/test_strata_guard.py
import pytest

from showdown_bot.eval.strata_guard import (
    detect_stratum, assert_no_cross_stratum_pooling, stratum_output_root,
    StratumRecord, StrataPoolingError, UnattestedStratumError, WINDOWS_STRATUM, KAGGLE_STRATUM,
)


def test_detect_stratum_respects_explicit_override_when_consistent_with_the_platform(monkeypatch):
    # Rev. 16 fix (§1o, P1 #1): an override may only CONFIRM what platform.system() can prove,
    # never CONTRADICT it -- see test_detect_stratum_rejects_an_override_that_contradicts_the_platform
    # below for the rejection side. "windows" on a real/simulated Windows box, and "kaggle" on a
    # simulated non-Windows box, are the only two consistent combinations.
    monkeypatch.setattr("platform.system", lambda: "Windows")
    assert detect_stratum(env_override="windows") == "windows"
    monkeypatch.setattr("platform.system", lambda: "Linux")
    assert detect_stratum(env_override="kaggle") == "kaggle"


def test_detect_stratum_rejects_an_override_that_contradicts_the_platform(monkeypatch):
    # Rev. 16 fix (§1o, P1 #1): before this fix, env_override bypassed platform.system() entirely
    # -- env_override="kaggle" on the real, fixed Windows measurement host (or the reverse on a
    # non-Windows box) succeeded silently, mislabeling a run's stratum regardless of where it
    # actually executed. DESIGN sec 3.5 cares about the ACTUAL hardware a run executed on, not
    # merely a claimed label -- an override that contradicts observable platform reality is not a
    # valid attestation.
    monkeypatch.setattr("platform.system", lambda: "Windows")
    with pytest.raises(UnattestedStratumError, match="Windows"):
        detect_stratum(env_override="kaggle")
    monkeypatch.setattr("platform.system", lambda: "Linux")
    with pytest.raises(UnattestedStratumError, match="not Windows"):
        detect_stratum(env_override="windows")


def test_detect_stratum_rejects_unknown_override():
    with pytest.raises(ValueError, match="unknown stratum"):
        detect_stratum(env_override="colab")


def test_detect_stratum_accepts_windows_via_platform_sniff(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Windows")
    assert detect_stratum() == "windows"


def test_detect_stratum_refuses_to_guess_kaggle_from_a_bare_linux_platform(monkeypatch):
    # P2-1 fix: a plain Linux/macOS/CI box must NOT be silently treated as the approved Kaggle
    # environment -- it could be any unattested machine.
    monkeypatch.setattr("platform.system", lambda: "Linux")
    with pytest.raises(UnattestedStratumError, match="env_override"):
        detect_stratum()


def test_assert_no_cross_stratum_pooling_passes_for_a_single_stratum():
    records = [
        StratumRecord(stratum=WINDOWS_STRATUM, platform_string="Windows-11", output_dir="a"),
        StratumRecord(stratum=WINDOWS_STRATUM, platform_string="Windows-11", output_dir="b"),
    ]
    assert_no_cross_stratum_pooling(records)


def test_assert_no_cross_stratum_pooling_rejects_mixed_strata():
    records = [
        StratumRecord(stratum=WINDOWS_STRATUM, platform_string="Windows-11", output_dir="a"),
        StratumRecord(stratum=KAGGLE_STRATUM, platform_string="Linux-5.15", output_dir="b"),
    ]
    with pytest.raises(StrataPoolingError, match="windows"):
        assert_no_cross_stratum_pooling(records)


def test_stratum_output_root_separates_strata():
    assert stratum_output_root("windows", "d") != stratum_output_root("kaggle", "d")


def test_stratum_output_root_rejects_unknown_stratum():
    with pytest.raises(ValueError, match="unknown stratum"):
        stratum_output_root("colab", "d")
