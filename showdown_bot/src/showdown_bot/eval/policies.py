"""Central opponent-policy registry (T3a).

Declares the full planned policy set with metadata NOW so panel + schedule validation have
a single source of truth, decoupled from when T3c wires the implementations. `implemented`
flips to True in T3c per policy; `reproducible=False` marks a policy that must never enter a
paired/reproducible schedule by default (only `random`).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyInfo:
    name: str
    implemented: bool
    reproducible: bool


POLICIES: dict[str, PolicyInfo] = {
    p.name: p for p in [
        PolicyInfo("heuristic", implemented=True, reproducible=True),
        PolicyInfo("max_damage", implemented=True, reproducible=True),  # eval-deterministic in T3c
        PolicyInfo("random", implemented=True, reproducible=False),     # intentionally non-reproducible
        PolicyInfo("greedy_protect", implemented=False, reproducible=True),
        PolicyInfo("simple_heuristic", implemented=False, reproducible=True),
        PolicyInfo("scripted_vgc", implemented=False, reproducible=True),
    ]
}


def is_known(name: str) -> bool:
    return name in POLICIES


def is_implemented(name: str) -> bool:
    return name in POLICIES and POLICIES[name].implemented


def is_reproducible(name: str) -> bool:
    return name in POLICIES and POLICIES[name].reproducible


def reproducible_names() -> set[str]:
    return {n for n, p in POLICIES.items() if p.reproducible}
