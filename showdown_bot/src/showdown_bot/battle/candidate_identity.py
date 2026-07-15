"""Structural candidate identity for DecisionTrace / CandidateTrace."""

from __future__ import annotations

import json
from dataclasses import replace

from showdown_bot.battle.actions import JointAction
from showdown_bot.models.actions import SlotAction


class ChosenCandidateResolutionError(RuntimeError):
    """Fail-closed resolution failure for chosen candidate lookup."""


class TeraSlotDerivationError(ValueError):
    """Invalid pre/post Tera overlay transition."""


def _slot_payload(sa: SlotAction) -> dict:
    return {
        "kind": sa.kind,
        "move_index": sa.move_index,
        "target": sa.target,
        "target_ident": sa.target_ident,
        "terastallize": sa.terastallize,
    }


def joint_action_key(ja: JointAction) -> str:
    """Versioned, canonical JSON structural key over both slot actions.

    This is the v1 payload (no ``mega_evolve`` field) -- kept byte-for-byte
    unchanged, still used to validate historical v2 trace rows. New writes use
    ``joint_action_key_v2`` instead (see decision-trace-v3, I7a-B Task 1).
    """
    payload = {
        "version": 1,
        "slots": [_slot_payload(ja.slot0), _slot_payload(ja.slot1)],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _slot_payload_v2(sa: SlotAction) -> dict:
    return {**_slot_payload(sa), "mega_evolve": sa.mega_evolve}


def joint_action_key_v2(ja: JointAction) -> str:
    """Candidate key v2: adds ``mega_evolve`` to each slot payload (I7a-B Task 1).

    Used for all new candidate/chosen keys once trace-v3 is written; the
    JointAction/SlotAction identity itself is unchanged, only the serialized
    key schema gains the Mega overlay flag alongside Tera's.
    """
    payload = {
        "version": 2,
        "slots": [_slot_payload_v2(ja.slot0), _slot_payload_v2(ja.slot1)],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _base_joint_action(ja: JointAction) -> JointAction:
    return JointAction(
        slot0=replace(ja.slot0, terastallize=False),
        slot1=replace(ja.slot1, terastallize=False),
    )


def derive_tera_slot(pre: JointAction, post: JointAction) -> int | None:
    """Derive overlay slot from pre/post actions. Fail-closed on invalid transitions."""
    pre_base = _base_joint_action(pre)
    post_base = _base_joint_action(post)
    if pre_base == post_base and pre == post:
        return None

    if pre_base != post_base:
        raise TeraSlotDerivationError("structural fields changed between pre and post Tera actions")

    changed_slots: list[int] = []
    for idx, (before, after) in enumerate(((pre.slot0, post.slot0), (pre.slot1, post.slot1))):
        if before == after:
            continue
        if before.kind != "move" or after.kind != "move":
            raise TeraSlotDerivationError("Tera overlay only allowed on move slots")
        if before.terastallize is not False or after.terastallize is not True:
            raise TeraSlotDerivationError("invalid terastallize transition")
        if (
            before.move_index != after.move_index
            or before.target != after.target
            or before.target_ident != after.target_ident
        ):
            raise TeraSlotDerivationError("non-tera slot fields changed")
        changed_slots.append(idx)

    if len(changed_slots) != 1:
        raise TeraSlotDerivationError("expected exactly one Tera slot to change")
    return changed_slots[0]


def candidate_identity(candidate) -> str:
    """Structural identity when available, otherwise legacy candidate_id label."""
    key = getattr(candidate, "candidate_key", None)
    if key:
        return key
    return candidate.candidate_id


def assert_unique_candidate_identities(candidates) -> None:
    """Fail-closed before dict construction when identities collide."""
    seen: dict[str, object] = {}
    for cand in candidates:
        ident = candidate_identity(cand)
        if ident in seen:
            raise ChosenCandidateResolutionError(
                f"ambiguous candidate identity={ident!r} matches multiple candidates"
            )
        seen[ident] = cand


def _strip_tera_suffix(candidate_id: str) -> str:
    return candidate_id.replace(" tera", "")


def resolve_chosen_candidate(trace) -> "CandidateTrace":
    """Resolve the chosen CandidateTrace. Fail-closed; never first-match on collision."""
    from showdown_bot.battle.decision_trace import CandidateTrace

    if trace.chosen_candidate_key:
        matches = [
            c for c in trace.candidates if getattr(c, "candidate_key", None) == trace.chosen_candidate_key
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ChosenCandidateResolutionError(
                f"ambiguous chosen_candidate_key={trace.chosen_candidate_key!r} matches "
                f"{len(matches)} candidates"
            )
        raise ChosenCandidateResolutionError(
            f"no candidate matches chosen_candidate_key={trace.chosen_candidate_key!r}"
        )

    chosen_id = trace.chosen_candidate_id
    if not chosen_id:
        raise ChosenCandidateResolutionError("chosen_candidate_id is missing on legacy trace")

    exact = [c for c in trace.candidates if c.candidate_id == chosen_id]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ChosenCandidateResolutionError(
            f"ambiguous chosen_candidate_id={chosen_id!r} matches {len(exact)} candidates"
        )

    stripped_target = _strip_tera_suffix(chosen_id)
    fallback = [c for c in trace.candidates if _strip_tera_suffix(c.candidate_id) == stripped_target]
    if len(fallback) == 1:
        return fallback[0]
    raise ChosenCandidateResolutionError(
        f"no candidate matches chosen_candidate_id={chosen_id!r} "
        f"(exact or tera-stripped); found {len(fallback)} stripped matches"
    )
