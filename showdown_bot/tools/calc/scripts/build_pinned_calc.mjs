#!/usr/bin/env node
/**
 * Build vendored @smogon/calc from a fixed upstream commit.
 *
 * Fetches smogon/damage-calc, installs repo-root bundler deps, runs upstream
 * `npm test` in calc/ (pretest build + jest + posttest lint), npm pack,
 * writes vendor/*.tgz and PINNED_CALC.json with source/lock/artifact SHA-256.
 */
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import {
  copyFileSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CALC_DIR = resolve(__dirname, '..');
const VENDOR_DIR = join(CALC_DIR, 'vendor');

const UPSTREAM_REPO = 'https://github.com/smogon/damage-calc.git';
const UPSTREAM_COMMIT = '6287bda767daeee7eec3ad10f70a0f94fbd4e803';
const CALC_SUBDIR = 'calc';
const PACKAGE_NAME = '@smogon/calc';
const PACKAGE_VERSION = '0.11.0';
const ARTIFACT_FILENAME = `@smogon+calc-${PACKAGE_VERSION}+commit6287bda.tgz`;

function sha256Buffer(buf) {
  return createHash('sha256').update(buf).digest('hex');
}

function sha256File(path) {
  return sha256Buffer(readFileSync(path));
}

function run(cmd, args, opts = {}) {
  const shell = process.platform === 'win32' && cmd.toLowerCase().endsWith('.cmd');
  const result = spawnSync(cmd, args, {
    stdio: 'inherit',
    shell,
    ...opts,
  });
  if (result.error) {
    throw new Error(`${cmd} ${args.join(' ')} failed: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`${cmd} ${args.join(' ')} failed (rc=${result.status})`);
  }
}

function npmCmd() {
  return process.platform === 'win32' ? 'npm.cmd' : 'npm';
}

function gitArchiveHash(repoDir, commit) {
  const result = spawnSync(
    'git',
    ['archive', '--format=tar', commit],
    {
      cwd: repoDir,
      encoding: 'buffer',
      shell: false,
      maxBuffer: 128 * 1024 * 1024,
    },
  );
  if (result.error) {
    throw new Error(`git archive failed: ${result.error.message}`);
  }
  if (result.status !== 0 && result.status !== null) {
    throw new Error(`git archive failed: ${result.stderr?.toString()}`);
  }
  if (!result.stdout?.length) {
    throw new Error('git archive produced empty output');
  }
  return sha256Buffer(result.stdout);
}

function rootLockfileHash(repoDir, commit) {
  const result = spawnSync(
    'git',
    ['show', `${commit}:package-lock.json`],
    { cwd: repoDir, encoding: 'buffer', shell: false },
  );
  if (result.status !== 0) {
    throw new Error(`git show root lockfile failed: ${result.stderr?.toString()}`);
  }
  return sha256Buffer(result.stdout);
}

function writeCanonicalJson(path, obj) {
  writeFileSync(path, `${JSON.stringify(obj, Object.keys(obj).sort())}\n`, 'utf8');
}

function main() {
  const workRoot = join(
    tmpdir(),
    `damage-calc-pin-${UPSTREAM_COMMIT.slice(0, 12)}-${Date.now()}`,
  );
  const repoDir = join(workRoot, 'repo');
  const calcDir = join(repoDir, CALC_SUBDIR);

  console.log(`Work directory: ${workRoot}`);
  mkdirSync(workRoot, { recursive: true });

  console.log('Cloning upstream repo (blobless)...');
  run('git', ['clone', '--filter=blob:none', UPSTREAM_REPO, repoDir]);
  run('git', ['checkout', UPSTREAM_COMMIT], { cwd: repoDir });

  const sourceTreeSha256 = gitArchiveHash(repoDir, UPSTREAM_COMMIT);
  const rootLockfileSha256 = rootLockfileHash(repoDir, UPSTREAM_COMMIT);
  console.log(`source_tree_sha256=${sourceTreeSha256}`);
  console.log(`root_lockfile_sha256=${rootLockfileSha256}`);

  console.log('Installing upstream repo-root dependencies (bundler + subpkg)...');
  run(npmCmd(), ['ci'], { cwd: repoDir });

  console.log('Running upstream npm test (pretest build + jest + posttest lint)...');
  run(npmCmd(), ['test', '--', '--runInBand'], { cwd: calcDir });

  console.log('Packing npm tarball (skip prepare rebuild)...');
  const packResult = spawnSync(
    npmCmd(),
    ['pack', '--ignore-scripts', '--pack-destination', workRoot],
    {
      cwd: calcDir,
      encoding: 'utf8',
      shell: process.platform === 'win32',
    },
  );
  if (packResult.status !== 0) {
    throw new Error(`npm pack failed: ${packResult.stderr}`);
  }
  const packedName = packResult.stdout.trim().split('\n').pop().trim();
  const packedPath = join(workRoot, packedName);

  mkdirSync(VENDOR_DIR, { recursive: true });
  const artifactPath = join(VENDOR_DIR, ARTIFACT_FILENAME);
  copyFileSync(packedPath, artifactPath);
  const artifactSha256 = sha256File(artifactPath);
  console.log(`artifact_sha256=${artifactSha256}`);

  const manifest = {
    artifact_filename: ARTIFACT_FILENAME,
    artifact_sha256: artifactSha256,
    calc_subdirectory: CALC_SUBDIR,
    package_name: PACKAGE_NAME,
    package_version: PACKAGE_VERSION,
    root_lockfile_sha256: rootLockfileSha256,
    source_tree_sha256: sourceTreeSha256,
    upstream_commit: UPSTREAM_COMMIT,
    upstream_repo: 'smogon/damage-calc',
  };

  const manifestPath = join(CALC_DIR, 'PINNED_CALC.json');
  writeCanonicalJson(manifestPath, manifest);
  const pinHash = sha256File(manifestPath).slice(0, 16);
  console.log(`Wrote ${manifestPath}`);
  console.log(`calc_pin_hash=${pinHash}`);
  console.log(`Wrote ${artifactPath}`);
}

main();
