from __future__ import annotations

from dataclasses import dataclass, field

from showdown_bot.engine.belief.hypotheses import (
    SetHypothesis,
    SpreadBook,
    hypothesis_from_state,
)
from showdown_bot.engine.log_parser import LogEvent
from showdown_bot.engine.mega_reconcile import MegaReconcileReducer, ReducedLogEvent
from showdown_bot.engine.state import BattleState


@dataclass
class BeliefTracker:
    """Maintains worst-case set hypotheses as observations arrive.

    The tracker advances a :class:`BattleState` and, after each event,
    re-derives the affected mon's :class:`SetHypothesis` from the updated
    state. This automatically folds in:

    * revealed moves (``|move|``)        -> ``known_moves`` grows
    * item triggers (``|-enditem|``/``|-item|``) -> item fixed, candidates collapse
    * boosts / status                    -> reflected in the hypothesis

    Speed observations are recorded separately for Phase 2 speed-tier inference.
    """

    state: BattleState
    book: SpreadBook
    hypotheses: dict[str, dict[str, SetHypothesis]] = field(default_factory=dict)
    speed_observations: list[tuple[str, str]] = field(default_factory=list)
    _mega_reducer: MegaReconcileReducer = field(default_factory=MegaReconcileReducer)

    @classmethod
    def from_state(cls, state: BattleState, book: SpreadBook) -> "BeliefTracker":
        tracker = cls(state=state, book=book)
        for side in state.sides:
            tracker._resync_side(side)
        return tracker

    def _resync_side(self, side: str) -> None:
        slot_map = self.hypotheses.setdefault(side, {})
        for slot, mon in self.state.side(side).items():
            slot_map[slot] = hypothesis_from_state(mon, self.book)
        # Drop hypotheses for slots no longer present (e.g. after a switch reset).
        for slot in list(slot_map):
            if slot not in self.state.side(side):
                del slot_map[slot]

    def _resync_slot(self, side: str, slot: str) -> None:
        mon = self.state.active(side, slot)
        if mon is None:
            self.hypotheses.get(side, {}).pop(slot, None)
            return
        self.hypotheses.setdefault(side, {})[slot] = hypothesis_from_state(mon, self.book)

    def _apply_reduced(self, event: ReducedLogEvent) -> None:
        # Record move-order info before mutating state (Phase 2 speed inference).
        if isinstance(event, LogEvent) and event.type == "move" and event.pokemon is not None:
            self.speed_observations.append((event.pokemon.side, event.pokemon.slot))

        self.state.apply_event(event)

        pokemon = event.pokemon
        if pokemon is not None:
            self._resync_slot(pokemon.side, pokemon.slot)

    def update(self, event: LogEvent) -> None:
        # Never flushes: a pending detailschange may pair with a -mega that
        # arrives on a later update() call. feed() defines the batch
        # boundary and flushes at the end.
        for reduced in self._mega_reducer.feed(event):
            self._apply_reduced(reduced)

    def feed(self, events: list[LogEvent]) -> None:
        for event in events:
            self.update(event)
        for reduced in self._mega_reducer.flush_pending():
            self._apply_reduced(reduced)

    def hypotheses_for(self, side: str) -> dict[str, SetHypothesis]:
        return self.hypotheses.get(side, {})
