# KAGGLE_ENV: {}
"""tools/kaggle/gated_override_kernel.py -- Kaggle SCRIPT kernel: 2b-4 gated reranker override
(Task 3). One instance, one MODE per push (env header):

  MODE=determinism -> kernel_payload.run_gated_override_determinism: Channel-A double-run
    identity check on config/eval/schedules/2b4_determinism_v001.yaml (the heuristic_reranker
    override agent, twice, same seed_base, fresh server each time). Prints
    ``2B4-DETERMINISM: PASS/FAIL``.
  MODE=strength -> kernel_payload.run_gated_override_strength: paired dev-panel strength runs
    on config/eval/schedules/2b4_devstrength_v001.yaml (heuristic vs override, same seed_base,
    same baseline villain). Prints ``2B4-STRENGTH: DONE`` and copies BOTH result JSONLs out for
    local T5 ``eval-report --mode paired`` report generation.

Mirrors tools/kaggle/datagen_kernel.py's bootstrap VERBATIM (see that file's docstring for the
attempt-1/2 operational lessons baked in here too) -- the only differences are the env header's
MODE field and which kernel_payload entry point + output layout follow bootstrap.

**Ordering (spec: "Identity before strength — non-negotiable") is enforced by the CONTROLLER**
(plan Task 4), which pushes+runs the determinism kernel first and only pushes the strength
kernel after a PASS -- this script only ever runs ONE mode per invocation and does not itself
gate strength on a prior determinism result.

The env header carries REPO_URL (optional, same default as datagen_kernel.py), REPO_SHA
(required), and MODE (required: "determinism" or "strength"). kaggle_driver.push injects all
three per kernel push.
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
_DEFAULT_REPO_URL = "https://github.com/chrismaghuhn/ShowdownBot"

_REPO_DIR = Path("/tmp/sb_repo")
_OUT_DIR = Path("/tmp/sb_out")
_SHOWDOWN_CACHE_DIR = Path("/tmp/sb_showdown_cache")
_WORKING_DIR = Path("/kaggle/working")

_MODES = ("determinism", "strength")
_SUBDIRS = {"determinism": ("run1", "run2"), "strength": ("heuristic", "override")}
_VERDICT_TAGS = {"determinism": "2B4-DETERMINISM", "strength": "2B4-STRENGTH"}

# showdown_bot runtime deps (import name -> pip name). Same 2026-07 Kaggle image assumption as
# repro_validation.py/datagen_kernel.py -- the install branch is a guard against future image
# changes only. LightGBM itself is NOT listed here: the 2026-07 Kaggle image ships it already,
# and the override loader (client/gauntlet.py's _load_reranker_override_from_env) imports it
# lazily -- only when SHOWDOWN_RERANKER_OVERRIDE is set, i.e. only in this kernel's own run.
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
    mode = env["MODE"]          # required: "determinism" or "strength"
    if mode not in _MODES:
        raise ValueError(f"MODE must be one of {_MODES}, got {mode!r}")

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
    kernel_payload.setup_calc_bridge(str(_REPO_DIR))  # attempt-2 lesson: calc dist/ absent on a fresh clone

    if mode == "determinism":
        result = kernel_payload.run_gated_override_determinism(str(_REPO_DIR), showdown_dir, str(_OUT_DIR))
    else:
        result = kernel_payload.run_gated_override_strength(str(_REPO_DIR), showdown_dir, str(_OUT_DIR))

    _WORKING_DIR.mkdir(parents=True, exist_ok=True)
    (_WORKING_DIR / "verdict.txt").write_text(result["verdict"] + "\n", encoding="utf-8")
    for sub in _SUBDIRS[mode]:
        kernel_payload.copy_outputs(str(_OUT_DIR / sub), working_dir=str(_WORKING_DIR / sub))


_CLIENT_LOG_TAIL_LINES = 120


def _salvage_outputs(mode: str) -> None:
    """Best-effort post-failure diagnostics -- same rationale/pattern as
    datagen_kernel.py/repro_validation.py's ``_salvage_outputs``, run per sub-run directory
    (this kernel always has two: run1/run2 or heuristic/override) so a mid-run failure still
    surfaces whichever half completed. Never raises."""
    for sub in _SUBDIRS.get(mode, ("run1", "run2")):
        try:
            client_log = _OUT_DIR / sub / "client.log"
            if client_log.exists():
                lines = client_log.read_text(encoding="utf-8", errors="replace").splitlines()
                print(f"--- {sub}/client.log tail "
                      f"({min(len(lines), _CLIENT_LOG_TAIL_LINES)} of {len(lines)} lines) ---")
                for line in lines[-_CLIENT_LOG_TAIL_LINES:]:
                    print(line)
                print(f"--- end {sub}/client.log tail ---")
        except Exception as exc:  # noqa: BLE001 -- diagnostics must never mask the real failure
            print(f"(salvage: could not read {sub}/client.log: {exc})")
        try:
            import kernel_payload  # importable only after main() got past the clone + sys.path setup

            kernel_payload.copy_outputs(str(_OUT_DIR / sub), working_dir=str(_WORKING_DIR / sub))
        except Exception as exc:  # noqa: BLE001
            print(f"(salvage: copy_outputs unavailable for {sub}: {exc})")


if __name__ == "__main__":
    _mode = "determinism"  # fallback tag if the env header itself can't be parsed
    try:
        _mode = _own_env().get("MODE", _mode)
    except Exception:  # noqa: BLE001 -- header parsing must never block the salvage tag choice
        pass
    try:
        main()
    except Exception as exc:  # noqa: BLE001 -- the driver must ALWAYS find a verdict line
        tag = _VERDICT_TAGS.get(_mode, "2B4-DETERMINISM")
        print(f"{tag}: FAIL (exception: {exc})")
        traceback.print_exc()
        _salvage_outputs(_mode)
