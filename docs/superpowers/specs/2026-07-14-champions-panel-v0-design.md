# Champions Panel v0 — Format Discovery, Validation & Panel Design

**Status:** PROPOSED — pending review (panel/schedule/team artefacts only; **no bot code**;
execution **not** approved)
**Date:** 2026-07-14
**Builds on:** [`2026-07-01-2b35-diverse-opponent-eval-harness.md`](2026-07-01-2b35-diverse-opponent-eval-harness.md)
(panel schema, `panel_hash`, schedule generator) · [`2026-07-14-vgc-battle-logs-import-audit.md`](2026-07-14-vgc-battle-logs-import-audit.md)
(Champions human-log context; **out of scope** for team sourcing in this slice)
**Precedes:** decision on whether the next larger strength run targets Reg-I `panel_v001` or
Champions `panel_champions_v0`.

## 0. What this slice does

Design and freeze a **small, Showdown-validated Champions/VGC-2026 panel v0** that can later
anchor Safety / Strength / Depth eval runs — without claiming strength and without bot refactors.

Deliverables (in mandatory order):

1. **Format discovery** — document the **live** Pokémon Showdown format ID(s) for Champions
   VGC 2026 Reg M-A / M-B (not guessed).
2. **Mechanics + validation audit** — record active rules (Mega / Tera / restricted / OTS / BO3)
   and prove every committed team passes `validate-team` for the chosen format ID.
3. **Panel v0** — five opponent archetypes (3 dev + 2 held-out) + a Champions hero team decision,
   with full provenance.
4. **Pilot smoke** — one tiny schedule proving pipeline compatibility:
   `schedule → gauntlet → result_jsonl → eval-report` (no large eval).

This slice answers:

> Can we stand up a reproducible Champions target panel on live Showdown, with validated teams and
> a working eval pipeline smoke — and is the format stable enough to plan future strength work?

## 1. Explicit non-goals

- **No bot / battle-engine code changes** in this slice (no `FormatConfig` yaml, no Mega/Tera logic,
  no policy retune). P4 pipeline smoke tests **harness plumbing only**, not decision quality.
  Missing Champions `FormatConfig` remains a **blocker for later strength runs** (§8.2).
- **No official Pokémon Champions app automation.**
- **No strength claim** from pilot smoke winrates.
- **No large eval run** (no dev-strength-scale schedules, no McNemar gate).
- **No VGC-Bench / HolidayOugi downloads** — teams come from public paste sources only (§6).
- **No mixing** with running `accuracy-default-on-devstrength-ab` measurement or frozen gate corpora.
- **No committing teams before** format ID + validator + provenance template are settled (§5).

## 2. Mandatory execution order (hard gate)

Each phase **blocks** the next. If a phase fails → **BLOCKED / NO-GO** for the slice; do not
work around with alias formats, unvalidated teams, or Reg-I fallbacks.

| Phase | Gate | On failure |
|-------|------|------------|
| **P0** Format discovery | Live Showdown exposes stable BO1 ID for Reg M-A | **NO-GO** — stop; file `reports/champions-panel-v0-format-discovery.md` with evidence |
| **P1** Mechanics audit | Rules documented; validator accepts/rejects as expected | **NO-GO** if validator unusable or ID unstable across pinned server |
| **P2** Team curation | Every team `validate-team` exit 0 + `pack-team` | **NO-GO** — no team files committed |
| **P3** Panel freeze | `panel_champions_v0.yaml` loads; `panel_hash` reproducible | **NO-GO** |
| **P4** Pilot smoke | ≥5 battles, 0 crashes / 0 invalid, report generates | **NO-GO** for “pipeline ready”; panel may still ship if P0–P3 pass and smoke fails only on known bot gaps (must be classified, §8) |

## 3. Phase P0 — Showdown format discovery

### 3.1 Procedure (must run, not infer)

