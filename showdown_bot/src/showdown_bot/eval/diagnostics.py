"""Diagnostics v0 -- log-based tactical-failure detectors (2b-3.5 diagnostics Task 1).

Mines COMPLETED, already-normalized battle-log frames (the T4c ``room_dump.normalize_battle_log``
output -- a list of ``|``-delimited protocol lines) for a small, deterministic, fail-closed set of
recurring tactical mistakes. NO live-path hook, NO new battles -- this is post-hoc analysis over
logs already produced. Spec: ``docs/superpowers/specs/2026-07-11-diagnostics-v0-design.md``.

v0 covers three buckets (the framework is extensible for the rest of the Deep-Research doc's
taxonomy, ``TestBOtpläne/12-diagnostic-buckets.md``, later):

  - ATTACK_INTO_PROTECT: an opponent-targeting move whose target Protected that same turn.
  - IMMUNITY_PUNISHED: an opponent-targeting move whose target was immune that same turn.
  - PANIC_SWITCHING: an A->B->A species oscillation on the same slot within a 3-turn window,
    with no faint on the switching side in that window.

Every detector is a PURE function, deterministic, and NEVER raises: a malformed line is skipped
(try/except per line), never crashes the whole detector or the battle's diagnosis.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from showdown_bot.eval.room_dump import _iter_lines

DiagnosticBucket = Literal["PANIC_SWITCHING", "ATTACK_INTO_PROTECT", "IMMUNITY_PUNISHED"]
Severity = Literal["info", "warn", "fail"]

_ATTACK_INTO_PROTECT: DiagnosticBucket = "ATTACK_INTO_PROTECT"
_IMMUNITY_PUNISHED: DiagnosticBucket = "IMMUNITY_PUNISHED"
_PANIC_SWITCHING: DiagnosticBucket = "PANIC_SWITCHING"

_SIDES = ("p1", "p2")
_PANIC_WINDOW_TURNS = 3


@dataclass(frozen=True)
class DiagnosticEvent:
    """One detected tactical-failure instance (spec schema, verbatim)."""

    battle_id: str
    turn: int
    side: str                  # "p1" | "p2" -- the side that made the mistake
    bucket: DiagnosticBucket
    severity: Severity
    action: str | None         # the move/switch involved
    target: str | None
    evidence: dict             # raw protocol snippet + derived counts; SORTED keys (determinism)


def _evidence(**kwargs) -> dict:
    """Build an evidence dict with keys inserted in sorted order (determinism, per spec)."""
    return {k: kwargs[k] for k in sorted(kwargs)}


# --- protocol-ident helpers (mirrors battle_parse._mon_key's split idiom) ------------------

def _slot_of(ident: str) -> str | None:
    """'p1a: Incineroar' -> 'p1a'. None for anything that isn't a well-formed slot ident
    (e.g. a side-level ident like 'p1: HeuristicBot3272' used by side-condition lines)."""
    if ": " not in ident:
        return None
    slot = ident.split(": ", 1)[0].strip()
    if len(slot) < 3 or slot[:2] not in _SIDES:
        return None
    return slot


def _side_of(ident: str) -> str | None:
    """'p1a: Incineroar' -> 'p1'. None if not a well-formed side-slot ident."""
    slot = _slot_of(ident)
    return slot[:2] if slot else None


def _species_of(ident: str) -> str | None:
    """'p1a: Incineroar' -> 'Incineroar'."""
    if ": " not in ident:
        return None
    species = ident.split(": ", 1)[1].strip()
    return species or None


# --- turn segmentation ----------------------------------------------------------------------

def _iter_turns(frames):
    """Yield ``(turn_number, lines)`` for each turn, using ``|turn|N`` markers.

    Turn 0 is the pre-first-turn lead/switch block (everything before the first ``|turn|``
    line). Lines from ``|turn|N`` up to (excluding) the next ``|turn|`` line are turn N's
    bucket -- this also captures a forced-switch response the server emits right after a faint,
    before the next turn marker (verified against the real fixture in
    ``data/eval/t4/rerun/room_raw``: a faint and its resulting forced switch land in the SAME
    turn bucket). A malformed ``|turn|`` line (non-integer arg) is tolerated: the turn counter
    just increments by one instead of raising. Deterministic (a single linear pass).
    """
    turn = 0
    current: list[str] = []
    for line in _iter_lines(frames):
        if not line.startswith("|"):
            continue
        parts = line.split("|")
        tag = parts[1] if len(parts) > 1 else ""
        if tag == "turn":
            yield turn, current
            current = []
            try:
                turn = int(parts[2])
            except (IndexError, ValueError):
                turn += 1
            continue
        current.append(line)
    yield turn, current


def _find_followup(lines: list, start: int, tgt_ident: str, tags: tuple):
    """Scan ``lines`` forward from ``start`` for the next line whose tag is in ``tags`` and
    whose ident (``parts[2]``) matches ``tgt_ident`` exactly, stopping at the next ``|move|``/
    ``|switch|`` action boundary (a new action means the search window for "did THIS move get
    blocked/immune" has closed). Returns the matched line's ``parts``, or ``None``.
    """
    for j in range(start, len(lines)):
        line = lines[j]
        if line.startswith("|move|") or line.startswith("|switch|"):
            return None
        parts = line.split("|")
        tag = parts[1] if len(parts) > 1 else ""
        if tag in tags and len(parts) > 2 and parts[2] == tgt_ident:
            return parts
    return None


# --- detectors --------------------------------------------------------------------------------

def detect_attack_into_protect(frames, *, battle_id: str) -> list:
    """ATTACK_INTO_PROTECT: an opponent-targeting move whose target Protected this turn.

    Signal: ``|move|<atk>|<mv>|<tgt>`` (attacker side != target side -- an opponent-targeting
    move) followed, before the next action, by ``|-activate|<tgt>|move: Protect...`` or
    ``|-block|<tgt>|...Protect...``. Severity "warn".

    APPROXIMATION (v0, documented per plan): v0 has no cheap access to the move dex here, so
    "damaging move" is approximated as "targets an OPPONENT slot" (attacker side != target
    side). A self/ally-targeting move (Protect cast on self, Tailwind cast on an ally) never
    matches since attacker side == target side there, so this can only over-fire on an
    opponent-targeting STATUS move (e.g. Taunt into a Protected target) being counted as a
    wasted "attack" -- accepted for v0; a real move-dex lookup is future work. A spread move's
    secondary targets (the ``[spread]`` tag) are not parsed; only the primary target
    (``parts[4]``) is checked.
    """
    events = []
    for turn, lines in _iter_turns(frames):
        for i, line in enumerate(lines):
            try:
                if not line.startswith("|move|"):
                    continue
                parts = line.split("|")
                if len(parts) < 5:
                    continue
                atk_ident, move_name, tgt_ident = parts[2], parts[3], parts[4]
                atk_side, tgt_side = _side_of(atk_ident), _side_of(tgt_ident)
                if not atk_side or not tgt_side or atk_side == tgt_side:
                    continue
                block = _find_followup(lines, i + 1, tgt_ident, ("-activate", "-block"))
                if block is None or len(block) < 4 or "protect" not in block[3].lower():
                    continue
                events.append(DiagnosticEvent(
                    battle_id=battle_id,
                    turn=turn,
                    side=atk_side,
                    bucket=_ATTACK_INTO_PROTECT,
                    severity="warn",
                    action=move_name,
                    target=tgt_ident,
                    evidence=_evidence(
                        attacker=atk_ident,
                        move=move_name,
                        target=tgt_ident,
                        block_line="|".join(block),
                    ),
                ))
            except Exception:  # noqa: BLE001 - malformed line, never crash the detector
                continue
    return events


def detect_immunity_punished(frames, *, battle_id: str) -> list:
    """IMMUNITY_PUNISHED: an opponent-targeting move whose target was immune this turn.

    Signal: ``|move|<atk>|<mv>|<tgt>`` (attacker side != target side) followed, before the
    next action, by ``|-immune|<tgt>...``. Severity "warn". Same v0 "damaging move"
    approximation as ``detect_attack_into_protect`` (see its docstring): no move-dex lookup,
    so an opponent-targeting status move that happened to hit an immune slot would also count
    -- accepted for v0. A supereffective (or any other non-immune) hit never matches since it
    has no ``-immune`` line.
    """
    events = []
    for turn, lines in _iter_turns(frames):
        for i, line in enumerate(lines):
            try:
                if not line.startswith("|move|"):
                    continue
                parts = line.split("|")
                if len(parts) < 5:
                    continue
                atk_ident, move_name, tgt_ident = parts[2], parts[3], parts[4]
                atk_side, tgt_side = _side_of(atk_ident), _side_of(tgt_ident)
                if not atk_side or not tgt_side or atk_side == tgt_side:
                    continue
                immune = _find_followup(lines, i + 1, tgt_ident, ("-immune",))
                if immune is None:
                    continue
                events.append(DiagnosticEvent(
                    battle_id=battle_id,
                    turn=turn,
                    side=atk_side,
                    bucket=_IMMUNITY_PUNISHED,
                    severity="warn",
                    action=move_name,
                    target=tgt_ident,
                    evidence=_evidence(
                        attacker=atk_ident,
                        move=move_name,
                        target=tgt_ident,
                        immune_line="|".join(immune),
                    ),
                ))
            except Exception:  # noqa: BLE001 - malformed line, never crash the detector
                continue
    return events


def detect_panic_switching(frames, *, battle_id: str) -> list:
    """PANIC_SWITCHING: an A->B->A species oscillation on the same slot within a 3-turn window.

    Per side/slot, collects ``|switch|<slot>: <species>`` events (turn, species). For each
    slot, a run of 3 consecutive switch events species[i], species[i+1], species[i+2] with
    species[i] == species[i+2] != species[i+1] and (turn[i+2] - turn[i]) <= 3 is an oscillation
    -- UNLESS a ``|faint|`` for that SIDE (any slot) occurred at a turn in
    ``[turn[i], turn[i+2]]`` (a same-side faint in that window means at least one of the
    transitions was a forced switch, not a voluntary panic-bounce). Severity "warn", one event
    per detected oscillation triple. ``turn`` is the RETURN switch's turn (turn[i+2] -- when
    the pattern becomes observable); ``side`` is the switching side; ``action`` is the slot;
    ``target`` is the species that panic-returned.
    """
    events = []
    switches: dict = {}          # slot -> [(turn, species), ...]
    faint_turns: dict = {"p1": [], "p2": []}

    for turn, lines in _iter_turns(frames):
        for line in lines:
            try:
                if line.startswith("|switch|"):
                    parts = line.split("|")
                    if len(parts) < 3:
                        continue
                    ident = parts[2]
                    slot, species = _slot_of(ident), _species_of(ident)
                    if not slot or not species:
                        continue
                    switches.setdefault(slot, []).append((turn, species))
                elif line.startswith("|faint|"):
                    parts = line.split("|")
                    if len(parts) < 3:
                        continue
                    side = _side_of(parts[2])
                    if side:
                        faint_turns[side].append(turn)
            except Exception:  # noqa: BLE001 - malformed line, never crash the detector
                continue

    for slot, seq in switches.items():
        side = slot[:2]
        for i in range(len(seq) - 2):
            t1, sp_a = seq[i]
            _t2, sp_b = seq[i + 1]
            t3, sp_a2 = seq[i + 2]
            if sp_a != sp_a2 or sp_a == sp_b:
                continue
            if t3 - t1 > _PANIC_WINDOW_TURNS:
                continue
            if any(t1 <= ft <= t3 for ft in faint_turns.get(side, [])):
                continue
            events.append(DiagnosticEvent(
                battle_id=battle_id,
                turn=t3,
                side=side,
                bucket=_PANIC_SWITCHING,
                severity="warn",
                action=slot,
                target=sp_a,
                evidence=_evidence(
                    slot=slot,
                    species_a=sp_a,
                    species_b=sp_b,
                    turns=[t1, _t2, t3],
                ),
            ))
    return events


def diagnose_battle(frames, *, battle_id: str) -> list:
    """Run all v0 detectors over ``frames`` and return events sorted by (turn, side, bucket)
    for determinism."""
    events = []
    events.extend(detect_attack_into_protect(frames, battle_id=battle_id))
    events.extend(detect_immunity_punished(frames, battle_id=battle_id))
    events.extend(detect_panic_switching(frames, battle_id=battle_id))
    return sorted(events, key=lambda e: (e.turn, e.side, e.bucket))
