# ShowdownBot

Competitive **Pokémon Showdown VGC Doubles** bot — custom protocol client, hybrid architecture (Preview → Belief → Policy → Search → Fusion).

## Status

- **Phase 0** — Showdown client, legal actions, random agent ✅
- **Phase 0.5** — Challstr auth, team preview, packed teams, multiline protocol, challenge/smoke CLI ✅
- **Phase 1** — Offline game engine: format config, log parser, `BattleState`, `@smogon/calc` bridge, set hypotheses / belief tracking, `validate-log` (>95% calc-match) ✅
- **Phase 2** — Heuristic doubles bot: speed primitive + `SpeedOracle`, one-ply tactical resolver (`resolve_turn`: Fake Out, redirection w/ powder immunity, spread moves, retargeting), memoized/batched `DamageOracle`, opponent response prediction with Protect priors, game-mode-aware policy aggregation, Tera overlay, hard-timeout fallback chain, `max_damage`/`random` baselines, and a local-server `gauntlet` harness ✅

Architecture: **Preview → Belief → Policy → Search → Fusion** (currently heuristic search; learned policy/fusion come in later phases).

## Quick start

```bash
cd showdown_bot
pip install -e ".[dev]"
python -m pytest -v
python -m showdown_bot.cli replay-fixture
```

### Auth + ladder (VGC)

```bash
cp .env.example .env
# SHOWDOWN_USERNAME=yourname  (guest: any alphanumeric name, no password)
# SHOWDOWN_PASSWORD=          (registered account only)
python -m showdown_bot.cli ladder -v
```

**Note:** VGC ladders on `sim3.psim.us` are often **closed** (`not ladderable`). Use challenge vs a friend:

```bash
python -m showdown_bot.cli challenge --opponent TheirUsername -v
```

### Smoke test (random doubles, no custom team)

```bash
python -m showdown_bot.cli smoke -v
```

Regenerate packed team after editing `teams/fixed_team.txt`:

```bash
pip install poke-env   # dev only
python tools/generate_packed_team.py
```

### Offline log validation (Phase 1)

```bash
python -m showdown_bot.cli validate-log <battle.log> --sets <sets.json>
```

### Local gauntlet (Phase 2)

Run the heuristic against a baseline on a local Showdown server (setup: `showdown_bot/tools/localserver/README.md`):

```bash
python -m showdown_bot.cli gauntlet --games 20 --villain max_damage --strict
```

`--strict` enforces exit criteria (winrate, p95 decision latency, zero crashes / invalid choices).

## Docs

- Design: [docs/superpowers/specs/2026-06-29-vgc-showdown-bot-design.md](docs/superpowers/specs/2026-06-29-vgc-showdown-bot-design.md)
- Plans: [docs/superpowers/plans/2026-06-29-vgc-showdown-bot-index.md](docs/superpowers/plans/2026-06-29-vgc-showdown-bot-index.md)

## License

Private hobby project.
