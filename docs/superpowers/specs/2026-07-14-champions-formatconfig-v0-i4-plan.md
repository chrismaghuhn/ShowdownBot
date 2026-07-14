# Champions FormatConfig v0 — I4 Native Calc Gen + SpeedOracle (Implementation Plan)

**Status:** APPROVED — rev 3 (implementation in progress)
**Date:** 2026-07-14 (rev 3 — provenance hashes, export factory binding, reproducible baseline capture, pinned gen-0 damage)
**Builds on:** [`2026-07-14-champions-formatconfig-v0-design.md`](2026-07-14-champions-formatconfig-v0-design.md) §7.3 · I3 (`f756105`)
**Supersedes:** rev 2 “factory or fail-closed” export ambiguity; inferred `stat_points` → gen 0; optional gen-0 damage smoke

## 0. Goal

I4 makes **opponent speed ranges** format-correct for Champions via pinned `@smogon/calc` **gen 0**
(`calculateChampions`, `Stats.calcStatChampions`). Stat Points stay native in yaml/meta. No
`if format_id == …` in Python.

**Architecture (approved direction):** explicit `calc_generation`, vendored `.tgz`, central
`CalcProfile` factory, native gen-0 stats, **deferred live damage threading** in the heuristic path.

**Non-goals:** full `DamageOracle` gen-0 threading in live decisions, Mega overlay, strength/McNemar, I5 smoke.

---

## 1. Verified mechanics (audit summary)

Champions VGC stat formula (Showdown `champions/scripts.ts::statModify`, no `levelclausemod`; upstream
`calcStatChampions` at `6287bda`):

| Stat | Formula (pre-nature) |
|------|----------------------|
| HP | `base + SP + 75` |
| Others | `floor(nature × (base + SP + 20))` |

**Not** `8×points−4` (that is Showdown `levelclausemod` only).

Pinned **stat** vectors (verified via `calcStat(0, …)` at `6287bda`):

| Mon | Stat | Base | SP | Nature | Expected |
|-----|------|------|----|--------|----------|
| Abomasnow | HP | 90 | 0 | — | **165** |
| Abomasnow | Atk | 92 | 32 | Adamant | **158** |
| Abomasnow | Spe | 60 | 32 | Hardy | **112** |

---

## 2. Upstream calc pin

| Artifact | Champions gen 0 |
|----------|-----------------|
| `@smogon/calc@0.10.0` (our lock) | **No** |
| npm `@smogon/calc@0.11.0` tarball | **No** |
| git **`6287bda767daeee7eec3ad10f70a0f94fbd4e803`** | **Yes** |

Vendor bump also changes **gen 9** code/data → Reg-I parity is a **merge gate** (§8).

---

## 3. Schema: explicit calc engine (not inferred from stat scale)

`stat_investment.kind` (yaml scale) and calc mechanics are **separate**.

```yaml
# Reg-I (explicit or omitted → default 9)
calc_generation: 9

# Champions (required)
calc_generation: 0
```

Loader: optional field, default **`9`**; allowed **`0 | 9`** only.

```python
DEFAULT_CALC_PROFILE = CalcProfile(
    generation=9,
    max_spe_investment=DEFAULT_STAT_INVESTMENT.max_per_stat,
)

def calc_profile_from_config(cfg: FormatConfig | None) -> CalcProfile:
    if cfg is None:
        return DEFAULT_CALC_PROFILE
    return CalcProfile(
        generation=cfg.calc_generation,
        max_spe_investment=cfg.stat_investment.max_per_stat,
    )
```

**No** derivation from `stat_investment.kind`.

---

## 4. Vendoring (normative, reproducible)

### 4.1 Deliverable

Complete installable npm package at fixed commit:

```
showdown_bot/tools/calc/
  PINNED_CALC.json
  vendor/
    @smogon+calc-0.11.0+commit6287bda.tgz   # committed
  package.json                              # file:vendor/….tgz
  package-lock.json
```

`.tgz` includes `package.json`, `dist/`, **MIT LICENSE**, full package metadata.

### 4.2 `PINNED_CALC.json` (no timestamps)

