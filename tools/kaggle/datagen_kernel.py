# KAGGLE_ENV: {}
"""tools/kaggle/datagen_kernel.py -- Kaggle SCRIPT kernel: per-hero seeded dataset export (2b-2.5a Task 5).

Single-file kernel, one instance per hero (four pushed concurrently in Task 6: slugs
sb-datagen-{fixed,trickroom,sun,rain}). Mirrors tools/kaggle/repro_validation.py's bootstrap
VERBATIM (same clone/sys.path/deps-guard/setup_calc_bridge lessons -- see that file's docstring
for the attempt-1/2 operational lessons baked in here too): the only difference is which
kernel_payload entry point it delegates to after bootstrap -- ``run_datagen(hero_key)`` instead
of ``validate_prefix_reproduction``.

The env header carries REPO_URL (optional, same default as repro_validation.py), REPO_SHA
(required), HERO_KEY (required -- one of showdown_bot.eval.datagen_2b25a.HERO_TEAMS' keys:
fixed/trickroom/sun/rain), and EXTRA_ENV (optional -- a JSON object of str->str
``SHOWDOWN_*`` env vars, e.g. ``{"SHOWDOWN_FAST_BOARD_PROTECT_PENALTY": "-3.0"}``, injected
into the gauntlet subprocess for THIS run only -- see ``kernel_payload.run_datagen``'s
``extra_env`` docstring). kaggle_driver.push injects the whole header dict, including a nested
EXTRA_ENV object, as a single JSON blob, so it round-trips without any special-casing. Absent
EXTRA_ENV -> ``None`` -> byte-identical to pre-passthrough behavior.

Flow: parse own env header -> git clone + checkout REPO_SHA -> put the cloned package on
sys.path/PYTHONPATH -> import kernel_payload from the clone -> bootstrap_node ->
setup_showdown -> setup_calc_bridge -> run_datagen(repo_root, showdown_dir, HERO_KEY, out_dir,
extra_env=<parsed EXTRA_ENV or None>) (resolves the hero's schedule + seed base, runs it with a
dataset export in rollout-teacher mode plus any extra_env, validates the output, and prints the
DATAGEN verdict line itself) -> write verdict.txt -> copy_outputs (dataset.jsonl gzipped
alongside results/manifest/seeds/client-log/verdict). Wrapped so a verdict line is ALWAYS
printed, even on a bootstrap-stage exception (the driver's ``parse_verdict`` must always find
one): ``DATAGEN: FAIL (exception: ...)`` + traceback + salvage (client-log tail + partial-output
copy) -- same pattern as repro_validation.py. A malformed EXTRA_ENV header field (not a JSON
object of str->str) raises inside this same wrapper, so it also surfaces as a
``DATAGEN: FAIL (exception: ...)`` verdict rather than a bare traceback.
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

# showdown_bot runtime deps (import name -> pip name). Same 2026-07 Kaggle image assumption as
# repro_validation.py -- the install branch is a guard against future image changes only.
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


def _extra_env_from_header(env: dict) -> dict | None:
    """Recover the optional ``EXTRA_ENV`` field from a parsed KAGGLE_ENV header dict (``env``,
    as returned by ``_own_env``) -- an arbitrary set of extra ``SHOWDOWN_*`` env vars to inject
    into this run's gauntlet subprocess (``kernel_payload.run_datagen``'s ``extra_env``
    passthrough). Returns ``None`` when the field is absent (the default -- byte-identical to
    pre-passthrough behavior: ``run_datagen`` then passes only its own base teacher-mode
    extra_env). Raises ``ValueError`` if the field IS present but is not a JSON object mapping
    str keys to str values -- fails loudly rather than silently mis-injecting a non-string env
    value into a subprocess env dict (which Python's ``subprocess`` module itself would reject
    at spawn time with a less legible error)."""
    if "EXTRA_ENV" not in env:
        return None
    extra_env = env["EXTRA_ENV"]
    if not isinstance(extra_env, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in extra_env.items()
    ):
        raise ValueError(
            f"EXTRA_ENV header field must be a JSON object of str -> str, got {extra_env!r}"
        )
    return extra_env


def _ensure_runtime_deps() -> None:
    missing = [pip_name for module_name, pip_name in _RUNTIME_DEPS
               if importlib.util.find_spec(module_name) is None]
    if missing:
        subprocess.run([sys.executable, "-m", "pip", "install", *missing], check=True)


def main() -> None:
    env = _own_env()
    repo_url = env.get("REPO_URL", _DEFAULT_REPO_URL)
    repo_sha = env["REPO_SHA"]  # required -- no floating main
    hero_key = env["HERO_KEY"]  # required -- one of datagen_2b25a.HERO_TEAMS' keys
    extra_env = _extra_env_from_header(env)  # optional -- None means no extra SHOWDOWN_* vars

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
    result = kernel_payload.run_datagen(
        str(_REPO_DIR), showdown_dir, hero_key, str(_OUT_DIR), extra_env=extra_env)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    (_OUT_DIR / "verdict.txt").write_text(result["verdict"] + "\n", encoding="utf-8")
    kernel_payload.copy_outputs(str(_OUT_DIR))


_CLIENT_LOG_TAIL_LINES = 120


def _salvage_outputs() -> None:
    """Best-effort post-failure diagnostics -- identical rationale/pattern to
    repro_validation.py's ``_salvage_outputs``: print the client-log tail into the kernel log
    (always retrievable even if ``copy_outputs`` never runs) and copy whatever partial outputs
    exist into /kaggle/working. Never raises."""
    try:
        client_log = _OUT_DIR / "client.log"
        if client_log.exists():
            lines = client_log.read_text(encoding="utf-8", errors="replace").splitlines()
            print(f"--- client.log tail ({min(len(lines), _CLIENT_LOG_TAIL_LINES)} of {len(lines)} lines) ---")
            for line in lines[-_CLIENT_LOG_TAIL_LINES:]:
                print(line)
            print("--- end client.log tail ---")
    except Exception as exc:  # noqa: BLE001 -- diagnostics must never mask the real failure
        print(f"(salvage: could not read client.log: {exc})")
    try:
        import kernel_payload  # importable only after main() got past the clone + sys.path setup

        kernel_payload.copy_outputs(str(_OUT_DIR))
    except Exception as exc:  # noqa: BLE001
        print(f"(salvage: copy_outputs unavailable: {exc})")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 -- the driver must ALWAYS find a verdict line
        print(f"DATAGEN: FAIL (exception: {exc})")
        traceback.print_exc()
        _salvage_outputs()
