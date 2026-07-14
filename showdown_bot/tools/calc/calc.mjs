// Node bridge to @smogon/calc.
//
// Protocol: reads JSON from stdin (either a single request object or an array
// of them) and writes a JSON array of results to stdout, preserving each
// request's `id`. @smogon/calc derives mechanics from the Generation object +
// Field (gameType), NOT from any Showdown "format" string.
//
// Request shape:
//   { id, attacker: {species, level, item, nature, evs, ivs, ability, boosts,
//                    status, teraType, move}, defender: {...}, move,
//     field: {gameType, weather, terrain} }
//
// Result shape:
//   { id, damage: [..16 rolls..], minDamage, maxDamage, minPercent, maxPercent,
//     maxHP, koChanceText, desc }

import { calculate, Generations, Pokemon, Move, Field } from '@smogon/calc';
import { createInterface } from 'node:readline';

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => (data += chunk));
    process.stdin.on('end', () => resolve(data));
    process.stdin.on('error', reject);
  });
}

function buildPokemon(gen, spec, fallbackMove) {
  const opts = {};
  if (spec.level != null) opts.level = spec.level;
  if (spec.item != null) opts.item = spec.item;
  if (spec.nature != null) opts.nature = spec.nature;
  if (spec.ability != null) opts.ability = spec.ability;
  if (spec.evs != null) opts.evs = spec.evs;
  if (spec.ivs != null) opts.ivs = spec.ivs;
  if (spec.boosts != null) opts.boosts = spec.boosts;
  if (spec.status != null) opts.status = spec.status;
  if (spec.teraType != null) opts.teraType = spec.teraType;
  if (spec.curHP != null) opts.curHP = spec.curHP;
  const moveName = spec.move || fallbackMove;
  if (moveName) opts.moves = [moveName];
  return new Pokemon(gen, spec.species, opts);
}

function buildField(spec) {
  if (!spec) return new Field({ gameType: 'Singles' });
  const opts = { gameType: spec.gameType || 'Singles' };
  if (spec.weather != null) opts.weather = spec.weather;
  if (spec.terrain != null) opts.terrain = spec.terrain;
  return new Field(opts);
}

// Normalize @smogon/calc damage (number | number[] | number[][]) to flat rolls.
function toRolls(damage) {
  if (typeof damage === 'number') return [damage];
  if (Array.isArray(damage) && damage.length > 0 && Array.isArray(damage[0])) {
    const hits = damage;
    return hits[0].map((_, i) => hits.reduce((sum, h) => sum + h[i], 0));
  }
  return Array.from(damage);
}

function runStats(gen, req) {
  const mon = buildPokemon(gen, req.mon, null);
  return {
    id: req.id,
    stats: {
      hp: mon.stats.hp,
      atk: mon.stats.atk,
      def: mon.stats.def,
      spa: mon.stats.spa,
      spd: mon.stats.spd,
      spe: mon.stats.spe,
    },
  };
}

function runTypes(gen, req) {
  const mon = buildPokemon(gen, { species: req.species }, null);
  return { id: req.id, types: mon.types || [] };
}

function runOne(gen, req) {
  const attacker = buildPokemon(gen, req.attacker, req.move);
  const defender = buildPokemon(gen, req.defender);
  const move = new Move(gen, req.move || req.attacker.move);
  const field = buildField(req.field);

  const result = calculate(gen, attacker, defender, move, field);
  const rolls = toRolls(result.damage);
  const maxHP = defender.maxHP();
  const minDamage = Math.min(...rolls);
  const maxDamage = Math.max(...rolls);

  let koChanceText = null;
  try {
    koChanceText = result.koChance().text || null;
  } catch (e) {
    koChanceText = null;
  }

  let desc = null;
  try {
    desc = result.desc();
  } catch (e) {
    desc = null;
  }

  return {
    id: req.id,
    damage: rolls,
    minDamage,
    maxDamage,
    maxHP,
    minPercent: (minDamage / maxHP) * 100,
    maxPercent: (maxDamage / maxHP) * 100,
    koChanceText,
    desc,
  };
}

// Shared per-request dispatch used by both one-shot and server modes.
function dispatch(gens, req) {
  try {
    const genNum = req.gen ?? 9;
    if (!gens.has(genNum)) gens.set(genNum, Generations.get(genNum));
    if (req.kind === "stats") return runStats(gens.get(genNum), req);
    if (req.kind === "types") return runTypes(gens.get(genNum), req);
    return runOne(gens.get(genNum), req);
  } catch (e) {
    return { id: req.id, error: e.message };
  }
}

async function main() {
  const raw = await readStdin();
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    process.stdout.write(JSON.stringify({ error: `invalid JSON: ${e.message}` }));
    process.exitCode = 1;
    return;
  }

  const requests = Array.isArray(parsed) ? parsed : [parsed];
  const gens = new Map();
  const results = requests.map((req) => dispatch(gens, req));

  process.stdout.write(JSON.stringify(results));
}

// Server mode: persistent line-loop; gens Map is shared across all lines.
function processBatch(gens, raw) {
  let parsed;
  try { parsed = JSON.parse(raw); }
  catch (e) { return JSON.stringify({ error: `invalid JSON: ${e.message}` }); }
  const requests = Array.isArray(parsed) ? parsed : [parsed];
  return JSON.stringify(requests.map((req) => dispatch(gens, req)));
}

function serve() {
  const gens = new Map();                              // SHARED across all lines (the win)
  const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
  rl.on('line', (raw) => {
    if (raw.trim() === '') return;
    process.stdout.write(processBatch(gens, raw) + '\n');  // stdout = protocol ONLY
  });
  rl.on('close', () => process.exit(0));               // stdin EOF -> clean exit 0
}

if (process.argv.includes('--server')) serve();
else main().catch((e) => {
  process.stdout.write(JSON.stringify({ error: e.message }));
  process.exitCode = 1;
});
