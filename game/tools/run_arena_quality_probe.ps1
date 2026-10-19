param(
 [ValidateSet('reference','dlss','dlss-half')][string]$Mode='dlss',
 [ValidateSet('skyfall','faceoff')][string]$Map='skyfall',
 [ValidateRange(20,120)][int]$SimulationFps=60,
 [switch]$RealTime,
 [switch]$EngineVerbose,
 [switch]$FullHD,
 [ValidateSet('lighting','regolith-aprons','sky-motion')][string]$ViewSet='lighting',
 [ValidateRange(128,16384)][int]$ReferenceSamples=1023,
 [ValidateRange(1,32)][int]$ReferenceBatchSamples=32,
 [ValidateSet('?','D','E')][string]$RRPreset='?',
 [ValidateRange(60,7200)][int]$CaptureTimeoutSeconds=600,
 [ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Prefix='arena-quality',
 [string]$Godot=(Join-Path $PSScriptRoot '../../engine/bin/godot.windows.editor.x86_64.console.exe')
)
$ErrorActionPreference='Stop'
if($ViewSet -eq 'sky-motion' -and $Mode -eq 'reference'){throw 'Moving camera capture cannot use fixed-view reference accumulation.'}



$project=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$engine=[IO.Path]::GetFullPath((Join-Path $project '../engine'))
$output=Join-Path $project "reports/performance/$Prefix-$Map-$Mode"
if(Test-Path -LiteralPath $output){throw 'Use a fresh arena quality prefix.'}
if(Get-CimInstance Win32_Process | Where-Object {$_.Name -like 'godot*' -or $_.Name -in @('KYLR.exe','KylrRTXDiagnostic.exe','blender.exe')}){throw 'Finish other renderer jobs before arena image qualification.'}
New-Item -ItemType Directory $output | Out-Null
$binary=Join-Path (Split-Path $Godot) 'godot.windows.editor.x86_64.exe'
$probe=Join-Path $project 'tools/probe_arena_denoiser_quality.gd'
$hash=(Get-FileHash -LiteralPath $binary).Hash
$probeHash=(Get-FileHash -LiteralPath $probe).Hash
$helper=Join-Path $project 'tools/hdr_reference_accumulator.gd'
$helperHash=(Get-FileHash -LiteralPath $helper).Hash
$observer=Join-Path $project 'scripts/debug/reconstruction_observer.gd'
$wrapperHash=(Get-FileHash -LiteralPath $PSCommandPath).Hash
$launcherHash=(Get-FileHash -LiteralPath $Godot).Hash
function Get-ArenaInputPaths {
 $paths=@($PSCommandPath,(Join-Path $project 'project.godot'),(Join-Path $project 'main.tscn'),(Join-Path $project 'app.tscn'))
 foreach($relative in @('scripts','data','assets','shaders','addons','tools','.godot/imported')){
  $paths+=@(Get-ChildItem -LiteralPath (Join-Path $project $relative) -File -Recurse | Where-Object {$_.FullName -notmatch '[\\/]__pycache__[\\/]'} | Select-Object -ExpandProperty FullName)
 }
 return @($paths|Sort-Object -Unique)
}
function Get-ArenaRuntimePaths {
 return @(Get-ChildItem -LiteralPath (Split-Path $Godot) -Filter '*.dll' -File -Recurse|Sort-Object FullName|Select-Object -ExpandProperty FullName)
}
$inputPaths=@(Get-ArenaInputPaths)
$frozenInputs=@($inputPaths|ForEach-Object {@{path=$_;sha256=(Get-FileHash -LiteralPath $_).Hash}})
$runtimePaths=@(Get-ArenaRuntimePaths)
$runtime=@($runtimePaths|ForEach-Object {@{name=[IO.Path]::GetRelativePath((Split-Path $Godot),$_);sha256=(Get-FileHash -LiteralPath $_).Hash}})
$saved=@{}
foreach($key in @('GODOT_DLSS_DIAGNOSTICS','VK_LAYER_PATH','VK_INSTANCE_LAYERS','VK_VALIDATION_VALIDATE_SYNC','GODOT_DLSS_RR_HISTORY_REJECTION')){$saved[$key]=[Environment]::GetEnvironmentVariable($key,'Process')}
$extraEnvironment=@('GODOT_DLSS_RR_TRANSPARENCY_LAYER','GODOT_DLSS_RR_OPAQUE_PARTICLE_GUIDES','GODOT_DLSS_RENDERER_EXPOSURE','GODOT_RT_LIGHT_PROPOSALS','GODOT_RT_LIGHT_PROPOSALS_DIAGNOSTICS','GODOT_RT_LIGHT_PROPOSALS_BAD_PDF','GODOT_RT_LIGHT_GRID','GODOT_RT_LIGHT_GRID_DIAGNOSTICS','GODOT_RT_LIGHT_GRID_OMIT_LIGHT')
foreach($key in $extraEnvironment){$saved[$key]=[Environment]::GetEnvironmentVariable($key,'Process')}
try{
 $env:GODOT_DLSS_DIAGNOSTICS=if($Mode -eq 'reference'){'0'}else{'1'}
 foreach($key in $extraEnvironment){[Environment]::SetEnvironmentVariable($key,$null,'Process')}
 $env:GODOT_RT_LIGHT_GRID='0'




 $env:VK_LAYER_PATH=Join-Path $engine '.local/vulkan-validation-1.4.363.0/Bin'
 if(-not(Test-Path -LiteralPath (Join-Path $env:VK_LAYER_PATH 'VkLayer_khronos_validation.json'))){throw 'Pinned validation layer missing.'}
 $env:VK_INSTANCE_LAYERS='VK_LAYER_KHRONOS_validation';$env:VK_VALIDATION_VALIDATE_SYNC='true'
 $env:GODOT_DLSS_RR_HISTORY_REJECTION=$null

 $arguments=@('--path',('"'+$project+'"'),'--render-thread','safe','--gpu-validation','--script','res://tools/probe_arena_denoiser_quality.gd')
 if(-not $RealTime){$arguments+=@('--fixed-fps',"$SimulationFps")}
 $arguments+=@('--',"--mode=$Mode","--map=$Map",('--report-dir='+$output.Replace('\','/')))

 $arguments+="--view-set=$ViewSet"
 $arguments+="--reference-spp=$ReferenceSamples"
 $arguments+="--reference-batch-spp=$ReferenceBatchSamples"
 $arguments+="--rr-preset=$RRPreset"
 $arguments+="--timeout-seconds=$CaptureTimeoutSeconds"
 if($FullHD){$arguments+='--full-hd=true'}
 Copy-Item -LiteralPath $probe -Destination (Join-Path $output 'probe.source.gd')
 Copy-Item -LiteralPath $helper -Destination (Join-Path $output 'hdr_reference_accumulator.source.gd')
 Copy-Item -LiteralPath $observer -Destination (Join-Path $output 'denoiser_quality_observer.source.gd')
 Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $output 'wrapper.source.ps1')
 $process=Start-Process -FilePath $Godot -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $output 'probe.log') -RedirectStandardError (Join-Path $output 'errors.log')
 if(-not $process.WaitForExit(($CaptureTimeoutSeconds+60)*1000)){$process.Kill($true);throw 'Arena quality capture timed out.'}
 $process.Refresh()
 $log=(Get-Content -LiteralPath (Join-Path $output 'probe.log') -Raw)+(Get-Content -LiteralPath (Join-Path $output 'errors.log') -Raw)
 if($process.ExitCode -ne 0 -or $log -match 'ERROR:|SCRIPT ERROR:|VUID-|SYNC-HAZARD|ObjectDB instances were leaked' -or $log -notmatch "ARENA_QUALITY_CAPTURE_PASS $Map $Mode" -or $log -notmatch 'VK_LAYER_KHRONOS_validation'){throw "Arena quality capture failed: $output"}
 $report=Get-Content -LiteralPath (Join-Path $output 'report.json') -Raw|ConvertFrom-Json
 $caseCount=if($ViewSet -eq 'sky-motion'){1}elseif($ViewSet -eq 'regolith-aprons'){3}else{2}
 $imagesPerCase=if($ViewSet -eq 'sky-motion'){32}elseif($Mode -eq 'reference'){4}else{16}
 $expected=$caseCount*$imagesPerCase
 if(-not $report.complete -or $report.cases.Count -ne $caseCount -or @(Get-ChildItem -LiteralPath $output -Filter '*.png' -File).Count -ne $expected){throw 'Incomplete arena quality report.'}
 if($Mode -ne 'reference'){
  foreach($case in $report.cases){if($case.denoiser.error -or $case.denoiser.adapter.backend -ne 'DLSS' -or -not $case.denoiser.adapter.evaluation_succeeded -or $case.denoiser.adapter.frames -le 0){throw 'Arena capture lacks native DLSS evaluation evidence.'}}
 }
 if($report.capture_revision -ne 6 -or $report.view_set -ne $ViewSet -or $report.reference_helper_sha256.ToUpperInvariant() -ne $helperHash){throw 'Arena HDR reference helper provenance differs.'}
 if([bool]$report.camera_motion -ne ($ViewSet -eq 'sky-motion')){throw 'Camera-motion configuration differs.'}
 if($ViewSet -eq 'sky-motion'){
  $case=$report.cases[0]
  if($case.camera_frames.Count -ne 32 -or ($case.camera_frames.file -join ',') -ne ($case.files -join ',')){throw 'Incomplete moving-camera pose coverage.'}
  for($index=1;$index -lt 32;$index++){
   $delta=$case.camera_frames[$index].yaw_radians-$case.camera_frames[$index-1].yaw_radians
   if([Math]::Abs($delta-0.08*[Math]::PI/180) -gt 0.000001){throw 'Camera did not follow the requested rotation steps.'}
  }
  $before=$case.denoiser_before.adapter;$after=$case.denoiser.adapter
  $evaluations=$after.frames-$before.frames
  if(-not $before.evaluation_succeeded -or $evaluations -lt 31 -or $evaluations -gt 34 -or $after.resets-$before.resets -gt 1){throw 'Native RR did not continuously evaluate the rotating-camera capture.'}
 }
 if($ViewSet -eq 'regolith-aprons'){
  $asset=if($Map -eq 'skyfall'){'bunker'}else{'shelter'}
  if($report.asset_placement.asset -ne $asset -or -not $report.asset_placement.fixture -or $report.asset_placement.surfaces.Count -lt 1 -or ($report.cases.name -join ',') -ne "$asset-hero,$asset-ground,$asset-side"){throw 'Missing authored apron placement views.'}
  foreach($channel in @('albedo','normal','orm')){if($report.asset_placement.textures.$channel -ne (Get-FileHash -LiteralPath (Join-Path $project "assets/textures/lunar_surface/regolith_$channel.png")).Hash){throw 'Captured apron texture hash differs.'}}
 }
 $denoiser=@{reference=0;dlss=1;'dlss-half'=1}[$Mode]
 $scale=if($Mode -eq 'dlss-half'){.5}else{1.0}
 if(-not $report.renderer.pathtracing_enabled -or $report.renderer.denoiser -ne $denoiser -or $report.renderer.max_bounces -ne 3 -or [Math]::Abs($report.renderer.internal_scale-$scale) -gt .001){throw 'Actual arena renderer configuration differs from the requested backend.'}
 $dispatchSpp=if($Mode -eq 'reference'){$remainder=$ReferenceSamples%$ReferenceBatchSamples;if($remainder -eq 0){$ReferenceBatchSamples}else{$remainder}}else{1}
 if($report.renderer.samples_per_pixel -ne $dispatchSpp){throw 'Actual arena ray dispatch sample count differs.'}

 if($report.rr_preset_requested -ne $RRPreset -or $report.reference_batch_spp -ne $ReferenceBatchSamples -or $log -notmatch ('ARENA_QUALITY_RR_PRESET '+[regex]::Escape($RRPreset))){throw 'Arena requested model or dispatch budget differs.'}
 if($Mode -eq 'reference'){
  if($report.renderer.scaling_mode -ne 0 -or $report.renderer.taa -or $report.renderer.msaa -ne 0 -or $report.renderer.screen_space_aa -ne 0){throw 'Raw arena reference unexpectedly uses reconstruction or antialiasing.'}
  $names=@($report.cases|ForEach-Object {$_.files}|ForEach-Object {$_})
  if(($report.reference_captures.name -join ',') -ne ($names -join ',')){throw 'Arena reference capture coverage differs.'}
  foreach($capture in $report.reference_captures){
   if(-not $capture.linear_hdr -or $capture.samples_per_internal_pixel -ne $ReferenceSamples -or $capture.completed_weight -ne $ReferenceSamples -or ($capture.batches|Measure-Object -Sum).Sum -ne $ReferenceSamples -or @($capture.batches|Where-Object {$_ -le 0 -or $_ -gt $ReferenceBatchSamples}).Count){throw 'Arena reference did not preserve its full HDR sample budget.'}
  }
 }elseif(@($report.reference_captures).Count -ne 0){throw 'Arena candidate unexpectedly used reference accumulation.'}
 $size=if($FullHD){@(1920,1080)}else{@(640,360)}
 if($report.output[0] -ne $size[0] -or $report.output[1] -ne $size[1] -or $report.reference_spp -ne $ReferenceSamples){throw 'Actual capture dimensions/sample budget differ from the request.'}
 if($hash -ne (Get-FileHash -LiteralPath $binary).Hash -or $probeHash -ne (Get-FileHash -LiteralPath $probe).Hash){throw 'Engine/probe changed during capture.'}
 foreach($file in $runtime){if($file.sha256 -ne (Get-FileHash -LiteralPath (Join-Path (Split-Path $Godot) $file.name)).Hash){throw 'Runtime changed during capture.'}}
 if($helperHash -ne (Get-FileHash -LiteralPath $helper).Hash){throw 'Arena HDR reference helper changed during capture.'}
 if((Get-FileHash -LiteralPath $Godot).Hash -ne $launcherHash -or (Get-FileHash -LiteralPath $PSCommandPath).Hash -ne $wrapperHash){throw 'Arena launcher/wrapper changed during capture.'}
 if(Compare-Object $inputPaths @(Get-ArenaInputPaths)){throw 'Arena input paths changed during capture.'}
 if(Compare-Object $runtimePaths @(Get-ArenaRuntimePaths)){throw 'Arena runtime paths changed during capture.'}
 foreach($frozenInput in $frozenInputs){if((Get-FileHash -LiteralPath $frozenInput.path).Hash -ne $frozenInput.sha256){throw "Arena input changed during capture: $($frozenInput.path)"}}

 @{capture_passed=$true;validation=$true;capture_revision=6;camera_motion=($ViewSet -eq 'sky-motion');rr_preset_requested=$RRPreset;reference_batch_spp=$ReferenceBatchSamples;view_set=$ViewSet;settings_control_revision=3;light_grid=$false;light_proposals=$false;input_coverage='project-scripts-data-assets-shaders-addons-tools-imported-v1';wrapper_sha256=$wrapperHash;engine_entrypoint_sha256=$launcherHash;engine_sha256=$hash;probe_sha256=$probeHash;reference_helper_sha256=$helperHash;runtime_dlls=$runtime;inputs=$frozenInputs;real_time=[bool]$RealTime;simulation_fps=$(if($RealTime){$null}else{$SimulationFps});full_game_quality_acceptance=$false;performance_acceptance=$false}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $output 'manifest.json') -Encoding utf8
 Write-Output "PASS $Map $Mode $ViewSet captures. Image review required; not an FPS result."
}finally{foreach($key in $saved.Keys){[Environment]::SetEnvironmentVariable($key,$saved[$key],'Process')}}