Use a **pinned** local `pokemon-showdown` clone (same pin as eval harness; currently documented
against upstream `f8ac140` in `tools/eval/patches/README.md`). Record `git rev-parse HEAD`.

**Source A (primary):** live format list

```bash
# From any machine with network; save raw artefact under data/eval/champions-panel-v0/discovery/
curl -sS https://play.pokemonshowdown.com/data/formats.js -o formats.js.snapshot
```

Parse for entries whose `name` contains `Champions` and `VGC 2026 Reg M`. Record `name`, `mod`,
`gameType`, `ruleset`, `searchShow`, `bestOfDefault`.

**Source B (cross-check):** upstream `config/formats.ts` at the pinned commit.

**Source C (cross-check):** at least one live replay URL under `replay.pokemonshowdown.com/` whose
path segment matches the candidate ID (proves the ID is used in battle creation, not just UI).

**Source D (negative check):** explicitly record that VGC-Bench human logs use **different** battle
header IDs (`gen9vgc2025regma` / `gen9vgc2025regmb` in our ingest fixtures) — these are **replay
data aliases**, not substitutes for live challenge IDs.

### 3.2 Expected IDs (hypothesis — must be confirmed in P0, not assumed)

Pre-discovery research (2026-07-14) points to the **`gen9champions…` namespace**, not the Reg-I
`gen9vgc2025regi` path:

| Human tier name (Showdown) | Expected machine ID | Role in panel v0 |
|--------------------------|---------------------|------------------|
| `[Gen 9 Champions] VGC 2026 Reg M-A` | `gen9championsvgc2026regma` | **Primary** — BO1 panel + smoke |
| `[Gen 9 Champions] VGC 2026 Reg M-A (Bo3)` | `gen9championsvgc2026regmabo3` | Document only; not pilot smoke default |
| `[Gen 9 Champions] VGC 2026 Reg M-B` | `gen9championsvgc2026regmb` | Document only; panel v0 targets **M-A first** |
| `[Gen 9 Champions] VGC 2026 Reg M-B (Bo3)` | `gen9championsvgc2026regmbbo3` | Document only |

**Legacy / do-not-use for validation or gauntlet challenge strings:**

- `gen9vgc2025regma`, `gen9vgc2025regmb` — appear in `cameronangliss/vgc-bench` logs; classified
  `MECHANICALLY_SIMILAR_BUT_NOT_TARGET` by `research/vgc_bench_ingest/format_gate.py`.

### 3.3 Stability criteria (PASS / NO-GO)

**PASS** when all hold on the pinned server:

- BO1 ID `gen9championsvgc2026regma` accepts a `/challenge …, <id>` (or gauntlet equivalent).
- `node pokemon-showdown validate-team <id>` runs without “unknown format”.
- ID unchanged between `formats.js` snapshot and pinned clone `formats.ts`.
- Tier string in a started battle's `|tier|` line matches the human name above.

**NO-GO** when:

- Only BSS / singles Champions formats exist; VGC doubles ID missing or `debug`-only.
- ID differs between live server and pinned clone **and** harness cannot pin to a matching server
  revision without a new patch cycle.
- Validator and challenge path disagree on format string.

## 4. Phase P1 — Mechanics & validation audit

### 4.1 Mechanics checklist (document in discovery report)

Compare **primary ID** `gen9championsvgc2026regma` against current target `gen9vgc2025regi`:

