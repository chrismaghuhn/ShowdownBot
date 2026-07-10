"""tools/kaggle/kernel_payload.py -- repo-side payload for Kaggle kernels (slice 2b-2.5a Task 2).

Imported by the thin single-file kernel scripts (``tools/kaggle/repro_validation.py``, later
``tools/kaggle/datagen_kernel.py``) AFTER they have cloned this repo at a pinned sha onto the
Kaggle instance. Splitting the logic out here (instead of inlining it in the kernel script)
makes it testable locally via a normal Python import.

Two families of functions live here, exactly like ``kaggle_driver.py``'s split:

1. Operational, Linux/Kaggle-target run-functions (``bootstrap_node``'s install branch,
   ``setup_showdown``, ``run_schedule_seeded``, ``copy_outputs``) -- these start subprocesses
   (node/git/the gauntlet CLI) and are NOT exercised by the local test suite. HARD CONSTRAINT
   (2026-07-10): the local CPU is saturated by a separate training job -- no local battle runs
   or Showdown servers anywhere in this slice. These functions only ever run on Kaggle.
2. Pure / read-only functions (``_parse_node_major``, ``validate_prefix_reproduction``,
   ``print_verdict``) -- these work everywhere and are unit-tested locally in
   ``showdown_bot/tests/test_kernel_payload.py``. ``validate_prefix_reproduction`` in
   particular only ever READS committed artifacts (the T4b prefix-reproduction fixture under
   ``data/eval/t4/rerun/``) plus a synthetic ``out_dir`` the test builds by copying that same
   fixture -- it never runs a battle.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from showdown_bot.eval.baseline import WinnerSequenceError, verify_winner_sequence
from showdown_bot.eval.room_dump import GAUNTLET_NAME_SUBS, normalize_battle_log
from showdown_bot.eval.run_manifest import load_showdown_commit

# Committed Phase-1 reproduction fixture (T4b, see reports/2026-07-10-2b35-T4-rerun.md Sec.9).
_PREFIX_REFERENCE_JSONL = "data/eval/t4/rerun/t4rerun-prefix.jsonl"
_PREFIX_REFERENCE_ROOM_RAW_DIR = "data/eval/t4/rerun/room_raw/prefix"
_PATCH_RELPATH = "tools/eval/patches/pokemon-showdown-seeded-battle.patch"

_SHOWDOWN_REPO_URL = "https://github.com/smogon/pokemon-showdown"
_SERVER_PORT = 8000
_SERVER_START_TIMEOUT_S = 120

_ROOM_NUMBER_RE = re.compile(r"(\d+)\.log(?:\.gz)?$")

# Files copy_outputs mirrors into the Kaggle working dir verbatim (when present).
_FLAT_OUTPUT_NAMES = (
    "results.jsonl",
    "results.jsonl.manifest.json",
    "seeds.jsonl",
    "client.log",
    "verdict.txt",
)


# ---------------------------------------------------------------------------
# Node bootstrap
# ---------------------------------------------------------------------------

def _parse_node_major(version_text: str) -> int:
    """Parse the major version number out of a ``node --version`` string, e.g.
    ``'v20.1.0' -> 20`` (also tolerates a missing leading 'v'). Raises ``ValueError`` if no
    digit run is found."""
    match = re.search(r"(\d+)", version_text)
    if not match:
        raise ValueError(f"cannot parse a node major version from {version_text!r}")
    return int(match.group(1))


def _node_version() -> str | None:
    try:
        result = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def bootstrap_node(min_major: int = 18) -> str:
    """Ensure a Node.js >= ``min_major`` is on PATH, installing it if necessary. Returns the
    (post-install) ``node --version`` output. Idempotent: a no-op when Node is already new
    enough. Kaggle-image assumption: apt (Debian-based image, likely root) or conda is
    available; tries apt first, then conda, then gives up with a clear error."""
    version = _node_version()
    if version is not None and _parse_node_major(version) >= min_major:
        return version

    for install_cmd in (
        ["apt-get", "install", "-y", "nodejs", "npm"],
        ["conda", "install", "-y", "nodejs"],
    ):
        try:
            subprocess.run(install_cmd, check=True)
        except (OSError, subprocess.CalledProcessError):
            continue
        version = _node_version()
        if version is not None and _parse_node_major(version) >= min_major:
            return version

    raise RuntimeError(
        f"could not bootstrap Node.js >= {min_major}: neither 'apt-get install -y nodejs npm' "
        f"nor 'conda install -y nodejs' produced a new-enough node (last seen: {version!r}). "
        "On Kaggle, check that the kernel has internet enabled and that the base image's "
        "package manager is reachable; a persistent failure here means the kernel bootstrap "
        "(this function), not repo source, needs a fix -- see plan Task 3 bounded iteration."
    )


# ---------------------------------------------------------------------------
# pokemon-showdown checkout + patch + build
# ---------------------------------------------------------------------------

def setup_showdown(repo_root, cache_dir) -> str:
    """Clone ``pokemon-showdown`` into ``cache_dir`` (if absent), check out the pinned
    ``provenance.yaml`` commit, apply the versioned seeded-battle server patch (idempotent --
    skips if already applied), then ``node build``. Returns the showdown checkout dir."""
    repo_root = Path(repo_root)
    cache_dir = Path(cache_dir)
    showdown_dir = cache_dir / "pokemon-showdown"
    commit = load_showdown_commit(str(repo_root / "config" / "eval" / "provenance.yaml"))
    patch_path = repo_root / _PATCH_RELPATH

    if not showdown_dir.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", _SHOWDOWN_REPO_URL, str(showdown_dir)], check=True)

    subprocess.run(["git", "checkout", commit], cwd=str(showdown_dir), check=True)

    can_apply = subprocess.run(
        ["git", "apply", "--check", str(patch_path)], cwd=str(showdown_dir), capture_output=True,
    )
    if can_apply.returncode == 0:
        subprocess.run(["git", "apply", str(patch_path)], cwd=str(showdown_dir), check=True)
    else:
        already_applied = subprocess.run(
            ["git", "apply", "--reverse", "--check", str(patch_path)],
            cwd=str(showdown_dir), capture_output=True,
        )
        if already_applied.returncode != 0:
            raise RuntimeError(
                f"{_PATCH_RELPATH} neither applies nor is already applied at "
                f"{showdown_dir} @ {commit} -- showdown checkout state is unexpected"
            )
        # Already applied (a re-run against a warm cache_dir): nothing to do.

    subprocess.run(["node", "build"], cwd=str(showdown_dir), check=True)
    return str(showdown_dir)


# ---------------------------------------------------------------------------
# Seeded schedule run (server + client subprocesses)
# ---------------------------------------------------------------------------

def _wait_for_port(host: str, port: int, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"server did not open port {port} within {timeout_s}s (last error: {last_error})")


def run_schedule_seeded(repo_root, showdown_dir, schedule_relpath, seed_base, out_dir, *,
                         dataset_export=None, extra_env=None, timeout_s=9000) -> dict:
    """Start a fresh seeded server (Channel A, counter from 0), run the T2 gauntlet CLI against
    ``schedule_relpath`` with the standard seeded/dataset env, then stop the server. Returns a
    dict of output paths under ``out_dir`` (results/seeds/client_log/room_raw_dir, +
    dataset_export when given).

    ``schedule_relpath`` is resolved against ``repo_root`` (e.g.
    ``config/eval/schedules/t4_smoke_v001_prefix.yaml``, which lives at the repo root, NOT
    under ``showdown_bot/``) and passed to ``--schedule`` as an absolute path -- the gauntlet
    CLI itself always runs with ``cwd=<repo_root>/showdown_bot`` (matching every committed
    reproduction recipe, e.g. reports/2026-07-10-2b35-T4-rerun.md Sec.9), so a bare relative
    path would resolve one directory too shallow.
    """
    repo_root = Path(repo_root)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    schedule_path = Path(repo_root) / schedule_relpath

    seed_log = out_dir / "seeds.jsonl"
    results = out_dir / "results.jsonl"
    room_raw_dir = out_dir / "room_raw"
    client_log = out_dir / "client.log"

    server_env = dict(os.environ)
    server_env["SHOWDOWN_BATTLE_SEED_BASE"] = seed_base
    server_env["SHOWDOWN_EVAL_SEED_LOG"] = str(seed_log)

    server_proc = subprocess.Popen(
        ["node", "pokemon-showdown", "start", str(_SERVER_PORT), "--no-security"],
        cwd=str(showdown_dir), env=server_env,
    )
    try:
        _wait_for_port("localhost", _SERVER_PORT, timeout_s=_SERVER_START_TIMEOUT_S)

        client_env = dict(os.environ)
        client_env.update({
            "PYTHONHASHSEED": "0",
            "SHOWDOWN_CALC_BACKEND": "persistent",
            "SHOWDOWN_BATTLE_SEED_BASE": seed_base,
            "SHOWDOWN_EVAL_SEED_LOG": str(seed_log),
            "SHOWDOWN_ROOM_RAW_DUMP": str(room_raw_dir),
        })
        if dataset_export is not None:
            client_env["SHOWDOWN_DATASET_EXPORT"] = str(dataset_export)
            client_env["SHOWDOWN_DATASET_TEACHER"] = "rollout"
        if extra_env:
            client_env.update(extra_env)

        cmd = [
            sys.executable, "-m", "showdown_bot.cli", "gauntlet",
            "--schedule", str(schedule_path),
            "--result-out", str(results),
        ]
        with open(client_log, "w", encoding="utf-8") as log_fh:
            subprocess.run(
                cmd, cwd=str(repo_root / "showdown_bot"), env=client_env,
                stdout=log_fh, stderr=subprocess.STDOUT, timeout=timeout_s, check=True,
            )
    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            server_proc.kill()

    paths = {
        "results": str(results),
        "seeds": str(seed_log),
        "client_log": str(client_log),
        "room_raw_dir": str(room_raw_dir),
        "manifest": f"{results}.manifest.json",
    }
    if dataset_export is not None:
        paths["dataset_export"] = str(dataset_export)
    return paths


# ---------------------------------------------------------------------------
# Prefix-reproduction validation (pure file reads; local-testable)
# ---------------------------------------------------------------------------

def _load_jsonl(path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _room_number(path: Path) -> int:
    match = _ROOM_NUMBER_RE.search(path.name)
    if not match:
        raise ValueError(f"cannot parse a trailing room number from {path.name!r}")
    return int(match.group(1))


def _read_room_log_frames(path: Path) -> list[str]:
    """Read a dumped room_raw log (plain ``.log`` or gzipped ``.log.gz``) back into the
    ``frames`` shape ``normalize_battle_log`` expects. ``dump_room_raw`` writes a file as
    ``"\\n".join(frames)``, so reading the whole file back as a single-element list round-trips
    correctly -- ``normalize_battle_log`` re-splits on "\\n" internally regardless of the
    original per-frame boundaries."""
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return [fh.read()]
    return [path.read_text(encoding="utf-8")]


def validate_prefix_reproduction(repo_root, out_dir) -> tuple[bool, str]:
    """Verify a fresh ``out_dir`` run reproduces the committed T4b prefix fixture: winner+seed
    sequence match (``verify_winner_sequence``) AND normalized room-log byte identity for all
    10 battles. Pure file reads -- reads ``<out_dir>/results.jsonl`` +
    ``<out_dir>/room_raw/*.log`` (fresh) against the committed
    ``data/eval/t4/rerun/t4rerun-prefix.jsonl`` + ``data/eval/t4/rerun/room_raw/prefix/*.log.gz``
    (reference). Returns ``(ok, detail)`` -- never raises."""
    repo_root = Path(repo_root)
    out_dir = Path(out_dir)

    fresh_results_path = out_dir / "results.jsonl"
    reference_results_path = repo_root / _PREFIX_REFERENCE_JSONL
    try:
        fresh_rows = _load_jsonl(fresh_results_path)
        reference_rows = _load_jsonl(reference_results_path)
    except OSError as exc:
        return False, f"could not read result rows: {exc}"

    try:
        verify_winner_sequence(reference_rows, fresh_rows)
    except WinnerSequenceError as exc:
        return False, str(exc)

    fresh_room_dir = out_dir / "room_raw"
    reference_room_dir = repo_root / _PREFIX_REFERENCE_ROOM_RAW_DIR

    try:
        fresh_logs = sorted(fresh_room_dir.glob("*.log"), key=_room_number)
        reference_logs = sorted(reference_room_dir.glob("*.log.gz"), key=_room_number)
    except (OSError, ValueError) as exc:
        return False, f"could not list room_raw logs: {exc}"

    if not reference_logs:
        return False, f"no reference room logs found under {reference_room_dir}"
    if len(fresh_logs) != len(reference_logs):
        return False, (
            f"room log count mismatch: fresh has {len(fresh_logs)}, "
            f"reference has {len(reference_logs)}"
        )

    for i, (fresh_path, ref_path) in enumerate(zip(fresh_logs, reference_logs)):
        fresh_norm = normalize_battle_log(_read_room_log_frames(fresh_path), name_subs=GAUNTLET_NAME_SUBS)
        ref_norm = normalize_battle_log(_read_room_log_frames(ref_path), name_subs=GAUNTLET_NAME_SUBS)
        if fresh_norm != ref_norm:
            return False, (
                f"room log mismatch at index {i}: fresh={fresh_path.name!r} "
                f"vs reference={ref_path.name!r}"
            )

    n = len(fresh_logs)
    return True, f"{n}/{n} winner+seed match, {n}/{n} room logs byte-identical after normalization"


# ---------------------------------------------------------------------------
# Verdict + output archival
# ---------------------------------------------------------------------------

def print_verdict(tag: str, ok: bool, detail: str) -> str:
    """Print (and return) the machine-greppable verdict line ``kaggle_driver.parse_verdict``
    scans for: ``<TAG>: PASS (detail)`` / ``<TAG>: FAIL (detail)``."""
    line = f"{tag}: {'PASS' if ok else 'FAIL'} ({detail})"
    print(line)
    return line


def copy_outputs(out_dir, working_dir="/kaggle/working") -> list[str]:
    """Copy the flat run outputs (results/manifest/seeds/client log/verdict) plus a gzipped
    copy of every room_raw log into ``working_dir``, so the driver's ``download_output`` picks
    them all up. Returns the list of destination paths actually written."""
    out_dir = Path(out_dir)
    working_dir = Path(working_dir)
    working_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for name in _FLAT_OUTPUT_NAMES:
        src = out_dir / name
        if src.exists():
            dest = working_dir / name
            shutil.copy2(src, dest)
            written.append(str(dest))

    room_raw_src = out_dir / "room_raw"
    if room_raw_src.is_dir():
        room_raw_dest = working_dir / "room_raw"
        room_raw_dest.mkdir(parents=True, exist_ok=True)
        for log_path in sorted(room_raw_src.glob("*.log")):
            gz_dest = room_raw_dest / f"{log_path.name}.gz"
            with open(log_path, "rb") as src_fh, gzip.open(gz_dest, "wb") as dst_fh:
                shutil.copyfileobj(src_fh, dst_fh)
            written.append(str(gz_dest))

    return written
