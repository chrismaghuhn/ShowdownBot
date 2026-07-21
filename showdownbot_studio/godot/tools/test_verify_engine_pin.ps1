# Plan B Task B0 - unit tests for verify_engine_pin.ps1 (no Godot required).
# Editor and console EXEs covered separately for missing and mismatch.
$ErrorActionPreference = "Stop"

$ToolsDir = $PSScriptRoot
$VerifyScript = Join-Path $ToolsDir "verify_engine_pin.ps1"
$SumsPath = Join-Path $ToolsDir "ENGINE_SHA256SUMS"
$script:failures = 0

function Get-PinnedNames {
    $editor = $null
    $console = $null
    foreach ($line in Get-Content -LiteralPath $SumsPath) {
        if ($line -match '^\s*#' -or [string]::IsNullOrWhiteSpace($line)) { continue }
        $parts = $line -split '\s+', 2
        if ($parts.Count -lt 2) { continue }
        $name = $parts[1].Trim()
        if ($name -like "*_console.exe") { $console = $name }
        elseif ($name -like "*.exe.zip") { }
        elseif ($name -like "*.exe") { $editor = $name }
    }
    if (-not $editor -or -not $console) {
        throw "ENGINE_SHA256SUMS missing editor or console entry"
    }
    return [pscustomobject]@{ Editor = $editor; Console = $console }
}

function New-TempEngineDir {
    $dir = Join-Path ([System.IO.Path]::GetTempPath()) ("sb-engine-pin-" + [guid]::NewGuid().ToString("n"))
    New-Item -ItemType Directory -Path $dir | Out-Null
    return $dir
}

function Write-DummyFile {
    param([string]$Path)
    [System.IO.File]::WriteAllBytes($Path, [byte[]](1..32))
}

function Invoke-Verify {
    param([string]$EngineDir)
    $out = & powershell -NoProfile -File $VerifyScript -EngineDir $EngineDir 2>&1 | Out-String
    return [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = $out }
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
        throw $Message
    }
}

function Run-Case {
    param([string]$Name, [scriptblock]$Body)
    try {
        & $Body
        Write-Host ("PASS: " + $Name)
    }
    catch {
        Write-Host ("FAIL: " + $Name + " - " + $_.Exception.Message)
        $script:failures++
    }
}

if (-not (Test-Path -LiteralPath $VerifyScript)) {
    Write-Host ("RED: verify_engine_pin.ps1 missing at " + $VerifyScript)
    exit 1
}

$pins = Get-PinnedNames
$RealEngine = Join-Path $ToolsDir "engine"
$RealEditor = Join-Path $RealEngine $pins.Editor
$RealConsole = Join-Path $RealEngine $pins.Console

Run-Case "missing_editor_exe" {
    $dir = New-TempEngineDir
    try {
        Write-DummyFile (Join-Path $dir $pins.Console)
        $r = Invoke-Verify -EngineDir $dir
        Assert-True ($r.ExitCode -eq 2) ("expected exit 2, got " + $r.ExitCode)
        Assert-True ($r.Output -match "engine_missing") "expected engine_missing in output"
    }
    finally {
        Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Run-Case "missing_console_exe" {
    $dir = New-TempEngineDir
    try {
        Write-DummyFile (Join-Path $dir $pins.Editor)
        $r = Invoke-Verify -EngineDir $dir
        Assert-True ($r.ExitCode -eq 2) ("expected exit 2, got " + $r.ExitCode)
        Assert-True ($r.Output -match "engine_missing") "expected engine_missing in output"
    }
    finally {
        Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Run-Case "mismatch_editor_exe" {
    if (-not (Test-Path -LiteralPath $RealConsole)) {
        throw "need real console EXE under tools/engine for this case"
    }
    $dir = New-TempEngineDir
    try {
        Copy-Item -LiteralPath $RealConsole -Destination (Join-Path $dir $pins.Console)
        Write-DummyFile (Join-Path $dir $pins.Editor)
        $r = Invoke-Verify -EngineDir $dir
        Assert-True ($r.ExitCode -ne 0) ("expected non-zero exit, got " + $r.ExitCode)
        Assert-True ($r.Output -match "engine_pin_mismatch") "expected engine_pin_mismatch"
    }
    finally {
        Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Run-Case "mismatch_console_exe" {
    if (-not (Test-Path -LiteralPath $RealEditor)) {
        throw "need real editor EXE under tools/engine for this case"
    }
    $dir = New-TempEngineDir
    try {
        Copy-Item -LiteralPath $RealEditor -Destination (Join-Path $dir $pins.Editor)
        Write-DummyFile (Join-Path $dir $pins.Console)
        $r = Invoke-Verify -EngineDir $dir
        Assert-True ($r.ExitCode -ne 0) ("expected non-zero exit, got " + $r.ExitCode)
        Assert-True ($r.Output -match "engine_pin_mismatch") "expected engine_pin_mismatch"
    }
    finally {
        Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Run-Case "missing_both_exes" {
    $dir = New-TempEngineDir
    try {
        $r = Invoke-Verify -EngineDir $dir
        Assert-True ($r.ExitCode -eq 2) ("expected exit 2, got " + $r.ExitCode)
        Assert-True ($r.Output -match "engine_missing") "expected engine_missing"
    }
    finally {
        Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

if ($script:failures -gt 0) {
    Write-Host ("FAILED: " + $script:failures + " case(s)")
    exit 1
}
Write-Host "ALL PASS"
exit 0
