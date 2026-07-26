# Orchestrates the whole studio-live-local-e2e CI lane inside ONE process: pinned server start
# + readiness poll, background gauntlet seeder + marker parse, the Godot e2e gdUnit run, and the
# truncation check -- with try/finally cleanup of BOTH background processes (seeder and server).
#
# WHY ONE SCRIPT/STEP (2026-07-26 fix, PR #94 CI, second failure). The previous design split
# these across several workflow steps. Windows GitHub-hosted runners tear down a STEP's own
# job-object process tree at step END -- the backgrounded node server process was killed the
# moment the "start server" step finished, even though its own readiness line had already printed
# successfully inside that same step (CI log: "Worker 1 now listening on 0.0.0.0:8000" + "pokemon-
# showdown ready (pid 6148)" at 23:34:03, then the NEXT step's seeder got ConnectionRefusedError
# at 23:34:11). This never reproduces on a local dev machine (no job-object cleanup outside CI),
# which is why every earlier manual local sequence in this repo's history passed. Composing the
# whole lifecycle into one script/step means nothing is torn down between "start the server" and
# "use the server."
#
# The existing individual scripts (start_local_showdown_server.ps1, stop_local_showdown_server.ps1,
# run_gdunit_headless.ps1, check_gdunit_truncation.ps1) are called UNCHANGED here so a developer's
# own single-purpose use of each stays modular. The one exception: start_local_showdown_server.ps1
# gained a new OPTIONAL, backward-compatible -StdoutLogPath parameter (default "" -- byte-identical
# to before for every existing caller that never passes it) so this script can capture the server's
# own console output to a file and print its tail on failure -- structural diagnosability, not
# relying on a ready-line happening to have already printed inside whatever step scrolled by.

param(
    [int]$Games = 1,
    [string]$Villain = "max_damage",
    [double]$MoveDelaySeconds = 3,
    [int]$MarkerTimeoutSeconds = 30,
    # FOUND during this fix's own local sanity run (reproduced consistently, 2/2): gdUnit4's
    # await_idle_frame() resolves near-instantly in headless mode -- it paces by engine ticks, not
    # wall-clock seconds -- so the whole gdUnit test can finish in well under 100ms regardless of
    # its own frame-count budgets (600/600/1200 frames). If Godot joins the room before the
    # seeder's first real move has actually landed, the resent room history the test observes is
    # only the bare |init|battle line, and the "at least one real event" assertion fails --
    # nothing to do with THIS script's process lifecycle, but it blocks getting a passing local
    # run, so mitigated here: wait for the seeder to have had time to submit its first real move
    # BEFORE starting Godot, so the room's own resendable history already has real content by the
    # time it joins.
    [int]$SettleSecondsAfterMarker = 5
)

$ErrorActionPreference = "Stop"
$ToolsDir = $PSScriptRoot
$RepoRoot = Resolve-Path (Join-Path $ToolsDir "../../..")
# FOUND during this fix's own local sanity run: the gauntlet seeder resolves several paths
# (SHOWDOWN_TEAM_PATH's own default "teams/fixed_team.txt", format/spread config lookups) relative
# to the process's CURRENT DIRECTORY, not to the showdown_bot package's own location -- every
# other known-good invocation of this CLI (showdown_bot/tools/localserver/README.md's own
# documented recipe, this repo's other gauntlet callers) runs it from showdown_bot/ itself. This
# script is launched from the repo root (matching the workflow's own working-directory), so the
# seeder is explicitly given showdown_bot/ as its OWN working directory below -- without it,
# relative team/config paths resolve against the wrong directory.
$ShowdownBotDir = Join-Path $RepoRoot "showdown_bot"
# Works identically under GitHub Actions (RUNNER_TEMP set) and a local dev run (falls back to the
# OS temp dir) -- this script is meant to be sanity-run locally end-to-end, not CI-only.
$TempDir = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [System.IO.Path]::GetTempPath() }

$ServerStdoutPath = Join-Path $TempDir "studio_e2e_server_stdout.txt"
$ServerStderrPath = "$ServerStdoutPath.err"
$GauntletStdoutPath = Join-Path $TempDir "studio_e2e_gauntlet_stdout.txt"
# FOUND during this fix's own local sanity run: Start-Process -RedirectStandardOutput alone
# misses anything the seeder writes to stderr (an uncaught exception's traceback, or any
# logging.* call that defaults to stderr) -- the very diagnostics this script exists to surface.
# Captured to its own file, alongside stdout, and tailed on any failure.
$GauntletStderrPath = "$GauntletStdoutPath.err"
$GauntletPidPath = Join-Path $TempDir "studio_e2e_gauntlet.pid"
$LocalServerUrl = "ws://127.0.0.1:8000/showdown/websocket"

