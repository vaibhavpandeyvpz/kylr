param(
    [ValidateSet('safe','separate')][string]$RenderThread='safe',
    [switch]$EngineVerbose,
    [ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Prefix=('loading-'+(Get-Date -Format 'yyyyMMdd-HHmmss')),
    [string]$Godot=$(if ($env:GODOT) { $env:GODOT } else { 'godot' })
)
$ErrorActionPreference='Stop'
$Godot = (Get-Command $Godot -CommandType Application -ErrorAction Stop).Source
$project=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$output=Join-Path $project "reports/performance/$Prefix"
if(Test-Path -LiteralPath $output){throw 'Use a fresh lifecycle report directory.'}
New-Item -ItemType Directory $output | Out-Null
$binary=$Godot
$probe=Join-Path $project 'tools/probe_loading_lifecycle.gd'
$hash=(Get-FileHash -LiteralPath $binary).Hash
$probeHash=(Get-FileHash -LiteralPath $probe).Hash
$runtime=@(Get-ChildItem -LiteralPath (Split-Path $Godot) -Filter '*.dll' -File | Sort-Object Name | ForEach-Object {
@{name=$_.Name;sha256=(Get-FileHash -LiteralPath $_.FullName).Hash;version=$_.VersionInfo.FileVersion}
})
$started=[DateTime]::UtcNow
$arguments=@('--path',('"'+$project+'"'),'--render-thread',$RenderThread,'--script','res://tools/probe_loading_lifecycle.gd','--',('--report-dir='+$output.Replace('\','/')))
if($EngineVerbose){$arguments=@('--verbose')+$arguments}
$stdout=Join-Path $output 'probe.log';$stderr=Join-Path $output 'errors.log'
$process=Start-Process -FilePath $Godot -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
if(-not $process.WaitForExit(300000)){$process.Kill($true);throw 'Loading lifecycle timed out.'}
$process.Refresh()
$log=(Get-Content -LiteralPath $stdout -Raw)+(Get-Content -LiteralPath $stderr -Raw)
if($process.ExitCode -ne 0 -or $log -match 'ERROR:|SCRIPT ERROR:|VUID-|SYNC-HAZARD|ObjectDB instances were leaked' -or $log -notmatch 'LOADING_LIFECYCLE_PASS'){
    throw "Loading lifecycle failed: $output"
}
$report=Get-Content -LiteralPath (Join-Path $output 'report.json') -Raw|ConvertFrom-Json
if(-not $report.complete -or $report.renderer -ne 'Raster' -or $report.backend_checks.Count -ne 4 -or $report.loading.Count -ne 4){throw 'Incomplete loading lifecycle report.'}
foreach($stage in $report.loading){if(-not $stage.rendering.ready){throw 'A loading stage was not render-ready.'}}
$images=@(Get-ChildItem -LiteralPath $output -Filter '*.png' -File)
if($images.Count -ne 9 -or @($images|Where-Object {$_.LastWriteTimeUtc -lt $started -or $_.Length -lt 100}).Count){throw 'Missing/stale lifecycle captures.'}
if($hash -ne (Get-FileHash -LiteralPath $binary).Hash -or $probeHash -ne (Get-FileHash -LiteralPath $probe).Hash){throw 'Engine/probe changed during the run.'}
foreach($file in $runtime){if($file.sha256 -ne (Get-FileHash -LiteralPath (Join-Path (Split-Path $Godot) $file.name)).Hash){throw 'Runtime changed during the run.'}}
@{passed=$true;validation=$false;renderer='Raster';render_thread=$RenderThread;engine_sha256=$hash;probe_sha256=$probeHash;runtime_dlls=$runtime;started_utc=$started.ToString('o');visual_quality_acceptance=$false;performance_acceptance=$false}|
    ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $output 'manifest.json') -Encoding utf8
Write-Output "PASS raster menu, both maps, repeat load and shutdown. Captures still require visual review."