| Field | Purpose |
|-------|---------|
| `upstream_repo` | `smogon/damage-calc` |
| `upstream_commit` | `6287bda767daeee7eec3ad10f70a0f94fbd4e803` |
| `calc_subdirectory` | `calc` |
| `package_name` / `package_version` | `@smogon/calc` / `0.11.0` |
| `source_tree_sha256` | `git archive` at commit |
| `lockfile_sha256` | upstream `calc/package-lock.json` at commit |
| `artifact_sha256` | SHA-256 of committed `.tgz` |
| `artifact_filename` | basename of `.tgz` |

**Forbidden:** build dates in manifest; floating branches; partial `dist/` without package.json.

### 4.3 Merge gates

1. `tools/calc/scripts/build_pinned_calc.mjs` — fetch commit, `npm ci && npm test && npm run build`, `npm pack`, verify hashes.
2. Clean checkout: `cd showdown_bot/tools/calc && npm ci` succeeds.
3. Upstream **`npm test`** at pin passes in build script (before pack).

---

## 5. Provenance / `config_hash` (rev 3 — mandatory)

### 5.1 Current gap

`cli._config_hash_for` / `build_config_manifest` today hash:

- `format_id`, `agent`, `priors_hash`, `spreads_hash`, `movedata_hash`, behavior `env`

**Missing:** format yaml content, calc engine selection, calc artifact pin.

### 5.2 New manifest fields

Extend `build_config_manifest` (and `_config_hash_for` caller):

| Field | Source |
|-------|--------|
| `format_config_hash` | SHA-1[:16] of resolved format yaml bytes (`cfg.source_path`) |
| `calc_pin_hash` | SHA-256[:16] (first 16 hex chars) of **committed `PINNED_CALC.json` UTF-8 bytes** |

`PINNED_CALC.json` MUST be written in canonical form (`sort_keys=True`,
`separators=(',', ':')`, trailing newline) so the hash is stable across platforms.

`calc_pin_hash` changes when the pin manifest changes (including `artifact_sha256`);
`format_config_hash` changes when yaml changes (including `calc_generation`).

### 5.4 Pin load verification (fail-closed)

Whenever `PINNED_CALC.json` is read (config-hash builder, `npm ci` gate helper, etc.):

1. Parse manifest; require `artifact_sha256` and `artifact_filename`.
2. Read `vendor/{artifact_filename}`; compute SHA-256 of raw `.tgz` bytes.
3. **Fail-closed** if computed digest ≠ `artifact_sha256` (do not proceed to hash or install).

No alternate hash source (no “artifact prefix” shortcut).

### 5.3 Tests (merge gate)

| Test | Assert |
|------|--------|
| `test_config_hash_includes_format_config_hash` | manifest contains hash of format yaml |
| `test_config_hash_includes_calc_pin_hash` | manifest contains calc pin |
| `test_config_hash_changes_when_calc_generation_changes` | same format yaml + different `calc_generation` → different hash |
| `test_config_hash_changes_when_calc_artifact_changes` | mock `calc_pin_hash` delta → different hash |

Existing movedata/priors/spreads hash tests unchanged.

---

## 6. Architecture

### 6.1 Central factory (binding)

```python
@dataclass(frozen=True)
class CalcProfile:
    generation: int          # 0 | 9
    max_spe_investment: int

def build_speed_oracle(stats_backend, profile: CalcProfile) -> SpeedOracle: ...
```

- **Not** pass full `FormatConfig` into `SpeedOracle`.
- **Not** expose ad-hoc `calc_gen` + `max_spe` at each call site.
- All live paths: `calc_profile_from_config(cfg)` → `build_speed_oracle(backend, profile)`.

### 6.2 Export runtime — **factory only (binding)**

`learning/export_runtime._build_rollout_provider` **must** use the same factory:

```python
cfg = load_format_config(format_id)
profile = calc_profile_from_config(cfg)
speed_oracle = build_speed_oracle(calc.backend, profile)
```

**No** “factory or fail-closed” alternative in implementation. If factory wiring for export
proves too large during coding: **stop, do not merge, request new review** — do not switch
mid-implementation to fail-closed.

