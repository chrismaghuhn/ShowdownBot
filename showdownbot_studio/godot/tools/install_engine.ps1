# Install pinned Godot 4.5.2-stable into tools/engine/ (Plan B §0.1).
# Flow: verify ZIP -> extract staging -> verify editor+console digests -> install -> delete staging.
param(
    [string]$ZipPath = "",
    [string]$EngineDir = ""
)

$ErrorActionPreference = "Stop"

$ToolsDir = $PSScriptRoot
$SumsPath = Join-Path $ToolsDir "ENGINE_SHA256SUMS"
if ([string]::IsNullOrWhiteSpace($EngineDir)) {
    $EngineDir = Join-Path $ToolsDir "engine"
}

function Get-FileSha256Hex {
    param([string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

$expected = @{}
foreach ($line in Get-Content -LiteralPath $SumsPath) {
    if ($line -match '^\s*#' -or [string]::IsNullOrWhiteSpace($line)) { continue }
    $parts = $line -split '\s+', 2
    if ($parts.Count -lt 2) { continue }
    $expected[$parts[1].Trim()] = $parts[0].Trim().ToLowerInvariant()
}

$editorName = $null
$consoleName = $null
$zipName = $null
foreach ($name in $expected.Keys) {
    if ($name -like "*_console.exe") { $consoleName = $name }
    elseif ($name -like "*.exe.zip") { $zipName = $name }
    elseif ($name -like "*.exe") { $editorName = $name }
}

if (-not $editorName -or -not $consoleName -or -not $zipName) {
    throw "ENGINE_SHA256SUMS incomplete"
}

if ([string]::IsNullOrWhiteSpace($ZipPath)) {
    $ZipPath = Join-Path $EngineDir $zipName
}
if (-not (Test-Path -LiteralPath $ZipPath)) {
    throw ("ZIP not found: " + $ZipPath + " - download Godot_v4.5.2-stable_win64.exe.zip from godotengine/godot-builds")
}

$zipActual = Get-FileSha256Hex -Path $ZipPath
if ($zipActual -ne $expected[$zipName]) {
    throw ("engine_pin_mismatch: ZIP digest mismatch for " + $zipName)
}

New-Item -ItemType Directory -Path $EngineDir -Force | Out-Null
$staging = Join-Path $EngineDir (".staging-" + [guid]::NewGuid().ToString("n"))
New-Item -ItemType Directory -Path $staging -Force | Out-Null

try {
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $staging -Force
    $editorSrc = Get-ChildItem -LiteralPath $staging -Recurse -Filter $editorName | Select-Object -First 1
    $consoleSrc = Get-ChildItem -LiteralPath $staging -Recurse -Filter $consoleName | Select-Object -First 1
    if (-not $editorSrc -or -not $consoleSrc) {
        throw "ZIP did not contain both editor and console EXEs"
    }
    $editorDigest = Get-FileSha256Hex -Path $editorSrc.FullName
    $consoleDigest = Get-FileSha256Hex -Path $consoleSrc.FullName
    if ($editorDigest -ne $expected[$editorName]) {
        throw ("engine_pin_mismatch: editor digest mismatch after extract")
    }
    if ($consoleDigest -ne $expected[$consoleName]) {
        throw ("engine_pin_mismatch: console digest mismatch after extract")
    }

    $editorDest = Join-Path $EngineDir $editorName
    $consoleDest = Join-Path $EngineDir $consoleName
    Copy-Item -LiteralPath $editorSrc.FullName -Destination $editorDest -Force
    Copy-Item -LiteralPath $consoleSrc.FullName -Destination $consoleDest -Force

    $zipDest = Join-Path $EngineDir $zipName
    if ((Resolve-Path -LiteralPath $ZipPath).Path -ne (Resolve-Path -LiteralPath $zipDest -ErrorAction SilentlyContinue).Path) {
        Copy-Item -LiteralPath $ZipPath -Destination $zipDest -Force
    }
}
finally {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
    }
}

& (Join-Path $ToolsDir "verify_engine_pin.ps1") -EngineDir $EngineDir
if ($LASTEXITCODE -ne 0) {
    throw ("verify_engine_pin failed after install with exit " + $LASTEXITCODE)
}
Write-Host ("Installed pinned Godot into " + $EngineDir)
