param([string]$Godot = (Join-Path $PSScriptRoot '../../engine/bin/godot.windows.editor.x86_64.console.exe'))
$ErrorActionPreference = 'Stop'
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$stdout = Join-Path $project 'reports/rt-settings-rendered.log'
$stderr = Join-Path $project 'reports/rt-settings-rendered-errors.log'
New-Item -ItemType Directory -Force (Join-Path $project 'reports') | Out-Null
$process = Start-Process -FilePath $Godot -ArgumentList @('--path',('"'+$project+'"'),'--windowed','--resolution','1280x720','-s','res://tools/probe_rt_settings.gd') -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
if (-not $process.WaitForExit(180000)) { $process.Kill($true); throw 'RT settings probe timed out.' }
$process.Refresh()
$output = (Get-Content $stdout -Raw) + (Get-Content $stderr -Raw)
if ($process.ExitCode -ne 0 -or $output -match 'ERROR:|SCRIPT ERROR:|VUID-|SYNC-HAZARD' -or $output -notmatch 'RT_SETTINGS_PASS') { throw "RT settings probe failed. See $stderr" }
Write-Output 'PASS: Ultra ray tracing, raster restore, and RT re-enable.'