| Mechanic | Reg I (`gen9vgc2025regi`) | Champions M-A (audit target) | Impact on panel v0 |
|----------|---------------------------|------------------------------|--------------------|
| Game type | Doubles | Doubles | Same harness |
| Level | 50 | 50 (via Flat Rules) | Same |
| Bring / pick | 6 → 4 | 6 → 4 | Same teampreview path |
| Team preview / OTS | OTS | `Open Team Sheets` in ruleset | Same broad shape |
| Terastallize | On (`tera: true` in our yaml) | **Audit** — Champions uses `Flat Rules`; confirm Tera availability via ruleset chain + sample log | Teams must not assume Tera if banned |
| Mega Evolution | No | **On** (headline) | Teams must include legal Mega options; bot not updated in this slice |
| Restricted legendaries | Limit 1 | **Audit** — M-A bans restricted (official); confirm via validator rejection test | No Miraidon/Koraidon/Calyrex teams |
| BO3 | Separate ID | Separate `…regmabo3` ID | Pilot uses BO1 only |
| Dex / move pool | SV Reg I | Champions dex | Species movesets differ — Reg-I teams invalid |

**Audit actions (required evidence):**

1. Paste ruleset expansion from pinned `config/formats.ts` for the primary ID.
2. **Validator probes:** one intentionally illegal Reg-I restricted team (e.g. current
   `teams/fixed_team.txt` if it includes restricted / illegal species) must **fail**
   `validate-team gen9championsvgc2026regma`.
3. **Validator probes:** one minimal legal M-A team (6 species known legal in Champions) must **pass**.
4. Optional: one-turn replay or protocol capture showing Mega button / absence of Tera — links in report.

### 4.2 Validation command (canonical for this slice)

All panel teams and hero teams must pass, from `showdown_bot/` with pinned clone on `PATH` or
`POKEMON_SHOWDOWN_PATH`:

```bash
node pokemon-showdown validate-team gen9championsvgc2026regma < teams/panel_champions_v0/<team>.txt
node pokemon-showdown pack-team < teams/panel_champions_v0/<team>.txt > teams/panel_champions_v0/<team>.packed
```

Replace ID if P0 discovers a different stable BO1 string — then **every** command and artefact
uses that ID consistently.

**Hard rule:** no `@Tera Type` lines unless P1 proves Tera is legal; if Tera is banned, teams
with Tera types must fail validation and be fixed before commit.

## 5. Phase P2–P3 — Panel v0 structure

### 5.1 Schema (reuse `eval/panel.py` unchanged)

Same contract as `panel_v001`:

- `version`, `policies`, `dev_teams[]`, `heldout_teams[]`
- Each team: `{team_id, team_path, archetype}` + content-derived `team_hash` (`.txt` + `.packed`)
- `panel_hash` = sha1 canonical payload (see `eval/panel.py`)

**Team path convention (load-bearing — same as `panel_v001`):**

| Context | Path form | Example |
|---------|-----------|---------|
| **Filesystem** (repo tree, docs, shell cwd notes) | `showdown_bot/teams/...` | `showdown_bot/teams/panel_champions_v0/goodstuff.txt` |
| **Panel YAML + schedules** (`team_path`, `hero_team_path`, `opp_team_path`) | **Gauntlet-relative** from `showdown_bot/` working dir | `teams/panel_champions_v0/goodstuff.txt` |
| **`load_panel(..., teams_root=...)`** | Resolve gauntlet-relative paths against `teams_root` (typically `showdown_bot/`) | — |

**Forbidden in committed YAML:** `showdown_bot/teams/...`, `../teams/...`, or any absolute path.
Mirror `panel_v001.yaml`:

```yaml
dev_teams:
  - {team_id: goodstuff, team_path: teams/panel_champions_v0/goodstuff.txt, archetype: balance_goodstuff}
```

Hero in schedules: `hero_team_path: teams/fixed_champions_v0.txt` (not
`showdown_bot/teams/fixed_champions_v0.txt`).

### 5.2 Archetypes (Champions M-A — dev 3 + held-out 2)

Default mapping (adjust only with cited meta evidence in provenance — e.g. Pikalytics/Limitless
usage, not Reg-I habit):

