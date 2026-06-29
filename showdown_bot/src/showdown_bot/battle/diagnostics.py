"""Human-readable text diagnostics for the HeuristicBot (debuggable turns).

Pure formatters: each takes a data structure and returns text. They are wired
into the decision flow + runner so every turn can emit a readable block showing
what happened in the battle and why the bot chose what it did.
"""

from __future__ import annotations

from showdown_bot.battle.resolve import TurnOutcome
from showdown_bot.battle.rollout import RolloutResult
from showdown_bot.engine.log_parser import HpStatus, LogEvent, PokemonId


def _slot(key) -> str:
    return f"{key[0]}{key[1]}"


def _name(pid: PokemonId | None) -> str:
    return pid.name if pid is not None else "?"


def _hp(hp: HpStatus | None) -> str:
    if hp is None:
        return "?"
    s = f"{hp.current}/{hp.maximum}" if hp.maximum else str(hp.current)
    if hp.status:
        s += f" {hp.status}"
    if hp.fainted:
        s += " (fnt)"
    return s


def _from(tags: list[str]) -> str:
    for tag in tags:
        if tag.startswith("[from]"):
            return f" ({tag[len('[from]'):].strip()})"
    return ""


def format_battle_events(events: list[LogEvent]) -> str:
    """Readable turn-by-turn transcript of the actual game from parsed log events."""
    lines: list[str] = []
    for e in events:
        t = e.type
        if t == "turn":
            lines.append(f"Turn {e.amount}")
        elif t == "move":
            tgt = f" -> {_name(e.target)}" if e.target else ""
            lines.append(f"  {_name(e.pokemon)} used {e.details}{tgt}")
        elif t == "switch":
            detail = f" ({e.details})" if e.details else ""
            lines.append(f"  {_name(e.pokemon)} switched in{detail}")
        elif t in ("damage", "sethp"):
            lines.append(f"  {_name(e.pokemon)} hurt{_from(e.tags)} -> {_hp(e.hp)}")
        elif t == "heal":
            lines.append(f"  {_name(e.pokemon)} healed{_from(e.tags)} -> {_hp(e.hp)}")
        elif t == "faint":
            lines.append(f"  {_name(e.pokemon)} fainted")
        elif t == "status":
            lines.append(f"  {_name(e.pokemon)} is now {e.value}{_from(e.tags)}")
        elif t == "curestatus":
            lines.append(f"  {_name(e.pokemon)} cured {e.value}")
        elif t == "boost" and e.amount is not None:
            lines.append(f"  {_name(e.pokemon)} {e.value} {e.amount:+d}")
        elif t == "weather":
            lines.append(f"  weather: {e.value or 'cleared'}")
        elif t in ("fieldstart", "fieldend"):
            lines.append(f"  field {e.value} {'started' if t == 'fieldstart' else 'ended'}")
        elif t in ("sidestart", "sideend"):
            lines.append(f"  {e.side} {e.value} {'up' if t == 'sidestart' else 'down'}")
        elif t in ("item", "enditem"):
            lines.append(f"  {_name(e.pokemon)} {'revealed' if t == 'item' else 'lost'} item {e.value}")
    return "\n".join(lines)


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


def format_decision(
    chosen: str, scored: list[tuple[str, float]], mode: str, max_alternatives: int = 3
) -> str:
    """Readable decision block: chosen action + score + top alternatives."""
    ranked = sorted(scored, key=lambda pair: pair[1], reverse=True)
    chosen_score = next((s for label, s in ranked if label == chosen), None)
    header = f"decision [mode={mode}]: chose {chosen}"
    if chosen_score is not None:
        header += f" {chosen_score:+.2f}"
    lines = [header]
    alts = [(label, s) for label, s in ranked if label != chosen][:max_alternatives]
    if alts:
        lines.append("  alternatives:")
        lines.extend(f"    {label}  {s:+.2f}" for label, s in alts)
    return "\n".join(lines)


def turn_report(battle_text: str, decision_text: str, rollout_text: str | None = None) -> str:
    """Combine the actual battle transcript and the bot's reasoning into one block."""
    parts = ["=== turn report ===", "[battle]", battle_text or "(no events)", "[decision]", decision_text]
    if rollout_text:
        parts.append(rollout_text)
    return "\n".join(parts)


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
