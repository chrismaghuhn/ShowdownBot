from __future__ import annotations

from dataclasses import dataclass

from showdown_bot.engine.log_parser import LogEvent, PokemonId


class MegaReconcileError(RuntimeError):
    """Raised when a ``-mega`` event cannot be paired with a pending detailschange."""


@dataclass(frozen=True)
class MegaReconcileEvent:
    pokemon: PokemonId
    mega_species_details: str
    base_species: str
    stone_display: str


ReducedLogEvent = LogEvent | MegaReconcileEvent


def _ident_key(pokemon: PokemonId | None) -> str | None:
    return None if pokemon is None else f"{pokemon.side}{pokemon.slot}"


class MegaReconcileReducer:
    def __init__(self) -> None:
        self.pending_detailschange: dict[str, LogEvent] = {}

    def feed(self, event: LogEvent) -> list[ReducedLogEvent]:
        key = _ident_key(event.pokemon)
        if event.type == "detailschange":
            emitted: list[ReducedLogEvent] = []
            previous = self.pending_detailschange.pop(key, None)
            if previous is not None:
                emitted.append(previous)
            self.pending_detailschange[key] = event
            return emitted
        if event.type == "mega":
            pending = self.pending_detailschange.pop(key, None)
            if pending is None:
                raise MegaReconcileError("mega_without_detailschange")
            return [MegaReconcileEvent(
                pokemon=event.pokemon,
                mega_species_details=pending.details or "",
                base_species=event.value or "",
                stone_display=event.details or "",
            )]
        emitted = []
        if key is not None:
            for pending_key in [k for k in self.pending_detailschange if k != key]:
                emitted.append(self.pending_detailschange.pop(pending_key))
        emitted.append(event)
        return emitted

    def flush_pending(self) -> list[ReducedLogEvent]:
        out = list(self.pending_detailschange.values())
        self.pending_detailschange.clear()
        return out


def reduce_log_events(
    events: list[LogEvent], reducer: MegaReconcileReducer | None = None
) -> list[ReducedLogEvent]:
    if reducer is None:
        reducer = MegaReconcileReducer()
    out: list[ReducedLogEvent] = []
    for event in events:
        out.extend(reducer.feed(event))
    out.extend(reducer.flush_pending())
    return out
