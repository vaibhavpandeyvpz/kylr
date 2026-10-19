param(
    [string]$Godot = (Join-Path $PSScriptRoot '../../engine/bin/godot.windows.editor.x86_64.console.exe'),
    [string]$ReleaseExecutable = '',
    [string[]]$Maps = @('skyfall', 'faceoff'),
    [ValidateSet('DM','TDM','CTF')][string[]]$Modes = @('DM','TDM','CTF'),
    [ValidateSet('ai','combat')][string[]]$Scenarios = @('ai','combat'),
    [ValidateRange(0,3)][int]$Quality = 3,
    [ValidateRange(20,600)][int]$Warmup = 20,
    [ValidateRange(15,600)][int]$Seconds = 30,
    [ValidateRange(1,1000)][int]$TargetFps = 240,
    [ValidateRange(640,7680)][int]$Width = 1920,
    [ValidateRange(360,4320)][int]$Height = 1080,
    [int]$Seed = 120,
    [string]$Tag = ('rendered-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
)
$ErrorActionPreference = 'Stop'
if ($ReleaseExecutable) { throw 'Shipping builds exclude profiling code. Run this diagnostic with -Godot against the development project.' }
if ($Tag -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Tag must contain only letters, digits, underscores and hyphens.' }
$project = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$catalog = Get-Content -LiteralPath (Join-Path $project 'data/maps/catalog.json') -Raw | ConvertFrom-Json
foreach ($map in $Maps) {
    if ($map -notin $catalog.maps.id) { throw "Unknown map: $map" }
}
$directory = Join-Path $project 'reports/performance'
New-Item -ItemType Directory -Force -Path $directory | Out-Null
$summary = @()
foreach ($map in $Maps) {
    foreach ($mode in $Modes) {
        foreach ($scenario in $Scenarios) {
            $name = "$Tag-$map-$mode-$scenario"
            $log = Join-Path $directory "$name.log"
            $arguments = @("--name=$name", "--map=$map", "--mode=$mode", '--robots=10', "--quality=$Quality", "--width=$Width", "--height=$Height", "--warmup=$Warmup", "--seconds=$Seconds", "--seed=$Seed", "--target-fps=$TargetFps")
            if ($scenario -eq 'combat') { $arguments += @('--stress=1','--world=1') }
            Write-Output "RUN $name"
            $started = Get-Date
            # Deliberately serial: neither headless throughput nor overlapping
            # GPU workloads constitute a rendered gameplay measurement.
            if ($ReleaseExecutable) {
                & $ReleaseExecutable --log-file $log -- --profile-rendered @arguments | Out-Null
            } else {
                & $Godot --path $project -s res://tools/profile_rendered_combat.gd -- @arguments *> $log
            }
            if ($LASTEXITCODE -ne 0 -or (Select-String -LiteralPath $log -Pattern 'SCRIPT ERROR:|ERROR:|instances were leaked')) {
                throw "Profile failed: $log"
            }
            $resultRoot = if ($ReleaseExecutable) { Join-Path (Split-Path (Resolve-Path $ReleaseExecutable)) 'reports/performance' } else { $directory }
            $resultPath = Join-Path $resultRoot "$name.json"
            if (-not (Test-Path -LiteralPath $resultPath)) { throw "Missing profile result: $resultPath" }
            if ((Get-Item -LiteralPath $resultPath).LastWriteTime -lt $started) { throw "Stale profile result: $resultPath" }
            $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
            $coverage = $true
            if ($scenario -eq 'combat') {
                foreach ($weapon in (Get-Content -LiteralPath (Join-Path $project 'data/weapons/catalog.json') -Raw | ConvertFrom-Json).weapons.psobject.Properties.Name) {
                    if ($weapon -in @('lightning_gun','flamethrower')) {
                        if ($result.stream_samples.$weapon -le 0 -or $result.contact_samples.$weapon -le 0) { $coverage = $false }
                    }
                    if ($result.weapons.$weapon -le 0) { $coverage = $false }
                }
                if ($result.damage_samples -le 0 -or $result.repair_samples -le 0) { $coverage = $false }
            }
            $summary += [pscustomobject]@{
                name=$name; release=$result.release; average_fps=$result.average_fps
                p50_ms=$result.frame_ms.p50; p95_ms=$result.frame_ms.p95; p99_ms=$result.frame_ms.p99
                max_ms=$result.frame_ms.max; over_budget_percent=$result.over_target_budget_percent
                combat_coverage=$coverage; passes=$coverage -and $result.meets_target_every_frame
            }
            $summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $directory "$Tag-summary.json")
            $summary[-1] | Format-List | Out-String | Write-Output
        }
    }
}
if (@($summary | Where-Object { -not $_.passes }).Count -gt 0) { exit 2 }
