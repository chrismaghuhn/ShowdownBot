"""Diagnostics v0 -- log-based tactical-failure detectors (2b-3.5 diagnostics Task 1).

Mines COMPLETED, already-normalized battle-log frames (the T4c ``room_dump.normalize_battle_log``
output -- a list of ``|``-delimited protocol lines) for a small, deterministic, fail-closed set of
recurring tactical mistakes. NO live-path hook, NO new battles -- this is post-hoc analysis over
logs already produced. Spec: ``docs/projects/evaluation/specs/2026-07-11-diagnostics-v0-design.md``.

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

# All v0 buckets, sorted -- the canonical iteration order for aggregate()/bucket_delta() so every
# bucket is ALWAYS present in their output (a bucket with zero events must show 0, never be
# silently missing -- same fail-closed ethos as the per-line try/except in the detectors).
_ALL_BUCKETS: tuple = tuple(sorted((_ATTACK_INTO_PROTECT, _IMMUNITY_PUNISHED, _PANIC_SWITCHING)))

# The not-a-gate invariant, embedded verbatim (per spec) in both bucket_delta()'s return value
# and format_diagnostics_md()'s output -- diagnostics are a signal for habit changes, NEVER a
# pass/fail gate. The strength gate stays paired McNemar/winrate (see eval/stats.py).
_NOT_A_GATE_NOTE = (
    "diagnostic signal only — NOT a gate; strength gate stays paired McNemar/winrate"
)


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


# --- aggregation ------------------------------------------------------------------------------

def _empty_bucket_stats() -> dict:
    return {"count": 0, "by_severity": {"info": 0, "warn": 0, "fail": 0}}


def aggregate(events) -> dict:
    """Aggregate a flat ``list[DiagnosticEvent]`` into per-bucket counts/severity breakdowns.

    Pure, deterministic: buckets are iterated in sorted order (``_ALL_BUCKETS``) so EVERY v0
    bucket appears in the output with a zero-filled entry even if no event of that bucket was
    observed -- a bucket that is absent from ``events`` must never be silently missing from the
    aggregate.

    Returns ``{bucket: {"count": int, "by_severity": {"info": int, "warn": int, "fail": int}},
    ..., "total": int, "n_battles": int}``.

    CAVEAT (documented, per controller notes): ``n_battles`` is the count of DISTINCT
    ``battle_id`` values seen among ``events`` -- NOT the true number of battles diagnosed. A
    battle that produced zero diagnostic events contributes no ``battle_id`` here and is
    invisible to this count. Callers who need the true battle total (and a parse-skipped tally)
    should use ``diagnose_run``, which layers ``battles_total``/``parse_skipped`` on top of this
    function's output.
    """
    stats: dict = {bucket: _empty_bucket_stats() for bucket in _ALL_BUCKETS}
    battle_ids: set = set()
    total = 0
    for event in events:
        total += 1
        battle_ids.add(event.battle_id)
        bucket_stats = stats.setdefault(event.bucket, _empty_bucket_stats())
        bucket_stats["count"] += 1
        bucket_stats["by_severity"][event.severity] = (
            bucket_stats["by_severity"].get(event.severity, 0) + 1
        )

    result: dict = {bucket: stats[bucket] for bucket in sorted(stats)}
    result["total"] = total
    result["n_battles"] = len(battle_ids)
    return result


def diagnose_run(battles) -> tuple:
    """Run ``diagnose_battle`` over an iterable of ``(battle_id, frames)`` pairs.

    Fail-closed: a battle whose ``frames`` cannot be diagnosed (any exception escaping
    ``diagnose_battle`` -- e.g. malformed/non-iterable frames) is SKIPPED, never crashes the
    run, and is tallied in the returned aggregate's ``parse_skipped`` count -- it is never
    silently dropped. ``battles_total`` (parsed + skipped) is also surfaced.

    Returns ``(all_events, run_aggregate)`` where ``all_events`` is the concatenation of every
    successfully-diagnosed battle's events (re-sorted by ``(battle_id, turn, side, bucket)`` for
    determinism regardless of input iteration order) and ``run_aggregate`` is
    ``aggregate(all_events)`` with ``"parse_skipped"`` and ``"battles_total"`` merged in.
    """
    all_events: list = []
    parse_skipped = 0
    battles_total = 0
    for battle_id, frames in battles:
        battles_total += 1
        try:
            events = diagnose_battle(frames, battle_id=battle_id)
        except Exception:  # noqa: BLE001 - fail-closed: skip, tally, never crash the run
            parse_skipped += 1
            continue
        all_events.extend(events)

    all_events.sort(key=lambda e: (e.battle_id, e.turn, e.side, e.bucket))
    run_aggregate = aggregate(all_events)
    run_aggregate["parse_skipped"] = parse_skipped
    run_aggregate["battles_total"] = battles_total
    return all_events, run_aggregate


# --- candidate-vs-baseline bucket delta --------------------------------------------------------

def bucket_delta(events_a, events_b, *, hero_side_a: str, hero_side_b: str) -> dict:
    """Per-bucket HERO-side event-count delta between two paired runs.

    ``events_a`` is the BASELINE agent's run, ``events_b`` is the CANDIDATE agent's run (same
    seeds/paired battles). Only events whose ``side`` matches the respective ``hero_side_*`` are
    counted -- the two runs may have the hero on different sides, though in the 2b-4 case both
    are ``p1``.

    SIGN CONVENTION (documented, load-bearing): ``delta = b_count - a_count`` (candidate minus
    baseline). ``delta < 0`` means the candidate has FEWER of that failure bucket than the
    baseline -> ``"candidate_improves"``. ``delta > 0`` means the candidate has MORE ->
    ``"candidate_regresses"``. ``delta == 0`` -> ``"flat"``.

    Every bucket in ``_ALL_BUCKETS`` is present in the output, even at 0/0/flat, so an absent
    bucket is never silently missing.

    Returns ``{"hero_side_a", "hero_side_b", "per_bucket": {bucket: {"a_count", "b_count",
    "delta"}}, "verdict_per_bucket": {bucket: verdict}, "note": <not-a-gate invariant>}``.
    """
    counts_a: dict = {bucket: 0 for bucket in _ALL_BUCKETS}
    counts_b: dict = {bucket: 0 for bucket in _ALL_BUCKETS}
    for event in events_a:
        if event.side == hero_side_a:
            counts_a[event.bucket] = counts_a.get(event.bucket, 0) + 1
    for event in events_b:
        if event.side == hero_side_b:
            counts_b[event.bucket] = counts_b.get(event.bucket, 0) + 1

    per_bucket: dict = {}
    verdict_per_bucket: dict = {}
    for bucket in sorted(set(counts_a) | set(counts_b) | set(_ALL_BUCKETS)):
        a_count = counts_a.get(bucket, 0)
        b_count = counts_b.get(bucket, 0)
        delta = b_count - a_count
        if delta < 0:
            verdict = "candidate_improves"
        elif delta > 0:
            verdict = "candidate_regresses"
        else:
            verdict = "flat"
        per_bucket[bucket] = {"a_count": a_count, "b_count": b_count, "delta": delta}
        verdict_per_bucket[bucket] = verdict

    return {
        "hero_side_a": hero_side_a,
        "hero_side_b": hero_side_b,
        "per_bucket": per_bucket,
        "verdict_per_bucket": verdict_per_bucket,
        "note": _NOT_A_GATE_NOTE,
    }


# --- markdown formatting -------------------------------------------------------------------------

def format_diagnostics_md(aggregate: dict, *, delta: dict | None = None) -> str:
    """Render a compact, deterministic markdown diagnostics section.

    Always includes: a bucket-count table (sorted buckets), the ``parse_skipped`` tally (0 if
    the given ``aggregate`` has none -- e.g. the plain ``aggregate()`` output rather than
    ``diagnose_run``'s), and the not-a-gate invariant note verbatim. If ``delta`` (a
    ``bucket_delta`` result) is given, also includes a candidate-vs-baseline delta table.
    Deterministic: buckets are always visited in sorted order.
    """
    lines: list = []
    lines.append("## Diagnostics v0")
    lines.append("")
    lines.append(
        f"Total events: {aggregate.get('total', 0)} across "
        f"{aggregate.get('n_battles', 0)} battle(s) with events."
    )
    battles_total = aggregate.get("battles_total")
    if battles_total is not None:
        lines.append(f"Battles diagnosed (parsed + skipped): {battles_total}.")
    lines.append(f"parse_skipped: {aggregate.get('parse_skipped', 0)}")
    lines.append("")
    lines.append("### Bucket counts")
    lines.append("")
    lines.append("| bucket | count | info | warn | fail |")
    lines.append("|---|---|---|---|---|")
    for bucket in sorted(_ALL_BUCKETS):
        bucket_stats = aggregate.get(bucket, _empty_bucket_stats())
        by_sev = bucket_stats.get("by_severity", {})
        lines.append(
            f"| {bucket} | {bucket_stats.get('count', 0)} | {by_sev.get('info', 0)} | "
            f"{by_sev.get('warn', 0)} | {by_sev.get('fail', 0)} |"
        )
    lines.append("")

    if delta is not None:
        lines.append("### Candidate vs baseline bucket delta")
        lines.append("")
        lines.append(
            f"hero_side_a (baseline) = {delta.get('hero_side_a')}, "
            f"hero_side_b (candidate) = {delta.get('hero_side_b')}. "
            "delta = b_count - a_count (negative = candidate improves)."
        )
        lines.append("")
        lines.append("| bucket | baseline (A) | candidate (B) | delta | verdict |")
        lines.append("|---|---|---|---|---|")
        per_bucket = delta.get("per_bucket", {})
        verdict_per_bucket = delta.get("verdict_per_bucket", {})
        for bucket in sorted(_ALL_BUCKETS):
            row = per_bucket.get(bucket, {"a_count": 0, "b_count": 0, "delta": 0})
            verdict = verdict_per_bucket.get(bucket, "flat")
            lines.append(
                f"| {bucket} | {row.get('a_count', 0)} | {row.get('b_count', 0)} | "
                f"{row.get('delta', 0)} | {verdict} |"
            )
        lines.append("")

    lines.append("### Not a gate")
    lines.append("")
    lines.append(_NOT_A_GATE_NOTE)
    lines.append("")
    return "\n".join(lines)
