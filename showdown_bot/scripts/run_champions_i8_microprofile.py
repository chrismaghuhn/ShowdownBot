"""Authorized executable for the Champions I8 microprofile run. THIN by design: it parses the
run parameters and delegates every piece of orchestration to
``showdown_bot.eval.profile_runner`` -- pure logic lives in a module, unit-tested there and
imported here, per the ``scripts/`` convention ``run_cap_latency_sweep.py`` states for itself.
It holds no fixtures, no arm matrix, no validator and no hash recipe.

The repetition count is REQUIRED and must be exactly ``30`` -- the approved microprofile scale
(15 arms x 30 reps = 450 rows). There is deliberately NO default: an unstated rep count is an
unlogged lever on which arm looks cheap, and a wrong one silently changes the run. The reusable
runner accepts any positive value for tests; only this entrypoint pins 30.

    Usage (PowerShell, from the repo; Windows is the fixed measurement host):
        Set-Location showdown_bot
        $env:PYTHONPATH = (Resolve-Path "src").Path
        python scripts/run_champions_i8_microprofile.py --reps 30 --out-dir <output-dir>

This starts no server and plays no battle: it drives the promoted fixtures through the scoring
path offline, and refuses to overwrite an existing --out-dir.
"""
from __future__ import annotations

import argparse
import sys

_APPROVED_REPS = 30


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Run the approved Champions I8 microprofile (15 arms x 30 reps = 450 rows) offline. "
            "--reps must be given explicitly and must be exactly 30; there is no default."
        )
    )
    # required (missing -> error) and constrained to the single approved value (0, negatives and
    # any other integer are rejected by argparse's own choices check; a non-integer by its type
    # conversion). This is what makes 30 the ONLY runnable rep count from the command line.
    p.add_argument(
        "--reps", type=int, required=True, choices=[_APPROVED_REPS],
        help="timed repetitions per arm; must be exactly 30 (the approved scale)",
    )
    p.add_argument(
        "--out-dir", required=True,
        help="output directory to create; refused if it already exists",
    )
    return p


def parse_args(argv=None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    # Imported lazily so parse_args (and its tests) never import the machinery or touch node.
    from showdown_bot.eval.profile_runner import run_microprofile

    report = run_microprofile(args.out_dir, reps=args.reps, log=print)
    print(f"microprofile complete: {report['rows']} rows across {len(report['arms'])} arms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
