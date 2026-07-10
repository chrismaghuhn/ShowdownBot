# KAGGLE_ENV: {}
"""tools/kaggle/repro_validation.py -- Kaggle SCRIPT kernel: Phase-1 validation gate (2b-2.5a).

Single-file kernel: this is the ONLY file present on the Kaggle instance before it clones the
repo, so it stays self-contained (no imports from this repo at module scope). The first line
is a machine-parseable ``# KAGGLE_ENV: {...}`` header that ``kaggle_driver.push`` overwrites
with ``{"REPO_URL": ..., "REPO_SHA": ...}`` before pushing (see kaggle_driver.py's docstring
for the convention). After the clone, everything delegates to ``kernel_payload`` (testable
locally) -- this script is just bootstrap + wiring.

Flow: parse own env header -> git clone + checkout REPO_SHA -> pip install -e the cloned
package -> import kernel_payload from the clone -> bootstrap_node -> setup_showdown ->
run_schedule_seeded(prefix schedule, seed base t4rerun2026) -> validate_prefix_reproduction ->
print_verdict("KAGGLE-REPRO", ...) -> copy_outputs. Wrapped so a verdict line is ALWAYS
printed, even on a bootstrap-stage exception (the driver's ``parse_verdict`` must always find
one): ``KAGGLE-REPRO: FAIL (exception: ...)`` + traceback.
"""
from __future__ import annotations

import json
import subprocess
import sys
import traceback
from pathlib import Path

_ENV_HEADER_PREFIX = "# KAGGLE_ENV: "
_SCHEDULE_RELPATH = "config/eval/schedules/t4_smoke_v001_prefix.yaml"
_SEED_BASE = "t4rerun2026"
_DEFAULT_REPO_URL = "https://github.com/chrismaghuhn/ShowdownBot"

_REPO_DIR = Path("/kaggle/working/repo")
_OUT_DIR = Path("/kaggle/working/out")
_SHOWDOWN_CACHE_DIR = Path("/kaggle/working/showdown-cache")


def _own_env() -> dict:
    first_line = Path(__file__).read_text(encoding="utf-8").splitlines()[0]
    if not first_line.startswith(_ENV_HEADER_PREFIX):
        return {}
    return json.loads(first_line[len(_ENV_HEADER_PREFIX):])


def main() -> None:
    env = _own_env()
    repo_url = env.get("REPO_URL", _DEFAULT_REPO_URL)
    repo_sha = env["REPO_SHA"]  # required -- no floating main

    subprocess.run(["git", "clone", repo_url, str(_REPO_DIR)], check=True)
    subprocess.run(["git", "checkout", repo_sha], cwd=str(_REPO_DIR), check=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(_REPO_DIR / "showdown_bot")], check=True,
    )

    sys.path.insert(0, str(_REPO_DIR / "tools" / "kaggle"))
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
