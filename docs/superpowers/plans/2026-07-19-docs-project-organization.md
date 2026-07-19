# Documentation Project Organization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** PROPOSED

**Goal:** Replace the flat workflow-oriented documentation layout with a project-centered layout while preserving every document, updating every live reference, and leaving frozen evidence byte-identical.

**Architecture:** A deterministic old-path to new-path map classifies all 117 workflow documents into six projects and four document kinds. One atomic migration commit moves all documents with `git mv`, rewrites mutable references, adds navigation and future-placement guidance, and verifies file accounting, links, tests, and frozen-evidence identity.

**Tech Stack:** Git worktrees, Git rename tracking, PowerShell 7, Markdown, Python 3 read-only validation, pytest.

---

## Files and ownership

**Create during implementation:**

- `docs/README.md` — reader-facing documentation entry point.
- `docs/PATH_MIGRATION.md` — complete old-path to new-path mapping.
- Project directories under `docs/projects/` for `champions`, `accuracy`,
  `evaluation`, `learning`, `core-bot`, and `operations` — project-owned
  documents moved without filename changes.
- `docs/guides/heuristic-bot/` — the four existing heuristic-bot guides.

**Move:**

- All 117 tracked files under `docs/superpowers/` after this plan is committed.
- All four tracked files under `docs/heuristic_bot/`.

**Modify:**

- `CLAUDE.md` — future document placement rule.
- `README.md` — documentation table points to `docs/README.md` and `docs/projects/`.
- Mutable tracked files containing exact old paths, including `docs/ROADMAP.md`,
  `docs/PROJECT_INDEX.md`, source docstrings, tests, reports, and studio docs.

**Must remain byte-identical:**

- `data/eval/**` — frozen evidence.
- Every pinned report discovered by the pre-migration hash scan.

## Deterministic classification contract

The implementation uses this function verbatim. It classifies the plan itself and
the approved design as `operations`, sends both Fable reviews to `evaluation`, and
handles the one root-level rollout report explicitly.

```powershell
function Get-DocsDestination([string] $source) {
    $source = $source.Replace('\', '/')
    $name = Split-Path $source -Leaf

    if ($source.StartsWith('docs/heuristic_bot/')) {
        return 'docs/guides/heuristic-bot/' + $name
    }
    if (-not $source.StartsWith('docs/superpowers/')) {
        throw "Not a migration source: $source"
    }

    if ($source -eq 'docs/superpowers/2026-06-30-1d-rollout-export-probe-report.md') {
        return 'docs/projects/core-bot/audits/' + $name
    }

    if ($source.Contains('/reviews/')) {
        $project = 'evaluation'
        $kind = 'reviews'
    } else {
        if ($name -match 'docs-project-organization') {
            $project = 'operations'
        } elseif ($name -match 'champions|i7b-a-status') {
            $project = 'champions'
        } elseif ($name -match 'accuracy-') {
            $project = 'accuracy'
        } elseif ($name -match '2b35|t4b-|t4c-|t5-|t6-|candidate-vs-baseline|diagnostics-v0|vgc-battle-logs') {
            $project = 'evaluation'
        } elseif ($name -match 'ml-reranker|1b-A-candidate|2b1-|2b2a-|2b3-|2b25a-|2b2b-|2b4-|2b5a-|2c-|dataset-reranker|teacher-disagreement|value-calibration') {
            $project = 'learning'
        } elseif ($name -match 'claude-md|restore-root-claude') {
            $project = 'operations'
        } else {
            $project = 'core-bot'
        }

        if ($name -match 'audit\.md$|strength-measurement\.md$') {
            $kind = 'audits'
        } elseif ($source.Contains('/specs/') -and $name -match '-i[34]-plan\.md$') {
            $kind = 'plans'
        } elseif ($source.Contains('/plans/')) {
            $kind = 'plans'
        } else {
            $kind = 'specs'
        }
    }

    return "docs/projects/$project/$kind/$name"
}
```

Expected post-classification counts:

| Project | Specs | Plans | Audits | Reviews | Total |
|---|---:|---:|---:|---:|---:|
| accuracy | 4 | 3 | 1 | 0 | 8 |
| champions | 8 | 11 | 2 | 0 | 21 |
| core-bot | 12 | 16 | 1 | 0 | 29 |
| evaluation | 7 | 13 | 1 | 2 | 23 |
| learning | 15 | 16 | 1 | 0 | 32 |
| operations | 2 | 2 | 0 | 0 | 4 |
| **Total** | **48** | **61** | **6** | **2** | **117** |

