# Diagnostics v0 — log-based tactical-failure detectors + a first candidate-vs-baseline delta

Date: 2026-07-11. Slice: `feat/slice-diagnostics-v0`. Spec/plan:
`docs/superpowers/specs/2026-07-11-diagnostics-v0-design.md`,
`docs/superpowers/plans/2026-07-11-diagnostics-v0.md`. Taxonomy source:
`TestBOtpläne/12-diagnostic-buckets.md` (banked Deep-Research doc).

## What this adds

`showdown_bot/src/showdown_bot/eval/diagnostics.py`: three pure, deterministic, fail-closed
detectors over normalized battle-log frames (the T4c `room_dump.normalize_battle_log` form), an
aggregator, and a **candidate-vs-baseline bucket delta**. The detectors mine COMPLETED logs — no
live-path hook, no battles. The bucket delta reports how a candidate's tactical HABITS differ
from a baseline's on the same battles, which a winrate/McNemar gate cannot express.

**Invariant (embedded in code + here): the bucket delta is diagnostic SIGNAL, not a gate. The
strength gate stays paired McNemar/winrate (T5).** A candidate is never accepted or rejected on
bucket counts.

### The three v0 detectors

- **ATTACK_INTO_PROTECT** — an opponent-targeting move whose target Protected that turn
  (`|-activate|…move: Protect` / `|-block|`). A wasted attack.
- **IMMUNITY_PUNISHED** — an opponent-targeting move immediately negated by `|-immune|` on the
  target. Attacked into a type/ability immunity.
- **PANIC_SWITCHING** — an A→B→A species oscillation on one slot within a 3-turn window with no
  faint on that side in between.

v0 approximation (documented in the detectors): with no move-dex at hand, "attacking move" =
"targets an opponent slot" (attacker side ≠ target side). This can over-count an
opponent-targeting *status* move; self/ally moves never match. The remaining ~30 buckets of the
taxonomy (belief, damage-roll, recovery, joint-action) need capabilities we don't yet have
(roll distributions, belief state) and are out of scope for v0.

## First application: 2b-4 dev-strength battles (heuristic vs reranker override)

Ran the detectors on the 2b-4 strength archive (150 seeds vs `max_damage`, hero = p1 both runs;
logs local, not committed — numbers cited here). This answers what the 2b-4 winrate NO-GO could
not: did the override change tactical habits?

**Hero-side (p1) bucket delta, candidate (override) minus baseline (heuristic):**

| bucket | baseline (heuristic) | candidate (override) | delta | verdict |
|---|---|---|---|---|
| IMMUNITY_PUNISHED | 12 | 6 | **−6** | candidate_improves |
| ATTACK_INTO_PROTECT | 0 | 0 | 0 | flat |
| PANIC_SWITCHING | 0 | 0 | 0 | flat |

**Reading:** the override roughly halved the "attacked into an immune target" mistake on the hero
side (12→6) — the reranker nudges toward better type/immunity awareness — while being flat on the
other two (the heuristic already avoids attacking into Protect and does not panic-switch). This
is a directional tactical signal, not a significance claim (12 vs 6 is small N); it is exactly
the kind of habit-level insight the winrate gate (NO-GO, p=0.105) cannot surface. It is
consistent with 2b-4's overall picture: a mild, real, but not-certified improvement.

**Detector validation on real data:** aggregated over BOTH sides, the override run shows 911
ATTACK_INTO_PROTECT and 273 IMMUNITY_PUNISHED events across 150 battles — nearly all on the p2
side, i.e. the `max_damage` villain. The known-reckless baseline attacks into Protects and
immunities constantly; the detectors catch it, which validates the logic on real logs (the hero
side commits almost none). `parse_skipped: 0` across all 300 battles.

## Limitations + next

- 3 buckets of a larger taxonomy; VGC-relevant cheap ones first.
- The 2b-4 application uses local logs (not committed, like the MEMTRACE analysis); the committed
  tests are fixture-based + reproducible (`tests/test_eval_diagnostics.py`, 28 tests).
- Natural extensions (later, as capabilities arrive): recovery-loop + PP buckets (need longer
  games), damage-roll buckets (need roll distributions), belief buckets (need the belief system).
  The `bucket_delta` becomes standard in future paired candidate evals (re-aimed reranker,
  belief/search candidates) so strength claims carry a habit-change breakdown alongside winrate.
