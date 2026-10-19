param(
 [ValidateSet('safe','separate')][string]$RenderThread='safe',
 [ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Prefix='renderer-startup',
 [string]$Godot=(Join-Path $PSScriptRoot '../../engine/bin/godot.windows.editor.x86_64.console.exe')
)
$ErrorActionPreference='Stop'
$project=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$engine=[IO.Path]::GetFullPath((Join-Path $project '../engine'))
$output=Join-Path $project "reports/performance/$Prefix-$RenderThread"
if(Test-Path -LiteralPath $output){throw 'Use fresh startup output; preserve existing evidence.'}
if(Get-CimInstance Win32_Process | Where-Object {$_.Name -like 'godot*' -or $_.Name -in @('KYLR.exe','KylrRTXDiagnostic.exe','blender.exe')}){throw 'Finish other renderer jobs before startup qualification.'}
New-Item -ItemType Directory -Path $output|Out-Null
$binary=Join-Path (Split-Path $Godot) 'godot.windows.editor.x86_64.exe'
$paths=@($Godot,$binary,$PSCommandPath)
foreach($name in @('tools/probe_renderer_startup.gd','scripts/debug/reconstruction_observer.gd','scripts/core/boot.gd','scripts/core/app.gd','scripts/core/preferences.gd','scripts/core/resource_preparation.gd','scripts/match/match.gd','main.tscn','app.tscn')){$paths+=Join-Path $project $name}
$paths+=@(Get-ChildItem -LiteralPath (Split-Path $Godot) -File -Filter '*.dll'|Select-Object -ExpandProperty FullName)
$paths+=Join-Path $project 'scripts/actors/robot.gd'
$frozen=@($paths|ForEach-Object {@{path=[IO.Path]::GetFullPath($_);sha256=(Get-FileHash -LiteralPath $_).Hash}})
$saved=@{}
foreach($name in @('GODOT_DLSS_DIAGNOSTICS','GODOT_DLSS_RR_OPAQUE_PARTICLE_GUIDES','GODOT_DLSS_RR_TRANSPARENCY_LAYER','VK_LAYER_PATH','VK_INSTANCE_LAYERS','VK_VALIDATION_VALIDATE_SYNC')){
 $saved[$name]=[Environment]::GetEnvironmentVariable($name,'Process')
 [Environment]::SetEnvironmentVariable($name,$null,'Process')
}
try{
 $env:GODOT_DLSS_DIAGNOSTICS='1'
 $env:VK_LAYER_PATH=Join-Path $engine '.local/vulkan-validation-1.4.363.0/Bin'
 if(-not(Test-Path (Join-Path $env:VK_LAYER_PATH 'VkLayer_khronos_validation.json'))){throw 'Pinned Vulkan validation layer missing.'}
 $env:VK_INSTANCE_LAYERS='VK_LAYER_KHRONOS_validation';$env:VK_VALIDATION_VALIDATE_SYNC='true'
 $arguments=@('--path',('"'+$project+'"'),'--gpu-validation','--render-thread',$RenderThread,'--script','res://tools/probe_renderer_startup.gd','--',('"--output='+$output.Replace('\','/')+'"'),"--thread=$RenderThread")
 $stdout=Join-Path $output 'probe.log';$stderr=Join-Path $output 'errors.log'
 $process=Start-Process -FilePath $Godot -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
 $process.WaitForExit();$process.Refresh()
 $log=(Get-Content $stdout -Raw)+(Get-Content $stderr -Raw)
 $unchanged=$true
 foreach($frozenInput in $frozen){if((Get-FileHash -LiteralPath $frozenInput.path).Hash -ne $frozenInput.sha256){$unchanged=$false}}
 $passed=$process.ExitCode -eq 0 -and $unchanged -and $log -match 'RENDERER_STARTUP_PASS captures=10' -and $log -match 'Inserted device layer "VK_LAYER_KHRONOS_validation"' -and $log -match '  - Synchronization' -and $log -notmatch 'ERROR:|SCRIPT ERROR:|VUID-|SYNC-HAZARD|leaked at exit|Resource[s]? still in use'
 $reportPath=Join-Path $output 'report.json'
 if(Test-Path -LiteralPath $reportPath){
  $report=Get-Content $reportPath -Raw|ConvertFrom-Json
  $passed=$passed -and $report.passed -and $report.rows.Count -eq 10 -and [string]::IsNullOrEmpty($report.preparation_error)
  foreach($mapName in @('faceoff','skyfall')){
   if($report.loading_hold_robot_observations.$mapName -lt 10 -or @($report.loading_hold_robot_ids.$mapName.PSObject.Properties.Name).Count -ne 10){$passed=$false}
   $revealed=@($report.rows|Where-Object {$_.label -eq "$mapName-spawn-revealed"})
   if($revealed.Count -ne 1 -or -not $revealed[0].local_spawn.visible -or -not $revealed[0].local_spawn.started){$passed=$false}
  }
 }else{$passed=$false}
 @{passed=$passed;exit_code=$process.ExitCode;inputs=$frozen;unchanged=$unchanged;validation=$true;render_thread=$RenderThread;visual_quality_accepted=$false;performance_accepted=$false}|ConvertTo-Json -Depth 5|Set-Content (Join-Path $output 'manifest.json') -Encoding utf8
 if(-not $passed){throw "Renderer startup failed: $output"}
 Write-Output 'PASS real boot, Ultra DLSS menu, both maps, spawn reveals and return-to-menu; inspect ten images.'
}finally{foreach($name in $saved.Keys){[Environment]::SetEnvironmentVariable($name,$saved[$name],'Process')}}
