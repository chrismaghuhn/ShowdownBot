"""Human-readable text diagnostics for the HeuristicBot (debuggable turns).

Pure formatters: each takes a data structure and returns text. They are wired
into the decision flow + runner so every turn can emit a readable block showing
what happened in the battle and why the bot chose what it did.
"""

from __future__ import annotations

from showdown_bot.battle.resolve import TurnOutcome
from showdown_bot.battle.rollout import RolloutResult


def _slot(key) -> str:
    return f"{key[0]}{key[1]}"


def format_outcome(outcome: TurnOutcome, our_side: str) -> str:
    """One-line summary of a chosen line's predicted turn-0 effect."""
    parts: list[str] = []
    if outcome.my_kos or outcome.my_faints:
        parts.append(f"KO {outcome.my_kos} / faint {outcome.my_faints}")
    dmg = [
        f"{_slot(key)}({'us' if key[0] == our_side else 'opp'}) {delta:+.2f}"
        for key, delta in outcome.hp_delta.items()
        if delta < -1e-9
    ]
    if dmg:
        parts.append("dmg: " + " ".join(dmg))
    if outcome.prevented_actions:
        parts.append("tempo: " + " ".join(f"{p.side}{p.slot}:{p.reason}" for p in outcome.prevented_actions))
    flags = sorted(f for f in outcome.flags if not f.startswith("protect:"))
    if flags:
        parts.append("flags: " + ",".join(flags))
    if outcome.tera_used_by_me:
        parts.append("tera:me")
    return "predicted: " + (" | ".join(parts) if parts else "(no effect)")


def format_rollout_trace(result: RolloutResult) -> str:
    """Readable rollout timeline: per-turn order, KOs, hp snapshot, score."""
    if not result.trace:
        return "rollout: 0 turns (no rollout)"
    lines = [f"rollout ({len(result.trace)} turns) value {result.value:+.2f}"]
    for t in result.trace:
        order = ",".join(_slot(k) for k in t.order) or "-"
        kos = ",".join(_slot(k) for k in t.kos) or "-"
        hp = " ".join(f"{name}={frac:.2f}" for name, frac in t.hp.items())
        lines.append(f"  T+{t.turn} order:{order} KO:{kos} hp:[{hp}] score:{t.score:+.2f}")
    return "\n".join(lines)
