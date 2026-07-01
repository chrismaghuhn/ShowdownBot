# pokemon-showdown eval-harness patches

Local-server patches the eval harness (slice 2b-3.5) depends on. They live **here, versioned**,
so the patched server is never a silent, undocumented state of one machine's clone.

The `pokemon-showdown` server itself is intentionally kept **outside** this repo (at
`~/.cache/showdownbot/pokemon-showdown`). These `.patch` files are the reproducible bridge.

## `pokemon-showdown-seeded-battle.patch`

**What:** injects a deterministic per-battle sim PRNG seed into the challenge/search
battle-creation path (`Ladder.match` → `Rooms.createBattle`, `server/ladders.ts`).

**Why:** stock Showdown seeds every battle with a fresh random seed (proven in the T0 probe:
6 identical-config battles → 3/6 split). The eval harness needs reproducible battles for
seed-fixed paired comparison. Showdown already supports this end-to-end — `RoomBattleOptions.seed`
→ the sim's `>start {seed}` → `new PRNG(seed)` — the challenge caller just never set it. This
patch closes that one gap.

**How it behaves:**
- `SHOWDOWN_BATTLE_SEED` **set** (e.g. `sodium,00000000000000000000000000000000`) → every battle
  created via challenge/search uses that seed → bit-reproducible battle (given deterministic bots).
- `SHOWDOWN_BATTLE_SEED` **unset** → the `seed` field is omitted → the sim generates a fresh random
  seed. **Stock behavior, zero change.** The patch is inert unless the env var is present.

**Seed format:** a `PRNGSeed` string. Default/representative form is `sodium,<hex>` (the hex is
zero-padded to 64 chars). `gen5,<hex>` and the legacy numeric `a,b,c,d` gen-5 form also work.

**Base commit:** applies cleanly on upstream `f8ac140`
(`Update Champions Random Battle for 1.1.0 changes (#12119)`).

### Apply

```bash
cd ~/.cache/showdownbot/pokemon-showdown
git apply /path/to/ShowdownBot/tools/eval/patches/pokemon-showdown-seeded-battle.patch
node build           # recompile TS -> dist/ (pokemon-showdown runs from dist/)
```

`node pokemon-showdown start --no-security 8000` rebuilds automatically (unless `--skip-build`),
so a plain restart also picks the patch up.

### Verify

Empirical bit-stability proof (T1a): `reports/2026-07-01-2b35-T1a-seeded-bit-stability.md`.
