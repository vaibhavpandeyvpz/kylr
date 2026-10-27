param(
    [ValidateSet('faceoff','skyfall','ramparts')][string]$Map = 'faceoff',
    [ValidatePattern('^[A-Za-z_][A-Za-z0-9_]*$')][string]$ReportPrefix = 'asset_handoff',
    [ValidateRange(1,16)][Nullable[int]]$DecisionPhases = $null,
    [string]$Godot = $(if ($env:GODOT) { $env:GODOT } else { 'godot' })
)
$ErrorActionPreference = 'Stop'
$Godot = (Get-Command $Godot -CommandType Application -ErrorAction Stop).Source
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$directory = Join-Path $project "reports/roster/$ReportPrefix-$Map"
if (Test-Path -LiteralPath $directory) { throw 'Choose a fresh roster report prefix.' }
New-Item -ItemType Directory -Force $directory | Out-Null
$binary = $Godot
$probe = Join-Path $project 'tools/profile_bot_routes.gd'
$binaryHash = (Get-FileHash -LiteralPath $binary).Hash
$probeHash = (Get-FileHash -LiteralPath $probe).Hash
$brain = Join-Path $project 'scripts/ai/brain.gd'
$brainHash = (Get-FileHash -LiteralPath $brain).Hash
$equipment = Join-Path $project 'scripts/ai/bot_equipment.gd'
$equipmentHash = (Get-FileHash -LiteralPath $equipment).Hash
$wrapperHash = (Get-FileHash -LiteralPath $PSCommandPath).Hash
$stdout = Join-Path $directory 'matrix.log'
$stderr = Join-Path $directory 'matrix-errors.log'
$arguments = @('--headless','--fixed-fps','60','--path',('"'+$project+'"'),'--script','res://tools/profile_bot_routes.gd','--',
    '--matrix',"--map=$Map","--report-directory=res://reports/roster/$ReportPrefix-$Map")
if($null -ne $DecisionPhases){$arguments+="--decision-phases=$DecisionPhases"}
$process = Start-Process -FilePath $Godot -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
$deadline = [DateTime]::UtcNow.AddMinutes(30)
while (-not $process.WaitForExit(1000)) {
    if ([DateTime]::UtcNow -ge $deadline) { $process.Kill($true); throw 'Roster matrix timed out.' }
}
$process.Refresh()
$log = (Get-Content -LiteralPath $stdout -Raw) + (Get-Content -LiteralPath $stderr -Raw)
if ($process.ExitCode -ne 0 -or $log -match 'ERROR:|SCRIPT ERROR:|instances were leaked|RID.*was leaked' -or $log -notmatch 'ROSTER_MATRIX_COMPLETE') {
    throw "Roster matrix failed. See $stdout and $stderr"
}
$rows = @()
foreach ($mode in @('DM','TDM','CTF','ELIMINATION','GUNGAME')) {
    foreach ($count in @(2,4,6,8,10)) {
        $seconds = if ($mode -eq 'CTF') { 120 } else { 30 }
        $stem = $mode.ToLowerInvariant() + '-' + $count
        $reportPath = Join-Path $directory "$stem.json"
        if (-not (Test-Path -LiteralPath $reportPath)) { throw "Missing roster report: $stem" }
        $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
        if($null -ne $DecisionPhases -and $report.decision_phases -ne $DecisionPhases){throw "Decision schedule mismatch: $stem"}
        if ($report.phase -ne 'Active' -or $report.mode -ne $mode -or $report.count -ne $count -or $report.robots.Count -ne $count -or
            $report.match_elapsed -lt ($seconds-.1)) { throw "Incomplete roster case: $stem" }
        $distance = ($report.robots | Measure-Object -Property distance -Sum).Sum
        if ($distance -lt 10) { throw "Roster did not move meaningfully: $stem" }
        $rows += @{mode=$mode; count=$count; simulated_seconds=$report.match_elapsed; distance_total=$distance;
            captures=($report.robots | Measure-Object -Property captures -Sum).Sum; decision_phases=$report.decision_phases; passed=$true}
        $rows | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $directory 'cases.json') -Encoding utf8
        Write-Output "PASS roster $Map $mode/$count ($seconds simulated seconds)"
    }
}
if ($binaryHash -ne (Get-FileHash -LiteralPath $binary).Hash -or $probeHash -ne (Get-FileHash -LiteralPath $probe).Hash) { throw 'Engine or probe changed during roster validation.' }
if($brainHash -ne (Get-FileHash -LiteralPath $brain).Hash -or $equipmentHash -ne (Get-FileHash -LiteralPath $equipment).Hash -or $wrapperHash -ne (Get-FileHash -LiteralPath $PSCommandPath).Hash){throw 'Decision scheduler, equipment policy or wrapper changed during roster validation.'}
@{passed=$true; cases=$rows; engine_sha256=$binaryHash; probe_sha256=$probeHash; brain_sha256=$brainHash; equipment_sha256=$equipmentHash; wrapper_sha256=$wrapperHash; decision_phases_requested=$DecisionPhases; map=$Map;
  functional_roster_acceptance=$true; performance_acceptance=$false;
  note='Headless functional matrix; inspect physical routes and objectives separately. Not an isolated performance measurement.'} |
    ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $directory 'manifest.json') -Encoding utf8
Write-Output 'PASS roster matrix: 25 cases. This is not rendered FPS qualification.'
