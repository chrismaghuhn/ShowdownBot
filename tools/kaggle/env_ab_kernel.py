# KAGGLE_ENV: {}
"""tools/kaggle/env_ab_kernel.py -- Kaggle SCRIPT kernel: generic paired dev-strength env-A/B
(2c-1). One instance per A/B comparison. Unlike gated_override_kernel.py's two hard-coded MODEs
(determinism/strength), both tied to the heuristic_reranker override agent, this kernel is
parameterized entirely by two caller-supplied env dicts (BASELINE_ENV/CANDIDATE_ENV) -- e.g. to
A/B SHOWDOWN_MUST_REACT_LAMBDA=0.3 (candidate) vs 0.6 (baseline) on the SAME dev-strength schedule
(config/eval/schedules/2b4_devstrength_v001.yaml) and seed_base
(kernel_payload._MUSTREACT_AB_SEED_BASE), producing two results.jsonl files that pair for a local
``cli eval-report`` McNemar comparison (``--run-a``/``--seedlog-a`` + ``--run-b``/``--seedlog-b``
-- paired mode, per ``cli.run_eval_report``).

Mirrors tools/kaggle/gated_override_kernel.py's bootstrap VERBATIM (clone/checkout, runtime-deps
guard, sys.path/PYTHONPATH wiring, bootstrap_node/setup_showdown/setup_calc_bridge) -- the only
differences are the env header's BASELINE_ENV/CANDIDATE_ENV fields (in place of MODE) and the
kernel_payload entry point (``run_devstrength_env_ab`` in place of
``run_gated_override_determinism``/``_strength``). Does NOT import gated_override_kernel or touch
config/eval/schedules/2b4_determinism_v001.yaml, ``_2b4_override_env``, or either
``run_gated_override_*`` function -- this is a separate, generic comparison path (spec: "Do NOT
modify the existing gated-override code").

The env header carries REPO_URL (optional, same default as the other kernels), REPO_SHA
(required), BASELINE_ENV (required -- a JSON object of str -> str SHOWDOWN_* env vars applied to
the baseline arm), and CANDIDATE_ENV (required -- same shape, applied to the candidate arm).
kaggle_driver.push injects the whole header dict, including the two nested env objects, as a
single JSON blob (same nested-dict mechanism as datagen_kernel.py's EXTRA_ENV field --
test_kernel_payload.py's EXTRA_ENV round-trip test already proves nested JSON objects survive
inject_env_header/parse_env_header unchanged; test_env_ab_kernel.py has the analogous proof for
BASELINE_ENV/CANDIDATE_ENV).

kernel_payload.run_devstrength_env_ab does its own output copying (both arms, into
<working_dir>/baseline and <working_dir>/candidate) -- unlike run_gated_override_strength, so
this script does not need its own per-subdir copy loop on the success path, only the top-level
verdict.txt write. The failure path's ``_salvage_outputs`` still copies each arm's partial output
independently (mirrors gated_override_kernel.py's salvage), since a mid-run exception can occur
before run_devstrength_env_ab reaches its own copy_outputs call for that arm.
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

_SUBDIRS = ("baseline", "candidate")

# showdown_bot runtime deps (import name -> pip name). Same 2026-07 Kaggle image assumption as
# the other kernels -- the install branch is a guard against future image changes only.
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


def _env_dict_from_header(env: dict, field: str) -> dict:
    """Recover a REQUIRED env-dict field (``BASELINE_ENV`` or ``CANDIDATE_ENV``) from a parsed
    KAGGLE_ENV header dict (``env``, as returned by ``_own_env``) -- validated exactly like
    ``datagen_kernel.py``'s ``_extra_env_from_header``, except REQUIRED (no absent-field
    default): unlike EXTRA_ENV's optional passthrough, both arms of this generic A/B kernel need
    an explicit env dict -- there is no sensible "no override" default for a comparison whose
    whole point is the two arms differing. Raises ``ValueError`` if ``field`` is absent from
    ``env``, or present but not a JSON object mapping str keys to str values -- fails loudly
    rather than silently mis-injecting a non-string env value into a subprocess env dict."""
    if field not in env:
        raise ValueError(f"{field} header field is required")
    value = env[field]
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        raise ValueError(
            f"{field} header field must be a JSON object of str -> str, got {value!r}"
        )
    return value


def _parsed_header_fields(env: dict) -> tuple[str, str, dict, dict]:
    """Extract + validate this kernel's env-header fields from a parsed KAGGLE_ENV header dict
    (``env``, as returned by ``_own_env``): ``(repo_url, repo_sha, baseline_env,
    candidate_env)``. ``REPO_URL`` is optional (defaults to ``_DEFAULT_REPO_URL``); ``REPO_SHA``
    is required (a bare dict index -- raises ``KeyError`` if absent, same "no floating main"
    convention as every other kernel script in this package); ``BASELINE_ENV``/``CANDIDATE_ENV``
    are both required JSON objects of str -> str (``_env_dict_from_header``, raises
    ``ValueError``). Pure -- no I/O, directly unit-testable without running ``main()``'s
    clone/subprocess steps."""
    repo_url = env.get("REPO_URL", _DEFAULT_REPO_URL)
    repo_sha = env["REPO_SHA"]  # required -- no floating main
    baseline_env = _env_dict_from_header(env, "BASELINE_ENV")
    candidate_env = _env_dict_from_header(env, "CANDIDATE_ENV")
    return repo_url, repo_sha, baseline_env, candidate_env


def _ensure_runtime_deps() -> None:
    missing = [pip_name for module_name, pip_name in _RUNTIME_DEPS
               if importlib.util.find_spec(module_name) is None]
    if missing:
        subprocess.run([sys.executable, "-m", "pip", "install", *missing], check=True)


def main() -> None:
    env = _own_env()
    repo_url, repo_sha, baseline_env, candidate_env = _parsed_header_fields(env)

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

    result = kernel_payload.run_devstrength_env_ab(
        str(_REPO_DIR), showdown_dir, str(_OUT_DIR),
        baseline_env=baseline_env, candidate_env=candidate_env, working_dir=str(_WORKING_DIR),
    )

    _WORKING_DIR.mkdir(parents=True, exist_ok=True)
    (_WORKING_DIR / "verdict.txt").write_text(result["verdict"] + "\n", encoding="utf-8")


_CLIENT_LOG_TAIL_LINES = 120


def _salvage_outputs() -> None:
    """Best-effort post-failure diagnostics -- same rationale/pattern as
    gated_override_kernel.py's ``_salvage_outputs``, run per arm directory (this kernel always
    has two: baseline/candidate) so a mid-run failure still surfaces whichever arm completed.
    Never raises."""
    for sub in _SUBDIRS:
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
    try:
        main()
    except Exception as exc:  # noqa: BLE001 -- the driver must ALWAYS find a verdict line
        print(f"ENV-AB-STRENGTH: FAIL (exception: {exc})")
        traceback.print_exc()
        _salvage_outputs()
