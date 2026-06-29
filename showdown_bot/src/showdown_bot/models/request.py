from __future__ import annotations

from pydantic import BaseModel, Field


class MoveSlot(BaseModel):
    move: str
    id: str
    pp: int
    maxpp: int
    target: str
    disabled: bool = False


class ActiveSlot(BaseModel):
    moves: list[MoveSlot]
    can_terastallize: str | None = Field(default=None, alias="canTerastallize")
    trapped: bool | None = None

    model_config = {"populate_by_name": True}


class PokemonSlot(BaseModel):
    ident: str
    details: str
    condition: str
    active: bool
    stats: dict[str, int] = Field(default_factory=dict)
    moves: list[str] = []
    base_types: list[str] = Field(default_factory=list, alias="baseTypes")

    model_config = {"populate_by_name": True}


class SideInfo(BaseModel):
    name: str | None = None
    id: str | None = None
    pokemon: list[PokemonSlot] = []


class BattleRequest(BaseModel):
    active: list[ActiveSlot] = []
    side: SideInfo = Field(default_factory=SideInfo)
    rqid: int
    force_switch: list[bool] | None = Field(default=None, alias="forceSwitch")
    team_preview: bool | None = Field(default=None, alias="teamPreview")
    max_team_size: int | None = Field(default=None, alias="maxTeamSize")

    model_config = {"populate_by_name": True}