foreach ($stale in @($ServerStdoutPath, $ServerStderrPath, $GauntletStdoutPath, $GauntletStderrPath, $GauntletPidPath)) {
    if (Test-Path -LiteralPath $stale) { Remove-Item -LiteralPath $stale -Force -ErrorAction SilentlyContinue }
}

function Write-DiagnosticTail {
    param([string]$Label, [string]$Path, [int]$Lines = 40)
    Write-Host "----- $Label (tail of $Path) -----"
    if (Test-Path -LiteralPath $Path) {
        Get-Content -LiteralPath $Path -Tail $Lines | ForEach-Object { Write-Host $_ }
    }
    else {
        Write-Host "(no file at $Path)"
    }
    Write-Host "----- end $Label -----"
}

function Write-FailureDiagnostics {
    Write-DiagnosticTail -Label "gauntlet seeder stdout" -Path $GauntletStdoutPath
    Write-DiagnosticTail -Label "gauntlet seeder stderr" -Path $GauntletStderrPath
    Write-DiagnosticTail -Label "pokemon-showdown server stdout" -Path $ServerStdoutPath
    Write-DiagnosticTail -Label "pokemon-showdown server stderr" -Path $ServerStderrPath
}

$gauntletProc = $null
try {
    Write-Host "Starting pinned local pokemon-showdown server (polls for readiness)..."
    & (Join-Path $ToolsDir "start_local_showdown_server.ps1") -StdoutLogPath $ServerStdoutPath
    if ($LASTEXITCODE -ne 0) {
        Write-FailureDiagnostics
        throw "start_local_showdown_server.ps1 failed (exit $LASTEXITCODE)"
    }

    Write-Host "Seeding a long-running battle in the background..."
    $gauntletProc = Start-Process -FilePath "python" `
        -ArgumentList @(
            "-m", "showdown_bot.cli", "gauntlet",
            "--games", "$Games", "--villain", $Villain,
            "--print-room-id", "--move-delay-seconds", "$MoveDelaySeconds",
            "--server-url", $LocalServerUrl
        ) `
        -WorkingDirectory $ShowdownBotDir `
        -RedirectStandardOutput $GauntletStdoutPath -RedirectStandardError $GauntletStderrPath -PassThru -NoNewWindow
    $gauntletProc.Id | Out-File -FilePath $GauntletPidPath -Encoding ascii

    # Poll the redirected stdout file for the marker line WHILE the process keeps running (it
    # does not exit after printing it -- Task 33's keep-alive mode) -- never wait for the process
    # to exit and read its complete output, which would defeat the point.
    $deadline = (Get-Date).AddSeconds($MarkerTimeoutSeconds)
    $roomId = $null
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $GauntletStdoutPath) {
            $match = Select-String -LiteralPath $GauntletStdoutPath -Pattern '^SHOWDOWN_ROOM_ID=(\S+)$' | Select-Object -First 1
            if ($match) {
                $roomId = $match.Matches[0].Groups[1].Value
                break
            }
        }
        Start-Sleep -Seconds 1
    }
    if (-not $roomId) {
        Write-Host "ERROR: no SHOWDOWN_ROOM_ID= marker found within $MarkerTimeoutSeconds s"
        Write-FailureDiagnostics
        throw "marker timeout"
    }
    Write-Host "SHOWDOWN_ROOM_ID=$roomId"
    $env:STUDIO_E2E_ROOM_ID = $roomId

    Write-Host "Waiting ${SettleSecondsAfterMarker}s for the seeder's first real move to land before Godot joins..."
    Start-Sleep -Seconds $SettleSecondsAfterMarker

    Write-Host "Running live-local-e2e gdUnit suite..."
    & (Join-Path $ToolsDir "run_gdunit_headless.ps1") -a "res://tests/e2e/"
    $gdUnitExitCode = $LASTEXITCODE
    if ($gdUnitExitCode -ne 0) {
        Write-FailureDiagnostics
        throw "run_gdunit_headless.ps1 failed (exit $gdUnitExitCode)"
    }

    Write-Host "Asserting gdUnit results were not truncated..."
    & (Join-Path $ToolsDir "check_gdunit_truncation.ps1")
    if ($LASTEXITCODE -ne 0) {
        Write-FailureDiagnostics
        throw "check_gdunit_truncation.ps1 failed (exit $LASTEXITCODE)"
    }

    Write-Host "studio-live-local-e2e: PASSED"
}
finally {
    Write-Host "Cleanup: stopping the gauntlet seeder and the pinned server..."
    if ($gauntletProc -and -not $gauntletProc.HasExited) {
        Stop-Process -Id $gauntletProc.Id -Force -ErrorAction SilentlyContinue
    }
    elseif (Test-Path -LiteralPath $GauntletPidPath) {
        $gauntletPid = Get-Content -LiteralPath $GauntletPidPath | Select-Object -First 1
        Stop-Process -Id $gauntletPid -Force -ErrorAction SilentlyContinue
    }
    & (Join-Path $ToolsDir "stop_local_showdown_server.ps1")
}
