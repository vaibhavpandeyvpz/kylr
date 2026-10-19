param(
    [string[]]$Modes = @('DM', 'TDM', 'CTF'),
    [ValidateRange(2, 10)][int[]]$Counts = @(2, 4, 6, 8, 10),
    [int]$Seconds = 60,
    [string]$Map = 'skyfall',
    [ValidateRange(0,3)][int]$Difficulty = 1,
    [ValidateRange(1,16)][int]$DecisionPhases = 1,
    [switch]$NativeClearRays
)

$ErrorActionPreference = 'Stop'
$godot = (Join-Path $PSScriptRoot '../../engine/bin/godot.windows.editor.x86_64.console.exe')
$project = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$reportDirectory = Join-Path $project 'reports'
New-Item -ItemType Directory -Force -Path $reportDirectory | Out-Null

foreach ($mode in $Modes) {
    foreach ($count in $Counts) {
        $caseSeconds = if ($mode -eq 'CTF') { [Math]::Max($Seconds, 120) } else { $Seconds }
        $id = '{0}_{1}' -f $mode.ToLowerInvariant(), $count
        if ($Map -ne 'skyfall') { $id = '{0}_{1}' -f $Map, $id }
        if ($Difficulty -ne 1) { $id = 'difficulty{0}_{1}' -f $Difficulty, $id }
        if ($DecisionPhases -ne 1) { $id = 'phases{0}_{1}' -f $DecisionPhases, $id }
        if ($NativeClearRays) { $id = 'native_rays_{0}' -f $id }
        $log = Join-Path $reportDirectory ('bot_profile_{0}.log' -f $id)
        Write-Output ('RUN {0} {1} robots / {2}s' -f $mode, $count, $caseSeconds)
        $nativeRayArgument = '--native-clear-rays={0}' -f [int][bool]$NativeClearRays
        & $godot --headless --fixed-fps 60 --profiling --path $project -s res://tools/profile_bot_routes.gd -- $mode $count $caseSeconds quiet 0 $Map $Difficulty "--decision-phases=$DecisionPhases" $nativeRayArgument 2>&1 | Set-Content -LiteralPath $log
        if ($LASTEXITCODE -ne 0) { throw ('Godot failed for {0}; see {1}' -f $id, $log) }
        $errors = Select-String -LiteralPath $log -Pattern 'SCRIPT ERROR|Parse Error|Invalid call'
        if ($errors) { throw ('Script error for {0}; see {1}' -f $id, $log) }
        $jsonPath = Join-Path $reportDirectory ('bot_profile_{0}.json' -f $id)
        $report = Get-Content -LiteralPath $jsonPath -Raw | ConvertFrom-Json
        if ($report.native_clear_rays -ne [bool]$NativeClearRays) { throw ('Native ray mode mismatch for {0}' -f $id) }
        $invaders = @($report.robots | Where-Object enemy_zone).Count
        $roofExits = @($report.robots | Where-Object { $_.roof_exit }).Count
        $kills = ($report.robots | Measure-Object -Property kills -Sum).Sum
        $captures = ($report.robots | Measure-Object -Property captures -Sum).Sum
        $repairs = ($report.robots | Measure-Object -Property repair_visits -Sum).Sum
        $portals = ($report.robots | Measure-Object -Property portal -Sum).Sum
        $pads = ($report.robots | Measure-Object -Property pad -Sum).Sum
        Write-Output ('RESULT {0}: invade={1}/{2} roof_exit={3} kills={4} captures={5} repairs={6} portal={7} pad={8} wall_ms/frame={9:N2}' -f $id, $invaders, $count, $roofExits, $kills, $captures, $repairs, $portals, $pads, $report.wall_ms_per_frame)
    }
}

$jumpLog = Join-Path $reportDirectory ('charged_jump_probe_{0}_difficulty{1}.log' -f $Map, $Difficulty)
Write-Output 'RUN physical charged-jump probe'
& $godot --headless --fixed-fps 60 --profiling --path $project -s res://tools/probe_charged_jump.gd -- $Map 2>&1 | Set-Content -LiteralPath $jumpLog
if ($LASTEXITCODE -ne 0) { throw ('Charged-jump probe failed; see {0}' -f $jumpLog) }
Get-Content -LiteralPath $jumpLog | Where-Object { $_ -match '^PROBE ' }
