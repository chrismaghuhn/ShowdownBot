# Assert a gdUnit4 headless run was not silently truncated (Plan F Sec.3.2, binding).
#
# Why this exists: gdUnit4's GdUnitTestCIRunner defaults fail_fast(true)
# (GdUnitTestCIRunner.gd:109); run_gdunit_headless.ps1 always passes -c to disable it, but a
# passing CI step is not evidence that flag would still catch a regression -- Plan F Sec.0.6
# found a run that silently reported only 14/33 executed test cases as a complete, "PASSED" run,
# with nothing in the console summary or exit code flagging it. Only the JUnit XML's declared
# per-suite `tests` count disagreeing with the number of written <testcase> elements revealed it.
# This script asserts that agreement directly instead of trusting the flag alone.
#
# What "declared" means here: for each <testsuite>, its own `tests` attribute is gdUnit's
# DISCOVERY-time count (set once, before the suite runs -- GdUnitTestSuiteReport._init, never
# mutated afterward: godot/addons/gdUnit4/src/reporters/GdUnitTestSuiteReport.gd:8-13). Cross-checked
# directly against a source-level grep of top-level `func test_` declarations in the suite's own
# .gd file (resolved from the testsuite's `package`+`name` attributes -- verified against a real
# run, 2026-07-25: e.g. name="test_bundle_validator" package="tests/bundle" tests="44", and
# `grep -cE "^\s*func test_" tests/bundle/test_bundle_validator.gd` independently also returns 44).
# Using two independently-computed counts (gdUnit's own discovery total, and a source-level grep)
# catches either one being wrong, not just a mismatch between run and declaration.
#
# Assumption this rests on (Plan F Sec.3.2, P2-3): the 1:1 "one func test_ line == one discovered
# test case" mapping holds only while no gdUnit PARAMETERIZED test exists in this suite -- a single
# `func test_x` under a parameter-source annotation can expand into many discovered/executed cases,
# which would still agree with gdUnit's own `tests` attribute (that count is post-expansion) but
# would break the separate source-grep cross-check on its own. Verified absent in this repo:
# `grep -rn "test_parameters" godot/tests` returns nothing (2026-07-25). If parameterized tests are
# ever introduced, the source-grep half of this check must be redefined per declared parameter set;
# it will not fail loudly on its own -- whoever adds the first parameterized test must update this
# script by hand.
param(
    [string]$ReportsDir = (Join-Path $PSScriptRoot "..\reports"),
    [string]$GodotRoot = (Split-Path $PSScriptRoot -Parent)
)

$ErrorActionPreference = "Stop"

function Write-Reason {
    param([string]$Code, [string]$Detail)
    Write-Host ("ERROR: " + $Code + " - " + $Detail)
}

if (-not (Test-Path -LiteralPath $ReportsDir)) {
    Write-Reason "report_missing" ("reports dir not found: " + $ReportsDir + " -- did run_gdunit_headless.ps1 run first?")
    exit 2
}

# gdUnit4 keeps a report-history: report_1, report_2, ... -- the run that just completed is the
# most recently written one, not necessarily the highest-numbered one (history rotates).
$latestReport = Get-ChildItem -LiteralPath $ReportsDir -Directory -Filter "report_*" |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $latestReport) {
    Write-Reason "report_missing" ("no report_* directory under " + $ReportsDir)
    exit 2
}

$resultsPath = Join-Path $latestReport.FullName "results.xml"
if (-not (Test-Path -LiteralPath $resultsPath)) {
    Write-Reason "report_missing" ("results.xml not found at " + $resultsPath)
    exit 2
}

[xml]$xml = Get-Content -LiteralPath $resultsPath -Raw
$suites = @($xml.testsuites.testsuite)

if ($suites.Count -eq 0) {
    Write-Reason "no_suites" ("results.xml at " + $resultsPath + " declares zero <testsuite> elements -- nothing was verified")
    exit 2
}

$failures = @()
foreach ($suite in $suites) {
    $declaredByGdUnit = [int]$suite.tests
    $writtenTestcases = @($suite.testcase).Count
    $gdPath = Join-Path $GodotRoot (Join-Path $suite.package ($suite.name + ".gd"))

    if (-not (Test-Path -LiteralPath $gdPath)) {
        $failures += ("suite '" + $suite.name + "': source file not found at resolved path " + $gdPath)
        continue
    }
    $declaredBySource = @(Select-String -LiteralPath $gdPath -Pattern '^\s*func\s+test_\w*\s*\(').Count

    if ($writtenTestcases -ne $declaredByGdUnit) {
        $failures += ("suite '" + $suite.name + "' (" + $gdPath + "): gdUnit declared " + $declaredByGdUnit + " tests at discovery time, but only " + $writtenTestcases + " <testcase> elements were written -- run was truncated (executed+skipped != declared)")
    }
    elseif ($writtenTestcases -ne $declaredBySource) {
        $failures += ("suite '" + $suite.name + "' (" + $gdPath + "): " + $writtenTestcases + " <testcase> elements written, but source declares " + $declaredBySource + " top-level 'func test_' -- gdUnit's own discovery count and the source disagree")
    }
}

if ($failures.Count -gt 0) {
    Write-Host ("Truncation guard FAILED (" + $failures.Count + " of " + $suites.Count + " suites):")
    foreach ($f in $failures) { Write-Host ("  - " + $f) }
    exit 1
}

Write-Host ("Truncation guard OK: " + $suites.Count + " suites, executed+skipped test cases match gdUnit's own discovery count and the source's declared 'func test_' count.")
exit 0
