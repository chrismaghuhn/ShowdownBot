#!/usr/bin/env node
/**
 * Fail-closed verification: PINNED_CALC.json artifact_sha256 matches vendor .tgz.
 */
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CALC_DIR = resolve(__dirname, '..');
const MANIFEST_PATH = join(CALC_DIR, 'PINNED_CALC.json');

function sha256File(path) {
  const data = readFileSync(path);
  return createHash('sha256').update(data).digest('hex');
}

function fail(msg) {
  console.error(`verify_pinned_calc: ${msg}`);
  process.exit(1);
}

const manifest = JSON.parse(readFileSync(MANIFEST_PATH, 'utf8'));
const filename = manifest.artifact_filename;
const expected = manifest.artifact_sha256;
if (!filename || !expected) {
  fail('PINNED_CALC.json missing artifact_filename or artifact_sha256');
}

const artifactPath = join(CALC_DIR, 'vendor', filename);
let actual;
try {
  actual = sha256File(artifactPath);
} catch (err) {
  fail(`cannot read artifact ${artifactPath}: ${err.message}`);
}

if (actual !== expected) {
  fail(
    `artifact SHA-256 mismatch for ${filename}\n` +
      `  expected: ${expected}\n` +
      `  actual:   ${actual}`,
  );
}

console.log(`verify_pinned_calc: OK (${filename})`);
