# Run gdUnit4 headless on the pinned Godot 4.5.2 console EXE (Plan B B0).
# Always verifies editor + console pins before launch.
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$GdUnitArgs
)

$ErrorActionPreference = "Stop"
$ToolsDir = $PSScriptRoot
$ProjectRoot = Split-Path -Parent $ToolsDir
$EngineDir = Join-Path $ToolsDir "engine"
$SumsPath = Join-Path $ToolsDir "ENGINE_SHA256SUMS"

& (Join-Path $ToolsDir "verify_engine_pin.ps1") -EngineDir $EngineDir
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$consoleName = $null
foreach ($line in Get-Content -LiteralPath $SumsPath) {
    if ($line -match '^\s*#' -or [string]::IsNullOrWhiteSpace($line)) { continue }
    $parts = $line -split '\s+', 2
    if ($parts.Count -lt 2) { continue }
    $name = $parts[1].Trim()
    if ($name -like "*_console.exe") { $consoleName = $name }
}
if (-not $consoleName) {
    Write-Host "ERROR: engine_missing - no console EXE in ENGINE_SHA256SUMS"
    exit 2
}

$godot = Join-Path $EngineDir $consoleName
$godotCache = Join-Path $ProjectRoot ".godot"
if (-not (Test-Path -LiteralPath (Join-Path $godotCache "global_script_class_cache.cfg"))) {
    Write-Host "Importing project (first run) to register global classes..."
    & $godot --path $ProjectRoot --headless --import
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Push-Location $ProjectRoot
try {
    # --ignoreHeadlessMode: Studio Plan B tests are non-UI; gdUnit4 otherwise exits 103.
    # -c: gdUnit4's GdUnitTestCIRunner defaults fail_fast(true) (GdUnitTestCIRunner.gd:109),
    # so a suite aborts at its first failure and every remaining test goes silently
    # unattempted -- neither the summary line nor the exit code says so. Always pass -c so a
    # truncated run can't happen by accident; it is not exposed as an opt-in switch on purpose.
    $argList = @(
        "--path", $ProjectRoot,
        "--headless",
        "-s", "res://addons/gdUnit4/bin/GdUnitCmdTool.gd",
        "--ignoreHeadlessMode",
        "-c"
    )
    if ($GdUnitArgs -and $GdUnitArgs.Count -gt 0) {
        $argList += $GdUnitArgs
    }
    Write-Host ("Running: " + $godot + " " + ($argList -join " "))
    & $godot @argList
    $code = $LASTEXITCODE
}
finally {
    Pop-Location
}
exit $code
