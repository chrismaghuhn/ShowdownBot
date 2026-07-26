# Starts the repository's pinned local pokemon-showdown server for the studio-live-local-e2e
# CI lane. No prior automation for this exists in the repo -- built from the manual recipe at
# showdown_bot/tools/localserver/README.md, reading the SAME pin the bot's own eval tooling uses
# (config/eval/provenance.yaml's showdown_commit) rather than a second, driftable pin.
param(
    [string]$CacheDir = (Join-Path $env:USERPROFILE ".cache/showdownbot/pokemon-showdown"),
    [int]$Port = 8000,
    [int]$ReadinessTimeoutSeconds = 60,
    # Optional, additive (2026-07-26): when given, the node server's own stdout/stderr are
    # redirected to this path (+ ".err") instead of inheriting the caller's console -- lets
    # run_live_e2e_ci.ps1 print a diagnostic tail on failure. Default "" is the ORIGINAL
    # behavior, byte-identical for every existing caller that never passes this.
    [string]$StdoutLogPath = ""
)

$ErrorActionPreference = "Stop"
# FIXED (2026-07-25 review): from showdownbot_studio/godot/tools/, the repo root is THREE levels
# up (tools -> godot -> showdownbot_studio -> repo root), not four -- the previous "../../../.."
# escaped the repository entirely.
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "../../..")
$ProvenancePath = Join-Path $RepoRoot "config/eval/provenance.yaml"
$PatchPath = Join-Path $RepoRoot "tools/eval/patches/pokemon-showdown-seeded-battle.patch"

$commitLine = Get-Content -LiteralPath $ProvenancePath | Where-Object { $_ -match '^showdown_commit:\s*(\S+)' }
if (-not $commitLine) {
    Write-Host "ERROR: could not read showdown_commit from $ProvenancePath"
    exit 2
}
$commit = ($commitLine -split ':\s*')[1].Trim()

if (-not (Test-Path -LiteralPath $CacheDir)) {
    git clone https://github.com/smogon/pokemon-showdown.git $CacheDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Push-Location $CacheDir
try {
    git fetch origin $commit
    git checkout $commit
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $patchCheck = git apply --reverse --check $PatchPath 2>$null
    if ($LASTEXITCODE -ne 0) {
        git apply $PatchPath
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    if (-not (Test-Path "config/config.js")) {
        Copy-Item "config/config-example.js" "config/config.js"
    }

    # FIXED (2026-07-25 review): npm ci, not npm install -- reproducible install from the
    # committed lockfile, the correct choice for pinned CI provisioning.
    npm ci
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    node build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $startArgs = @{
        FilePath = "node"
        ArgumentList = @("pokemon-showdown", "start", "$Port", "--no-security")
        WorkingDirectory = $CacheDir
        PassThru = $true
        NoNewWindow = $true
    }
    if ($StdoutLogPath) {
        $startArgs["RedirectStandardOutput"] = $StdoutLogPath
        $startArgs["RedirectStandardError"] = "$StdoutLogPath.err"
    }
    $proc = Start-Process @startArgs
    $proc.Id | Out-File -FilePath (Join-Path $PSScriptRoot ".local_showdown_server.pid") -Encoding ascii

    # FIXED (2026-07-25 review): poll for readiness instead of assuming the port is open the
    # instant the process starts.
    # FIXED (2026-07-26 review): 127.0.0.1, not "localhost" -- consistency fix alongside the real
    # bug this session found (the gauntlet seeder's default WebSocket URL resolving "localhost"
    # to IPv6 first on a CI Windows runner, where this IPv4-only server never answers). This
    # readiness probe was not the actual failure point (it already reported ready in CI), but
    # every address in this lane should agree rather than leave a second "localhost" for the
    # next host-resolution-order surprise.
    $deadline = (Get-Date).AddSeconds($ReadinessTimeoutSeconds)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        $test = Test-NetConnection -ComputerName "127.0.0.1" -Port $Port -WarningAction SilentlyContinue
        if ($test.TcpTestSucceeded) {
            $ready = $true
            break
        }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) {
        Write-Host "ERROR: pokemon-showdown did not become ready on port $Port within $ReadinessTimeoutSeconds s"
        exit 2
    }
    Write-Host "pokemon-showdown ready (pid $($proc.Id)) on port $Port, commit $commit"
}
finally {
    Pop-Location
}
