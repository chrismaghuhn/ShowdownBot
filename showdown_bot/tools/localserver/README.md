# Local Showdown server (gauntlet)

The gauntlet runs two of our bots against each other on a local Pokémon Showdown
server so we can measure win rate / latency without touching the public ladder.

## One-time setup

```bash
git clone https://github.com/smogon/pokemon-showdown.git
cd pokemon-showdown
npm install
cp config/config-example.js config/config.js
```

## Run the server (no auth)

```bash
node pokemon-showdown start --no-security
```

`--no-security` disables the login server and rate limits, so our clients can
log in with just a name (empty assertion) and challenge each other freely.

The server listens on `ws://localhost:8000/showdown/websocket`.

## Run the gauntlet

From the `showdown_bot` project root, with the team configured:

```bash
python -m showdown_bot.cli gauntlet --games 50 --villain max_damage
```

This logs in two guest clients, has the heuristic bot challenge the baseline
`--villain` bot N times in the configured VGC format, and prints win rate,
decision-latency percentiles, and invalid/crash/timeout counts.
