#!/usr/bin/env node
/**
 * Capture pinned gen-0 damage fixture (§7.1) from installed @smogon/calc.
 */
import { calculate, Generations, Move, Pokemon } from '@smogon/calc';
import { writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, '..', '..', '..');
const FIXTURE_PATH = join(
  REPO_ROOT,
  'tests',
  'fixtures',
  'calc_gen0_damage_upstream.json',
);

const REQUEST = {
  id: 'gen0_body_slam_mega_sol',
  gen: 0,
  attacker: {
    species: 'Meganium-Mega',
    ability: 'Mega Sol',
    item: 'Meganiumite',
  },
  defender: {
    species: 'Abomasnow',
    ability: 'Soundproof',
  },
  move: 'Body Slam',
};

function toRolls(damage) {
  if (typeof damage === 'number') return [damage];
  if (Array.isArray(damage) && damage.length > 0 && Array.isArray(damage[0])) {
    const hits = damage;
    return hits[0].map((_, i) => hits.reduce((sum, h) => sum + h[i], 0));
  }
  return Array.from(damage);
}

const gen = Generations.get(0);
const attacker = new Pokemon(gen, REQUEST.attacker.species, {
  ability: REQUEST.attacker.ability,
  item: REQUEST.attacker.item,
});
const defender = new Pokemon(gen, REQUEST.defender.species, {
  ability: REQUEST.defender.ability,
});
const move = new Move(gen, REQUEST.move);
const result = calculate(gen, attacker, defender, move);
const rolls = toRolls(result.damage);
const minDamage = Math.min(...rolls);
const maxDamage = Math.max(...rolls);
const maxHP = defender.maxHP();
const desc = result.desc();

const fixture = {
  meta: {
    purpose: 'Pinned gen-0 damage smoke (T2) — upstream calc.test.ts Mega Sol Body Slam',
    upstream_commit: '6287bda767daeee7eec3ad10f70a0f94fbd4e803',
    calc_package: '@smogon/calc',
    calc_version: '0.11.0',
  },
  case: {
    id: REQUEST.id,
    kind: 'damage',
    request_payload: REQUEST,
    expected_response: {
      id: REQUEST.id,
      damage: rolls,
      minDamage,
      maxDamage,
      maxHP,
      minPercent: (minDamage / maxHP) * 100,
      maxPercent: (maxDamage / maxHP) * 100,
      desc,
    },
  },
};

writeFileSync(FIXTURE_PATH, `${JSON.stringify(fixture, null, 2)}\n`, 'utf8');
console.log(`Wrote ${FIXTURE_PATH}`);
console.log(`expected min=${minDamage} max=${maxDamage} rolls=${rolls.length}`);
console.log(`desc=${desc}`);
