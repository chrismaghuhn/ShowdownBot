"""Windows atomic-directory-publish helper (Gate B publish robustness fix).

Both the strength-holdout ARM and the COMBINE publish their fully-staged bundle with a single
atomic directory rename ``os.replace(staging_dir, out_dir)``. On Windows that one rename can fail
with a *transient* access/lock error (WinError 5 ACCESS_DENIED, 32 SHARING_VIOLATION,
33 LOCK_VIOLATION) even though the move itself is valid -- another process (indexer, AV, a
not-yet-released handle on a just-written staging file) can hold the directory or a file inside it
for a short window. Arm A on candidate ``c8752b3`` reproduced exactly this: all 180 battles ran
and staged, then the lone unguarded ``os.replace`` raised WinError 5 and the whole arm aborted
with no publish.

These tests pin the shared helper's contract with fully injected seams (no real clock, no real
filesystem race): bounded retry of ONLY the three classified transient winerrors, exactly one
publish, fail-closed on a persistent transient error (staging preserved, final absent), immediate
abort with no retry for a non-transient OSError, and never overwriting an existing final dir.
"""
from __future__ import annotations

import os

import pytest

from showdown_bot.eval.strength_holdout_runner import GateBAbort, _atomic_publish_dir


def _oserr(winerror):
    """A cross-platform stand-in for a Windows rename failure: a real OSError whose ``winerror``
    attribute the helper classifies. Set explicitly so the test is identical on POSIX CI, where
    the OS never populates ``winerror`` on its own."""
    exc = OSError("simulated rename failure")
    exc.winerror = winerror
    return exc


class _Replace:
    """A fake ``os.replace``: raises the queued exceptions (one per call) then succeeds. Records
    every ``(src, dst)`` call so the test can assert the exact attempt count."""

    def __init__(self, fail_with):
        self.fail_with = list(fail_with)
        self.calls = []

    def __call__(self, src, dst):
        self.calls.append((src, dst))
        if self.fail_with:
            exc = self.fail_with.pop(0)
            if exc is not None:
                raise exc


class _AlwaysRaise:
    def __init__(self, exc):
        self.exc = exc
        self.calls = []

    def __call__(self, src, dst):
        self.calls.append((src, dst))
        raise self.exc


class _Clock:
    """Deterministic monotonic clock: returns the queued values in order, repeating the last."""

    def __init__(self, values):
        self.values = list(values)
        self.i = 0

    def __call__(self):
        v = self.values[min(self.i, len(self.values) - 1)]
        self.i += 1
        return v


def test_publishes_on_the_first_try_with_no_retry(tmp_path):
    replace = _Replace(fail_with=[])  # succeeds immediately
    sleeps = []
    _atomic_publish_dir(
        "staging", "out", replace=replace, exists=lambda p: False,
        monotonic=_Clock([0.0]), sleep=sleeps.append,
    )
    assert replace.calls == [("staging", "out")]  # exactly one publish
    assert sleeps == []  # no retry, no backoff


def test_retries_winerror_5_then_publishes_exactly_once(tmp_path):
    replace = _Replace(fail_with=[_oserr(5), _oserr(5), None])  # 2 transient failures, then success
    sleeps = []
    _atomic_publish_dir(
        "staging", "out", replace=replace, exists=lambda p: False,
        monotonic=_Clock([0.0]), sleep=sleeps.append, deadline_s=10.0, backoff_s=0.2,
    )
    assert len(replace.calls) == 3  # two failed attempts + one successful publish
    assert sleeps == [0.2, 0.2]  # a bounded backoff between each retry


@pytest.mark.parametrize("winerror", [32, 33])
def test_retries_sharing_and_lock_violations_then_succeeds(winerror):
    replace = _Replace(fail_with=[_oserr(winerror), None])
    sleeps = []
    _atomic_publish_dir(
        "staging", "out", replace=replace, exists=lambda p: False,
        monotonic=_Clock([0.0]), sleep=sleeps.append,
    )
    assert len(replace.calls) == 2  # WinError 32/33 are transient too: retried, then published
    assert sleeps == [0.2]


