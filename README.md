# ShowdownBot

ShowdownBot is a research-oriented **Pokémon Showdown VGC Doubles bot**. It combines a custom
Showdown protocol client, a mechanics-aware battle state, a pinned `@smogon/calc` bridge,
heuristic and search-based decision making, optional learned reranking, and a provenance-heavy
evaluation harness.

The project is deliberately conservative about claims: a green safety smoke is not a strength
result, held-out data is not used for tuning, and unsupported mechanics fail closed instead of
quietly falling back to an optimistic approximation.

## Current status

The authoritative status is maintained in [docs/ROADMAP.md](docs/ROADMAP.md). New contributors
should start with [docs/PROJECT_INDEX.md](docs/PROJECT_INDEX.md).

As of **2026-07-16**:

| Area | Status |
|---|---|
| Protocol client, authentication, teams and CLI | Built |
| Battle state, parser, calc bridge and belief/spread infrastructure | Built |
| Heuristic VGC Doubles policy, game modes, Tera and fail-safe fallbacks | Built |
| Seeded evaluation harness, decision traces, reports and held-out gates | Built |
| Learned reranker infrastructure | Built; live override remains a strength NO-GO |
| Champions format: gen-0 speed and live damage | Safety-validated |
| Champions own Mega (`I7a`) | Merged; safety pass, no strength claim |
| Champions opponent Mega (`I7b-A` / `I7b-B`) | Merged; limited-view hypotheses and dual-Mega scoring are live for Mega-enabled formats |
| Champions telemetry/smoke (`I7b-C`) | Safety pass with **narrow exposure**: only 1 of 17 scored decisions exposed an opponent-Mega hypothesis, slot 1 only. No strength claim, no latency claim |
| Champions strength | **NO-GO** until a dedicated latency gate passes |
| ShowdownBot Studio | Product and bundle-contract design approved; exporter planning is separate from the bot runtime |

That provenance issue is now fixed. Several configuration identities were historically computed
from raw text-file bytes whose CRLF/LF representation depended on the checkout platform, so the
same configuration hashed differently on Windows than on Linux. Every raw-byte-hashed provenance
input is now pinned to LF, and **CI proves the platform independence rather than asserting it**:
a dedicated job runs on both Windows and Linux and requires them to compute the identical
configuration hash. A single-platform job could not catch this class of defect at all — it only
ever showed up as a disagreement *between* hosts.

Evidence recorded before that fix is kept, not rewritten: the rows record what the run that
actually happened computed, so re-hashing them would falsify it. Such runs are archived under a
`superseded-*` path and are explicitly marked as carrying a platform-specific configuration
identity, which must not be compared against or joined with any later run. The I7b-C smoke was
re-recorded from the identical schedule and seed base under the platform-stable hash.

## What is in the bot?

The decision stack is organized around:

```text
Preview → Observable state → Belief/priors → Candidate generation
        → Tactical evaluation/search → Policy fusion → Legal Showdown choice
```

Important components include:

- a Showdown WebSocket client and protocol/request models;
- an immutable/copy-on-project battle state for counterfactual evaluation;
- format-specific mechanics through `FormatConfig` and `CalcProfile`;
- speed, damage, KO, survival, Protect and opponent-response models;
- structural candidate identities and `decision-trace-v3` diagnostics;
- own-Mega and limited-view opponent-Mega projection for Champions;
- seeded schedules, frozen panels, result JSONL, sidecars and gate reports;
- offline dataset auditing, rollout-teacher tooling and an optional LightGBM reranker.

The heuristic policy remains the legality and safety floor. Learned components may rerank
candidates, but they do not bypass legality checks or fabricate unsupported battle mechanics.

## Reproducible evaluation

The local evaluation harness is designed to make bot-vs-bot experiments reviewable and
repeatable:

1. A pinned Pokémon Showdown checkout is patched with a versioned deterministic seed hook.
2. Schedules, panels and team inputs are frozen and content-hashed.
3. Runs record Git state, configuration identity, server provenance, seeds and result rows.
4. Optional decision and research sidecars expose how a choice was reached.
5. Safety gates run before any strength interpretation.
6. Paired comparisons use fixed schedules and seeds; battle-level retries and seed shopping are
   forbidden.

Representative evidence:

