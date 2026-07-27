"""Optional in-memory sink for Depth-2 readiness telemetry (spec §6.5).

Allocated only when the decision-profile writer is enabled. Records work
where it actually happens: at the real scoring call sites. The sink performs
no file I/O and no environment reads.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Depth2ReadinessCounts:
    search_depth: int = 1
    search_topn_requested: int = 0
    search_topm_requested: int = 0
    depth2_candidates_selected: int = 0
    depth2_response_slots_eligible: int = 0
    accuracy_mode: bool = False
    accuracy_branch_cap: int = 6
    turn1_accuracy_leaf_count: int = 0
    turn1_accuracy_cap_hits: int = 0
    turn2_accuracy_leaf_count: int = 0
    turn2_accuracy_cap_hits: int = 0

    @property
    def turn1_accuracy_cap_fallback(self) -> bool:
        return self.turn1_accuracy_cap_hits > 0

    @property
    def turn2_accuracy_cap_fallback(self) -> bool:
        return self.turn2_accuracy_cap_hits > 0

    def add_turn1_accuracy(self, *, leaf_count: int, cap_hits: int) -> None:
        self.turn1_accuracy_leaf_count += leaf_count
        self.turn1_accuracy_cap_hits += cap_hits

    def add_turn2_accuracy(self, *, leaf_count: int, cap_hits: int) -> None:
        self.turn2_accuracy_leaf_count += leaf_count
        self.turn2_accuracy_cap_hits += cap_hits

    def to_dict(self) -> dict:
        return {
            "search_depth": self.search_depth,
            "search_topn_requested": self.search_topn_requested,
            "search_topm_requested": self.search_topm_requested,
            "depth2_candidates_selected": self.depth2_candidates_selected,
            "depth2_response_slots_eligible": self.depth2_response_slots_eligible,
            "accuracy_mode": self.accuracy_mode,
            "accuracy_branch_cap": self.accuracy_branch_cap,
            "turn1_accuracy_leaf_count": self.turn1_accuracy_leaf_count,
            "turn1_accuracy_cap_hits": self.turn1_accuracy_cap_hits,
            "turn1_accuracy_cap_fallback": self.turn1_accuracy_cap_fallback,
            "turn2_accuracy_leaf_count": self.turn2_accuracy_leaf_count,
            "turn2_accuracy_cap_hits": self.turn2_accuracy_cap_hits,
            "turn2_accuracy_cap_fallback": self.turn2_accuracy_cap_fallback,
        }
