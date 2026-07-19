# Diagnostics v0 — log-based tactical-failure detectors + candidate-vs-baseline bucket delta

**Status:** roadmap slice after 2b-4 (merged). From the banked Deep-Research doc
`TestBOtpläne/12-diagnostic-buckets.md`. First cut of the diagnostic layer: a small, fail-closed,
deterministic set of detectors that mine COMPLETED battle logs for recurring tactical mistakes,
plus a candidate-vs-baseline bucket-delta so paired evals report habit changes, not just winrate.

## Motivation (concrete, from 2b-4)

2b-4's paired eval returned NO-GO on winrate (override +13 net vs max_damage, p=0.105 n.s.). A
winrate gate cannot say WHETHER the override changed tactical habits — improved some, regressed
others. The bucket-delta answers exactly that on the SAME battles. This makes every future
candidate eval (a re-aimed reranker, later belief/search candidates) more informative than a
single win/loss number.

## Scope (v0 — deliberately small)

Input: normalized battle-log frames (the T4c `room_dump.normalize_battle_log` output — the same
canonical form the row↔log sha binds), optionally the result row for context. NO live-path hook,
NO new battles — this is post-hoc analysis over logs we already produce (and, later, over
VGC-Bench replays — a bridge to 2b-5a).

**Three detectors** (the most VGC-relevant + reliably log-detectable; the framework is
extensible for the rest of the doc's buckets later):

1. **PANIC_SWITCHING** — a side makes ≥K switches in a W-turn window with a repeated A→B→A
   oscillation and no faint/KO progress in between. Protocol: `|switch|` lines per side/slot,
   `|faint|` as the progress signal. Severity scales with oscillation count.
2. **ATTACK_INTO_PROTECT** (PROTECT_OR_STALL_UNDERMODELED, offense side) — an attacking move
   targets a slot that is Protected that turn. Protocol: `|move|<attacker>|<move>|<target>`
   followed by `|-activate|<target>|move: Protect` (or `|-block|`), with the move being a
   damaging move (not a self/ally/status target). One wasted attack = one event.
3. **IMMUNITY_PUNISHED** (IMMUNITY_PIVOT_PUNISHED, offense side) — an attacking move hits a
   target that is immune. Protocol: `|move|...|<target>` immediately followed by
   `|-immune|<target>` (type/ability immunity). One event per immune-negated attack.

Each detector is a PURE function `detect(frames) -> list[DiagnosticEvent]`, deterministic,
never raises (a malformed frame is skipped, counted in a `parse_skipped` tally surfaced in the
report — fail-closed, no silent swallow).

## Schema

```python
DiagnosticBucket = Literal["PANIC_SWITCHING", "ATTACK_INTO_PROTECT", "IMMUNITY_PUNISHED"]  # v0 subset

@dataclass(frozen=True)
class DiagnosticEvent:
    battle_id: str
    turn: int
    side: str          # "p1" | "p2"
    bucket: DiagnosticBucket
    severity: Literal["info", "warn", "fail"]
    action: str | None      # the move/switch involved
    target: str | None
    evidence: dict          # the raw protocol snippet + derived counts (deterministic, sorted keys)
```

## Aggregation + bucket delta

- `diagnose_battle(frames, battle_id) -> list[DiagnosticEvent]` runs all detectors for BOTH sides.
- `aggregate(events) -> {bucket -> {count, by_severity}, total, parse_skipped}`.
- `bucket_delta(events_a, events_b, *, hero_side)` — for a paired candidate-vs-baseline run
  (same seeds, hero_side is the agent under test): per bucket, the HERO-side event count in A vs
  B and the delta (B minus A). "Candidate improves" = fewer fail-events of that bucket;
  "regresses" = more. This is DIAGNOSTIC signal, explicitly NOT a gate (the gate stays
  McNemar/winrate — a doc-level invariant repeated in code comments).

## Non-goals

The remaining ~30 buckets (belief, damage-roll, recovery, joint-action — many need capabilities
we don't have: roll distributions, belief state). No feature-availability tagging (I1) — that
belongs to 2b-5a where it's consumed. No live emission into DecisionTrace. No gating on buckets.

## Testing strategy

Fixture-based, deterministic. Small hand-authored normalized-log fixtures for each detector
(positive + negative case), a bucket_delta test on fabricated event lists, and a parse-skipped
test with a malformed frame. The real application on the 2b-4 strength logs (local archive
`C:/tmp/kaggle25a/2b4/strength_v2/*/room_raw`) is a demonstration in the closeout report — the
per-bucket delta numbers are cited (logs stay local, like the MEMTRACE analysis; the repo test
suite is fixture-only + reproducible).
