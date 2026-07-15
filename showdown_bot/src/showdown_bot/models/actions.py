from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SlotAction:
    kind: Literal["move", "switch", "pass"]
    move_index: int | None = None      # 1-based for /choose
    target: int | None = None          # 1 or 2 for foe slots, -1 ally, -2 self
    terastallize: bool = False
    target_ident: str | None = None    # for switch: bench ident suffix
    mega_evolve: bool = False


@dataclass(frozen=True)
class SlotPair:
    slot0: SlotAction
    slot1: SlotAction
