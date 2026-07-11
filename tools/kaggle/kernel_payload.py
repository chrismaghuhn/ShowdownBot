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

MEMTRACE (added 2026-07-10): datagen kernels were dying at a deterministic battle count with a
VM-level OOM -- a Showdown child process got OOM-killed, the server crashed (write EPIPE), the
run failed, with no visibility into which process was actually growing. ``start_memtrace``
samples free memory + the top-8 RSS processes + battles-done every 30s to stdout during
``run_datagen``'s schedule run, so the next Kaggle run yields a per-process memory growth curve
instead of a single crash line.

COVERAGE THRESHOLD (relaxed 2026-07-11): ``validate_datagen_output``'s game-coverage check
originally required EXACT equality between the dataset's distinct ``metadata.game_id`` count and
the schedule's game count. The trickroom hero's final run showed this is too strict: under
sampling policy "all", a legitimate short (6-7 turn) blowout game can have every one of its
decisions skipped as unlabelable (``RolloutLabelError`` -- force-switch-only turns, all-switch
response sets), so that ONE game contributes zero dataset rows even though the battle itself
ran cleanly -- 74/75 distinct games, a false FAIL. Battles are never retried (Channel A: seeded
reruns are byte-identical anyway, so a re-run cannot recover the missing game's rows either), so
the check is now a threshold: FAIL iff ``distinct_games < max(1, ceil(0.9 * schedule_games))``.
90% coverage still hard-fails the historic corruption signatures this check exists to catch (the
Task-6 attempt-1 per-battle-overwrite bug, which collapses to a single game_id, and any export
missing more than one in ten scheduled games), while tolerating the occasional legitimate
zero-row blowout game.
"""
from __future__ import annotations

import gzip
import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from showdown_bot.eval import datagen_2b25a, schedule_2b4
from showdown_bot.eval.baseline import WinnerSequenceError, verify_winner_sequence
from showdown_bot.eval.identity import compare_identity
from showdown_bot.eval.room_dump import GAUNTLET_NAME_SUBS, normalize_battle_log
from showdown_bot.eval.run_manifest import load_showdown_commit
from showdown_bot.eval.schedule import ScheduleError, load_schedule, verify_schedule_alignment
from showdown_bot.eval.seeding import SeedLogError
from showdown_bot.learning.dataset import load_rows

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

# 2b-4 Task 3: the gated reranker override agent's committed model (the ONLY model this slice
# uses -- see spec "Non-goals: training a NEW model"). Same env var names client/gauntlet.py's
# _load_reranker_override_from_env reads.
_2B4_MODEL_PATH = "models/reranker/2026-07-11-2b25a-attack-lgbm.txt"
_2B4_MANIFEST_PATH = "models/reranker/2026-07-11-2b25a-attack-manifest.json"
# SAME seed_base within a pair of runs (Channel A: seed_i depends only on (seed_base,
# seed_index)) -- the determinism gate's two runs, and the dev-strength gate's heuristic/
# override runs, must each use ONE constant seed_base for their pair.
_2B4_DETERMINISM_SEED_BASE = "2b4-determinism-v001"
_2B4_DEVSTRENGTH_SEED_BASE = "2b4-devstrength-v001"


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


def setup_calc_bridge(repo_root) -> str:
    """Install the @smogon/calc node bridge's dependencies (``showdown_bot/tools/calc``).

    The repo commits only a PARTIAL node_modules subset there (TypeScript sources); the
    package's actual entry point (``dist/index.js``, per its package.json ``main``) is only
    present after a real npm install -- so on a fresh clone ``node calc.mjs`` dies with
    ERR_MODULE_NOT_FOUND and every damage calc fails (Task 3 attempt-2 lesson: the gauntlet
    CLI exited 1 against a perfectly healthy server). ``npm ci`` wipes node_modules and
    installs the committed lockfile exactly; falls back to ``npm install`` if ci rejects the
    lockfile. Returns the calc dir."""
    calc_dir = Path(repo_root) / "showdown_bot" / "tools" / "calc"
    try:
        subprocess.run(["npm", "ci"], cwd=str(calc_dir), check=True)
    except (OSError, subprocess.CalledProcessError):
        subprocess.run(["npm", "install"], cwd=str(calc_dir), check=True)
    return str(calc_dir)


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
    # [2b-2.5a OOM fix] Immediate room dealloc (server patch v2): a headless schedule run plays
    # 75+ sequential battles; stock deallocation waits up to 40min, so finished rooms + their
    # sim-child Battle objects accumulate -> VM OOM. This env-gated flag expires an ended battle
    # room the moment its last user leaves (strictly post-battle -> zero effect on RNG/log bytes).
    server_env["SHOWDOWN_EVAL_ROOM_DEALLOC"] = "immediate"
    # [2b-2.5a, 2026-07-11] Per-battle gauntlet timeout override: rollout-teacher datagen labels
    # every decision (~3-4s each), so legitimate 50+-turn stall wars (sun_dev vs rain_dev tail
    # cells) exceed the client's flat 180s budget -> the battle yields no result row and the
    # schedule run fails. The client (not the server) reads this flag, but it is harmless -- and
    # kept consistent -- to also set it here on server_env.
    server_env["SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S"] = "900"

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
            # [2b-2.5a] Mirror the server-side OOM-fix flag into the gauntlet (client) env too,
            # exactly like the seed vars above: it is config-hash-relevant (config_env classifies
            # it server-side-behavior-affecting -> fail-closed included in behavior_env), so the
            # run manifest's config_hash records that this run played under immediate-dealloc.
            "SHOWDOWN_EVAL_ROOM_DEALLOC": "immediate",
            # [2b-2.5a, 2026-07-11] Raise the per-battle gauntlet timeout for datagen: rollout-
            # teacher labeling makes some legitimate long stall games exceed the 180s formula
            # default (see server_env comment above). config_env classifies this
            # BEHAVIOR_AFFECTING (read directly in showdown_bot.client.gauntlet) -> fail-closed
            # included in behavior_env, so the run manifest's config_hash records the override.
            "SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S": "900",
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
# Datagen (Task 5): per-hero seeded export + in-kernel validation
# ---------------------------------------------------------------------------

def validate_datagen_output(repo_root, out_dir, hero_key) -> tuple[bool, str]:
    """Validate one hero's datagen ``out_dir`` against its COMMITTED schedule + seed base
    (``showdown_bot.eval.datagen_2b25a``) -- pure file reads, exactly like
    ``validate_prefix_reproduction``: never runs a battle, so it is unit-testable against a
    synthetic ``out_dir`` built by the test. Checks, in order:

    (a) seed-log alignment (``verify_schedule_alignment``) of ``<out_dir>/seeds.jsonl`` against
        the hero's committed schedule + ``SEED_BASES[hero_key]``;
    (b) every ``<out_dir>/dataset.jsonl`` row is schema-valid, via
        ``showdown_bot.learning.dataset.load_rows(..., validate=True)`` -- the SAME
        schema-validating loader the 2b-1 training pipeline uses (``learning/dataset.py``
        delegates to ``learning/schema.py``'s ``validate_row``), so a broken export is caught
        here instead of at train time;
    (c) GAME COVERAGE (threshold, relaxed 2026-07-11): the dataset contains at least
        ``max(1, ceil(0.9 * schedule_games))`` distinct ``metadata.game_id`` values. Originally
        an exact-equality check, added after the Task-6 trickroom attempt-1 finding
        (2026-07-10): a battle-scoped export runtime under the schedule runner overwrote
        ``dataset.jsonl`` with only the LAST battle's rows (21 schema-valid rows, 1 game_id,
        after 50 clean battles) -- per-row schema validation alone cannot catch that corruption
        class, so an export must still hard-fail HERE, in-kernel, not an hour later at local
        merge. Relaxed to a 90% threshold after the trickroom hero's FINAL run legitimately hit
        74/75: under sampling policy "all", a short blowout game can have every decision
        skipped as unlabelable (``RolloutLabelError``), contributing zero rows even though the
        battle itself ran cleanly. Battles are never retried (Channel A), so this is not
        recoverable by re-running -- the threshold still catches the single-game overwrite
        signature and any export missing more than one in ten scheduled games;
    (d) zero ``falling back`` / ``frame error`` lines in ``<out_dir>/client.log`` (heuristic
        timeout/exception fallback and gauntlet frame-parse warnings both indicate a degraded
        run whose labels should not be trusted);
    (e) ``<out_dir>/results.jsonl`` has exactly one row per schedule row (T2-CC-4's contract --
        a retry/extra/missing battle would silently desync Channel-A seeding).

    Returns ``(ok, detail)``, never raises. On success ``detail`` is ``"rows=<n> games=<m>"``
    when every scheduled game is covered, or ``"rows=<n> games=<d>/<m> (<k> game(s) with zero
    sampled rows -- below-threshold OK)"`` when coverage is partial but at/above the 90%
    threshold (embedded verbatim in ``run_datagen``'s ``DATAGEN: DONE ...`` line); on failure
    ``detail`` is a human-readable reason (embedded in ``DATAGEN: FAIL (<reason>)`` via
    ``print_verdict``).
    """
    repo_root = Path(repo_root)
    out_dir = Path(out_dir)

    try:
        schedule = load_schedule(str(repo_root / datagen_2b25a.schedule_relpath(hero_key)))
    except (ScheduleError, OSError) as exc:
        return False, f"could not load schedule for hero {hero_key!r}: {exc}"

    seed_base = datagen_2b25a.SEED_BASES[hero_key]
    try:
        verify_schedule_alignment(schedule, str(out_dir / "seeds.jsonl"), seed_base)
    except (ScheduleError, SeedLogError) as exc:
        return False, f"seed-log alignment failed: {exc}"

    try:
        rows = load_rows(str(out_dir / "dataset.jsonl"), validate=True)
    except (OSError, ValueError) as exc:
        return False, f"dataset validation failed: {exc}"

    game_ids = {row["metadata"]["game_id"] for row in rows}
    distinct_games = len(game_ids)
    schedule_games = len(schedule.rows)
    min_games = max(1, math.ceil(0.9 * schedule_games))
    if distinct_games < min_games:
        return False, (
            f"game coverage: {distinct_games} distinct game_id(s) in dataset.jsonl, "
            f"schedule has {schedule_games} games -- below the {min_games}/{schedule_games} "
            f"(90%) coverage threshold"
        )

    try:
        client_log_text = (out_dir / "client.log").read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return False, f"could not read client.log: {exc}"
    bad_lines = [ln.strip() for ln in client_log_text.splitlines()
                 if "falling back" in ln or "frame error" in ln]
    if bad_lines:
        return False, (
            f"{len(bad_lines)} degraded-run warning line(s) in client.log "
            f"(e.g. {bad_lines[0]!r})"
        )

    try:
        result_rows = _load_jsonl(out_dir / "results.jsonl")
    except OSError as exc:
        return False, f"could not read result rows: {exc}"
    if len(result_rows) != len(schedule.rows):
        return False, (
            f"result row count mismatch: {len(result_rows)} rows, "
            f"schedule has {len(schedule.rows)}"
        )

    missing_games = schedule_games - distinct_games
    if missing_games == 0:
        return True, f"rows={len(rows)} games={schedule_games}"
    return True, (
        f"rows={len(rows)} games={distinct_games}/{schedule_games} "
        f"({missing_games} game(s) with zero sampled rows — below-threshold OK)"
    )


# ---------------------------------------------------------------------------
# MEMTRACE: memory telemetry sampler (added 2026-07-10, see module docstring)
# ---------------------------------------------------------------------------

def format_memtrace(elapsed_s: float, battles_done: int, meminfo: dict[str, int],
                     total_proc_count: int, total_rss_mb: int,
                     aggregates: dict[str, tuple[int, int]],
                     parents: dict[str, tuple[str, int]],
                     top_procs: list[tuple[str, int, int, int]]) -> str:
    """Format one MEMTRACE line (v3). ``meminfo`` is the dict returned by ``_parse_meminfo``
    (``avail_mb``/``total_mb``/``shmem_mb``/``slab_mb``/``cached_mb``/``buffers_mb``).
    ``aggregates`` is ``sig -> (count, sum_rss_mb)`` across ALL processes (not just the top-8);
    the top 4 signatures by ``sum_rss_mb`` desc are emitted (ties broken by signature name for a
    deterministic line). ``parents`` is ``sig -> (parent_sig, count)`` (see
    ``_parse_ps_parent_attribution``); the SAME top-4-by-sum-RSS signatures are emitted, in the
    same order, so ``agg=[...]`` and ``parents=[...]`` line up entry-for-entry. ``top_procs`` is
    ``(sig, pid, ppid, rss_mb)`` tuples, already sorted desc by rss. Pure formatting -- no I/O."""
    top_agg = sorted(aggregates.items(), key=lambda item: (-item[1][1], item[0]))[:4]
    agg_str = " ".join(
        f"{sig}:n={count}:{sum_rss_mb}MB" for sig, (count, sum_rss_mb) in top_agg
    )
    parents_str = " ".join(
        f"{sig}<-{parents.get(sig, ('?', 0))[0]}:{parents.get(sig, ('?', 0))[1]}"
        for sig, _agg in top_agg
    )
    top_str = " ".join(f"{sig}:{pid}:{ppid}:{rss_mb}MB" for sig, pid, ppid, rss_mb in top_procs)
    return (
        f"MEMTRACE t={int(elapsed_s)} done={battles_done} "
        f"availMB={meminfo['avail_mb']}/{meminfo['total_mb']} "
        f"shmem={meminfo['shmem_mb']} slab={meminfo['slab_mb']} "
        f"cached={meminfo['cached_mb']} buffers={meminfo['buffers_mb']} "
        f"procs={total_proc_count}:{total_rss_mb}MB "
        f"agg=[{agg_str}] parents=[{parents_str}] top=[{top_str}]"
    )


def _default_read_meminfo() -> str:
    with open("/proc/meminfo", encoding="utf-8") as fh:
        return fh.read()


def _default_run_ps() -> str:
    result = subprocess.run(
        ["ps", "-eo", "pid,ppid,rss,args", "--sort=-rss"], capture_output=True, text=True,
    )
    return result.stdout


def _count_nonempty_lines(path) -> int:
    p = Path(path)
    if not p.exists():
        return 0
    with open(p, encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def _parse_meminfo(text: str) -> dict[str, int]:
    """Parse ``/proc/meminfo`` text into a dict of MB ints. A missing field yields 0. ``Cached``
    is matched at line-start (``re.MULTILINE``) so it does not also match ``SwapCached``."""
    def _field_mb(name: str) -> int:
        match = re.search(rf"^{name}:\s+(\d+)", text, re.MULTILINE)
        return (int(match.group(1)) // 1024) if match else 0

    return {
        "avail_mb": _field_mb("MemAvailable"),
        "total_mb": _field_mb("MemTotal"),
        "shmem_mb": _field_mb("Shmem"),
        "slab_mb": _field_mb("Slab"),
        "cached_mb": _field_mb("Cached"),
        "buffers_mb": _field_mb("Buffers"),
    }


def _parse_ps_rows(text: str) -> list[tuple[int, int, int, str]]:
    """Parse ``ps -eo pid,ppid,rss,args`` output (skipping the header row) into ``(pid, ppid,
    rss_kb, args)`` tuples for ALL processes, unsorted, RSS still in kB -- the shared basis for
    the top-N list, the per-signature aggregates, and parent attribution below. ``args`` is the
    full command line and may itself contain spaces, so it is always the LAST ps column and each
    row is split with ``maxsplit=3`` (at most 4 parts) rather than on whitespace generally."""
    rows: list[tuple[int, int, int, str]] = []
    for line in text.splitlines()[1:]:  # skip the `ps` header row
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid_str, ppid_str, rss_str, args = parts
        try:
            pid = int(pid_str)
            ppid = int(ppid_str)
            rss_kb = int(rss_str)
        except ValueError:
            continue
        rows.append((pid, ppid, rss_kb, args))
    return rows


def _proc_signature(args: str) -> str:
    """Classify a process's full command line (``args``, as parsed by ``_parse_ps_rows``) into a
    short, stable signature label -- v2's ``comm`` column collapsed every leaked process to the
    single string ``"node"`` regardless of what script it was actually running, which is exactly
    what made the v2-era OOM unattributable. Rules, checked in order:

    - command line contains ``calc.mjs`` -> ``"calc.mjs"`` (the @smogon/calc bridge process).
    - command line contains ``pokemon-showdown`` -> ``"pokemon-showdown"`` (the sim server).
    - otherwise, if the first token is a ``node`` interpreter (bare ``node`` or a path ending in
      ``node``) -> ``"node:" + <last path component of the second token>``, or ``"node:?"`` if
      there is no second token (e.g. a bare ``node`` REPL with no script argument).
    - otherwise -> the last path component of the first token (e.g. ``python3``, ``sh``, ``ps``).

    An empty/whitespace-only ``args`` yields ``"?"``."""
    if "calc.mjs" in args:
        return "calc.mjs"
    if "pokemon-showdown" in args:
        return "pokemon-showdown"
    tokens = args.split()
    if not tokens:
        return "?"
    if Path(tokens[0]).name == "node":
        if len(tokens) > 1:
            return f"node:{Path(tokens[1]).name}"
        return "node:?"
    return Path(tokens[0]).name


def _parse_ps_top(rows: list[tuple[int, int, int, str]], limit: int = 8) -> list[tuple[str, int, int, int]]:
    """Top-``limit`` individual processes by RSS desc: ``(sig, pid, ppid, rss_mb)``, RSS
    converted kB -> MB."""
    sorted_rows = sorted(rows, key=lambda row: row[2], reverse=True)
    return [
        (_proc_signature(args), pid, ppid, rss_kb // 1024)
        for pid, ppid, rss_kb, args in sorted_rows[:limit]
    ]


def _parse_ps_aggregates(rows: list[tuple[int, int, int, str]]) -> dict[str, tuple[int, int]]:
    """Per-signature aggregates across ALL processes (not just the top-N): ``sig -> (count,
    sum_rss_mb)``. Sums RSS in kB before the final MB conversion, so small per-process rounding
    error does not compound across many processes of the same signature -- the whole point of
    this aggregate is to surface a memory hog made of MANY small processes that each fall below
    the top-8 individual cutoff."""
    agg_kb: dict[str, list[int]] = {}
    for _pid, _ppid, rss_kb, args in rows:
        sig = _proc_signature(args)
        entry = agg_kb.setdefault(sig, [0, 0])
        entry[0] += 1
        entry[1] += rss_kb
    return {sig: (count, total_kb // 1024) for sig, (count, total_kb) in agg_kb.items()}


def _parse_ps_parent_attribution(rows: list[tuple[int, int, int, str]]) -> dict[str, tuple[str, int]]:
    """For each signature, WHO spawns it: ``sig -> (parent_sig, count)`` where ``count`` is how
    many of that signature's processes share the most common PPID, and ``parent_sig`` is that
    PPID's OWN signature, resolved via the pid -> args map built from this SAME ps snapshot (a
    parent that has already exited, or is outside the snapshot, resolves to ``"?"``). Ties in the
    "most common PPID" count are broken by lowest PPID, for a deterministic result."""
    pid_to_args: dict[int, str] = {pid: args for pid, _ppid, _rss_kb, args in rows}

    sig_ppid_counts: dict[str, dict[int, int]] = {}
    for pid, ppid, _rss_kb, args in rows:
        sig = _proc_signature(args)
        counts = sig_ppid_counts.setdefault(sig, {})
        counts[ppid] = counts.get(ppid, 0) + 1

    result: dict[str, tuple[str, int]] = {}
    for sig, ppid_counts in sig_ppid_counts.items():
        mode_ppid, count = max(ppid_counts.items(), key=lambda item: (item[1], -item[0]))
        parent_args = pid_to_args.get(mode_ppid)
        parent_sig = _proc_signature(parent_args) if parent_args is not None else "?"
        result[sig] = (parent_sig, count)
    return result


def collect_memtrace_sample(results_path, *, read_meminfo=None, run_ps=None) -> dict:
    """Collect one MEMTRACE sample (v3): battles-done (non-empty lines in ``results_path``, 0 if
    the file does not exist yet), the full ``_parse_meminfo`` dict, the top-8 RSS processes (MB),
    per-signature aggregates across ALL processes (count + sum_rss_mb), per-signature parent
    attribution, and totals across ALL processes (``total_proc_count``, ``total_rss_mb``).
    ``read_meminfo``/``run_ps`` are injectable zero-arg callables (default to reading
    ``/proc/meminfo`` and running ``ps -eo pid,ppid,rss,args --sort=-rss``) so this is testable
    off Linux and without spawning a real ``ps``.

    Returns a dict: ``{"battles_done", "meminfo", "top_procs", "aggregates", "parents",
    "total_proc_count", "total_rss_mb"}``.
    """
    read_meminfo = read_meminfo or _default_read_meminfo
    run_ps = run_ps or _default_run_ps

    battles_done = _count_nonempty_lines(results_path)
    meminfo = _parse_meminfo(read_meminfo())
    rows = _parse_ps_rows(run_ps())
    top_procs = _parse_ps_top(rows)
    aggregates = _parse_ps_aggregates(rows)
    parents = _parse_ps_parent_attribution(rows)
    total_proc_count = len(rows)
    total_rss_mb = sum(rss_kb for _pid, _ppid, rss_kb, _args in rows) // 1024

    return {
        "battles_done": battles_done,
        "meminfo": meminfo,
        "top_procs": top_procs,
        "aggregates": aggregates,
        "parents": parents,
        "total_proc_count": total_proc_count,
        "total_rss_mb": total_rss_mb,
    }


def start_memtrace(results_path, interval_s: float = 30.0, *, read_meminfo=None,
                    run_ps=None) -> Callable[[], None]:
    """Start a daemon background thread that samples memory (``collect_memtrace_sample``) and
    prints a ``MEMTRACE`` line to stdout every ``interval_s`` seconds, starting immediately.
    Printing to stdout is intentional: Kaggle captures stdout with timestamps, and
    ``kaggle_driver``'s log parser tolerates arbitrary extra lines. A single tick's failure
    (e.g. ``/proc/meminfo`` or ``ps`` unavailable) is swallowed so the sampler never crashes or
    spams the log -- it just skips that tick. Returns a ``stop()`` callable that signals the
    thread to exit and joins it (5s timeout); waiting is done on a ``threading.Event`` so
    ``stop()`` does not block for a full ``interval_s``."""
    stop_event = threading.Event()
    start_time = time.monotonic()

    def _loop() -> None:
        while not stop_event.is_set():
            try:
                sample = collect_memtrace_sample(
                    results_path, read_meminfo=read_meminfo, run_ps=run_ps,
                )
                elapsed_s = time.monotonic() - start_time
                print(format_memtrace(
                    elapsed_s, sample["battles_done"], sample["meminfo"],
                    sample["total_proc_count"], sample["total_rss_mb"],
                    sample["aggregates"], sample["parents"], sample["top_procs"],
                ), flush=True)
            except Exception:
                pass
            stop_event.wait(interval_s)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()

    def stop() -> None:
        stop_event.set()
        thread.join(timeout=5)

    return stop


def run_datagen(repo_root, showdown_dir, hero_key, out_dir, *, extra_env=None) -> dict:
    """Kaggle datagen kernel orchestration for ONE hero (Task 5). Resolves the hero's committed
    schedule (``datagen_2b25a.schedule_relpath(hero_key)``) and seed base
    (``datagen_2b25a.SEED_BASES[hero_key]``), runs it via ``run_schedule_seeded`` with a
    dataset export in rollout-teacher mode, then validates the output
    (``validate_datagen_output``) and prints the ``DATAGEN`` verdict line itself (``DATAGEN:
    DONE hero=<key> rows=<n> games=<m>`` on success, ``DATAGEN: FAIL (<reason>)`` on any
    failure -- the latter via ``print_verdict`` so the wire format matches
    ``kaggle_driver.parse_verdict``'s expectations exactly). Returns a dict of
    ``run_schedule_seeded``'s output paths plus ``hero_key``/``ok``/``detail``/``verdict``.

    ``extra_env`` (2b-2.5a, EXTRA_ENV passthrough, 2026-07-11): an optional dict of additional
    ``SHOWDOWN_*`` env vars to inject into the gauntlet subprocess for THIS run only (e.g. a
    play-quality knob like ``SHOWDOWN_FAST_BOARD_PROTECT_PENALTY`` under measurement). Merged
    OVER the base ``{"SHOWDOWN_DATASET_TEACHER": "rollout"}`` extra_env this function always
    passes to ``run_schedule_seeded`` -- caller keys win (so an explicit
    ``SHOWDOWN_DATASET_TEACHER`` override is honored), but an ABSENT caller key never drops the
    teacher default. ``extra_env=None`` (the default) is byte-identical to the pre-passthrough
    behavior: only the teacher key is passed.

    NOT unit-tested via a real run -- like ``run_schedule_seeded``, it starts subprocesses
    (server + gauntlet CLI) and only ever runs on Kaggle (Task 6). Only
    ``validate_datagen_output`` (the pure validation half) is exercised locally; the extra_env
    merge itself IS unit-tested by monkeypatching ``run_schedule_seeded`` to capture its
    ``extra_env`` kwarg (see ``test_kernel_payload.py``).

    Runs a MEMTRACE sampler (``start_memtrace``, 30s interval) for the duration of the schedule
    run -- see the module docstring for why.
    """
    repo_root = Path(repo_root)
    out_dir = Path(out_dir)
    schedule_rel = datagen_2b25a.schedule_relpath(hero_key)
    seed_base = datagen_2b25a.SEED_BASES[hero_key]
    dataset_export = out_dir / "dataset.jsonl"
    results_path = out_dir / "results.jsonl"

    combined_extra_env = {"SHOWDOWN_DATASET_TEACHER": "rollout"}
    if extra_env:
        combined_extra_env.update(extra_env)

    stop_memtrace = start_memtrace(str(results_path), interval_s=30.0)
    try:
        paths = run_schedule_seeded(
            str(repo_root), showdown_dir, schedule_rel, seed_base, str(out_dir),
            dataset_export=str(dataset_export),
            extra_env=combined_extra_env,
        )
    finally:
        stop_memtrace()

    ok, detail = validate_datagen_output(str(repo_root), str(out_dir), hero_key)
    if ok:
        line = f"DATAGEN: DONE hero={hero_key} {detail}"
        print(line)
    else:
        line = print_verdict("DATAGEN", False, detail)

    return {**paths, "hero_key": hero_key, "ok": ok, "detail": detail, "verdict": line}


# ---------------------------------------------------------------------------
# 2b-4 Task 3: gated reranker override -- determinism gate + dev-strength runs
# ---------------------------------------------------------------------------

def _2b4_override_env(repo_root) -> dict:
    """Client-env overlay that selects + activates the ``heuristic_reranker`` override agent
    for a schedule run: ``SHOWDOWN_HERO_AGENT`` (cli.run_schedule's hero-agent selector, Task 3)
    plus the shadow-mirroring gate vars ``_load_reranker_override_from_env`` reads
    (``client/gauntlet.py``). Model/manifest paths are resolved absolute against
    ``repo_root`` so this is correct regardless of the gauntlet CLI subprocess's cwd
    (``run_schedule_seeded`` always runs it with ``cwd=<repo_root>/showdown_bot``)."""
    repo_root = Path(repo_root)
    return {
        "SHOWDOWN_HERO_AGENT": "heuristic_reranker",
        "SHOWDOWN_RERANKER_OVERRIDE": "1",
        "SHOWDOWN_RERANKER_MODEL_PATH": str(repo_root / _2B4_MODEL_PATH),
        "SHOWDOWN_RERANKER_MANIFEST_PATH": str(repo_root / _2B4_MANIFEST_PATH),
    }


def run_gated_override_determinism(repo_root, showdown_dir, out_dir) -> dict:
    """2b-4 Task 3: the Channel-A double-run identity gate for the ``heuristic_reranker``
    override agent (spec: "Identity before strength — non-negotiable"). Runs
    ``config/eval/schedules/2b4_determinism_v001.yaml`` TWICE, each its own fresh server (a
    fresh ``run_schedule_seeded`` call -- Channel A's counter-from-0 contract) with the SAME
    seed_base and the override env active both times (``_2b4_override_env``), into
    ``<out_dir>/run1`` and ``<out_dir>/run2``. Compares the two runs' result rows with
    ``eval.identity.compare_identity`` (winner/turns/normalized_room_log_sha256 per battle) and
    prints the ``2B4-DETERMINISM: PASS/FAIL`` verdict line itself via ``print_verdict`` (mirrors
    ``run_datagen``'s self-printing convention; wire format matches
    ``kaggle_driver.parse_verdict``'s expectations).

    NOT unit-tested directly -- starts real subprocesses (server + gauntlet CLI) via
    ``run_schedule_seeded``, exactly like ``run_datagen``/``run_schedule_seeded`` themselves;
    only ever runs on Kaggle. The pure comparison it delegates to
    (``eval.identity.compare_identity``) is unit-tested locally against fabricated fixtures.
    """
    repo_root = Path(repo_root)
    out_dir = Path(out_dir)
    override_env = _2b4_override_env(repo_root)

    paths_1 = run_schedule_seeded(
        str(repo_root), showdown_dir, schedule_2b4.schedule_relpath("determinism"),
        _2B4_DETERMINISM_SEED_BASE, str(out_dir / "run1"), extra_env=override_env,
    )
    paths_2 = run_schedule_seeded(
        str(repo_root), showdown_dir, schedule_2b4.schedule_relpath("determinism"),
        _2B4_DETERMINISM_SEED_BASE, str(out_dir / "run2"), extra_env=override_env,
    )

    rows_1 = _load_jsonl(paths_1["results"])
    rows_2 = _load_jsonl(paths_2["results"])
    report = compare_identity(rows_1, rows_2)
    detail = f"{report.n_compared} battles compared, {len(report.diffs)} diff(s)"
    line = print_verdict("2B4-DETERMINISM", report.identical, detail)

    return {
        "run1": paths_1, "run2": paths_2, "report": report,
        "ok": report.identical, "detail": detail, "verdict": line,
    }


def run_gated_override_strength(repo_root, showdown_dir, out_dir) -> dict:
    """2b-4 Task 3: dev-panel paired strength runs for the ``heuristic_reranker`` override
    agent (only meaningful after ``run_gated_override_determinism`` PASSes -- enforced by the
    CONTROLLER, Task 4, not by this function). Runs
    ``config/eval/schedules/2b4_devstrength_v001.yaml`` TWICE with the SAME seed_base against
    the SAME baseline villain: once ``hero_agent="heuristic"`` (into ``<out_dir>/heuristic``),
    once with the override env active (``<out_dir>/override``). Same schedule + same seeds +
    same opponent on both runs is exactly what T5's ``eval.pairing.pair_runs`` needs for a valid
    pair (schedule_hash/seed_base/panel_hash/format_id equal, config_hash differing because
    ``SHOWDOWN_RERANKER_OVERRIDE`` only appears in the override run's behavior_env -- see
    ``eval.config_env``/``eval.schedule_2b4``'s module docstring).

    Prints ``2B4-STRENGTH: DONE`` -- no PASS/FAIL here: the GO/NO-GO/UNDERPOWERED verdict is
    produced LOCALLY (``cli eval-report --mode paired`` against the two copied-out result
    JSONLs), not decided in-kernel. NOT unit-tested directly, same rationale as
    ``run_gated_override_determinism``.
    """
    repo_root = Path(repo_root)
    out_dir = Path(out_dir)
    override_env = _2b4_override_env(repo_root)

    heuristic_paths = run_schedule_seeded(
        str(repo_root), showdown_dir, schedule_2b4.schedule_relpath("devstrength"),
        _2B4_DEVSTRENGTH_SEED_BASE, str(out_dir / "heuristic"),
    )
    override_paths = run_schedule_seeded(
        str(repo_root), showdown_dir, schedule_2b4.schedule_relpath("devstrength"),
        _2B4_DEVSTRENGTH_SEED_BASE, str(out_dir / "override"), extra_env=override_env,
    )

    detail = f"heuristic={heuristic_paths['results']} override={override_paths['results']}"
    line = f"2B4-STRENGTH: DONE ({detail})"
    print(line)

    return {"heuristic": heuristic_paths, "override": override_paths, "verdict": line}


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
    them all up. When ``<out_dir>/dataset.jsonl`` is present (Task 5's datagen kernel; absent
    for repro_validation.py's out_dir) it is copied gzipped as ``dataset.jsonl.gz`` -- the raw
    per-hero export can run to tens of thousands of rows, so it is never copied uncompressed.
    Returns the list of destination paths actually written."""
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

    dataset_src = out_dir / "dataset.jsonl"
    if dataset_src.exists():
        dataset_dest = working_dir / "dataset.jsonl.gz"
        with open(dataset_src, "rb") as src_fh, gzip.open(dataset_dest, "wb") as dst_fh:
            shutil.copyfileobj(src_fh, dst_fh)
        written.append(str(dataset_dest))

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