def test_persistent_transient_error_aborts_after_the_deadline_and_preserves_staging(tmp_path):
    staging = tmp_path / "arm.staging"
    staging.mkdir()
    (staging / "rows.jsonl").write_text("kept for diagnosis\n", encoding="utf-8")
    out = tmp_path / "arm"
    replace = _AlwaysRaise(_oserr(5))  # the transient error never clears
    # start=0.0; after the first failed attempt elapsed=0.4 (< 1.0 -> retry); after the second
    # elapsed=2.0 (>= 1.0 -> give up). Bounded: two attempts, then a clean GateBAbort.
    with pytest.raises(GateBAbort, match="could not atomically publish"):
        _atomic_publish_dir(
            str(staging), str(out), replace=replace, exists=lambda p: False,
            monotonic=_Clock([0.0, 0.4, 2.0]), sleep=lambda s: None, deadline_s=1.0, backoff_s=0.2,
        )
    assert len(replace.calls) == 2  # bounded, not infinite
    assert staging.exists()  # staging left intact for diagnosis
    assert (staging / "rows.jsonl").read_text(encoding="utf-8") == "kept for diagnosis\n"
    assert not out.exists()  # final dir was never created; nothing copied or promoted


def test_non_transient_oserror_aborts_immediately_without_retry(tmp_path):
    replace = _AlwaysRaise(_oserr(13))  # 13 is NOT one of the classified transient winerrors
    sleeps = []
    with pytest.raises(OSError) as excinfo:
        _atomic_publish_dir(
            "staging", "out", replace=replace, exists=lambda p: False,
            monotonic=_Clock([0.0]), sleep=sleeps.append, deadline_s=10.0,
        )
    assert excinfo.value.winerror == 13  # the original OSError, not a GateBAbort
    assert not isinstance(excinfo.value, GateBAbort)
    assert len(replace.calls) == 1  # tried once, no retry
    assert sleeps == []


def test_plain_oserror_without_winerror_is_non_transient(tmp_path):
    replace = _AlwaysRaise(OSError("no winerror attribute at all"))
    with pytest.raises(OSError) as excinfo:
        _atomic_publish_dir(
            "staging", "out", replace=replace, exists=lambda p: False,
            monotonic=_Clock([0.0]), sleep=lambda s: None,
        )
    assert not isinstance(excinfo.value, GateBAbort)
    assert len(replace.calls) == 1  # winerror is None -> not classified transient -> no retry


def test_final_dir_appearing_during_retry_fails_closed_and_never_overwrites(tmp_path):
    # exists() is False at entry, then becomes True while we are between retries: another writer
    # published into out_dir mid-flight. The helper must refuse -- never overwrite -- and must not
    # attempt the rename again after seeing it.
    exists_seq = iter([False, True])
    replace = _Replace(fail_with=[_oserr(5)])  # first attempt hits a transient error, then retries
    with pytest.raises(GateBAbort, match="already exists"):
        _atomic_publish_dir(
            "staging", "out", replace=replace, exists=lambda p: next(exists_seq),
            monotonic=_Clock([0.0]), sleep=lambda s: None, deadline_s=10.0,
        )
    assert len(replace.calls) == 1  # never attempted again once out_dir appeared


def test_existing_final_dir_at_entry_fails_closed_without_touching_replace(tmp_path):
    replace = _Replace(fail_with=[])
    with pytest.raises(GateBAbort, match="already exists"):
        _atomic_publish_dir(
            "staging", "out", replace=replace, exists=lambda p: True,
            monotonic=_Clock([0.0]), sleep=lambda s: None,
        )
    assert replace.calls == []  # fail-closed before ever attempting the rename
