param(
    [ValidateSet('skyfall','faceoff','ramparts')][string[]]$Maps = @('skyfall','faceoff'),
    [ValidateSet('DM','TDM','CTF')][string[]]$Modes = @('DM','TDM','CTF'),
    [ValidateRange(0,2)][int[]]$Qualities = @(0,1,2),
    [ValidateRange(2,10)][int[]]$Counts = @(10),
    [ValidateRange(1,10)][int]$Repeats = 1,
    [ValidateRange(25,300)][int]$Seconds = 25,
    [ValidateSet('safe','separate')][string]$RenderThread = 'safe',
    [string]$ReportDirectory = 'reports/performance/presets'
)

# Use actual preset defaults. Experimental scale, AI and ray-query overrides
# belong in separate trials, not in this baseline matrix.
$ErrorActionPreference = 'Stop'
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$runtime = Join-Path $project 'reports/performance/release-diagnostic/KylrDiagnostic.exe'
$sourceRuntime = $(if ($env:GODOT_TEMPLATE) { $env:GODOT_TEMPLATE } else { Join-Path $env:APPDATA 'Godot/export_templates/4.7.2.stable/windows_release_x86_64.exe' })
$pack = [IO.Path]::ChangeExtension($runtime, '.pck')
if (-not (Test-Path -LiteralPath $runtime) -or -not (Test-Path -LiteralPath $pack)) {
    throw 'Run the official editor with -s res://tools/pack_rendered_profile.gd first.'
}
$runtimeHash = (Get-FileHash -LiteralPath $runtime).Hash
if ($runtimeHash -ne (Get-FileHash -LiteralPath $sourceRuntime).Hash) {
    throw 'Diagnostic runtime is stale; repack using the official editor.'
}
$reportDirectory = if ([IO.Path]::IsPathRooted($ReportDirectory)) {
    [IO.Path]::GetFullPath($ReportDirectory)
} else {
    [IO.Path]::GetFullPath((Join-Path $project $ReportDirectory))
}
New-Item -ItemType Directory -Force -Path $reportDirectory | Out-Null
$manifest = [ordered]@{
    target_fps = 120
    output = '1920x1080'
    runtime_sha256 = $runtimeHash
    pack_sha256 = (Get-FileHash -LiteralPath $pack).Hash
    render_thread = $RenderThread
    samples = @()
    completed = $false
}
$manifestPath = Join-Path $reportDirectory 'matrix.json'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath
foreach ($map in $Maps) {
    foreach ($mode in $Modes) {
        foreach ($count in $Counts) {
            foreach ($quality in $Qualities) {
                foreach ($repeat in 1..$Repeats) {
                    $name = "rt120-preset-$map-$mode-$count-q$quality-r$repeat"
                    $stdout = Join-Path $reportDirectory "$name.stdout.log"
                    $stderr = Join-Path $reportDirectory "$name.stderr.log"
                    $started = Get-Date
                    $arguments = @('--render-thread',$RenderThread,'--',"--name=$name", "--map=$map", "--mode=$mode", "--robots=$count", "--quality=$quality", '--width=1920', '--height=1080', '--warmup=20', '--sample-at-sim=40', "--seconds=$Seconds", '--seed=120', '--target-fps=120', '--follow-bot=1', '--frame-times-only=1', "--report-dir=$reportDirectory")
                    # Start-Process joins arguments; quote paths for other workspaces.
                    $quotedArguments = $arguments | ForEach-Object { '"' + $_ + '"' }
                    $run = Start-Process -FilePath $runtime -ArgumentList $quotedArguments -WorkingDirectory $project -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
                    Write-Output "RUN $name pid=$($run.Id)"
                    $run.WaitForExit()
                    if ($run.ExitCode -ne 0) { throw "$name failed with exit $($run.ExitCode)" }
                    if (Select-String -LiteralPath $stdout,$stderr -Pattern 'SCRIPT ERROR|^ERROR:|VUID-|SYNC-HAZARD') { throw "Runtime error in $name" }
                    $path = Join-Path $reportDirectory "$name.json"
                    if ((Get-Item -LiteralPath $path).LastWriteTime -lt $started) { throw "Stale report $name" }
                    $report = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
                    if ($report.target_fps -ne 120 -or $report.quality_settings.quality -ne $quality -or $report.display.changed_during_sample -or $report.display.window_size -ne '(1920, 1080)' -or $report.follow_bot.moving_seconds -lt 3 -or $report.frames -lt 60) { throw "Invalid sample $name" }
                    if ($report.quality_settings.fixture_lighting -ne ($quality -eq 2) -or $report.quality_settings.active_renderer -ne 'Raster') { throw "Incorrect preset features in $name" }
                    $manifest.samples += [ordered]@{name=$name; report=$path; average_fps=$report.average_fps; frame_ms=$report.frame_ms; over_target_budget_percent=$report.over_target_budget_percent; meets_target_every_frame=$report.meets_target_every_frame}
                    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath
                    Write-Output "RESULT $name fps=$($report.average_fps) p95=$($report.frame_ms.p95) p99=$($report.frame_ms.p99)"
                }
            }
        }
    }
}
$manifest.completed = $true
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath
Write-Output 'GRAPHICS_MATRIX_COMPLETE'
