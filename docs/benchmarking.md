# Benchmarking the HeuristicBot — what the mirror gauntlet does and doesn't tell us

> **The core lesson, up front:**
> **The local mirror-vs-`max_damage` gauntlet is a *bug detector*, not an
> optimization target.** It is excellent at surfacing catastrophic behaviour
> (0/16 = something is badly broken). It is *misleading* as a fine-tuning signal,
> because in a mirror against a relentless damage-maximizer it **rewards
> recklessness** — correct, cautious modeling can *lose* it.

## Why the benchmark misleads

`max_damage` in a mirror just clicks the hardest hit every turn. Against that, a
bot that models threats *correctly* and plays patiently loses the damage race;
a bot that is *over-confident* (under-rates incoming, over-rates its own KOs)
races ahead. So the metric pulls toward over-confidence, which is exactly wrong
against real, varied opponents who punish recklessness.

**Hard evidence from the June 2026 investigation:**

- A crude "model all our own mons as bulky" proxy (factually wrong) **beat**
  correct real team spreads in the mirror: proxy **11/24** vs real spreads
  **2/24**. The proxy "won" by accidental over-confidence, not by being right.
- Correct real spreads *regressed* the mirror winrate (more perceived threat →
  more Protect → loses the race), even though they are right for real play.
- Conversely, removing *false* threat legitimately (opponent likely-sets instead
  of worst-case-in-every-dimension) **did** move it (0/16 → 6/16) *and* improved
  every behavioural metric — because that over-estimation was a genuine error,
  not a safety margin.

So: "wins the benchmark" and "is correct" only coincide when the change removes a
genuine modeling error. They diverge whenever a change trades correctness for
over-confidence.

## How to use the benchmark properly

1. **As a catastrophe guardrail, not a target.** A run that craters to ~0 means a
   real bug or pathology — investigate. A run that holds is "no regression."
   Don't chase the absolute winrate.
2. **Read behavioural metrics, not just winrate.** At N=16 the winrate is very
   noisy (an "8/16" firmed to 9/30 ≈ 30%). The robust signals, read from the
   trace logs, are: `Protect%`, `endgame-Protect%`, `out/in` predicted damage,
   `must_react%`, `AHEAD%`, `targeted-move%`. These moved decisively and
   consistently when a real lever was found, well before winrate could confirm.
3. **Use self-play for a positional signal.** Heuristic-vs-heuristic is ~50% by
   symmetry (verified — a 3/14 dip was noise, the code is side-symmetric), so the
   winrate isn't the point; the *behaviour* against a competent (non-reckless)
   opponent is. Self-play is also the natural data source for the ML phases.
4. **Always A/B with a knob** (e.g. `SHOWDOWN_OPP_SETS`, `SHOWDOWN_PROTECT_PENALTY`)
   so on/off is bit-identical except the one change.

## Confirmed levers vs non-levers (mirror, vs `max_damage`)

| Change | Effect | Verdict |
|---|---|---|
| Protect stall/endgame/abandon penalty | 4→8/16, endgame-Protect 46%→17% | **big lever** |
| Opponent likely-sets (realistic damage spread) | 0→6/16, predicted-incoming −40%, AHEAD 0%→32% | **big lever** |
| Self-bulk modeling (real own spreads / proxy) | reduces false panic; proxy over-shoots | **lever (but see caveat above)** |
| Fake Out prune when `moved_since_switch` | removes a guaranteed wasted endgame turn | **correctness** (small winrate) |
| Own speed truth + opponent speed | endgame-Protect 20%→11%, AHEAD +9pts; winrate flat | **modest correctness** |
| MUST_REACT λ tuning | winrate noise, Protect% flat | **non-lever** |
| Opponent best-move by damage (Stage A) alone | 0/16 | **non-lever in isolation** |

Current state: ~30–37% vs `max_damage` with **principled correct models on both
sides** (real own spreads + speed truth + opponent likely-sets/speed), no visible
pathologies, full test suite green.

## The honest ceiling, and the next clean steps

Further hand-built heuristic slices (opponent moves, team-preview matchup) would
be *modest* like the speed slice — bulk+offense was the dominant false-threat
dimension and it's already addressed. The path **past ~37%** is structural:
learn the caution-vs-aggression balance from real outcomes rather than hand-tuning
an eval against a benchmark that rewards recklessness.

Start the next session with ONE of these clean paths — not "one more fix":

1. **Consolidate / review / merge the branch.** The current state is coherent
   (speed truth, real spreads, opponent realism, Protect/Fake-Out fixes, tests
   green) — a good review/merge candidate.
2. **Design the ML pivot** (`/brainstorming`): features, labels, self-play/replay
   data generation, policy/value learning. We now have an honest signal
   (self-play) and correct features as the foundation.
3. **Finalize the "brain document"**: decide which features from the now-correct
   models (own sets, opponent likely-sets, speed truth) feed the learner.
