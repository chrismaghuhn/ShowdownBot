from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CalcMon:
    """A Pokemon spec for a single damage calculation."""

    species: str
    level: int = 50
    item: str | None = None
    nature: str | None = None
    ability: str | None = None
    evs: dict[str, int] | None = None
    ivs: dict[str, int] | None = None
    boosts: dict[str, int] | None = None
    status: str | None = None
    tera_type: str | None = None
    move: str | None = None

    def to_payload(self) -> dict:
        payload: dict[str, object] = {"species": self.species, "level": self.level}
        if self.item is not None:
            payload["item"] = self.item
        if self.nature is not None:
            payload["nature"] = self.nature
        if self.ability is not None:
            payload["ability"] = self.ability
        if self.evs is not None:
            payload["evs"] = self.evs
        if self.ivs is not None:
            payload["ivs"] = self.ivs
        if self.boosts is not None:
            payload["boosts"] = self.boosts
        if self.status is not None:
            payload["status"] = self.status
        if self.tera_type is not None:
            payload["teraType"] = self.tera_type
        if self.move is not None:
            payload["move"] = self.move
        return payload


@dataclass
class DamageRequest:
    attacker: CalcMon
    defender: CalcMon
    move: str
    field: dict | None = None
    gen: int = 9
    id: str | None = None

    def to_payload(self) -> dict:
        payload: dict[str, object] = {
            "id": self.id,
            "gen": self.gen,
            "attacker": self.attacker.to_payload(),
            "defender": self.defender.to_payload(),
            "move": self.move,
        }
        payload["field"] = self.field or {"gameType": "Doubles"}
        return payload


@dataclass
class DamageResult:
    rolls: list[int] = field(default_factory=list)
    min_damage: int = 0
    max_damage: int = 0
    max_hp: int = 0
    min_percent: float = 0.0
    max_percent: float = 0.0
    ko_chance_text: str | None = None
    desc: str | None = None
    id: str | None = None
    error: str | None = None

    @property
    def is_guaranteed_ohko(self) -> bool:
        """Even the lowest roll kills (worst-case-for-defender KO)."""
        return self.max_hp > 0 and self.min_damage >= self.max_hp

    @property
    def can_ohko(self) -> bool:
        """At least the highest roll kills."""
        return self.max_hp > 0 and self.max_damage >= self.max_hp

    # Convenience alias; "is_ohko" means a guaranteed KO.
    @property
    def is_ohko(self) -> bool:
        return self.is_guaranteed_ohko

    @classmethod
    def from_json(cls, data: dict) -> "DamageResult":
        if "error" in data and data.get("error"):
            return cls(id=data.get("id"), error=str(data["error"]))
        rolls = [int(x) for x in data.get("damage", [])]
        return cls(
            rolls=rolls,
            min_damage=int(data.get("minDamage", min(rolls) if rolls else 0)),
            max_damage=int(data.get("maxDamage", max(rolls) if rolls else 0)),
            max_hp=int(data.get("maxHP", 0)),
            min_percent=float(data.get("minPercent", 0.0)),
            max_percent=float(data.get("maxPercent", 0.0)),
            ko_chance_text=data.get("koChanceText"),
            desc=data.get("desc"),
            id=data.get("id"),
        )
