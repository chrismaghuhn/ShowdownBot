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
   shows the same slot's species matches the EXACT Mega form ``mega_form_for`` derives from
   the pre-click species and stone item (``engine/mega_form.py`` -- the same base-species+item
   mapping ``mega_projection.py`` uses) -- not merely ANY different species, which a later
   switch could produce too. This substitutes for asserting raw ``detailschange``/``-mega``
   protocol lines directly, since raw room logs are deliberately never committed as evidence;
   see ``bind_protocol_mega_pair`` below for binding to the actual protocol pair when a raw
   log is available at run time.

Returns ``None`` when no such path exists in the given rows -- callers MUST treat this as
INCONCLUSIVE, never as PASS, and MUST NOT silently retry with other seeds to manufacture a
PASS. This includes the legitimate case where the Mega'd mon later switches out or faints
before the exact Mega form is ever observed again in a later decision -- that is normal play,
not a defect, so it is INCONCLUSIVE too (the search scans every later decision, not just the
next one, in case the mon later switches back in). Raises ``MegaEvidenceError`` only for
internal contradictions that are real defects regardless of how the battle played out: a
mega click whose ``/choose`` string doesn't actually contain "mega", a click on a
team-preview row, or a pre-click species/stone item that can't be resolved to any known
Mega mapping at all.
"""
from __future__ import annotations

import hashlib
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


@dataclass(frozen=True)
class ProtocolMegaBinding:
    """A compact, hash-bound reference to the actual ``detailschange``/``-mega`` protocol
    line pair -- NOT the raw log itself. Proves the derived trace-level MegaEvidence
    corresponds to real observed protocol events, without committing full raw room logs."""
    detailschange_line_sha256: str
    mega_line_sha256: str
    normalized_log_sha256: str


def bind_protocol_mega_pair(
    normalized_log_text: str, *, actor_ident: str, mega_species_details: str,
    base_species: str, stone_display: str, expected_normalized_log_sha256: str,
) -> ProtocolMegaBinding:
    """Locate the ``detailschange``/``-mega`` line pair for ``actor_ident`` matching the
    given post-Mega species details, base species, and stone in ``normalized_log_text``,
    and return a compact hash-bound reference to those two lines plus the whole log.

    ``expected_normalized_log_sha256`` must be the battle's result row's
    ``normalized_room_log_sha256`` -- the function refuses to bind evidence to a log that
    doesn't match it (Codex re-review: without this check, evidence could silently bind
    to the wrong or a tampered log).

    Fails closed (``MegaEvidenceError``, nothing returned) if:
    - the log doesn't hash to ``expected_normalized_log_sha256``;
    - no line pair matches exactly (wrong stone, wrong actor, missing lines);
    - more than one line matches either role (ambiguous pairing -- refuses to guess which
      pair is the real one);
    - the matching ``-mega`` line does not come strictly AFTER its ``detailschange`` line
      (Codex re-review: the two were previously matched independently, so a reversed
      ``-mega`` / ``detailschange`` order was wrongly accepted as a valid pair)."""
    actual_log_hash = hashlib.sha256(normalized_log_text.encode("utf-8")).hexdigest()
    if actual_log_hash != expected_normalized_log_sha256:
        raise MegaEvidenceError(
            f"normalized log hash mismatch: expected {expected_normalized_log_sha256!r} "
            f"(the battle's recorded normalized_room_log_sha256), got {actual_log_hash!r} "
            f"-- refusing to bind evidence to a log that isn't the one this battle recorded"
        )

    detailschange_matches: list[tuple[int, str]] = []
    mega_matches: list[tuple[int, str]] = []
    for i, line in enumerate(normalized_log_text.splitlines()):
        parts = line.split("|")
        if len(parts) < 4:
            continue
        # "|detailschange|ACTOR|SPECIES_DETAILS" / "|-mega|ACTOR|BASE_SPECIES|STONE"
        _, kind, actor, *rest = parts
        if kind == "detailschange" and actor == actor_ident and rest[0] == mega_species_details:
            detailschange_matches.append((i, line))
        elif (
            kind == "-mega" and actor == actor_ident and len(rest) >= 2
            and rest[0] == base_species and rest[1] == stone_display
        ):
            mega_matches.append((i, line))

    if len(detailschange_matches) > 1 or len(mega_matches) > 1:
        raise MegaEvidenceError(
            f"ambiguous protocol pairing for actor={actor_ident!r}: found "
            f"{len(detailschange_matches)} matching detailschange line(s) and "
            f"{len(mega_matches)} matching -mega line(s) -- expected exactly one of each, "
            f"refusing to guess which pair is the real one"
        )
    if not detailschange_matches or not mega_matches:
        raise MegaEvidenceError(
            f"no matching detailschange/-mega protocol pair found for actor={actor_ident!r} "
            f"mega_species_details={mega_species_details!r} base_species={base_species!r} "
            f"stone={stone_display!r}"
        )

    (dc_index, detailschange_line) = detailschange_matches[0]
    (mega_index, mega_line) = mega_matches[0]
    if dc_index >= mega_index:
        raise MegaEvidenceError(
            f"protocol pair out of order for actor={actor_ident!r}: detailschange at line "
            f"{dc_index} must come strictly before -mega at line {mega_index}"
        )

    return ProtocolMegaBinding(
        detailschange_line_sha256=hashlib.sha256(detailschange_line.encode("utf-8")).hexdigest(),
        mega_line_sha256=hashlib.sha256(mega_line.encode("utf-8")).hexdigest(),
        normalized_log_sha256=actual_log_hash,
    )


def _slot_key(mega_slot: int) -> str:
    return "a" if mega_slot == 0 else "b"


def _mon_field(row: dict, our_side: str, slot_key: str, field: str):
    return (
        (row.get("state_summary") or {})
        .get("sides", {})
        .get(our_side, {})
        .get(slot_key, {})
        .get(field)
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

    slot_key = _slot_key(mega_slot)
    pre_species = _mon_field(mega_row, our_side, slot_key, "species")
    pre_item_known = _mon_field(mega_row, our_side, slot_key, "item_known")
    pre_item = _mon_field(mega_row, our_side, slot_key, "item") if pre_item_known else None
    if not pre_species or not pre_item:
        raise MegaEvidenceError(
            f"decision_index={mega_row['decision_index']}: cannot verify the claimed Mega "
            f"click without a known pre-click species/stone item for side={our_side!r} "
            f"slot={slot_key!r} (species={pre_species!r} item={pre_item!r} "
            f"item_known={pre_item_known!r})"
        )

    from showdown_bot.engine.mega_form import mega_form_for

    expected_form = mega_form_for(pre_species, pre_item)
    if expected_form is None:
        raise MegaEvidenceError(
            f"decision_index={mega_row['decision_index']}: no known Mega mapping for "
            f"pre-click species={pre_species!r} item={pre_item!r} -- cannot verify the "
            f"claimed click"
        )

    # Search ALL later decisions (not just the immediate next one) for the first row whose
    # slot shows the exact expected Mega form. A legitimate intervening switch/faint means
    # some later rows won't show it -- that alone is not a defect (Codex re-review:
    # semantics), so absence of a match anywhere is INCONCLUSIVE (None), never an error.
    for row in later:
        post_species = _mon_field(row, our_side, slot_key, "species")
        if post_species == expected_form.form_species_name:
            return MegaEvidence(
                battle_id=mega_row["battle_id"],
                mega_decision_index=mega_row["decision_index"],
                turn_number=mega_row["turn_number"],
                mega_slot=mega_slot,
                chosen_candidate_key=mega_row.get("chosen_candidate_key"),
                post_mega_decision_index=row["decision_index"],
                post_mega_species=post_species,
            )
    return None
