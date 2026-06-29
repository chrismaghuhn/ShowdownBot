from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ProtectPriors:
    """Prior probability that the opponent clicks Protect, used to weight the
    opponent's candidate responses (Step 12)."""

    default: float = 0.18
    threatened_bump: float = 0.45
    consecutive_penalty: float = 0.4
    species: dict[str, float] = field(default_factory=dict)

    def rate(self, species: str, *, threatened: bool = False, consecutive: int = 0) -> float:
        base = self.species.get(species, self.default)
        if threatened:
            base += self.threatened_bump
        # Each consecutive prior Protect makes another Protect less likely / less
        # reliable -> shrink the rate multiplicatively.
        base *= self.consecutive_penalty ** max(0, consecutive)
        return max(0.0, min(1.0, base))


def load_protect_priors(path: Path) -> ProtectPriors:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return ProtectPriors(
        default=float(data.get("default", 0.18)),
        threatened_bump=float(data.get("threatened_bump", 0.45)),
        consecutive_penalty=float(data.get("consecutive_penalty", 0.4)),
        species={k: float(v) for k, v in (data.get("species") or {}).items()},
    )
