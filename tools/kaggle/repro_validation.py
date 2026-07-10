# KAGGLE_ENV: {}
"""tools/kaggle/repro_validation.py -- Kaggle SCRIPT kernel: Phase-1 validation gate (2b-2.5a).

Single-file kernel: this is the ONLY file present on the Kaggle instance before it clones the
repo, so it stays self-contained (no imports from this repo at module scope). The first line
is a machine-parseable ``# KAGGLE_ENV: {...}`` header that ``kaggle_driver.push`` overwrites
with ``{"REPO_URL": ..., "REPO_SHA": ...}`` before pushing (see kaggle_driver.py's docstring
for the convention). After the clone, everything delegates to ``kernel_payload`` (testable
locally) -- this script is just bootstrap + wiring.

Flow: parse own env header -> git clone + checkout REPO_SHA -> put the cloned package on
sys.path/PYTHONPATH -> import kernel_payload from the clone -> bootstrap_node ->
setup_showdown -> run_schedule_seeded(prefix schedule, seed base t4rerun2026) ->
validate_prefix_reproduction -> print_verdict("KAGGLE-REPRO", ...) -> copy_outputs. Wrapped
so a verdict line is ALWAYS printed, even on a bootstrap-stage exception (the driver's
``parse_verdict`` must always find one): ``KAGGLE-REPRO: FAIL (exception: ...)`` + traceback.

Attempt-1 operational lessons (2026-07-10) baked in:
- ``pip install -e`` does NOT make the package importable in the SAME process: Kaggle runs
  script kernels through a notebook conversion, and the editable install's .pth finder only
  takes effect at interpreter startup. Fix: ``sys.path`` insert for this process +
  ``PYTHONPATH`` for the gauntlet CLI subprocess that kernel_payload starts.
- Scratch trees (repo clone, showdown checkout, raw out dir) must live under ``/tmp``, NOT
  ``/kaggle/working``: /kaggle/working IS the kernel-output directory, and attempt 1
  uploaded the entire repo clone as kernel output. /kaggle/working stays reserved for
  ``kernel_payload.copy_outputs`` results.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

_ENV_HEADER_PREFIX = "# KAGGLE_ENV: "
_SCHEDULE_RELPATH = "config/eval/schedules/t4_smoke_v001_prefix.yaml"
_SEED_BASE = "t4rerun2026"
_DEFAULT_REPO_URL = "https://github.com/chrismaghuhn/ShowdownBot"

_REPO_DIR = Path("/tmp/sb_repo")
_OUT_DIR = Path("/tmp/sb_out")
_SHOWDOWN_CACHE_DIR = Path("/tmp/sb_showdown_cache")

# showdown_bot runtime deps (import name -> pip name). The 2026-07 Kaggle image ships all
# four ("Requirement already satisfied" in the attempt-1 log) -- the install branch is a
# guard against future image changes only.
_RUNTIME_DEPS = (
    ("pydantic", "pydantic"),
    ("yaml", "pyyaml"),
    ("websockets", "websockets"),
    ("dotenv", "python-dotenv"),
)


def _own_env() -> dict:
    first_line = Path(__file__).read_text(encoding="utf-8").splitlines()[0]
    if not first_line.startswith(_ENV_HEADER_PREFIX):
        return {}
    return json.loads(first_line[len(_ENV_HEADER_PREFIX):])


def _ensure_runtime_deps() -> None:
    missing = [pip_name for module_name, pip_name in _RUNTIME_DEPS
               if importlib.util.find_spec(module_name) is None]
    if missing:
        subprocess.run([sys.executable, "-m", "pip", "install", *missing], check=True)


def main() -> None:
    env = _own_env()
    repo_url = env.get("REPO_URL", _DEFAULT_REPO_URL)
    repo_sha = env["REPO_SHA"]  # required -- no floating main

    subprocess.run(["git", "clone", repo_url, str(_REPO_DIR)], check=True)
    subprocess.run(["git", "checkout", repo_sha], cwd=str(_REPO_DIR), check=True)

    _ensure_runtime_deps()
    src_dir = _REPO_DIR / "showdown_bot" / "src"
    sys.path.insert(0, str(src_dir))          # this process (kernel_payload's imports)
    sys.path.insert(0, str(_REPO_DIR / "tools" / "kaggle"))
    prior = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = str(src_dir) + (os.pathsep + prior if prior else "")  # subprocesses (gauntlet CLI)

    import kernel_payload  # from the clone above -- not importable before this point

    kernel_payload.bootstrap_node()
    showdown_dir = kernel_payload.setup_showdown(str(_REPO_DIR), str(_SHOWDOWN_CACHE_DIR))
    kernel_payload.run_schedule_seeded(
        str(_REPO_DIR), showdown_dir, _SCHEDULE_RELPATH, _SEED_BASE, str(_OUT_DIR),
    )
    ok, detail = kernel_payload.validate_prefix_reproduction(str(_REPO_DIR), str(_OUT_DIR))
    line = kernel_payload.print_verdict("KAGGLE-REPRO", ok, detail)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    (_OUT_DIR / "verdict.txt").write_text(line + "\n", encoding="utf-8")
    kernel_payload.copy_outputs(str(_OUT_DIR))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 -- the driver must ALWAYS find a verdict line
        print(f"KAGGLE-REPRO: FAIL (exception: {exc})")
        traceback.print_exc()