---

### Task 1: Prove the baseline and build the complete move map

**Files:**

- Read: `docs/superpowers/**`
- Read: `docs/heuristic_bot/**`
- Read: `data/eval/**`
- No file changes in this task.

- [ ] **Step 1: Verify the isolated branch and clean tree**

Run from `C:\Users\chris\Documents\SHowdown BOt\.worktrees\docs-project-organization`:

```powershell
git branch --show-current
git status --short
git rev-parse --short HEAD
```

Expected: branch `codex/docs-project-organization`, empty status, and HEAD containing
the approved design plus this plan.

- [ ] **Step 2: Capture the immutable evidence tree identity**

```powershell
$evidenceTree = (git rev-parse HEAD:data/eval).Trim()
if ($evidenceTree -ne 'ff6bf74868a35c5615afde81a9427796491a32bc') {
    throw "Unexpected data/eval tree: $evidenceTree"
}
```

Expected: no output and exit 0.

- [ ] **Step 3: Build the source list and deterministic destination map**

Define `Get-DocsDestination` exactly as shown in the classification contract, then run:

```powershell
$sources = @(
    git ls-files 'docs/superpowers/**' 'docs/heuristic_bot/**'
)
if ($sources.Count -ne 121) {
    throw "Expected 117 workflow docs + 4 guides, got $($sources.Count)"
}

$moves = foreach ($source in $sources) {
    [pscustomobject]@{
        Old = $source.Replace('\', '/')
        New = Get-DocsDestination $source
    }
}

if (($moves.New | Sort-Object -Unique).Count -ne 121) {
    throw 'Two source documents map to one destination'
}
if (@($moves | Where-Object { $_.Old -eq $_.New }).Count -ne 0) {
    throw 'A migration source maps to itself'
}
```

Expected: no exception.

- [ ] **Step 4: Verify exact project totals before touching files**

