# ShowdownBot

Competitive **Pokémon Showdown VGC Doubles** bot — custom protocol client, hybrid architecture (Preview → Belief → Policy → Search → Fusion).

## Status

**Phase 0** (Showdown client + legal actions + random ladder agent) — implemented.

## Quick start

```bash
cd showdown_bot
pip install -e ".[dev]"
python -m pytest -v
python -m showdown_bot.cli replay-fixture
```

Ladder (requires Showdown account):

```bash
cp .env.example .env
# set SHOWDOWN_USERNAME
python -m showdown_bot.cli ladder -v
```

## Docs

- Design: [docs/superpowers/specs/2026-06-29-vgc-showdown-bot-design.md](docs/superpowers/specs/2026-06-29-vgc-showdown-bot-design.md)
- Plans: [docs/superpowers/plans/2026-06-29-vgc-showdown-bot-index.md](docs/superpowers/plans/2026-06-29-vgc-showdown-bot-index.md)

## License

Private hobby project.