| Split | `team_id` | Archetype | Intent |
|-------|-----------|-----------|--------|
| dev | `goodstuff` | `balance_goodstuff` | Incineroar / Garchomp / Kingambit-style flexible balance — M-A usage core |
| dev | `tailwind_offense` | `tailwind_offense` | Fast Tailwind + priority (Whimsicott / Sneasler axis) |
| dev | `trick_room` | `trick_room` | Sinistcha / Farigiraf-style TR (dominant M-A archetype) |
| held-out | `rain_offense` | `weather_rain` | Pelipper rain (or documented Sun if rain pool too thin at curation time) |
| held-out | `disruption` | `bulky_disruption` | Anti-meta control — Sableye / redirect / bulky setup (not a Reg-I clone) |

**Deviation rule:** if curation finds an archetype non-viable (cannot validate 6 mons), replace
with the closest M-A meta archetype and document **why** in `PROVENANCE.md` with usage link.

**Do not port** `panel_v001` rosters verbatim — Reg-I restricted cores (Flutter Mane + restricted
box legends) are expected to fail Champions validation.

### 5.3 Policies (pilot-minimal)

For v0, keep policies narrow until a separate bot-readiness slice exists:

```yaml
policies: [heuristic, max_damage]
```

Rationale: same reproducible baseline as dev-strength smoke; avoids implying `scripted_vgc` /
Champions-mechanic coverage before bot supports Mega. Expanding policies is a **follow-up**, not
v0.

### 5.4 Hero team decision

**Do not reuse** `teams/fixed_team.txt` without revalidation — it was built for `gen9vgc2025regi`
and contains Reg-I meta (e.g. Flutter Mane) that may be illegal or suboptimal in Champions.

**Default (v0): single hero** — `teams/fixed_champions_v0.txt`

- One flexible M-A team curated from a public top-cut / high-usage core (document source).
- Used as `hero_team_path` in all smoke rows.
- **Switch to two heroes** only if provenance review shows no single team covers both TR and
  non-TR preview stress without extreme skew:
  - `teams/fixed_champions_v0_offense.txt`
  - `teams/fixed_champions_v0_tr.txt`
  - Smoke schedule then uses offense hero for dev cells, TR hero for held-out cells (document split).

Decision recorded in `PROVENANCE.md` (filesystem:
`showdown_bot/teams/panel_champions_v0/PROVENANCE.md`) §Hero.

## 6. Team provenance (required before commit)

File: `showdown_bot/teams/panel_champions_v0/PROVENANCE.md`

Per team (including hero), one row:

| Field | Required |
|-------|----------|
| `team_id` | panel id |
| `source` | URL or citation (Pikalytics, Limitless, Victory Road, Showdown paste, etc.) |
| `source_date` | ISO date accessed |
| `format_id` | validated format (post-P0) |
| `archetype` | from §5.2 |
| `validation_cmd` | exact command run |
| `validation_exit` | `0` |
| `team_hash` | from `load_panel` / `team_content_hash` |
| `notes` | adaptations from source (item/spread/ species subs) |

**Allowed sources:** public paste sites, tournament team reports, usage pages.

**Forbidden in this slice:** extracting teams from `cameronangliss/vgc-battle-logs` or
`vgc-battle-logs-sv` (separate import-audit track).

## 7. Artefacts & layout

### 7.0 Path rule (YAML vs filesystem)

Team **files** live under `showdown_bot/teams/` on disk. **References** in
`panel_champions_v0.yaml` and all schedules use gauntlet-relative paths only
(`teams/panel_champions_v0/<team>.txt`), identical to `panel_v001`. The gauntlet
and `load_panel(..., teams_root=<showdown_bot>)` resolve them; do not embed
`showdown_bot/` in YAML.

### 7.1 Filesystem layout (repo tree)

