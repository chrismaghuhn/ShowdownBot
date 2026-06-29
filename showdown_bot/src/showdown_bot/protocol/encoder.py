from __future__ import annotations

from showdown_bot.models.actions import SlotAction, SlotPair


def format_slot_action(action: SlotAction) -> str:
    if action.kind == "pass":
        return "pass"
    if action.kind == "switch":
        return f"switch {action.target_ident}"
    parts = ["move", str(action.move_index)]
    if action.target is not None:
        parts.append(str(action.target))
    if action.terastallize:
        parts.append("terastallize")
    return " ".join(parts)


def encode_choose(pair: SlotPair, rqid: int | None = None) -> str:
    body = f"{format_slot_action(pair.slot0)}, {format_slot_action(pair.slot1)}"
    return f"/choose {body}"
