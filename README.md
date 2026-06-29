# ShowdownBot

Competitive **Pokémon Showdown VGC Doubles** bot — custom protocol client, hybrid architecture (Preview → Belief → Policy → Search → Fusion).

## Status

**Phase 0** — Showdown client, legal actions, random agent  
**Phase 0.5** — Challstr auth, team preview, packed teams, multiline protocol, challenge/smoke CLI

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

## Docs

- Design: [docs/superpowers/specs/2026-06-29-vgc-showdown-bot-design.md](docs/superpowers/specs/2026-06-29-vgc-showdown-bot-design.md)
- Plans: [docs/superpowers/plans/2026-06-29-vgc-showdown-bot-index.md](docs/superpowers/plans/2026-06-29-vgc-showdown-bot-index.md)

## License

Private hobby project.
