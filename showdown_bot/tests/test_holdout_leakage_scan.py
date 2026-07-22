import os
import subprocess

import pytest

from showdown_bot.eval.holdout_leakage_scan import (
    scan_for_leakage, scan_for_raw_payload_leakage, assert_no_holdout_leakage,
    LeakageDriftError, LeakageScanError, LeakageHit, _is_allowed,
)


def _init_repo(tmp_path, files: dict[str, bytes]) -> str:
    """Real git repo fixture: init, write, add, commit every given path -> bytes, exactly as
    given. Several tests below need REAL committed git blobs, not a monkeypatched stand-in for
    the comparison logic -- the whole point of the raw-payload scan (P1 #2, Rev. 12 review) is
    what it finds when it reads actual git-tracked content, including a case (CRLF) that mocking
    the comparison alone could never exercise."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    # Local to this throwaway fixture repo only (never --global): the fixture writes exact bytes
    # and must commit exactly those bytes, not whatever this machine's own core.autocrlf=true
    # would rewrite them to on `git add` -- and gpgsign=false so a machine with commit signing
    # enforced globally can't make this disposable fixture repo hang or fail.
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)
    for rel_path, content in files.items():
        full = repo / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(content)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=repo, check=True)
    return str(repo)


def test_is_allowed_matches_exact_allowlisted_files():
    assert _is_allowed("config/eval/panels/panel_champions_strength_holdout_v0.yaml")
    assert _is_allowed("config/eval/holdout/champions_strength_holdout_v0_manifest.json")
    assert _is_allowed("config/eval/baselines/champions-strength-holdout-v0.json")
    assert _is_allowed("config/eval/heldout_ledger.jsonl")


def test_is_allowed_matches_real_children_of_directory_prefixes():
    assert _is_allowed("showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.txt")
    assert _is_allowed("data/eval/champions-panel-v0/strength-holdout-v0/verdict.json")


def test_is_allowed_rejects_dev_and_coverage_paths():
    assert not _is_allowed("config/eval/schedules/champions_dev_gauntlet.yaml")
    assert not _is_allowed("showdown_bot/teams/panel_champions_v0/rain_offense.txt")
    assert not _is_allowed("config/eval/coverage/champions_coverage_v0_manifest.json")


def test_is_allowed_rejects_suffix_and_pseudo_subpath_bypasses_of_exact_files():
    # P1 #1 (Rev. 12 review): `path == prefix or path.startswith(prefix)` treated single FILES
    # as prefixes too, so anything sharing that prefix -- regardless of what followed it --
    # matched. Single files now require exact equality (ALLOWED_EXACT_PATHS); all three must be
    # rejected under the fixed rule.
    assert not _is_allowed("config/eval/heldout_ledger.jsonl.evil")
    assert not _is_allowed("config/eval/panels/panel_champions_strength_holdout_v0.yaml.backup")
    assert not _is_allowed("config/eval/holdout/champions_strength_holdout_v0_manifest.json/copied")


def test_is_allowed_normalizes_backslashes_before_comparing():
    # git itself always reports/expects forward slashes; a caller-supplied Windows-style path
    # (e.g. from os.path.join on Windows) must not bypass or miss the allowlist on that account.
    assert _is_allowed("showdown_bot\\teams\\panel_champions_strength_holdout_v0\\holdout_0.txt")
    assert not _is_allowed("config\\eval\\heldout_ledger.jsonl.evil")


def test_scan_for_leakage_finds_no_hits_for_an_identifier_absent_from_the_repo(tmp_path):
    # Found running for real: this can't default to cwd="." (the real ambient repo) -- the
    # Gate B plan document embeds this whole test file as a worked example and is itself
    # committed, so the "absent" identifier string literally appears in a tracked file the
    # moment the plan lands. An isolated fixture repo has no such self-reference risk.
    repo = _init_repo(tmp_path, {"README.md": b"unrelated content"})
    assert scan_for_leakage(["definitely-not-a-real-identifier-zzz-9f8e7d"], cwd=repo) == []


def test_scan_for_leakage_rejects_empty_identifier():
    with pytest.raises(ValueError, match="empty identifier"):
        scan_for_leakage([""])


def test_scan_for_raw_payload_leakage_flags_txt_payload_copied_into_a_report(tmp_path):
    txt_payload = b"Fixture Mon @ Focus Sash\nAbility: Levitate\n"
    repo = _init_repo(tmp_path, {
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.txt": txt_payload,
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.packed": b"|packed-0|",
        "reports/some-analysis.md": b"# Analysis\n\n" + txt_payload,
    })
    hits = scan_for_raw_payload_leakage(["holdout_0"], cwd=repo)
    assert any(h.path == "reports/some-analysis.md" for h in hits)


def test_scan_for_raw_payload_leakage_flags_packed_payload_copied_into_a_test_fixture(tmp_path):
    packed_payload = b"|packed-payload-bytes|"
    repo = _init_repo(tmp_path, {
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.txt": b"Fixture Mon @ Focus Sash\n",
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.packed": packed_payload,
        "showdown_bot/tests/fixtures/some_test_fixture.py": b"PACKED = " + packed_payload,
    })
    hits = scan_for_raw_payload_leakage(["holdout_0"], cwd=repo)
    assert any(h.path == "showdown_bot/tests/fixtures/some_test_fixture.py" for h in hits)


def test_scan_for_raw_payload_leakage_flags_payload_embedded_inside_a_larger_tracked_file(tmp_path):
    txt_payload = b"Fixture Mon @ Focus Sash\nAbility: Levitate\n"
    repo = _init_repo(tmp_path, {
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.txt": txt_payload,
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.packed": b"|packed-0|",
        # the payload sits in the MIDDLE of a much bigger tracked file -- not a whole-file match.
        "docs/scratch/team-dump.json": b'{"unrelated": "prefix", "blob": "' + txt_payload + b'", "more": "suffix"}',
    })
    hits = scan_for_raw_payload_leakage(["holdout_0"], cwd=repo)
    assert any(h.path == "docs/scratch/team-dump.json" for h in hits)


def test_scan_for_raw_payload_leakage_flags_a_txt_only_copy_with_no_packed_partner(tmp_path):
    # the OLD scan_for_content_leakage (Rev. 10 and earlier) required a co-located .packed file
    # to even compute a comparable hash -- a .txt-only copy was invisible by construction
    # (team_content_hash raised PanelError, silently skipped via `except PanelError: continue`).
    # The raw-payload scan has no such precondition: it matches byte content directly.
    txt_payload = b"Fixture Mon @ Focus Sash\nAbility: Levitate\n"
    repo = _init_repo(tmp_path, {
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.txt": txt_payload,
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.packed": b"|packed-0|",
        # a bare .txt copy elsewhere, deliberately with NO .packed sibling at all.
        "showdown_bot/teams/panel_champions_v0/suspicious_copy.txt": txt_payload,
    })
    hits = scan_for_raw_payload_leakage(["holdout_0"], cwd=repo)
    assert any(h.path == "showdown_bot/teams/panel_champions_v0/suspicious_copy.txt" for h in hits)


def test_scan_for_raw_payload_leakage_does_not_flag_the_holdouts_own_allowlisted_files(tmp_path):
    txt_payload = b"Fixture Mon @ Focus Sash\nAbility: Levitate\n"
    packed_payload = b"|packed-0|"
    repo = _init_repo(tmp_path, {
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.txt": txt_payload,
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.packed": packed_payload,
        # legitimate self-reference: the manifest happens to embed the team's own .txt content
        # verbatim (e.g. a debug/export dump) -- must NOT be flagged, it's the holdout's own file.
        "config/eval/holdout/champions_strength_holdout_v0_manifest.json": b'{"embedded": "' + txt_payload + b'"}',
        "data/eval/champions-panel-v0/strength-holdout-v0/rows.jsonl": packed_payload,
    })
    hits = scan_for_raw_payload_leakage(["holdout_0"], cwd=repo)
    assert hits == []


def test_scan_for_raw_payload_leakage_rejects_an_empty_payload(tmp_path):
    # fail-closed (P1 #2, Rev. 12 review): an empty payload would match every tracked file
    # trivially (`b"" in x` is always True in Python) -- a silent no-op dressed up as "clean".
    repo = _init_repo(tmp_path, {
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.txt": b"",
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.packed": b"|packed-0|",
    })
    with pytest.raises(ValueError, match="empty"):
        scan_for_raw_payload_leakage(["holdout_0"], cwd=repo)


def test_scan_for_raw_payload_leakage_rejects_an_empty_team_id_list():
    # P1 fix (Rev. 13, §1l, second review round): an empty team_ids list must fail closed here
    # too, independent of Task 10's own caller-side cross-check (defense in depth, not either/or)
    # -- otherwise `payloads` stays {} and the scan silently "passes" without checking anything.
    with pytest.raises(ValueError, match="team_ids must be non-empty"):
        scan_for_raw_payload_leakage([])


def test_scan_for_raw_payload_leakage_wraps_a_git_blob_read_failure(tmp_path):
    # fail-closed (P1 #2, Rev. 12 review): a team_id with no actual committed blob at the
    # conventional path (e.g. a caller passes a team_id that was never sealed/committed) must
    # raise LeakageScanError, not silently scan with a missing/empty needle or crash raw.
    repo = _init_repo(tmp_path, {"README.md": b"unrelated"})
    with pytest.raises(LeakageScanError, match="could not read committed blob"):
        scan_for_raw_payload_leakage(["never_sealed_team"], cwd=repo)


def test_scan_for_raw_payload_leakage_reads_committed_bytes_not_the_crlf_working_copy(tmp_path):
    # DESIGN sec 3.3 + P1 #2 (Rev. 12 review): panel.team_content_hash reads via
    # Path.read_text(), which is subject to this repo's own global core.autocrlf=true translation
    # on a Windows checkout -- a needle sourced that way would silently stop matching a haystack
    # sourced from committed (LF) blob bytes the moment the working copy's line endings drift
    # from what is actually committed. This scan must never have that failure mode: both the
    # needle (the sealed payload) and every haystack file are read via `git show HEAD:<path>`,
    # which returns the COMMITTED bytes regardless of what sits in the working copy right now.
    payload_lf = b"Fixture Mon @ Focus Sash\nAbility: Levitate\n"
    repo = _init_repo(tmp_path, {
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.txt": payload_lf,
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.packed": b"|packed-0|",
        "reports/leaked-copy.md": payload_lf,  # outside the allowlist -- the leak to catch
    })
    # Corrupt the WORKING COPY of the sealed team's own .txt to CRLF, post-commit, WITHOUT
    # committing that change -- the committed blob (what `git show` reads) stays pure LF.
    working_copy_path = os.path.join(
        repo, "showdown_bot", "teams", "panel_champions_strength_holdout_v0", "holdout_0.txt",
    )
    with open(working_copy_path, "wb") as fh:
        fh.write(payload_lf.replace(b"\n", b"\r\n"))

    hits = scan_for_raw_payload_leakage(["holdout_0"], cwd=repo)
    assert any(h.path == "reports/leaked-copy.md" for h in hits)


def test_assert_no_holdout_leakage_raises_on_either_scan_type(monkeypatch):
    monkeypatch.setattr(
        "showdown_bot.eval.holdout_leakage_scan.scan_for_leakage",
        lambda identifiers, cwd=".": [LeakageHit(identifier="leaked-id", path="config/eval/schedules/other.yaml", line="x")],
    )
    monkeypatch.setattr(
        "showdown_bot.eval.holdout_leakage_scan.scan_for_raw_payload_leakage",
        lambda team_ids, cwd=".": [],
    )
    # team_ids is a placeholder here (the real scan is mocked away) -- kept non-empty since an
    # empty list is no longer a legal input to the real scan_for_raw_payload_leakage (Rev. 13).
    with pytest.raises(LeakageDriftError, match="leaked-id"):
        assert_no_holdout_leakage(identifiers=["leaked-id"], team_ids=["placeholder"])


def test_assert_no_holdout_leakage_raises_on_raw_payload_hits_too(monkeypatch):
    monkeypatch.setattr(
        "showdown_bot.eval.holdout_leakage_scan.scan_for_leakage",
        lambda identifiers, cwd=".": [],
    )
    monkeypatch.setattr(
        "showdown_bot.eval.holdout_leakage_scan.scan_for_raw_payload_leakage",
        lambda team_ids, cwd=".": [LeakageHit(identifier="holdout_0:txt", path="reports/leak.md", line="(raw payload match)")],
    )
    with pytest.raises(LeakageDriftError, match="holdout_0:txt"):
        assert_no_holdout_leakage(identifiers=[], team_ids=["holdout_0"])


def test_git_tracked_files_wraps_a_called_process_error(tmp_path):
    # NF4 fix (Rev. 8): check=True raises subprocess.CalledProcessError when cwd is not a git
    # repository -- a real (not mocked) way to trigger it: point cwd at an empty tmp_path. This
    # was unguarded and would escape scan_for_leakage/scan_for_raw_payload_leakage ->
    # assert_no_holdout_leakage -> combine_strength_holdout_arms as a raw traceback. The N3 fix
    # (Rev. 5) that made cwd/teams_root caller-controllable is exactly what makes this reachable:
    # a caller-supplied teams_root that isn't a git checkout now reaches git directly.
    from showdown_bot.eval.holdout_leakage_scan import _git_tracked_files
    with pytest.raises(LeakageScanError, match="could not list git-tracked files"):
        _git_tracked_files(cwd=str(tmp_path))


def test_grep_identifier_wraps_a_missing_git_executable(monkeypatch):
    # Self-found sibling gap in the same module, same pass: _grep_identifier never set check=True
    # (a nonzero exit is already handled via the manual returncode check right below it), but
    # subprocess.run raises FileNotFoundError for a missing git executable regardless of check=.
    from showdown_bot.eval.holdout_leakage_scan import _grep_identifier

    def _raise(*a, **kw):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr("showdown_bot.eval.holdout_leakage_scan.subprocess.run", _raise)
    with pytest.raises(LeakageScanError, match="could not run git grep"):
        _grep_identifier("some-id", ["some/file.txt"])


def test_read_git_blob_wraps_a_called_process_error(tmp_path):
    # a path that isn't tracked at HEAD (or cwd isn't a git repo) makes `git show HEAD:<path>`
    # exit non-zero -- must surface as LeakageScanError, not a raw CalledProcessError.
    from showdown_bot.eval.holdout_leakage_scan import _read_git_blob
    repo = _init_repo(tmp_path, {"README.md": b"unrelated"})
    with pytest.raises(LeakageScanError, match="could not read committed blob"):
        _read_git_blob("no/such/path.txt", cwd=repo)
