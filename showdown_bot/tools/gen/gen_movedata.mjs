// Build-time generator: @pkmn/dex -> config/moves/movedata.json + config/items/itemdata.json
//
// This is the canonical Pokemon-Showdown data mirror used for MOVE/ITEM SEMANTICS.
// @smogon/calc stays damage-only (see spec invariant I-1). The generated JSON is
// checked in, so the Python runtime needs no Node to look up move/item metadata.
//
// Usage:
//   node gen_movedata.mjs           # write the JSON files
//   node gen_movedata.mjs --check   # exit 1 if checked-in files are stale (CI/test)

import { Dex } from '@pkmn/dex';
import { createHash } from 'node:crypto';
import { writeFileSync, readFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const GEN = 9;
const FORMAT = 'gen9vgc2024regg';
const here = dirname(fileURLToPath(import.meta.url));
const configDir = resolve(here, '../../config');
const require = createRequire(import.meta.url);
const sourceVersion = require('@pkmn/dex/package.json').version;
const dex = Dex.forGen(GEN);

// resolve.py models Fake Out's flinch via `"flinch" in move.flags`. @pkmn/dex
// encodes flinch as a secondary effect, not a flag, so synthesize the flag to
// preserve the resolver's behavior (backward-compat contract, Phase A plan).
function hasFlinch(m) {
  const secs = m.secondaries ? m.secondaries : m.secondary ? [m.secondary] : [];
  return secs.some((s) => s && s.volatileStatus === 'flinch');
}

function moveRecord(m) {
  const flags = Object.keys(m.flags || {});
  if (hasFlinch(m)) flags.push('flinch');
  return {
    id: m.id,
    name: m.name,
    basePower: m.basePower,
    category: m.category,
    type: m.type,
    priority: m.priority,
    target: m.target,
    status: m.status ?? null,
    volatileStatus: m.volatileStatus ?? null,
    sideCondition: m.sideCondition ?? null,
    slotCondition: m.slotCondition ?? null,
    weather: m.weather ?? null,
    terrain: m.terrain ?? null,
    boosts: m.boosts ?? null,
    self: m.self ?? null,
    secondary: m.secondary ?? null,
    secondaries: m.secondaries ?? null,
    drain: m.drain ?? null,
    recoil: m.recoil ?? null,
    multihit: m.multihit ?? null,
    flags: [...new Set(flags)].sort(),
  };
}

function itemRecord(it) {
  return {
    id: it.id,
    name: it.name,
    isBerry: !!it.isBerry,
    isChoice: !!it.isChoice,
    boosts: it.boosts ?? null,
    naturalGift: it.naturalGift ?? null,
    fling: it.fling ?? null,
    shortDesc: it.shortDesc ?? it.desc ?? '',
  };
}

function pack(kind, records) {
  const data = Object.fromEntries(records.map((r) => [r.id, r]));
  const dataHash = createHash('sha256').update(JSON.stringify(data)).digest('hex').slice(0, 16);
  return { source_version: sourceVersion, generation: GEN, format: FORMAT, data_hash: dataHash, [kind]: data };
}

const moves = dex.moves.all().map(moveRecord).sort((a, b) => a.id.localeCompare(b.id));
const items = dex.items.all().map(itemRecord).sort((a, b) => a.id.localeCompare(b.id));

const targets = [
  ['moves/movedata.json', pack('moves', moves)],
  ['items/itemdata.json', pack('items', items)],
];

if (process.argv.includes('--check')) {
  let stale = false;
  for (const [rel, fresh] of targets) {
    const cur = JSON.parse(readFileSync(resolve(configDir, rel), 'utf8'));
    if (cur.data_hash !== fresh.data_hash) {
      console.error(`STALE: ${rel} (checked-in ${cur.data_hash} != fresh ${fresh.data_hash})`);
      stale = true;
    }
  }
  if (stale) process.exit(1);
  console.log('fresh');
  process.exit(0);
}

mkdirSync(resolve(configDir, 'moves'), { recursive: true });
mkdirSync(resolve(configDir, 'items'), { recursive: true });
for (const [rel, out] of targets) {
  writeFileSync(resolve(configDir, rel), JSON.stringify(out, null, 1) + '\n');
}
console.log(`wrote ${moves.length} moves, ${items.length} items`);
