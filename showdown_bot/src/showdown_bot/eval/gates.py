"""Eval gate constants (T3f Task 6): pin the decision-latency p95 budget.

``config/eval/gates.yaml`` holds gate constants pinned ahead of enforcement. T3f only pins
``decision_latency_p95_budget_ms`` as a config constant (current measured baseline ~200 ms);
T5 is responsible for enforcing it as a gate.
"""
from __future__ import annotations

from pathlib import Path

import yaml

# Repo root (contains config/ and tools/): this file is at
# <repo>/showdown_bot/src/showdown_bot/eval/gates.py -> parents[4] == <repo>.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_GATES = _REPO_ROOT / "config" / "eval" / "gates.yaml"


class GatesConfigError(ValueError):
    """``gates.yaml`` is missing or malformed."""


def load_latency_budget_ms(path=None) -> int:
    """Read ``decision_latency_p95_budget_ms`` from ``config/eval/gates.yaml``."""
    p = Path(path) if path is not None else _GATES
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise GatesConfigError(f"gates config not found: {p}") from exc
    budget = (data or {}).get("decision_latency_p95_budget_ms")
    if not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0:
        raise GatesConfigError(
            f"gates config missing/invalid 'decision_latency_p95_budget_ms': {p}"
        )
    return budget