```
config/eval/panels/panel_champions_v0.yaml          # COMMIT after P3
config/eval/schedules/champions_v0_smoke_pilot.yaml # COMMIT — tiny pilot only

showdown_bot/teams/panel_champions_v0/
  PROVENANCE.md                                      # COMMIT
  goodstuff.txt / .packed
  tailwind_offense.txt / .packed
  trick_room.txt / .packed
  rain_offense.txt / .packed
  disruption.txt / .packed

showdown_bot/teams/fixed_champions_v0.txt            # COMMIT (+ .packed)
# OR fixed_champions_v0_offense.txt + fixed_champions_v0_tr.txt if two-hero path

data/eval/champions-panel-v0/                        # smoke outputs — prefer gitignore except report
  discovery/
    formats.js.snapshot                              # COMMIT (small)
    format-discovery-report.md                       # COMMIT
  smoke/
    results.jsonl                                    # local / optional commit if tiny
    seeds.jsonl
    champions-v0-smoke-report.md                     # COMMIT after P4
```

### 7.2 YAML path examples (committed schedules / panel)

```yaml
# config/eval/panels/panel_champions_v0.yaml — team_path values ONLY like this:
team_path: teams/panel_champions_v0/goodstuff.txt

# config/eval/schedules/champions_v0_smoke_pilot.yaml — hero/opp paths ONLY like this:
hero_team_path: teams/fixed_champions_v0.txt
opp_team_path: teams/panel_champions_v0/trick_room.txt
```

### 7.3 Pilot schedule (not strength run)

Generate via `generate_dev_schedule` **or** hand-write ≤10 rows:

- **Format:** confirmed BO1 ID (§3)
- **Cells:** 3 dev teams × `{heuristic, max_damage}` = 6 rows minimum; optionally +2 held-out
  rows with `confirm_heldout=True` → **8 rows** max for pilot
- **Seeds:** `seeds_per_cell=1`, `seed_base=champions-panel-v0-smoke`
- **Hero:** `fixed_champions_v0` (or split heroes per §5.4)

Reference shape: `config/eval/schedules/smoke_nonmirror.yaml`, `t4_smoke_v001.yaml` — but every
row uses Champions `format_id` and Champions team paths.

**Explicitly out:** schedules with >10 battles, held-out-only strength gates, paired A/B env arms.

## 8. Phase P4 — Pipeline compatibility smoke

Prove harness path only:

```bash
cd showdown_bot
# Fresh seeded server — same contract as T1b (tools/eval/patches/pokemon-showdown-seeded-battle.patch)
PYTHONHASHSEED=0 SHOWDOWN_BATTLE_SEED_BASE=champions-panel-v0-smoke \
  SHOWDOWN_EVAL_SEED_LOG=/tmp/champions-v0-seeds.jsonl \
  python -m showdown_bot.cli gauntlet \
    --schedule ../config/eval/schedules/champions_v0_smoke_pilot.yaml \
    --result-out /tmp/champions-v0-results.jsonl

python -m showdown_bot.cli eval-report \
  --run-a /tmp/champions-v0-results.jsonl \
  --seedlog-a /tmp/champions-v0-seeds.jsonl \
  --schedule ../config/eval/schedules/champions_v0_smoke_pilot.yaml \
  --panel ../config/eval/panels/panel_champions_v0.yaml \
  --out data/eval/champions-panel-v0/smoke/ \
  --mode dev
```

### 8.1 PASS criteria (pipeline)

| Check | PASS |
|-------|------|
| Battles complete | all schedule rows produce a result row |
| Safety | `crashes=0`, `invalid_choices=0` |
| Provenance | `panel_hash` in rows matches recomputed panel |
| `format_id` | constant and equals P0 primary ID |
| Report | `eval-report` exits 0 in `--mode dev` |

### 8.2 Known non-blockers vs hard blockers

**P4-only non-blocker (document, do not “fix” in this slice):**

- For **pipeline smoke only**: `load_format_config(format_id)` raises for the Champions ID →
  gauntlet runs with `book=None`, `priors=None` (`gauntlet._load_belief_deps` best-effort).
  Acceptable **only** because P4 tests harness plumbing, not decision quality.
