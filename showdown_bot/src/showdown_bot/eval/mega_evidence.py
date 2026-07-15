"""Own-Mega smoke evidence gate (I7a-C P1.3).

The I7a-C safety smoke must not report ``I7a OWN-MEGA SAFETY PASS`` merely because a
Mega-capable candidate was *evaluated*: the review found that criterion lets the verdict
pass even when the bot never actually clicked Mega. ``derive_mega_evidence`` requires
observing a FULL own-Mega path in a battle's decision-trace rows:

1. a non-team-preview decision that actually chose the Mega overlay -- ``chosen_mega_slot``
   set AND the sent ``/choose`` string containing ``"mega"`` (trace-v3's own loader already
   enforces internal consistency between ``chosen_mega_slot``, ``normalized_action``, and the
   chosen candidate's ``mega_evolve`` flag -- see ``decision_capture._validate_v3_mega_overlay``
   -- so a validated row with ``chosen_mega_slot`` set already proves an evaluated, projectable
   Mega candidate was chosen);
2. at least one LATER non-team-preview decision for the same battle whose ``state_summary``
   shows the same slot's species differs from its pre-click species -- direct evidence that
   the bot rebuilt state from the reconciled post-Mega form and made a further decision from
   it (this substitutes for asserting raw ``detailschange``/``-mega`` protocol lines directly,
   since raw room logs are deliberately never committed as evidence).

Returns ``None`` when no such path exists in the given rows -- callers MUST treat this as
INCONCLUSIVE, never as PASS, and MUST NOT silently retry with other seeds to manufacture a
PASS. Raises ``MegaEvidenceError`` when a row's own fields contradict each other (e.g. a
mega click whose ``/choose`` string doesn't actually contain "mega", or a claimed post-Mega
decision whose species never changed) -- that is a real defect, not mere absence of evidence.
"""
from __future__ import annotations

from dataclasses import dataclass


class MegaEvidenceError(Exception):
    """A trace row's own fields are internally contradictory -- a real bug to fix, not
    something an INCONCLUSIVE verdict should paper over."""


@dataclass(frozen=True)
class MegaEvidence:
    battle_id: str
    mega_decision_index: int
    turn_number: int
    mega_slot: int
    chosen_candidate_key: str | None
    post_mega_decision_index: int
    post_mega_species: str


def _slot_key(mega_slot: int) -> str:
    return "a" if mega_slot == 0 else "b"


def _species(row: dict, our_side: str, slot_key: str) -> str | None:
    return (
        (row.get("state_summary") or {})
        .get("sides", {})
        .get(our_side, {})
        .get(slot_key, {})
        .get("species")
    )


def derive_mega_evidence(trace_rows: list[dict], *, our_side: str) -> MegaEvidence | None:
    mega_rows = sorted(
        (r for r in trace_rows if r.get("chosen_mega_slot") is not None),
        key=lambda r: r["decision_index"],
    )
    if not mega_rows:
        return None
    mega_row = mega_rows[0]
    mega_slot = mega_row["chosen_mega_slot"]

    if mega_row.get("decision_phase") == "team_preview":
        raise MegaEvidenceError(
            f"decision_index={mega_row['decision_index']}: chosen_mega_slot={mega_slot!r} "
            f"set on a team_preview decision row -- Mega cannot be chosen at team preview"
        )
    if "mega" not in (mega_row.get("actual_choose_string") or ""):
        raise MegaEvidenceError(
            f"decision_index={mega_row['decision_index']}: chosen_mega_slot={mega_slot!r} "
            f"but actual_choose_string {mega_row.get('actual_choose_string')!r} does not "
            f"contain 'mega' -- the /choose actually sent did not carry the overlay"
        )

    later = sorted(
        (
            r for r in trace_rows
            if r["battle_id"] == mega_row["battle_id"]
            and r["decision_index"] > mega_row["decision_index"]
            and r.get("decision_phase") != "team_preview"
        ),
        key=lambda r: r["decision_index"],
    )
    if not later:
        return None
    post = later[0]

    slot_key = _slot_key(mega_slot)
    pre_species = _species(mega_row, our_side, slot_key)
    post_species = _species(post, our_side, slot_key)
    if not post_species or post_species == pre_species:
        raise MegaEvidenceError(
            f"post-Mega decision_index={post['decision_index']}: state_summary species "
            f"{post_species!r} for side={our_side!r} slot={slot_key!r} does not differ from "
            f"the pre-click species {pre_species!r} -- no evidence the state was rebuilt "
            f"from the reconciled Mega form before this later decision"
        )

    return MegaEvidence(
        battle_id=mega_row["battle_id"],
        mega_decision_index=mega_row["decision_index"],
        turn_number=mega_row["turn_number"],
        mega_slot=mega_slot,
        chosen_candidate_key=mega_row.get("chosen_candidate_key"),
        post_mega_decision_index=post["decision_index"],
        post_mega_species=post_species,
    )
