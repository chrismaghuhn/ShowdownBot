"""Side-agnostic battle-result parse from room_raw (T2).

Returns raw slot data — winner name, tie flag, turn count, the ``|player|`` name map, and
per-player HP sums — WITHOUT any hero/villain knowledge. The row assembler (T2 Task 3)
resolves sides explicitly from these. HP is best-effort: ``hp_by_slot=None`` on any
surprise, never a crash (``end_hp_diff`` then becomes null downstream).

Known limitation (documented, acceptable for a best-effort margin): ``hp_by_slot`` sums only
mons that **appeared** in the log. In bring-4 doubles an un-played reserve (brought but never
switched in) isn't counted, so a winner with an un-played reserve can read lower than its true
remaining HP. The ``winner`` field is the authoritative outcome; ``end_hp_diff`` is a
supplementary margin only.
"""
from __future__ import annotations

from showdown_bot.eval.room_dump import _iter_lines


def _hp_fraction(hp_field: str):
    """Parse a Showdown HP field ('202/202', '160/202', '0 fnt', '100/100 par', '20/100y') -> [0,1] or None."""
    s = hp_field.strip()
    if "fnt" in s:
        return 0.0
    tok = s.split(" ", 1)[0]  # drop a status suffix like 'par'/'brn'
    if "/" not in tok:
        return None
    cur_s, mx_s = tok.split("/", 1)
    # Champions payloads can append a single-letter max-HP flag without a space (e.g. 100y).
    cur_s = cur_s.rstrip("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
    mx_s = mx_s.rstrip("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
    try:
        cur, mx = float(cur_s), float(mx_s)
    except ValueError:
        return None
    return 0.0 if mx <= 0 else cur / mx


def _mon_key(ident: str):
    """'p1a: Incineroar' -> ('p1', 'Incineroar'); unique per side (species clause)."""
    if ": " not in ident:
        return None
    pos, name = ident.split(": ", 1)
    if len(pos) < 2 or pos[:2] not in ("p1", "p2"):
        return None
    return (pos[:2], name)


def _detect_end_reason(frames) -> str:
    """Best-effort battle end_reason from room_raw markers (T3f Task 5).

    Ordinary completed battles (a plain ``|win|`` / ``|tie``) are ``"normal"``. Showdown
    emits distinctive text just before the terminal ``|win|`` for the non-normal endings:
      - ``"crash"``   — a sim crash notice ("The battle crashed").
      - ``"timeout"`` — an inactivity loss ("<name> lost due to inactivity.").
      - ``"forfeit"`` — a forfeit ("<name> forfeited.").
    Matching is case-insensitive substring; priority crash > timeout > forfeit > normal so a
    root-cause crash isn't masked by the win/timeout frames it also produces. Never raises.
    """
    crash = timeout = forfeit = False
    for line in _iter_lines(frames):
        if line.startswith(">"):
            # Client->server/session lines (room-id header, and since the choose-dispatch
            # log, >choose diagnostic lines) -- never sim output, same classification
            # normalize_battle_log already applies.
            continue
        low = line.lower()
        if "crashed" in low:
            crash = True
        elif "inactivity" in low:   # "<name> lost due to inactivity."
            timeout = True
        elif "forfeited" in low:    # "<name> forfeited."
            forfeit = True
    if crash:
        return "crash"
    if timeout:
        return "timeout"
    if forfeit:
        return "forfeit"
    return "normal"


def parse_battle_result(frames) -> dict:
    turns = 0
    winner_name = None
    is_tie = False
    players: dict[str, str] = {}
    mon_hp: dict[tuple, float] = {}
    hp_ok = True
    try:
        for line in _iter_lines(frames):
            if not line.startswith("|"):
                continue
            parts = line.split("|")
            tag = parts[1] if len(parts) > 1 else ""
            if tag == "turn":
                turns += 1
            elif tag == "player" and len(parts) >= 4:
                slot, name = parts[2], parts[3]
                if slot in ("p1", "p2") and name:
                    players[slot] = name
            elif tag == "win":
                winner_name = parts[2] if len(parts) > 2 and parts[2] else None
            elif tag == "tie":
                is_tie = True
            elif tag in ("switch", "drag") and len(parts) >= 5:
                key, frac = _mon_key(parts[2]), _hp_fraction(parts[4])
                if key and frac is not None:
                    mon_hp[key] = frac
            elif tag in ("-damage", "-heal") and len(parts) >= 4:
                key, frac = _mon_key(parts[2]), _hp_fraction(parts[3])
                if key and frac is not None:
                    mon_hp[key] = frac
            elif tag == "faint" and len(parts) >= 3:
                key = _mon_key(parts[2])
                if key:
                    mon_hp[key] = 0.0
    except Exception:  # noqa: BLE001 - HP is best-effort; downstream sets end_hp_diff=null
        hp_ok = False

    if hp_ok and mon_hp:
        hp_by_slot = {"p1": 0.0, "p2": 0.0}
        for (player, _name), frac in mon_hp.items():
            hp_by_slot[player] += frac
    else:
        hp_by_slot = None

    return {
        "winner_name": winner_name,
        "is_tie": is_tie,
        "turns": turns,
        "players": players,
        "hp_by_slot": hp_by_slot,
        "end_reason": _detect_end_reason(frames),
    }