- Winrate near zero / heuristic oddities on Mega teams — **not** a P4 pipeline failure.

**FormatConfig gate (applies beyond P4):**

Missing `config/formats/<champions_format_id>.yaml` is **not** a P4 non-blocker in general — it is a
**hard blocker** for any later **Strength-**, **Decision-Quality-**, or **paired McNemar** run on
`panel_champions_v0`, unless that run is explicitly specced as a **`book=None` / `priors=None`
degraded baseline** (hypothesis named upfront, not a default).

Concretely **forbidden without FormatConfig slice:**

- Large Champions dev-strength panel run intended to inform ship/strength decisions.
- **Champions vs Reg-I strength comparison** (cross-format winrate claims) — formats differ in
  mechanics, belief deps, and meta; comparison would confound panel change with missing format config.
- Treating P4 smoke winrate as a meaningful strength signal.

**Hard blocker (NO-GO for P4 and panel ship):**

- Server rejects format ID at challenge time.
- Widespread `invalid_choices` or crashes attributable to harness (not single-turn bot gap).
- `validate-team` passes locally but packed team fails at load-battle.

## 9. Data strategy note (`cameronangliss/vgc-battle-logs`)

This slice **does not** download VGC-Bench logs. Still answers the strategic question for the
follow-on import-audit:

| Dataset | Role while target = Reg I | Role when target = Champions M-A |
|---------|---------------------------|----------------------------------|
| `vgc-battle-logs-sv` | Primary human Reg-I archive | Stays Reg-I only; never mixed |
| `vgc-battle-logs` (active) | OOD / parser stress (`MECHANICALLY_SIMILAR`) | Becomes **primary human candidate** for M-A/M-B priors — **after** Part B ingest |

Panel v0 teams are **independent** of that promotion; import audit remains gated separately.

## 10. Acceptance checklist

- [ ] P0 report commits with **confirmed** live BO1 format ID (not guessed).
- [ ] P1 mechanics table filled; Reg-I hero **fails** Champions validation.
- [ ] All 5 panel teams + hero validate and pack cleanly.
- [ ] `panel_champions_v0.yaml` loads; `panel_hash` stable across reload.
- [ ] `PROVENANCE.md` complete for every team.
- [ ] Pilot schedule ≤10 battles runs with 0 crashes / 0 invalid choices.
- [ ] `eval-report` generates for smoke bundle.
- [ ] Verdict doc states **PIPELINE-READY** vs **BLOCKED** and recommends next strength-run target.

## 11. Decision output (for user gate after slice)

The smoke report must end with an explicit recommendation (evidence-backed, not a strength claim):

1. **Champions panel v0 + FormatConfig ready** → next large strength run *may* switch to
   `panel_champions_v0` (still requires Mega/Tera bot logic for meaningful winrate).
2. **Panel ready, FormatConfig missing** → **keep strength on Reg-I `panel_v001`**; Champions panel
   limited to pipeline soak / explicit degraded baselines only — **no** large strength run, **no**
   Champions-vs-Reg-I comparison until `config/formats/<id>.yaml` exists.
3. **Panel ready, bot not** → same as (2); format-yaml and battle-engine readiness are separate
   gates from panel freeze.
4. **NO-GO** → format or validation unstable; defer Champions panel; continue Reg-I panel.

## 12. Related specs (unchanged scope)

| Spec | Interaction |
|------|-------------|
| `2026-07-14-vgc-battle-logs-import-audit.md` | Parallel; no shared downloads in this slice |
| `2026-07-14-accuracy-default-on-strength-measurement.md` | Do not collide paths or schedules |
| Future `format_config` yaml for Champions | **Out of scope here** — **blocker** before any strength / decision-quality eval on this panel (§8.2); P4 smoke exempt |

---

**Review ask:** confirm primary format ID after P0, approve archetype table vs M-A meta, and
choose single- vs dual-hero default before team curation begins.
