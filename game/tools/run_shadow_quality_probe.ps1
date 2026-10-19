param(
 [ValidateSet('reference','dlss','dlss-half')][string]$Mode='dlss',
 [ValidateRange(640,1920)][int]$Width=640,
 [ValidateRange(360,1080)][int]$Height=360,
 [ValidateSet('safe','separate')][string]$RenderThread='safe',
 [ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Prefix=('shadow-quality-'+(Get-Date -Format 'yyyyMMdd-HHmmss')),
 [string]$Godot=(Join-Path $PSScriptRoot '../../engine/bin/godot.windows.editor.x86_64.console.exe')
)
$ErrorActionPreference='Stop'


if(Get-CimInstance Win32_Process | Where-Object {$_.Name -like 'godot*' -or $_.Name -in @('KYLR.exe','KylrRTXDiagnostic.exe','blender.exe') -or ($_.Name -eq 'python.exe' -and $_.CommandLine -like '*SCons*')}){throw 'Finish other engine builds and renderer jobs before shadow capture.'}
$project=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$output=Join-Path $project "reports/performance/$Prefix-$Mode"
if (Test-Path -LiteralPath $output) {throw 'Choose a fresh shadow report prefix.'}
$binary=Join-Path (Split-Path $Godot) 'godot.windows.editor.x86_64.exe'
$probe=Join-Path $project 'tools/probe_shadow_quality.gd'
$hash=(Get-FileHash -LiteralPath $binary).Hash;$probeHash=(Get-FileHash -LiteralPath $probe).Hash
$observer=Join-Path $project 'scripts/debug/reconstruction_observer.gd'
$observerHash=(Get-FileHash -LiteralPath $observer).Hash
$launcherHash=(Get-FileHash -LiteralPath $Godot).Hash
$wrapperHash=(Get-FileHash -LiteralPath $PSCommandPath).Hash
function Get-ShadowInputPaths {
 $paths=@($PSCommandPath,(Join-Path $project 'project.godot'),(Join-Path $project 'main.tscn'),(Join-Path $project 'app.tscn'))
 foreach($relative in @('scripts','data','assets','shaders','addons','tools','.godot/imported')){
  $paths+=@(Get-ChildItem -LiteralPath (Join-Path $project $relative) -File -Recurse | Where-Object {$_.FullName -notmatch '[\\/]__pycache__[\\/]'} | Select-Object -ExpandProperty FullName)
 }
 return @($paths | Sort-Object -Unique)
}
function Get-ShadowRuntimePaths {
 return @(Get-ChildItem -LiteralPath (Split-Path $Godot) -Filter '*.dll' -File -Recurse | Sort-Object FullName | Select-Object -ExpandProperty FullName)
}
$inputPaths=@(Get-ShadowInputPaths)
$frozenInputs=@($inputPaths | ForEach-Object {@{path=$_;sha256=(Get-FileHash -LiteralPath $_).Hash}})
$frozenInputs | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath "$output-inputs-before.json" -Encoding utf8
$runtimePaths=@(Get-ShadowRuntimePaths)
$runtime=@($runtimePaths | ForEach-Object {@{name=[IO.Path]::GetRelativePath((Split-Path $Godot),$_);sha256=(Get-FileHash -LiteralPath $_).Hash}})
$saved=@{}
$saved['GODOT_DLSS_DIAGNOSTICS']=[Environment]::GetEnvironmentVariable('GODOT_DLSS_DIAGNOSTICS','Process')
foreach ($name in @('GODOT_RT_LIGHT_PROPOSALS','GODOT_RT_LIGHT_PROPOSALS_DIAGNOSTICS','GODOT_RT_LIGHT_PROPOSALS_BAD_PDF','GODOT_RT_LIGHT_GRID','GODOT_RT_LIGHT_GRID_DIAGNOSTICS','GODOT_RT_LIGHT_GRID_OMIT_LIGHT','GODOT_DLSS_RR_HISTORY_REJECTION','VK_LAYER_PATH','VK_INSTANCE_LAYERS','VK_VALIDATION_VALIDATE_SYNC')) {
 $saved[$name]=[Environment]::GetEnvironmentVariable($name,'Process')
}
try {
 $env:GODOT_DLSS_DIAGNOSTICS=if($Mode -eq 'reference'){'0'}else{'1'}
 foreach($name in @('GODOT_RT_LIGHT_PROPOSALS','GODOT_RT_LIGHT_PROPOSALS_DIAGNOSTICS','GODOT_RT_LIGHT_PROPOSALS_BAD_PDF','GODOT_RT_LIGHT_GRID_DIAGNOSTICS','GODOT_RT_LIGHT_GRID_OMIT_LIGHT','GODOT_DLSS_RR_HISTORY_REJECTION')){[Environment]::SetEnvironmentVariable($name,$null,'Process')}
 $env:GODOT_RT_LIGHT_GRID='0'




 $env:VK_LAYER_PATH=[IO.Path]::GetFullPath((Join-Path $project '../engine/.local/vulkan-validation-1.4.363.0/Bin'))
 if (-not (Test-Path -LiteralPath (Join-Path $env:VK_LAYER_PATH 'VkLayer_khronos_validation.json'))) {throw 'Pinned validation layer missing.'}
 $env:VK_INSTANCE_LAYERS='VK_LAYER_KHRONOS_validation';$env:VK_VALIDATION_VALIDATE_SYNC='true'
 $stdout="$output.log";$stderr="$output-errors.log"
 $arguments=@('--path',('"'+$project+'"'),'--render-thread',$RenderThread,'--gpu-validation','--script','res://tools/probe_shadow_quality.gd','--',"--mode=$Mode","--prefix=$Prefix","--width=$Width","--height=$Height")

 $started=[DateTime]::UtcNow
 $process=Start-Process -FilePath $Godot -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
 if (-not $process.WaitForExit(360000)) {$process.Kill($true);throw 'Shadow capture timed out.'}
 $process.Refresh()
 $log=(Get-Content -LiteralPath $stdout -Raw)+(Get-Content -LiteralPath $stderr -Raw)
 if ($process.ExitCode -ne 0 -or $log -match 'ERROR:|SCRIPT ERROR:|VUID-|SYNC-HAZARD|ObjectDB.*leaked at exit|Resources still in use' -or $log -notmatch "SHADOW_QUALITY_CAPTURE_PASS $Mode" -or $log -notmatch 'Inserted device layer "VK_LAYER_KHRONOS_validation"' -or $log -notmatch '  - Synchronization') {throw "Shadow capture failed: $stderr"}
 $report=Get-Content -LiteralPath (Join-Path $output 'report.json') -Raw|ConvertFrom-Json
 $expected=4
 if ($report.cases.Count -ne $expected) {throw 'Missing shadow fixtures.'}
 if($report.capture_revision -ne 2 -or $report.observer_sha256.ToUpperInvariant() -ne $observerHash){throw 'Shadow observer provenance differs.'}

 foreach ($case in $report.cases) {
  if($Mode -ne 'reference' -and ($case.denoiser_after.error -or $case.denoiser_after.adapter.backend -ne 'DLSS' -or -not $case.denoiser_after.adapter.evaluation_succeeded -or $case.denoiser_after.adapter.frames -le $case.denoiser_before.adapter.frames)){throw 'Shadow capture lacks advancing native DLSS evaluation.'}
  $image=Get-Item -LiteralPath (Join-Path $output $case.image)
  if ($image.LastWriteTimeUtc -lt $started -or $image.Length -eq 0) {throw 'Missing or stale shadow image.'}

 }
 if ($hash -ne (Get-FileHash -LiteralPath $binary).Hash -or $probeHash -ne (Get-FileHash -LiteralPath $probe).Hash) {throw 'Engine or shadow fixture changed during capture.'}
 if($observerHash -ne (Get-FileHash -LiteralPath $observer).Hash -or $launcherHash -ne (Get-FileHash -LiteralPath $Godot).Hash -or $wrapperHash -ne (Get-FileHash -LiteralPath $PSCommandPath).Hash){throw 'Shadow observer, launcher or wrapper changed during capture.'}
 if(Compare-Object $inputPaths @(Get-ShadowInputPaths)){throw 'Shadow dependency paths were added or removed.'}
 foreach($inputFile in $frozenInputs){if((Get-FileHash -LiteralPath $inputFile.path).Hash -ne $inputFile.sha256){throw "Shadow dependency changed: $($inputFile.path)"}}
 if(Compare-Object $runtimePaths @(Get-ShadowRuntimePaths)){throw 'Shadow runtime dependency paths changed.'}
 foreach($file in $runtime){if($file.sha256 -ne (Get-FileHash -LiteralPath (Join-Path (Split-Path $Godot) $file.name)).Hash){throw 'Runtime DLL changed during shadow capture.'}}
 @{engine_sha256=$hash;probe_sha256=$probeHash;mode=$Mode;validation=$true;capture_passed=$true;
   settings_control_revision=2;
   light_grid=$false;light_proposals=$false;render_thread=$RenderThread;
   inputs=$frozenInputs;input_coverage='project-scripts-data-assets-shaders-addons-tools-imported-v1';
   capture_revision=2;observer_sha256=$observerHash;engine_entrypoint_sha256=$launcherHash;wrapper_sha256=$wrapperHash;runtime_dlls=$runtime;
   visual_quality_acceptance=$false;performance_acceptance=$false} |
  ConvertTo-Json | Set-Content -LiteralPath (Join-Path $output 'manifest.json') -Encoding utf8
 Write-Output "PASS $Mode shadow captures ($expected cases). Reference comparison remains required."
} finally {
 foreach ($name in $saved.Keys) {[Environment]::SetEnvironmentVariable($name,$saved[$name],'Process')}
}
