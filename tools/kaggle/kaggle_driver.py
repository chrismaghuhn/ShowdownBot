"""tools/kaggle/kaggle_driver.py -- local driver for slice 2b-2.5a Kaggle kernels.

Runs on the developer's machine (never imported by the live bot or by
kernel-side payload code). Two families of functions live here:

1. PURE parts (unit-tested in showdown_bot/tests/test_kaggle_driver.py, no
   network): `build_kernel_metadata`, `inject_env_header`/`parse_env_header`,
   `parse_verdict`.
2. Thin NETWORK functions (`push`, `status`, `wait`, `download_output`) --
   NOT unit-tested here (no real Kaggle API calls in tests); exercised
   operationally in Task 3/6. Each imports the `kaggle` package lazily
   inside the function body so importing this module never requires Kaggle
   credentials to be configured.

Env-header convention
----------------------
Kaggle SCRIPT kernels have no native mechanism for passing environment
variables into the running script. This driver's convention: the pushed
script's FIRST LINE is a machine-parseable header

    # KAGGLE_ENV: {"REPO_SHA": "...", "HERO_KEY": "fixed", ...}

`inject_env_header` writes/replaces this line before a script is staged for
push; `parse_env_header` reads it back. Kernel-side payload code
(tools/kaggle/kernel_payload.py, added in Task 2) parses this header at
startup to recover REPO_SHA, REPO_URL, and other per-run parameters.

Verdict convention
-------------------
Kernels print a single machine-greppable line near the end of their run,
e.g.:

    KAGGLE-REPRO: PASS (10/10 winner+seed match)
    DATAGEN: DONE hero=fixed rows=1234 games=75
    DATAGEN: FAIL (skip_rate=0.12 > 0.05)

`parse_verdict` scans a downloaded log and returns the LAST such line found
(later lines win, e.g. after a retry), split into a (status, full_line) pair.
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
import time
from pathlib import Path

KAGGLE_USERNAME = "chrismaghuhn"

_ENV_HEADER_PREFIX = "# KAGGLE_ENV: "
_VERDICT_PREFIXES = ("KAGGLE-REPRO:", "DATAGEN:")
_VERDICT_TOKENS = ("PASS", "FAIL", "DONE")

# Kernel statuses that mean "the run is finished, stop polling" (kagglesdk
# KernelWorkerStatus enum: NEW_SCRIPT, QUEUED, RUNNING, COMPLETE, ERROR,
# CANCEL_REQUESTED, CANCEL_ACKNOWLEDGED).
_TERMINAL_STATUSES = {"COMPLETE", "ERROR", "CANCEL_ACKNOWLEDGED"}


# ---------------------------------------------------------------------------
# Pure parts
# ---------------------------------------------------------------------------

def build_kernel_metadata(slug: str, code_file: str, *, enable_internet: bool = True,
                           enable_gpu: bool = False) -> dict:
    """Kaggle kernel-metadata.json shape for a private script kernel owned by
    KAGGLE_USERNAME. `code_file` may be an absolute/relative path -- only its
    basename is written (the metadata file and the script sit side by side in
    the staged kernel folder)."""
    return {
        "id": f"{KAGGLE_USERNAME}/{slug}",
        "title": slug,
        "code_file": Path(code_file).name,
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": enable_gpu,
        "enable_internet": enable_internet,
    }


def inject_env_header(script_text: str, env: dict) -> str:
    """Prepend a `# KAGGLE_ENV: {json}` header line to `script_text`,
    replacing an existing header line if the script already has one."""
    lines = script_text.splitlines()
    header = _ENV_HEADER_PREFIX + json.dumps(env, sort_keys=True)
    if lines and lines[0].startswith(_ENV_HEADER_PREFIX):
        lines[0] = header
    else:
        lines.insert(0, header)
    text = "\n".join(lines)
    if script_text.endswith("\n"):
        text += "\n"
    return text


def parse_env_header(script_text: str) -> dict:
    """Recover the env dict written by inject_env_header. Returns {} if the
    script has no KAGGLE_ENV header."""
    if not script_text:
        return {}
    first_line = script_text.splitlines()[0]
    if not first_line.startswith(_ENV_HEADER_PREFIX):
        return {}
    return json.loads(first_line[len(_ENV_HEADER_PREFIX):])


def parse_verdict(log_text: str) -> tuple[str | None, str]:
    """Find the LAST line starting with `KAGGLE-REPRO:` or `DATAGEN:` in a
    kernel log. Returns (verdict, full_line) where verdict is one of
    "PASS"/"FAIL"/"DONE" (the first token after the prefix) or None if no
    such line is present (or its token isn't recognized). full_line is ""
    when no matching line was found."""
    last_line = ""
    for raw in log_text.splitlines():
        stripped = raw.strip()
        if stripped.startswith(_VERDICT_PREFIXES):
            last_line = stripped
    if not last_line:
        return None, ""
    rest = last_line.split(":", 1)[1].strip()
    token = rest.split(maxsplit=1)[0] if rest else ""
    verdict = token if token in _VERDICT_TOKENS else None
    return verdict, last_line


# ---------------------------------------------------------------------------
# Thin network functions -- NOT unit-tested; exercised operationally in
# Task 3/6. `kaggle` is imported lazily so this module loads without it.
# ---------------------------------------------------------------------------

def _kaggle_api():
    from kaggle.api.kaggle_api_extended import KaggleApi  # lazy: avoid hard dep at import time

    api = KaggleApi()
    api.authenticate()
    return api


def _full_slug(slug: str) -> str:
    return slug if "/" in slug else f"{KAGGLE_USERNAME}/{slug}"


def push(slug: str, script_path: str, env: dict, staging_dir: str | None = None):
    """Stage a temp kernel folder (kernel-metadata.json + an env-injected copy
    of the script) and push it via KaggleApi.kernels_push. Returns the
    ApiSaveKernelResponse. `staging_dir` overrides the auto-created tempdir
    (mainly for operational debugging -- inspecting what got pushed)."""
    script_path = Path(script_path)
    injected = inject_env_header(script_path.read_text(encoding="utf-8"), env)

    stage_root = Path(staging_dir) if staging_dir else Path(tempfile.mkdtemp(prefix="kaggle_push_"))
    stage_root.mkdir(parents=True, exist_ok=True)
    (stage_root / script_path.name).write_text(injected, encoding="utf-8")
    metadata = build_kernel_metadata(slug, script_path.name)
    (stage_root / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    api = _kaggle_api()
    return api.kernels_push(str(stage_root))


def status(slug: str) -> str:
    """Current Kaggle kernel worker status (e.g. QUEUED/RUNNING/COMPLETE/ERROR)."""
    api = _kaggle_api()
    response = api.kernels_status(_full_slug(slug))
    raw_status = response.status
    return getattr(raw_status, "name", str(raw_status))


def wait(slug: str, timeout_s: int = 3600, poll_s: int = 60) -> str:
    """Poll `status(slug)` until it reaches a terminal state (COMPLETE/ERROR/
    CANCEL_ACKNOWLEDGED) or timeout_s elapses. Sleeps poll_s between polls --
    deliberately no tight loops. Returns the last observed status (which may
    be non-terminal if timeout_s was hit)."""
    deadline = time.monotonic() + timeout_s
    last = status(slug)
    while last not in _TERMINAL_STATUSES:
        if time.monotonic() >= deadline:
            break
        time.sleep(poll_s)
        last = status(slug)
    return last


def download_output(slug: str, dest_dir: str) -> list[str]:
    """Download a kernel's output files to dest_dir via KaggleApi.kernels_output.
    Returns the list of downloaded file paths."""
    api = _kaggle_api()
    Path(dest_dir).mkdir(parents=True, exist_ok=True)
    files, _status = api.kernels_output(_full_slug(slug), str(dest_dir))
    return files


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_env_args(pairs: list[str]) -> dict:
    env: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"--env expects key=value, got {pair!r}")
        key, value = pair.split("=", 1)
        env[key] = value
    return env


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kaggle kernel push/poll/pull driver (slice 2b-2.5a).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_push = sub.add_parser("push", help="Stage + push a script kernel with an env header.")
    p_push.add_argument("slug")
    p_push.add_argument("script")
    p_push.add_argument("--env", action="append", default=[], metavar="K=V",
                         help="repeatable; passed via the KAGGLE_ENV header")

    p_wait = sub.add_parser("wait", help="Poll a kernel until it reaches a terminal status.")
    p_wait.add_argument("slug")
    p_wait.add_argument("--timeout-s", type=int, default=3600)
    p_wait.add_argument("--poll-s", type=int, default=60)

    p_pull = sub.add_parser("pull", help="Download a kernel's output files.")
    p_pull.add_argument("slug")
    p_pull.add_argument("dest")

    args = parser.parse_args(argv)

    if args.command == "push":
        push(args.slug, args.script, _parse_env_args(args.env))
        print(f"pushed {args.slug}")
    elif args.command == "wait":
        final = wait(args.slug, timeout_s=args.timeout_s, poll_s=args.poll_s)
        print(f"{args.slug}: {final}")
    elif args.command == "pull":
        files = download_output(args.slug, args.dest)
        print(f"downloaded {len(files)} file(s) to {args.dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
