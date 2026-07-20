"""CLI for showdownbot-studio-export."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .errors import ExportRefuse
from .export_bundle import export_bundle


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="showdownbot-studio-export")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--battle-log", type=Path, default=None)
    p.add_argument("--decision-trace", type=Path, default=None)
    p.add_argument("--results", type=Path, default=None)
    p.add_argument("--run-manifest", type=Path, default=None)
    p.add_argument("--config-manifest", type=Path, default=None)
    p.add_argument("--battle-id", type=str, default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        export_bundle(
            out=args.out.resolve(),
            battle_log=args.battle_log,
            decision_trace=args.decision_trace,
            results=args.results,
            run_manifest=args.run_manifest,
            config_manifest=args.config_manifest,
            battle_id=args.battle_id,
        )
        return 0
    except ExportRefuse as exc:
        print(exc.format_stderr(), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"internal_error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
