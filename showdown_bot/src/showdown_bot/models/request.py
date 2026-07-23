from __future__ import annotations

from pydantic import BaseModel, Field


class MoveSlot(BaseModel):
    move: str
    id: str
    # Struggle-only requests (all moves out of PP) omit both pp and maxpp
    # entirely (T6 held-out finding, seed t6heldout2026 idx 23).
    pp: int | None = None
    maxpp: int | None = None
    # Optional: when omitted, Showdown expects a targetless /choose (e.g. Solar
    # Beam release). Do not backfill from MoveMeta — legal_actions treats None
    # as [None] in _move_targets.
    target: str | None = None
    disabled: bool = False


class ActiveSlot(BaseModel):
    moves: list[MoveSlot]
    can_terastallize: str | None = Field(default=None, alias="canTerastallize")
    can_mega_evo: bool = Field(
        default=False,
        alias="canMegaEvo",
        exclude_if=lambda value: value is False,
    )
    trapped: bool | None = None
    # The server sets `maybeTrapped` INSTEAD of `trapped` for the LAST active slot when the trap
    # comes from an ability: all three trapping abilities call `tryTrap(true)` -> `trapped='hidden'`
    # (sim/pokemon.ts:1613-1618, field typed `boolean | "hidden"` at :131), and the request
    # serializer restricts information for the last active (:1098) -- a non-last slot uses the loose
    # `if (this.trapped)` (:1124) while the last active uses the strict `if (this.trapped === true)`
    # (:1135-1138), which 'hidden' fails. So for an ability trap this means "actually trapped,
    # withheld", NOT "uncertain". Without this field pydantic silently DROPPED the key (no
    # extra="forbid"), the slot parsed to trapped=None, and _voluntary_switches offered switches for
    # a trapped Pokemon -- the illegal action behind the Gate B SAFETY-FAIL. See
    # docs/projects/champions/audits/2026-07-23-gate-b-trapped-switch-defect-diagnosis.md
    #
    # `exclude_if` (same device as can_mega_evo above, and required for the same reason): several
    # callers serialize this model with `model_dump(..., exclude_none=False)`
    # (eval/decision_capture.py, eval/room_raw_replay.py) and eval/decision_profile.py hashes the
    # dump. Without this predicate a bare `maybe_trapped=None` would be emitted on EVERY board and
    # silently change `fixture_input_hash` -- it did: the pinned C3-proof board moved
    # 3d246b21910204ec -> 1a15d8ded702c464 before this was added. Omitting the field when the server
    # did not send it keeps every non-maybeTrapped board byte-identical to before this slice, so the
    # behaviour change is confined to boards that actually carry the flag.
    maybe_trapped: bool | None = Field(
        default=None,
        alias="maybeTrapped",
        exclude_if=lambda value: value is None,
    )
    model_config = {"populate_by_name": True}


class PokemonSlot(BaseModel):
    ident: str
    details: str
    condition: str
    active: bool
    stats: dict[str, int] = Field(default_factory=dict)
    moves: list[str] = []
    base_types: list[str] = Field(default_factory=list, alias="baseTypes")
    item: str | None = None

    model_config = {"populate_by_name": True}


class SideInfo(BaseModel):
    name: str | None = None
    id: str | None = None
    pokemon: list[PokemonSlot] = []


class BattleRequest(BaseModel):
    # A doubles side with one Pokémon left serializes the empty slot as null,
    # e.g. "active": [ {...}, null ], so entries are Optional.
    active: list[ActiveSlot | None] = []
    side: SideInfo = Field(default_factory=SideInfo)
    rqid: int = 0
    force_switch: list[bool] | None = Field(default=None, alias="forceSwitch")
    team_preview: bool | None = Field(default=None, alias="teamPreview")
    max_team_size: int | None = Field(default=None, alias="maxTeamSize")
    wait: bool = False

    model_config = {"populate_by_name": True}
