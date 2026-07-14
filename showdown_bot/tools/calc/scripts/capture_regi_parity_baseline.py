#!/usr/bin/env python3
"""Capture Reg-I gen-9 @smogon/calc parity baseline (commit 1 gate).

Verifies installed @smogon/calc is exactly 0.10.0, runs fixed stats/types/damage
probes through calc.mjs, writes calc_regi_parity_baseline.json. Refuses to
overwrite an existing fixture unless --force.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REQUIRED_CALC_VERSION = "0.10.0"

# Repo paths (showdown_bot/tools/calc/scripts/ -> repo root is 4 levels up).
SCRIPT_DIR = Path(__file__).resolve().parent
CALC_DIR = SCRIPT_DIR.parent
REPO_ROOT = CALC_DIR.parents[1]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "calc_regi_parity_baseline.json"

# Fixed probe list — same inputs as T0 parity gate (§8).
PROBES: list[dict] = [
    {
        "id": "stats_incineroar_adamant",
        "kind": "stats",
        "request_payload": {
            "id": "stats_incineroar_adamant",
            "kind": "stats",
            "gen": 9,
            "mon": {
                "species": "Incineroar",
                "level": 50,
                "nature": "Adamant",
                "evs": {"hp": 252, "atk": 4},
            },
        },
    },
    {
        "id": "stats_flutter_mane_timid",
        "kind": "stats",
        "request_payload": {
            "id": "stats_flutter_mane_timid",
            "kind": "stats",
            "gen": 9,
            "mon": {
                "species": "Flutter Mane",
                "level": 50,
                "nature": "Timid",
                "evs": {"spa": 252, "spe": 252},
            },
        },
    },
    {
        "id": "types_incineroar",
        "kind": "types",
        "request_payload": {
            "id": "types_incineroar",
            "kind": "types",
            "gen": 9,
            "species": "Incineroar",
        },
    },
    {
        "id": "types_flutter_mane",
        "kind": "types",
        "request_payload": {
            "id": "types_flutter_mane",
            "kind": "types",
            "gen": 9,
            "species": "Flutter Mane",
        },
    },
    {
        "id": "damage_flare_blitz_ohko",
        "kind": "damage",
        "request_payload": {
            "id": "damage_flare_blitz_ohko",
            "gen": 9,
            "attacker": {
                "species": "Incineroar",
                "level": 50,
                "nature": "Adamant",
                "evs": {"atk": 252},
                "move": "Flare Blitz",
            },
            "defender": {
                "species": "Flutter Mane",
                "level": 50,
                "nature": "Timid",
                "evs": {"hp": 4},
            },
            "move": "Flare Blitz",
            "field": {"gameType": "Doubles"},
        },
    },
    {
        "id": "damage_knock_off",
        "kind": "damage",
        "request_payload": {
            "id": "damage_knock_off",
            "gen": 9,
            "attacker": {
                "species": "Incineroar",
                "level": 50,
                "nature": "Adamant",
                "evs": {"atk": 252},
                "ability": "Intimidate",
            },
            "defender": {
                "species": "Flutter Mane",
                "level": 50,
                "nature": "Timid",
                "evs": {"hp": 252, "spd": 252},
            },
            "move": "Knock Off",
            "field": {"gameType": "Doubles"},
        },
    },
    {
        "id": "damage_shadow_ball",
        "kind": "damage",
        "request_payload": {
            "id": "damage_shadow_ball",
            "gen": 9,
            "attacker": {
                "species": "Flutter Mane",
                "level": 50,
                "nature": "Timid",
                "evs": {"spa": 252, "spe": 252},
                "ability": "Protosynthesis",
            },
            "defender": {
                "species": "Incineroar",
                "level": 50,
                "nature": "Adamant",
                "evs": {"hp": 252, "spd": 4},
            },
            "move": "Shadow Ball",
            "field": {"gameType": "Doubles"},
        },
    },
    {
        "id": "damage_moonblast",
        "kind": "damage",
        "request_payload": {
            "id": "damage_moonblast",
            "gen": 9,
            "attacker": {
                "species": "Flutter Mane",
                "level": 50,
                "nature": "Timid",
                "evs": {"spa": 252},
            },
            "defender": {
                "species": "Incineroar",
                "level": 50,
                "nature": "Careful",
                "evs": {"hp": 252},
            },
            "move": "Moonblast",
            "field": {"gameType": "Doubles"},
        },
    },
]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_calc_version(calc_dir: Path) -> str:
    lock_path = calc_dir / "package-lock.json"
    nm_pkg = calc_dir / "node_modules" / "@smogon" / "calc" / "package.json"
    if not lock_path.is_file():
        raise SystemExit(f"missing package-lock.json: {lock_path}")
    if not nm_pkg.is_file():
        raise SystemExit(
            f"missing node_modules/@smogon/calc — run: cd {calc_dir} && npm ci"
        )

    lock = _read_json(lock_path)
    lock_ver = (
        lock.get("packages", {})
        .get("node_modules/@smogon/calc", {})
        .get("version")
    )
    installed_ver = _read_json(nm_pkg).get("version")

    if lock_ver != REQUIRED_CALC_VERSION:
        raise SystemExit(
            f"package-lock pins @smogon/calc {lock_ver!r}, expected {REQUIRED_CALC_VERSION!r}"
        )
    if installed_ver != REQUIRED_CALC_VERSION:
        raise SystemExit(
            f"installed @smogon/calc is {installed_ver!r}, expected {REQUIRED_CALC_VERSION!r}"
        )
    return installed_ver


def _resolve_executable(name: str) -> str:
    """Resolve CLI tool path; Windows npm is npm.cmd, not npm."""
    candidates = [name]
    if sys.platform == "win32" and name == "npm":
        candidates = ["npm.cmd", "npm.exe", "npm"]
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return path
    raise SystemExit(f"{name!r} not found on PATH")


def _tool_version(name: str) -> str:
    exe = _resolve_executable(name)
    try:
        proc = subprocess.run(
            [exe, "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"{name} --version failed (rc={exc.returncode}): {exc.stderr.strip()}"
        ) from exc
    line = (proc.stdout or proc.stderr).strip().splitlines()[0]
    if not line or line.startswith("unavailable"):
        raise SystemExit(f"{name} --version returned empty output")
    return line


def run_calc_batch(calc_dir: Path, payloads: list[dict]) -> list[dict]:
    raw = json.dumps(payloads)
    proc = subprocess.run(
        ["node", "calc.mjs"],
        input=raw,
        capture_output=True,
        text=True,
        cwd=str(calc_dir),
        timeout=60.0,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"calc.mjs failed (rc={proc.returncode}): {proc.stderr.strip()}"
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"calc.mjs returned invalid JSON: {exc}") from exc
    if not isinstance(data, list) or len(data) != len(payloads):
        raise SystemExit(
            f"expected {len(payloads)} results, got {type(data).__name__}"
        )
    return data


def capture_cases(calc_dir: Path) -> list[dict]:
    payloads = [p["request_payload"] for p in PROBES]
    responses = run_calc_batch(calc_dir, payloads)
    cases: list[dict] = []
    for probe, resp in zip(PROBES, responses):
        if resp.get("error"):
            raise SystemExit(
                f"probe {probe['id']!r} failed: {resp['error']}"
            )
        cases.append(
            {
                "id": probe["id"],
                "kind": probe["kind"],
                "request_payload": probe["request_payload"],
                "expected_response": resp,
            }
        )
    return cases


def fixture_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing baseline fixture",
    )
    args = parser.parse_args()

    if FIXTURE_PATH.exists() and not args.force:
        raise SystemExit(
            f"fixture already exists: {FIXTURE_PATH}\n"
            "Re-run with --force to overwrite."
        )

    calc_version = verify_calc_version(CALC_DIR)
    cases = capture_cases(CALC_DIR)

    fixture = {
        "meta": {
            "purpose": "Reg-I gen-9 parity baseline for @smogon/calc vendor bump gate (T0)",
            "calc_package": "@smogon/calc",
            "calc_version": calc_version,
            "node_version": _tool_version("node"),
            "npm_version": _tool_version("npm"),
            "platform": platform.platform(),
            "probe_count": len(cases),
        },
        "cases": cases,
    }

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(
        json.dumps(fixture, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    digest = fixture_sha256(FIXTURE_PATH)
    print(f"Wrote {FIXTURE_PATH}")
    print(f"fixture_sha256={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