(Accuracy gates / offline scripts remain Reg-I gen-9 default — OUT of I4.)

### 6.3 Bridge

| Location | Fix |
|----------|-----|
| `calc.mjs:127` | `req.gen ?? 9` |
| `client.py` `stats_batch(specs, *, gen=9)` | both backends |
| `speed.py` | profile-driven; cache key `(profile.generation, species, nature, evs)` |

Live `DamageRequest.gen` threading: **deferred** (separate slice). Gen-0 damage **smoke** (§7) proves
`calculateChampions` is vendored and reachable through bridge.

---

## 7. Test matrix (rev 3)

| ID | Requirement | Gate |
|----|-------------|------|
| **T0** | Reg-I gen-9 stats + damage parity vs 0.10.0 baseline fixture | **merge** |
| **T1** | Gen-0 stat vectors SP 0/1/2/32 | merge |
| **T2** | **Gen-0 damage smoke (mandatory)** — exact pin §7.1 | **merge** |
| **T3** | Upstream `npm test` at pin (build script) | merge |
| **T4** | All **three** fakes: `FakeStatsBackend`, `FakeBackend` (`test_speed.py`), `_SpeFake` (`test_opponent.py`) implement `stats_batch(specs, *, gen=9)` | merge |
| **T5–T13** | SpeedOracle Reg-I/Champions max, likely spread, legacy None, gauntlet/decision/export factory parity, cache cross-format, config_hash tests (§5.3) | merge |
| **T14** | Existing `test_speed.py`, I3 suite, calc integration | merge |
| **T15** | **Full Python test suite** (`pytest` from repo root, all non-skipped tests) | **merge (pre-merge only)** |

Focused gates (T0–T14) run after each slice commit; **T15 is mandatory once before merge**
because the global calc swap can affect any integration path.

### 7.1 Pinned gen-0 damage case (exact — not “≠ gen 9”)

**Upstream reference:** `smogon/damage-calc@6287bda` · `calc/src/test/calc.test.ts` ·
`describe('Champions')` → `Mega Sol` → Body Slam (no-snow defender variant).

**Inputs (gen 0):**

| Role | Spec |
|------|------|
| Attacker | `Meganium-Mega`, ability `Mega Sol`, item `Meganiumite` (defaults) |
| Defender | `Abomasnow`, ability `Soundproof` |
| Move | `Body Slam` |
| Field | default |

**Expected (verified at pin via upstream `dist/index.js`):**

| Metric | Value |
|--------|-------|
| `min_damage` | **39** |
| `max_damage` | **46** |
| `damage` rolls | **16 rolls**, min 39 max 46 |
| `desc` prefix | `0 Atk Meganium-Mega Body Slam vs. 0 HP / 0 Def Abomasnow: 39-46` |

Committed fixture: `showdown_bot/tests/fixtures/calc_gen0_damage_upstream.json` (inputs + expected).

Bridge test: same payload through `calc.mjs` / `SubprocessCalcBackend.calc_batch` with `gen: 0`.

**Secondary immunity pin (optional guard):** gen 0 Snorlax Hyper Beam vs Gengar → all rolls **0**
(`calc.test.ts` `Immunity (gen 0)`).

---

## 8. Reg-I baseline capture (reproducible — commit 1)

Commit 1 is **not** fixture-only. It includes:

### 8.1 Script

`showdown_bot/tools/calc/scripts/capture_regi_parity_baseline.py`:

1. **Verify** installed `@smogon/calc` is exactly **0.10.0** (`package-lock.json` + `node_modules/@smogon/calc/package.json`).
2. Record **Node version**, npm version, platform in output metadata.
3. Run fixed list of stats + damage probes (same inputs as T0).
4. Write `showdown_bot/tests/fixtures/calc_regi_parity_baseline.json` with `{meta, cases[]}`.
5. **Fail** if fixture already exists unless `--force` (no silent overwrite).
6. Print sha256 of fixture to stdout for commit message.

### 8.2 Fixture contents

Each case: `{id, kind, request_payload, expected_response}` — sufficient to replay through bridge
after vendor bump.

### 8.3 Gate

Commit 3 (`test(calc): assert Reg-I parity on vendored calc`) reads fixture; any drift fails CI.

