param([string]$Godot = (Join-Path $PSScriptRoot '../../engine/bin/godot.windows.editor.x86_64.console.exe'))
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'check_local_assets.ps1')
$projectRoot = Split-Path -Parent $PSScriptRoot
$reportRoot = Join-Path $projectRoot 'reports/verification'
New-Item -ItemType Directory -Path $reportRoot -Force | Out-Null

function Invoke-Check([string]$Name, [string[]]$Arguments) {
    $log = Join-Path $reportRoot "$Name.log"
    & $Godot --headless --path $projectRoot @Arguments *> $log
    $engineExit = $LASTEXITCODE
    $failures = Select-String -LiteralPath $log -Pattern 'SCRIPT ERROR:|ERROR:|\[Failed\]|Leaked instance:|instances were leaked'
    if ($engineExit -ne 0 -or $failures) {
        Write-Host "$Name engine exit code: $engineExit"
        if ($failures) {
            Write-Host 'Errors found in the complete log:'
            Select-String -LiteralPath $log -Pattern 'SCRIPT ERROR:|ERROR:|\[Failed\]|Leaked instance:|instances were leaked' -Context 3,8 |
                ForEach-Object { Write-Output $_.ToString() }
        }
        Get-Content -LiteralPath $log -Tail 40
        throw "$Name failed. See $log"
    }
    Write-Host "PASS $Name"
}

Invoke-Check 'import' @('--editor','--import','--quit')
Invoke-Check 'tests' @('-s','addons/gut/gut_cmdln.gd','-gdir=res://tests','-gexit')
foreach ($mode in @('DM','TDM','CTF','ELIMINATION','GUNGAME')) {
    $robots = if ($mode -eq 'CTF') { '9' } else { '10' }
    $duration = if ($mode -eq 'CTF') { '120' } else { '40' }
    Invoke-Check "smoke-$mode" @('--fixed-fps','60','--','--smoke',"--type=$mode","--robots=$robots","--duration=$duration")
    $log = Join-Path $reportRoot "smoke-$mode.log"
    if (-not (Select-String -LiteralPath $log -Pattern 'SMOKE phase=Active')) {
        throw "$mode did not reach Active play. See $log"
    }
}
Invoke-Check 'results-flow' @('--fixed-fps','60','--','--smoke','--limit-seconds=5','--duration=30')
if (-not (Select-String -LiteralPath (Join-Path $reportRoot 'results-flow.log') -Pattern 'SMOKE phase=Finished')) {
    throw 'Timed match did not reach its results state.'
}
Write-Host "Verification complete. Logs: $reportRoot"
