# Verify local Godot 4.5.2-stable pin (Plan B §0.1).
# Always checks editor + console EXE digests. ZIP digest required when ZIP is present.
param(
    [string]$EngineDir = ""
)

$ErrorActionPreference = "Stop"

$ToolsDir = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($EngineDir)) {
    $EngineDir = Join-Path $ToolsDir "engine"
}
$SumsPath = Join-Path $ToolsDir "ENGINE_SHA256SUMS"

function Write-Reason {
    param([string]$Code, [string]$Detail)
    Write-Host ("ERROR: " + $Code + " - " + $Detail)
}

function Get-FileSha256Hex {
    param([string]$Path)
    $hash = Get-FileHash -LiteralPath $Path -Algorithm SHA256
    return $hash.Hash.ToLowerInvariant()
}

if (-not (Test-Path -LiteralPath $SumsPath)) {
    Write-Reason "engine_missing" ("ENGINE_SHA256SUMS not found: " + $SumsPath)
    exit 2
}

$expected = @{}
foreach ($line in Get-Content -LiteralPath $SumsPath) {
    if ($line -match '^\s*#' -or [string]::IsNullOrWhiteSpace($line)) { continue }
    $parts = $line -split '\s+', 2
    if ($parts.Count -lt 2) { continue }
    $digest = $parts[0].Trim().ToLowerInvariant()
    $name = $parts[1].Trim()
    $expected[$name] = $digest
}

$editorName = $null
$consoleName = $null
$zipName = $null
foreach ($name in $expected.Keys) {
    if ($name -like "*_console.exe") { $consoleName = $name }
    elseif ($name -like "*.exe.zip") { $zipName = $name }
    elseif ($name -like "*.exe") { $editorName = $name }
}

if (-not $editorName -or -not $consoleName) {
    Write-Reason "engine_missing" "ENGINE_SHA256SUMS incomplete (need editor + console)"
    exit 2
}

if (-not (Test-Path -LiteralPath $EngineDir)) {
    Write-Reason "engine_missing" ("EngineDir not found: " + $EngineDir)
    exit 2
}

$editorPath = Join-Path $EngineDir $editorName
$consolePath = Join-Path $EngineDir $consoleName

if (-not (Test-Path -LiteralPath $editorPath)) {
    Write-Reason "engine_missing" ("missing editor EXE: " + $editorName)
    exit 2
}
if (-not (Test-Path -LiteralPath $consolePath)) {
    Write-Reason "engine_missing" ("missing console EXE: " + $consoleName)
    exit 2
}

$editorActual = Get-FileSha256Hex -Path $editorPath
if ($editorActual -ne $expected[$editorName]) {
    Write-Reason "engine_pin_mismatch" ("editor digest mismatch for " + $editorName)
    exit 1
}

$consoleActual = Get-FileSha256Hex -Path $consolePath
if ($consoleActual -ne $expected[$consoleName]) {
    Write-Reason "engine_pin_mismatch" ("console digest mismatch for " + $consoleName)
    exit 1
}

if ($null -ne $zipName) {
    $zipPath = Join-Path $EngineDir $zipName
    if (Test-Path -LiteralPath $zipPath) {
        $zipActual = Get-FileSha256Hex -Path $zipPath
        if ($zipActual -ne $expected[$zipName]) {
            Write-Reason "engine_pin_mismatch" ("ZIP digest mismatch for " + $zipName)
            exit 1
        }
    }
}

Write-Host ("OK: engine pin verified at " + $EngineDir)
exit 0
