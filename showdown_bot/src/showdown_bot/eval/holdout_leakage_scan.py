"""Repo-wide leakage-drift guard for the Gate B strength holdout (DESIGN sec 3.3): scans for
BOTH short identifiers (team_hash/team_path/team_id -- line-based grep is fine here) AND the
actual sealed .txt/.packed CONTENT appearing anywhere else in the repo (packed/.txt content --
grep cannot reliably match multi-line content, and a whole-file combined-hash comparison misses a
payload copied into a bigger file or copied without its hash-partner -- see Rev. 12 review's
P1 #2, §1k, fixed this revision by a byte-exact substring scan over every git-tracked file's
COMMITTED content)."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass

ALLOWED_EXACT_PATHS = (
    "config/eval/panels/panel_champions_strength_holdout_v0.yaml",
    "config/eval/holdout/champions_strength_holdout_v0_manifest.json",
    "config/eval/baselines/champions-strength-holdout-v0.json",
    "config/eval/heldout_ledger.jsonl",
)
ALLOWED_DIRECTORY_PREFIXES = (
    "showdown_bot/teams/panel_champions_strength_holdout_v0/",
    "data/eval/champions-panel-v0/strength-holdout-v0/",
    # Spec Amendment A1.2 (APPROVED, 2026-07-22): the holdout's own frozen provenance directory.
    # The six sealed .txt team files are DELIBERATELY byte-identical to the pastes frozen here --
    # that byte-equality is the evidence nothing was altered between the published source and the
    # sealed artifact. scan_for_raw_payload_leakage uses those bytes as its needle, so without this
    # entry the guard reports the holdout's own authoritative source as a leak. Renaming the teams
    # cannot avoid it: the needle is the file's content, not its name.
    #
    # Scope is exactly this directory. The sibling selection-audit file, any broader docs/ prefix,
    # and every test file stay OUTSIDE the allowlist and must keep failing the scan. The trailing
    # "/" makes this a bounded directory prefix, so a similarly-named sibling directory does not
    # inherit the exemption (see _is_allowed).
    "docs/projects/champions/audits/2026-07-22-task13-vgcpastes-source-evidence/",
)
HOLDOUT_TEAMS_DIR = "showdown_bot/teams/panel_champions_strength_holdout_v0/"


class LeakageDriftError(Exception):
    """The scan COMPLETED and FOUND a leak (or git grep itself reported a real error)."""


class LeakageScanError(Exception):
    """NF4 fix (Rev. 8): the scan could NOT be completed at all (git missing from PATH, `cwd`/
    `teams_root` is not a git repository, or a sealed team's committed blob could not be read) --
    distinct from LeakageDriftError, which means the scan ran to completion and found something.
    Collapsing the two would erase a distinction a caller might reasonably want: retrying an
    infra failure is sensible, auto-retrying past a genuine leak finding is not. Left unwrapped
    by combine_strength_holdout_arms, exactly like LeakageDriftError already is (§1f/§19) -- the
    CLI boundary is where these get a documented, per-class handler, not this module."""


@dataclass(frozen=True)
class LeakageHit:
    identifier: str
    path: str
    line: str


def _normalize_path(path: str) -> str:
    """Git always reports/expects forward-slash paths regardless of OS; normalize before any
    comparison so a caller-supplied Windows-style path (e.g. from os.path.join) can't bypass or
    miss the allowlist purely on separator form (P1 #1, Rev. 12 review, §1k)."""
    return path.replace("\\", "/")


def _is_allowed(path: str) -> bool:
    path = _normalize_path(path)
    if path in ALLOWED_EXACT_PATHS:
        return True
    # P1 #1 fix (Rev. 12 review, §1k): directory prefixes already end in "/", so
    # `.startswith(prefix)` only ever matches a REAL child under that directory --
    # "...strength_holdout_v0_evil/x" does NOT start with ".../strength_holdout_v0/" (the "/"
    # itself breaks the match). The bug was never in this branch; it was single FILES being
    # checked with the same startswith rule but no trailing separator to protect them -- fixed by
    # requiring exact equality for those instead (above), not by changing this branch.
    return any(path.startswith(prefix) for prefix in ALLOWED_DIRECTORY_PREFIXES)


def _git_tracked_files(cwd: str = ".") -> list[str]:
    # N3 fix: explicit cwd, never ambient process CWD -- a "unit" test (or a caller with a
    # non-default teams_root) that relies on process CWD is a real Windows-multi-worktree
    # failure mode, not a hypothetical one.
    #
    # NF4 fix (Rev. 8): check=True raises subprocess.CalledProcessError if cwd is not a git repo
    # (or any other nonzero git exit); a missing git executable raises FileNotFoundError from
    # subprocess.run itself, check=True or not. Neither was caught anywhere -- both would escape
    # as a raw traceback through scan_for_leakage/scan_for_raw_payload_leakage ->
    # assert_no_holdout_leakage -> combine_strength_holdout_arms. The N3 fix that made `cwd`
    # caller-controllable is exactly what makes this reachable: a caller-supplied teams_root that
    # doesn't point at a git checkout now reaches git directly, where it didn't before.
    try:
        result = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True, cwd=cwd)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise LeakageScanError(f"could not list git-tracked files under cwd={cwd!r}: {exc}") from exc
    return [line for line in result.stdout.splitlines() if line]


def _read_git_blob(path: str, *, cwd: str = ".") -> bytes:
    """Reads a git-tracked file's COMMITTED bytes (HEAD's blob) -- never the working-copy bytes.
    Reading via open()/Path.read_text() (as panel.py's team_content_hash does, for a different,
    still-legitimate purpose -- team identity/disjointness, not this scan) would make this scan's
    result depend on this repo's global core.autocrlf=true translation on a Windows checkout,
    since a needle and haystack sourced from two different places (one committed, one
    working-copy) can silently stop matching even when the underlying content is identical
    (P1 #2, Rev. 12 review, §1k). `git show HEAD:<path>` reads the blob straight out of the
    object database in binary form, bypassing any working-tree filter, so every comparison this
    function feeds compares the same kind of bytes on both sides."""
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{path}"], capture_output=True, check=True, cwd=cwd,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise LeakageScanError(f"could not read committed blob for {path!r} under cwd={cwd!r}: {exc}") from exc
    return result.stdout


def _grep_identifier(identifier: str, files: list[str], cwd: str = ".") -> list[LeakageHit]:
    if not identifier:
        raise ValueError("empty identifier would match every line in the repo")
    if not files:
        return []
    # NF4 fix (Rev. 8): unlike _git_tracked_files, this call never set check=True -- a nonzero
    # exit is already handled below via the manual returncode check. But subprocess.run raises
    # FileNotFoundError (git missing from PATH) regardless of check=, and that path was still
    # unguarded -- self-found while fixing NF4's sibling gap in the same module, same pass.
    #
    # Found running the real test suite against this repo's own 2038 tracked files (131 KB of
    # path text): passing `files` as individual argv entries overflows Windows' CreateProcess
    # command-line length limit (WinError 206, "filename or extension too long") well before
    # 32K chars. `files` is always the caller's complete _git_tracked_files() list (never a
    # narrower subset), and `git grep` with no explicit pathspec already searches every tracked
    # file by default -- so omitting the file list changes nothing about what gets searched,
    # only how the scope is expressed, and removes the argv-length ceiling entirely.
    try:
        result = subprocess.run(
            ["git", "grep", "-n", "-F", identifier], capture_output=True, text=True, cwd=cwd,
        )
    except FileNotFoundError as exc:
        raise LeakageScanError(f"could not run git grep under cwd={cwd!r}: {exc}") from exc
    if result.returncode not in (0, 1):
        raise LeakageDriftError(f"git grep failed for {identifier!r}: {result.stderr.strip()}")
    hits = []
    for line in result.stdout.splitlines():
        path, _, rest = line.partition(":")
        hits.append(LeakageHit(identifier=identifier, path=path, line=rest))
    return hits


def scan_for_leakage(identifiers: list[str], *, cwd: str = ".") -> list[LeakageHit]:
    """Short-token scan (team_hash/team_path/team_id). Empty list == clean."""
    files = _git_tracked_files(cwd=cwd)
    violations: list[LeakageHit] = []
    for identifier in identifiers:
        for hit in _grep_identifier(identifier, files, cwd=cwd):
            if not _is_allowed(hit.path):
                violations.append(hit)
    return violations


def scan_for_raw_payload_leakage(team_ids: list[str], *, cwd: str = ".") -> list[LeakageHit]:
    """Byte-exact scan (DESIGN sec 3.3's 'packed/.txt content' leg; P1 #2 fix, Rev. 12 review,
    §1k): for each sealed holdout team_id, reads its .txt and .packed COMMITTED payload (path
    derived from the fixed HOLDOUT_TEAMS_DIR convention -- the same directory
    ALLOWED_DIRECTORY_PREFIXES already grants) and checks every OTHER git-tracked file's
    COMMITTED bytes for that exact payload as a substring.

    Unlike the whole-file combined-hash comparison this replaces (Rev. 10 and earlier's
    scan_for_content_leakage / _all_tracked_team_content_hashes), this is repo-wide (every
    git-tracked file, not just showdown_bot/teams/*.txt), requires no co-located .packed partner
    on the OTHER side of the comparison (a bare copied .txt is still caught), and matches a
    payload embedded inside a larger file (substring, not whole-file equality). The existing
    combined panel.team_content_hash remains the right tool for team IDENTITY and DISJOINTNESS
    (Task 5, and Task 9's opp_team_hash row-stamping) -- a single hash per team is exactly what
    those need; it is not replaced, only no longer relied on for THIS scan.

    Fails closed on every kind of degenerate input, never silently: an EMPTY team_ids LIST would
    make the whole scan a silent no-op (the payload-collection loop never runs, so `payloads`
    stays `{}` and every downstream file trivially "passes" -- rejected here, Rev. 13 §1l second
    review round P1, as defense in depth independent of Task 10's own caller-side check). An
    empty PAYLOAD for a given team would match every tracked file trivially (`b"" in x` is always
    True in Python); a missing or unreadable committed blob for a claimed team_id is refused
    (LeakageScanError, via _read_git_blob) rather than scanned as an empty needle or silently
    skipped."""
    if not team_ids:
        raise ValueError("team_ids must be non-empty -- an empty list makes this scan vacuous (it would silently report no leaks without checking anything)")
    payloads: dict[str, bytes] = {}
    for team_id in team_ids:
        txt_path = f"{HOLDOUT_TEAMS_DIR}{team_id}.txt"
        packed_path = f"{HOLDOUT_TEAMS_DIR}{team_id}.packed"
        txt_bytes = _read_git_blob(txt_path, cwd=cwd)
        packed_bytes = _read_git_blob(packed_path, cwd=cwd)
        if not txt_bytes:
            raise ValueError(f"empty .txt payload for {team_id!r} at {txt_path!r} -- refusing to scan")
        if not packed_bytes:
            raise ValueError(f"empty .packed payload for {team_id!r} at {packed_path!r} -- refusing to scan")
        payloads[f"{team_id}:txt"] = txt_bytes
        payloads[f"{team_id}:packed"] = packed_bytes

    violations: list[LeakageHit] = []
    for path in _git_tracked_files(cwd=cwd):
        if _is_allowed(path):
            continue
        blob = _read_git_blob(path, cwd=cwd)
        for name, payload in payloads.items():
            if payload in blob:
                violations.append(LeakageHit(identifier=name, path=path, line="(raw payload match)"))
    return violations


def assert_no_holdout_leakage(*, identifiers: list[str], team_ids: list[str], teams_root: str = ".") -> None:
    violations = scan_for_leakage(identifiers, cwd=teams_root) + scan_for_raw_payload_leakage(team_ids, cwd=teams_root)
    if violations:
        detail = "\n".join(f"  {v.identifier!r} in {v.path}: {v.line.strip()}" for v in violations)
        raise LeakageDriftError(f"holdout identifier(s)/content leaked outside the allowlist:\n{detail}")