- [seeded byte-stability rerun](reports/2026-07-10-2b35-T4-rerun.md)
- [Champions I6 live-damage gen-0 smoke](reports/champions-panel-v0-i6-smoke.md)
- [Champions I7a own-Mega smoke](reports/champions-panel-v0-i7a-mega-smoke.md)
- [Pokémon Showdown protocol differential audit](reports/champions-pkmn-protocol-differential-audit.md)

The current LF/configuration-provenance repair is intentionally called out above: the harness has
caught a real cross-platform identity defect, and the affected claim stays blocked until the root
cause and evidence are corrected.

## Quick start

Requirements:

- Python supported by the project environment;
- Node.js for the pinned calc bridge and generated-data checks;
- a local Pokémon Showdown checkout only for live/gauntlet runs.

```bash
cd showdown_bot
python -m pip install -e ".[dev]"
npm ci --prefix tools/calc
npm ci --prefix tools/gen
python -m pytest -q
python -m showdown_bot.cli replay-fixture
```

`node_modules/` is intentionally not committed. Fresh worktrees need the relevant `npm ci`
commands before calc- or generator-backed tests can be trusted.

### Local gauntlet

Set up the pinned local server using
[showdown_bot/tools/localserver/README.md](showdown_bot/tools/localserver/README.md). A basic run:

```bash
cd showdown_bot
python -m showdown_bot.cli gauntlet --games 20 --villain max_damage --strict
```

Schedule-driven evaluation requires a fresh correctly patched server plus explicit seed and output
paths. Treat the committed schedules and the commands recorded in their verdict reports as the
reproduction contract; do not substitute a different seed after seeing a result.

### Ladder or challenge

```bash
cd showdown_bot
cp .env.example .env
python -m showdown_bot.cli ladder -v
python -m showdown_bot.cli challenge --opponent TheirUsername -v
```

Configure `SHOWDOWN_USERNAME` and `SHOWDOWN_PASSWORD` in `.env`. Never commit credentials.

## ShowdownBot Studio

[`showdownbot_studio/`](showdownbot_studio/) is a separate desktop-tool track for replay and
decision-trace inspection. Its initial target is a deterministic Python viewer bundle followed by
a Godot desktop viewer. It does not run the bot, recompute decisions or alter battle evidence.

Start with:

- [Studio master spec](showdownbot_studio/docs/MASTER_SPEC.md)
- [Viewer v0 design](showdownbot_studio/docs/specs/viewer-v0-design.md)
- [Approved bundle contract](showdownbot_studio/docs/specs/viewer-v0-bundle-contract-design.md)

## Repository map

| Path | Purpose |
|---|---|
| `showdown_bot/src/showdown_bot/battle/` | Live decision core, evaluation, opponent modeling and search |
| `showdown_bot/src/showdown_bot/engine/` | Battle state, calc bridge, metadata and belief infrastructure |
| `showdown_bot/src/showdown_bot/eval/` | Results, traces, schedules, manifests, reports and statistical gates |
| `showdown_bot/src/showdown_bot/learning/` | Dataset, teacher, audit, reranker and outcome tooling |
| `showdown_bot/tests/` | Unit, regression, replay, Champions and provenance tests |
| `config/eval/` | Frozen panels, schedules, baselines and held-out controls |
| `data/eval/` | Committed evaluation evidence |
| `reports/` | Audits, safety verdicts and experiment reports |
| `docs/superpowers/` | Approved designs and implementation plans |
| `showdownbot_studio/` | Separate replay/decision-trace desktop-tool project |

## Engineering rules

- Legal actions and fail-closed behavior take priority over estimated strength.
- No hidden opponent team data may enter limited-view decision paths.
- No model label or battle outcome may leak into live features.
- Configuration, model and generated-data identities are verified before use.
- Held-out results are not development feedback.
- A safety pass is not a strength pass.
- No battle retries or seed selection are allowed in frozen evaluations.
- Local logs, credentials and raw room dumps are not committed as public evidence.

## Documentation

- [Project index](docs/PROJECT_INDEX.md)
- [Canonical roadmap](docs/ROADMAP.md)
- [Pokémon Showdown protocol differential audit](reports/champions-pkmn-protocol-differential-audit.md)
- [poke-env reference audit](reports/champions-poke-env-reference-audit.md)

## License and affiliation

Private hobby/research project. This project is not affiliated with Nintendo, Game Freak, The
Pokémon Company, Smogon or Pokémon Showdown. Third-party code and data remain subject to their
respective licenses and provenance requirements.