---

## 9. Call-site matrix (rev 3)

| Site | I4 action |
|------|-----------|
| `gauntlet._decision_deps` | **IN** — factory |
| `decision._choose_best` | **IN** — factory |
| `runner` → `choose_with_fallback` | **IN** (via decision) |
| **`learning/export_runtime._build_rollout_provider`** | **IN** — **factory only** |
| `baselines.max_damage_choice` | **IN** when internal oracle built; gauntlet client oracle covered |
| `cli._config_hash_for` | **IN** — format + calc pin hashes |
| Accuracy gates / scripts | **OUT** — Reg-I offline |
| `decide_adapter` | **OUT** |

---

## 10. Backward compatibility

| Scenario | Behaviour |
|----------|-----------|
| yaml omits `calc_generation` | **9** |
| `format_config=None` | `DEFAULT_CALC_PROFILE` (gen 9, max from `DEFAULT_STAT_INVESTMENT`) |
| Reg-I explicit `calc_generation: 9` | parity gate vs 0.10.0 baseline |
| Vendor pin bump | requires T0 + T2 + hash updates |

---

## 11. Risks

1. Gen-9 drift on vendor bump — T0 gate.
2. Incomplete provenance — §5 fixes.
3. Export silent wrong-gen — factory binding §6.2.
4. Baseline overwrite — capture script `--force` gate §8.

---

## 12. Non-goals

Live heuristic damage gen-0; Mega overlay; strength; inferring calc gen from stat scale; mid-implementation export fail-closed fallback.

---

## 13. Implementation order

1. **Capture script + baseline fixture** (0.10.0 verified).
2. **Vendor `.tgz` + `PINNED_CALC.json`**; upstream tests; gen-0 damage fixture §7.1.
3. **T0 parity** on new pin.
4. **`calc_generation` schema** + yaml backfill.
5. **Provenance hashes** in config manifest.
6. **Bridge + CalcProfile factory + SpeedOracle**.
7. **Threading:** gauntlet, decision, **export**.
8. **Tests T1–T14**; `git diff --check`.

**Stop line:** no strength run.

---

## 14. Commit boundaries

| # | Message | Contents |
|---|---------|----------|
| 0 | `docs(format): add I4 native calc plan rev 3` | this file |
| 1 | `test(calc): add Reg-I parity capture script and baseline at 0.10.0` | script + fixture + meta |
| 2 | `chore(calc): vendor @smogon/calc 6287bda as pinned tgz` | `.tgz`, `PINNED_CALC.json`, lock, gen-0 damage fixture |
| 3 | `test(calc): assert Reg-I parity and gen-0 damage smoke on vendored calc` | T0, T2 |
| 4 | `feat(format): add calc_generation and config_hash provenance` | loader, yamls, manifest |
| 5 | `fix(calc): bridge gen 0 and stats_batch gen param` | calc.mjs, client.py |
| 6 | `feat(format): CalcProfile factory and SpeedOracle wiring` | profile, speed, gauntlet, decision, export |
| 7 | `test(format): SpeedOracle and config_hash coverage` | remaining tests |

---

## 15. Review ask (rev 3)

1. **`calc_generation: 0|9`** explicit; default 9.
2. **Pinned `.tgz` + SHA manifest** without build dates; `npm ci` gate.
3. **`format_config_hash` + `calc_pin_hash`** in `config_hash`; tests on yaml/calc changes.
4. **Export: factory only**; stop-and-review if scope blows up.
5. **Reproducible baseline capture script** with 0.10.0 verification and no silent overwrite.
6. **Gen-0 damage pin** `[39, 46]` Body Slam case (§7.1), mandatory merge gate.

---

## 16. Placeholder scan

| Location | Note |
|----------|------|
| `eval/config_env.py` `build_config_manifest` | add provenance fields |
| `cli.py` `_config_hash_for` | load format yaml hash + calc pin |
| `export_runtime.py:229` | factory |
| `speed.py:125` | 252 assumption |
| Three test fakes | `stats_batch(..., gen=)` |

Rev 3 approved 2026-07-14; implementation follows §13–§14.