```powershell
$workflow = $moves | Where-Object { $_.New.StartsWith('docs/projects/') }
$actual = $workflow | ForEach-Object {
    $parts = $_.New.Split('/')
    "$($parts[2])/$($parts[3])"
} | Group-Object | ForEach-Object { "$($_.Name)=$($_.Count)" } | Sort-Object

$expected = @(
    'accuracy/audits=1','accuracy/plans=3','accuracy/specs=4',
    'champions/audits=2','champions/plans=11','champions/specs=8',
    'core-bot/audits=1','core-bot/plans=16','core-bot/specs=12',
    'evaluation/audits=1','evaluation/plans=13','evaluation/reviews=2','evaluation/specs=7',
    'learning/audits=1','learning/plans=16','learning/specs=15',
    'operations/plans=2','operations/specs=2'
) | Sort-Object

if (Compare-Object $expected $actual) {
    throw "Classification totals differ:`n$($actual -join "`n")"
}
```

Expected: no exception.

- [ ] **Step 5: Demonstrate the layout guard is RED before migration**

```powershell
if (Test-Path docs/projects) { throw 'docs/projects unexpectedly exists before migration' }
if (-not (Test-Path docs/superpowers)) { throw 'old workflow layout unexpectedly absent' }
Write-Output 'RED: project layout absent; old workflow layout present'
```

Expected: `RED: project layout absent; old workflow layout present`.

---

### Task 2: Move all documents and generate the migration ledger

**Files:**

- Move: all paths in `$moves`
- Create: `docs/PATH_MIGRATION.md`

- [ ] **Step 1: Rebuild and revalidate `$moves`**

Repeat Task 1 Steps 3 and 4 in the same PowerShell session. Do not reconstruct
the map from memory or filename inspection.

- [ ] **Step 2: Create destination directories and move with Git**

```powershell
foreach ($move in $moves | Sort-Object Old) {
    $parent = Split-Path $move.New -Parent
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    git mv -- $move.Old $move.New
    if ($LASTEXITCODE -ne 0) {
        throw "git mv failed: $($move.Old) -> $($move.New)"
    }
}
```

Expected: 121 successful tracked renames.

- [ ] **Step 3: Remove only the now-empty legacy directory trees**

```powershell
$repoRoot = [IO.Path]::GetFullPath((Get-Location).Path)
foreach ($relative in @('docs/superpowers', 'docs/heuristic_bot')) {
    $absolute = [IO.Path]::GetFullPath((Join-Path $repoRoot $relative))
    if (-not $absolute.StartsWith($repoRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Legacy path escaped repository root: $absolute"
    }
    if (Test-Path $absolute) {
        $remainingFiles = @(Get-ChildItem -LiteralPath $absolute -Recurse -File -Force)
        if ($remainingFiles.Count -ne 0) {
            throw "Legacy directory still contains files: $absolute"
        }
        Remove-Item -LiteralPath $absolute -Recurse
    }
}
```

Expected: only empty directories are removed; both legacy roots are absent.

- [ ] **Step 4: Generate the complete migration ledger**

```powershell
$lines = @(
    '# Documentation Path Migration',
    '',
    'On 2026-07-19 the repository documentation was reorganized by project.',
    'Historical evidence may still cite an old path; use this table to find its current location.',
    '',
    '| Old path | New path |',
    '|---|---|'
)
$lines += $moves | Sort-Object Old | ForEach-Object {
    "| ``$($_.Old)`` | ``$($_.New)`` |"
}
[IO.File]::WriteAllLines(
    (Join-Path (Get-Location) 'docs/PATH_MIGRATION.md'),
    $lines,
    [Text.UTF8Encoding]::new($false)
)
```

Expected: 121 mapping rows, UTF-8 without BOM.

- [ ] **Step 5: Prove the move accounting before reference edits**

```powershell
if (Test-Path docs/superpowers) { throw 'docs/superpowers still exists' }
if (Test-Path docs/heuristic_bot) { throw 'docs/heuristic_bot still exists' }
if (@(git ls-files 'docs/projects/**').Count -ne 117) { throw 'wrong project-doc count' }
if (@(git ls-files 'docs/guides/heuristic-bot/**').Count -ne 4) { throw 'wrong guide count' }
if ((Select-String -Path docs/PATH_MIGRATION.md -Pattern '^\| `docs/' | Measure-Object).Count -ne 121) {
    throw 'migration ledger does not contain 121 rows'
}
```

Expected: no exception.

---

### Task 3: Rewrite every mutable old-path reference

**Files:**

- Modify: tracked mutable text files containing paths from `$moves`.
- Do not modify: `data/eval/**` or any report proven pinned by hash.

- [ ] **Step 1: Rebuild `$moves` from the committed ledger**

Because the old files have moved, parse the ledger rather than scanning old directories:

```powershell
$moves = Get-Content docs/PATH_MIGRATION.md | ForEach-Object {
    if ($_ -match '^\| `([^`]+)` \| `([^`]+)` \|$') {
        [pscustomobject]@{ Old = $matches[1]; New = $matches[2] }
    }
} | Where-Object { $_ }
if ($moves.Count -ne 121) { throw "Expected 121 migration rows, got $($moves.Count)" }
```

- [ ] **Step 2: Identify pinned reports before rewriting**

```powershell
$pinnedReports = @()
foreach ($report in @(git ls-files 'reports/**')) {
    $name = Split-Path $report -Leaf
    $hits = @(git grep -l --fixed-strings $name -- 'data/eval/**' 2>$null)
    if ($hits.Count -gt 0) { $pinnedReports += $report }
}
$pinnedReports = @($pinnedReports | Sort-Object -Unique)
$pinnedReports
```

Expected: the exact pinned-report list is printed in the task log and excluded below.

- [ ] **Step 3: Apply exact full-path replacements mechanically**

```powershell
$candidates = @(git grep -Il -e 'docs/superpowers' -e 'docs/heuristic_bot' -- `
    ':!data/eval/**' `
    ':!docs/PATH_MIGRATION.md' `
    ':!docs/projects/operations/specs/2026-07-19-docs-project-organization-design.md' `
    ':!docs/projects/operations/plans/2026-07-19-docs-project-organization.md')
$candidates = $candidates | Where-Object { $pinnedReports -notcontains $_ }

foreach ($file in $candidates) {
    $text = [IO.File]::ReadAllText($file)
    $updated = $text
    foreach ($move in $moves | Sort-Object { $_.Old.Length } -Descending) {
        $updated = $updated.Replace($move.Old, $move.New)
    }
    $fragments = [ordered]@{
        'docs/superpowers/reviews/' = 'docs/projects/evaluation/reviews/'
        'docs/superpowers/plans/2026-07-15-champions-mega-i7a' = 'docs/projects/champions/plans/2026-07-15-champions-mega-i7a'
        'docs/superpowers/plans/2026-07-10-decision-error-atlas.md' = 'docs/projects/learning/plans/2026-07-10-decision-error-atlas.md'
        'docs/superpowers/plans/2026-06-29-phase' = 'docs/projects/core-bot/plans/2026-06-29-phase'
        'docs/superpowers/specs/2026-07-11-fast-board-protect-' = 'docs/projects/core-bot/specs/2026-07-11-fast-board-protect-'
        '| `docs/superpowers/` | Approved designs and implementation plans |' = '| [`docs/`](docs/README.md) | Project-organized designs, plans, audits, reviews, guides, roadmap, and index |'
        'docs/superpowers/' = 'docs/projects/'
        'docs/heuristic_bot/' = 'docs/guides/heuristic-bot/'
    }
    foreach ($oldFragment in $fragments.Keys) {
        $updated = $updated.Replace($oldFragment, $fragments[$oldFragment])
    }
    if ($updated -ne $text) {
        [IO.File]::WriteAllText($file, $updated, [Text.UTF8Encoding]::new($false))
    }
}
```

Expected: exact file references move to their exact destination; generic directory
descriptions move to the new project/guides roots.

- [ ] **Step 4: Resolve line-wrapped residuals deterministically**

```powershell
$allowed = @(
    'docs/PATH_MIGRATION.md',
    'docs/projects/operations/specs/2026-07-19-docs-project-organization-design.md',
    'docs/projects/operations/plans/2026-07-19-docs-project-organization.md'
)
$residual = @(git grep -n -e 'docs/superpowers' -e 'docs/heuristic_bot' -- ':!data/eval/**')
$unexpected = $residual | Where-Object {
    $path = ($_ -split ':', 2)[0]
    $allowed -notcontains $path -and $pinnedReports -notcontains $path
}
if ($unexpected.Count -gt 0) {
    $unexpected
    throw 'Unexpected old-path reference remains; use PATH_MIGRATION basename lookup to replace it'
}
```

Expected: no unexpected residual. Any residual is a mapping defect; stop and add
one exact fragment replacement backed by the migration ledger before continuing.

---

### Task 4: Add navigation and prevent layout regression

**Files:**

- Create: `docs/README.md`
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Create `docs/README.md`**

Use `apply_patch` to create this exact content:

```markdown
# Documentation

Start with [ROADMAP](ROADMAP.md) for priorities and
[PROJECT_INDEX](PROJECT_INDEX.md) for the complete project status.

## Projects

| Project | Scope |
|---|---|
| [Champions](projects/champions/) | Champions format, panel, Mega, and latency work |
| [Accuracy](projects/accuracy/) | Hit probability and accuracy gates |
| [Evaluation](projects/evaluation/) | Harnesses, schedules, reports, heldout gates, and provenance |
| [Learning](projects/learning/) | Reranker, datagen, sampling, teacher, and calibration work |
| [Core bot](projects/core-bot/) | Client, engine, heuristic, opponent knowledge, speed, and calc |
| [Operations](projects/operations/) | Repository and agent-operation documentation |

Cross-project architecture lives in [architecture](architecture/). User-facing
material lives in [guides](guides/). Historical old paths are resolved through
[PATH_MIGRATION](PATH_MIGRATION.md).

Within a project, use `specs/`, `plans/`, `audits/`, and `reviews/` only when that
kind exists. Do not recreate `docs/superpowers/`.
```

- [ ] **Step 2: Add project-local README indexes**

Run this exact generator; it links only child directories that actually exist:

```powershell
$projects = [ordered]@{
    'champions'  = @('Champions', 'Champions format, panel, Mega, and latency work')
    'accuracy'   = @('Accuracy', 'Hit probability and accuracy gates')
    'evaluation' = @('Evaluation', 'Harnesses, schedules, reports, heldout gates, and provenance')
    'learning'   = @('Learning', 'Reranker, datagen, sampling, teacher, and calibration work')
    'core-bot'   = @('Core Bot', 'Client, engine, heuristic, opponent knowledge, speed, and calc')
    'operations' = @('Operations', 'Repository and agent-operation documentation')
}
foreach ($slug in $projects.Keys) {
    $title, $scope = $projects[$slug]
    $dir = "docs/projects/$slug"
    $lines = @("# $title", '', $scope + '.', '', '## Documents', '')
    foreach ($kind in @('specs', 'plans', 'audits', 'reviews')) {
        if (Test-Path "$dir/$kind") {
            $label = (Get-Culture).TextInfo.ToTitleCase($kind)
            $lines += "- [$label]($kind/)"
        }
    }
    [IO.File]::WriteAllLines(
        (Join-Path (Get-Location) "$dir/README.md"),
        $lines,
        [Text.UTF8Encoding]::new($false)
    )
}
```

Expected: six project README files; none links an absent directory.

- [ ] **Step 3: Verify the root README documentation row**

Task 3's exact fragment migration must have replaced the old row with:

```markdown
| [`docs/`](docs/README.md) | Project-organized designs, plans, audits, reviews, guides, roadmap, and index |
```

Run:

```powershell
if (@(Select-String -Path README.md -SimpleMatch '| [`docs/`](docs/README.md) | Project-organized designs, plans, audits, reviews, guides, roadmap, and index |').Count -ne 1) {
    throw 'Root README documentation row is missing or duplicated'
}
```

Expected: no exception.

- [ ] **Step 4: Add the future-placement rule to `CLAUDE.md`**

Append this section without changing other instructions:

```markdown
## Documentation placement

Store new documentation by subject under `docs/projects/<project>/`: designs and
contracts in `specs/`, implementation plans in `plans/`, audits in `audits/`, and
reviews in `reviews/`. Put user-facing material in `docs/guides/<topic>/` and
cross-project architecture in `docs/architecture/`. Do not recreate
`docs/superpowers/`; see `docs/README.md` and `docs/PATH_MIGRATION.md`.
```

- [ ] **Step 5: Re-run exact-reference replacement for the new files**

Repeat Task 3 Steps 1, 3, and 4. The only permitted old-path strings remain the
historical descriptions in the migration ledger, approved design, and this plan,
plus immutable evidence/pinned reports.

---

### Task 5: Prove the migration is complete and behavior-neutral

**Files:**

- Verify all changed files.
- No new implementation changes unless a gate identifies a specific defect.

- [ ] **Step 1: Verify layout counts and uniqueness**

```powershell
$projectFiles = @(git ls-files 'docs/projects/**' | Where-Object { $_ -notmatch '/README\.md$' })
if ($projectFiles.Count -ne 117) { throw "Expected 117 project docs, got $($projectFiles.Count)" }
if (@(git ls-files 'docs/guides/heuristic-bot/**').Count -ne 4) { throw 'Expected 4 guides' }
if (Test-Path docs/superpowers) { throw 'docs/superpowers was recreated' }
if (Test-Path docs/heuristic_bot) { throw 'docs/heuristic_bot was recreated' }
if (($projectFiles | Sort-Object -Unique).Count -ne 117) {
    throw 'Duplicate complete destination path detected'
}
$duplicateBasenames = @(
    $projectFiles | ForEach-Object { Split-Path $_ -Leaf } |
    Group-Object | Where-Object Count -gt 1 | Select-Object -ExpandProperty Name
)
if (Compare-Object @('2026-07-01-2b35-diverse-opponent-eval-harness.md') $duplicateBasenames) {
    throw "Unexpected duplicate basename set: $($duplicateBasenames -join ', ')"
}
```

Expected: exit 0. The single reviewed duplicate basename is a distinct evaluation
spec and plan; complete destination paths remain unique and neither file is renamed.

- [ ] **Step 2: Verify frozen evidence identity**

```powershell
$evidenceTree = (git rev-parse HEAD:data/eval).Trim()
if ($evidenceTree -ne 'ff6bf74868a35c5615afde81a9427796491a32bc') {
    throw "Frozen evidence changed: $evidenceTree"
}
git diff --exit-code main -- data/eval
```

Expected: no diff and exit 0.

- [ ] **Step 3: Verify old-path allowlist only**

Run Task 3 Step 4. Expected: no unexpected residual references.

- [ ] **Step 4: Validate relative Markdown links**

Run this read-only checker from the repository root:

```powershell
@'
import pathlib, re, sys

root = pathlib.Path.cwd()
bad = []
pattern = re.compile(r'\[[^\]]*\]\(([^)]+)\)')
fenced = re.compile(r'```.*?```', re.S)
root_relative = ('docs/', 'reports/', 'showdown_bot/', 'showdownbot_studio/',
                 'data/', 'config/', 'tools/')
for path in (root / 'docs').rglob('*.md'):
    text = fenced.sub('', path.read_text(encoding='utf-8'))
    for raw in pattern.findall(text):
        target = raw.strip().strip('<>')
        if not target or target.startswith(('#', 'http://', 'https://', 'mailto:')):
            continue
        target = target.split('#', 1)[0]
        if not target:
            continue
        resolved = ((root / target) if target.startswith(root_relative)
                    else (path.parent / target)).resolve()
        if not resolved.exists():
            bad.append(f'{path.relative_to(root).as_posix()} -> {raw}')
known_missing = {
    '2026-06-29-phase2-heuristic-bot.md',
    '2026-06-29-phase3-imitation.md',
    '2026-06-29-phase4-self-play.md',
    '2026-06-29-phase5-scale.md',
}
actual_missing = {entry.rsplit('/', 1)[-1] for entry in bad}
if actual_missing != known_missing or len(bad) != 4:
    print('\n'.join(bad))
    sys.exit(1)
print('NO NEW BROKEN DOC LINKS; 4 PRE-EXISTING FUTURE-PHASE LINKS ALLOWLISTED')
'@ | python -
```

Expected: `NO NEW BROKEN DOC LINKS; 4 PRE-EXISTING FUTURE-PHASE LINKS ALLOWLISTED`.

- [ ] **Step 5: Run the documentation-path consumer tests**

```powershell
Set-Location showdown_bot
python -m pytest -q `
  tests/test_decision_profile_writer.py `
  tests/test_cache_sizes.py `
  tests/test_calc_counters.py `
  tests/test_baselines.py `
  tests/test_run_manifest.py `
  tests/i7a/test_i7a_trace_v3.py
Set-Location ..
```

Expected: exit 0 with the pre-existing skip/xfail set unchanged.

- [ ] **Step 6: Run the full suite**

```powershell
Set-Location showdown_bot
python -m pytest -q
Set-Location ..
```

Expected: exit 0; reconcile the pass count and name the unchanged skip/xfail set
in the implementation report.

- [ ] **Step 7: Verify whitespace, LF, and scope**

```powershell
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed' }
git status --short
git diff --name-only main -- data/eval
```

Expected: clean diff check, no `data/eval` output, and only the planned migration,
navigation, guidance, and exact-reference files in status.

---

### Task 6: Commit the atomic migration and stop for review

**Files:**

- Stage all verified migration files from Tasks 2–5.
- Do not stage unrelated files.

- [ ] **Step 1: Stage the exact migration scope**

```powershell
git add -A -- docs CLAUDE.md README.md reports showdown_bot showdownbot_studio
git diff --cached --check
git diff --cached --name-status
```

Expected: renames under `docs/`, new navigation/migration files, and only exact
reference updates elsewhere. No `data/eval` path may appear.

- [ ] **Step 2: Re-run the frozen-evidence and stale-reference gates on the index**

```powershell
if (git diff --cached --name-only | Select-String '^data/eval/') {
    throw 'Frozen evidence is staged'
}
```

Then repeat Task 3 Step 4 and Task 5 Steps 1–4. Expected: all green.

- [ ] **Step 3: Commit once so moves and references are atomic**

```powershell
git commit -m "docs: organize documentation by project"
```

Expected: one implementation commit containing the complete migration.

- [ ] **Step 4: Verify the committed state**

```powershell
git status --short
git diff --check main..HEAD
git log --oneline --decorate -5
```

Expected: clean tree; the approved design/plan commits followed by the single
atomic migration commit. Do not push or open a PR without separate authorization.
