param([switch]$Skyfall, [switch]$TenRobots, [ValidateRange(0.25,1.0)][double]$Scale = 0.5, [switch]$Timings)
$ErrorActionPreference = 'Stop'
$prefix = if ($Skyfall) { 'skyfall' } else { 'faceoff' }
if ($TenRobots) { $prefix += '-10robots' }
if ($Scale -ne 0.5) { $prefix += "-scale" + [math]::Round($Scale * 100) }
if ($Timings) { $prefix += "-timings" }
New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot '../reports') | Out-Null
$telemetry = Join-Path $PSScriptRoot "../reports/$prefix-soak-gpu.csv"
$gpu = Start-Process -FilePath (Get-Command nvidia-smi -ErrorAction Stop).Source -ArgumentList '--query-gpu=timestamp,memory.used,utilization.gpu,temperature.gpu,power.draw --format=csv -l 1' -WindowStyle Hidden -PassThru -RedirectStandardOutput $telemetry -RedirectStandardError (Join-Path $PSScriptRoot "../reports/$prefix-soak-gpu.stderr.log")
try {
    & (Join-Path $PSScriptRoot 'run-nvidia-rt-test.ps1') -Acceptance -Soak -RayReconstruction -Skyfall:$Skyfall -TenRobots:$TenRobots -Scale $Scale -Timings:$Timings
    $testExit = $LASTEXITCODE
} finally {
    if (-not $gpu.HasExited) { Stop-Process -Id $gpu.Id }
}
exit $testExit
