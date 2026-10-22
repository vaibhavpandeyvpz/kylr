#Requires -Version 7.4
param(
    [ValidateSet('skyfall','faceoff')][string[]]$Maps=@('skyfall','faceoff'),
    [ValidateRange(0,2)][int[]]$Quality=@(0,1,2),
    [ValidateRange(8,60)][int]$Seconds=12,
    [ValidateSet('safe','separate')][string]$RenderThread='safe',
    [string]$ReportName='arena-stress',
    [ValidateRange(1,16)][int]$DecisionPhases=1,
    [switch]$Repack,
    [switch]$PresetLighting,
    [switch]$Costs,
    [switch]$GpuProfile,
    [switch]$RenderTiming,
    [ValidateRange(0.5,1.0)][Nullable[double]]$RasterScale=$null,
    [ValidateSet('fsr2','bilinear')][string]$RasterUpscaler='fsr2',
    [ValidateRange(0,16)][int]$GPUIndex=0,
    [string]$ExpectedGPU='',
    [ValidateSet('project','off','on')][string]$VSync='project',
    [string]$RuntimeDirectory='reports/performance/release-diagnostic'
)
$ErrorActionPreference='Stop'
$failurePattern='^ERROR:|SCRIPT ERROR|VUID-|SYNC-HAZARD|instances were leaked|Leaked instance:'
$gameRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $gameRoot
$editor=(Get-Command $(if ($env:GODOT) { $env:GODOT } else { 'godot' }) -ErrorAction Stop).Source
$RuntimeDirectory=[IO.Path]::GetFullPath($RuntimeDirectory,$gameRoot)
if(Get-CimInstance Win32_Process | Where-Object {$_.Name -like 'godot*' -or $_.Name -eq 'KylrDiagnostic.exe'}){throw 'Finish other engine jobs before this serial benchmark.'}
if($Repack){
    & $editor --headless --path $gameRoot -s res://tools/pack_rendered_profile.gd -- "--output=$RuntimeDirectory" *> reports/performance/arena-stress-pack.log
    if($LASTEXITCODE -ne 0){throw 'Diagnostic pack failed'}
}
$runtime=(Resolve-Path (Join-Path $RuntimeDirectory 'KylrDiagnostic.exe')).Path
$pack=[IO.Path]::ChangeExtension($runtime,'.pck')
$package=Get-Content -LiteralPath (Join-Path $RuntimeDirectory 'manifest.json') -Raw | ConvertFrom-Json
if(-not $package.pack_content_verified -or $package.verified_payloads -ne $package.files -or $package.files -lt 1 -or $package.engine_sha256 -ne (Get-FileHash $runtime).Hash -or $package.pack_sha256 -ne (Get-FileHash $pack).Hash){throw 'Diagnostic package payload/hash verification failed; repack first.'}
$report=Join-Path $gameRoot "reports/performance/$ReportName"
if(Test-Path -LiteralPath $report){throw 'Choose a fresh report name; preserve previous evidence.'}
New-Item -ItemType Directory -Force $report | Out-Null
$manifest=@{completed=$false;render_thread=$RenderThread;decision_phases=$DecisionPhases;game_head=(git rev-parse HEAD);engine_sha256=(Get-FileHash $runtime).Hash;pack_sha256=(Get-FileHash $pack).Hash;runs=@()}
$manifestPath=Join-Path $report 'matrix.json'
$manifest.preset_lighting=[bool]$PresetLighting
$manifest.performance_acceptance=$false
$manifest.quality_acceptance=$false
$manifest.cpu_instrumentation=[bool]$Costs
$manifest.gpu_instrumentation=[bool]$GpuProfile
$manifest.render_timing_instrumented=[bool]$RenderTiming
$manifest.diagnostic_raster_scale=$RasterScale
$manifest.diagnostic_raster_upscaler=$(if($null -ne $RasterScale){$RasterUpscaler}else{$null})
$manifest.gpu_index=$GPUIndex
$manifest.expected_gpu=$ExpectedGPU
$manifest.vsync_policy=$VSync
$manifest.wrapper_sha256=(Get-FileHash -LiteralPath $PSCommandPath).Hash
foreach($map in $Maps){foreach($preset in $Quality){
    $name="$map-q$preset"
    $argsList=@('--gpu-index',"$GPUIndex",'--render-thread',$RenderThread,'--','--arena-stress=1',"--map=$map",'--mode=DM','--robots=10',"--quality=$preset",'--width=1920','--height=1080','--warmup=6','--combat-warmup=5',"--seconds=$Seconds",'--seed=120','--frame-times-only=1',"--name=$name","--report-dir=$($report.Replace('\','/'))")
    if($RenderTiming){$argsList=@($argsList | Where-Object {$_ -ne '--frame-times-only=1'})}
    $argsList+=@("--vsync=$VSync","--decision-phases=$DecisionPhases",'--target-fps=60')
    if($GpuProfile){$argsList=@('--gpu-profile')+$argsList;$argsList+='--gpu-profile-markers=1'}
    if($Costs){$argsList+='--costs=1'}
    if($null -ne $RasterScale){$argsList+=@("--diagnostic-raster-scale=$($RasterScale.ToString([Globalization.CultureInfo]::InvariantCulture))","--diagnostic-raster-upscaler=$RasterUpscaler")}
    if($PresetLighting){$argsList+='--preset-lighting=1'}
    $stdout=Join-Path $report "$name.stdout.log"
    $stderr=Join-Path $report "$name.stderr.log"
    Write-Output "RUN $name"
    $run=Start-Process -FilePath $runtime -ArgumentList $argsList -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    if(-not $run.WaitForExit(180000+$Seconds*1000)){
        if(-not $run.HasExited){$run.Kill()}
        throw "Stress diagnostic timed out: $name"
    }
    if($run.ExitCode -ne 0 -or (Select-String -Path $stdout,$stderr -Pattern $failurePattern)){throw "Stress diagnostic failed: $name"}
    $result=Get-Content (Join-Path $report "$name.json") -Raw | ConvertFrom-Json
    if([bool]$result.gpu_timing_sampled -ne [bool]$RenderTiming){throw "Render timing mode mismatch: $name"}
    if($ExpectedGPU -and -not $result.adapter.Contains($ExpectedGPU,[StringComparison]::OrdinalIgnoreCase)){throw "Unexpected GPU '$($result.adapter)', expected '$ExpectedGPU': $name"}
    if($result.display.vsync -ne $result.display.requested_vsync -or ($VSync -eq 'off' -and $result.display.vsync -ne 0) -or ($VSync -eq 'on' -and $result.display.vsync -ne 1)){throw "Presentation mode mismatch: $name"}
    if(-not $result.rendering_preparation.ready -or -not $result.rendering_preparation.loading_overlay -or $result.rendering_preparation.warmup_orbit_degrees -lt 360){throw "Rendered scene was not fully prepared under the loading screen: $name"}
    if(-not $result.rendering_preparation.preparation_audio_muted -or -not $result.rendering_preparation.audio_state_restored){throw "Benchmark preparation audio was not muted/restored correctly: $name"}
    if(-not $result.release -or -not $result.arena_stress.valid -or [bool]$result.arena_stress.preset_lighting -ne [bool]$PresetLighting){throw "Stress coverage failed: $name"}
    $expectedFixtures= -not $PresetLighting -or $preset -ge 2
    if([bool]$result.quality_settings.fixture_lighting -ne $expectedFixtures -or (-not $PresetLighting -and @($result.environments | Where-Object {-not $_.sdfgi_enabled}).Count)){throw "Preset lighting mismatch: $name"}
    if(-not $expectedFixtures -and ($result.fixture_light_state.illuminating -ne 0 -or $result.fixture_light_state.shadow_casting -ne 0)){throw "Disabled preset fixtures still illuminate: $name"}
    if($expectedFixtures -and ($result.fixture_light_state.illuminating -ne $result.fixture_light_state.total -or ($result.quality_settings.shadows -and $result.fixture_light_state.shadow_casting -ne $result.fixture_light_state.total))){throw "Enabled preset fixtures lack illumination/shadows: $name"}
    $expectedJumbotron=if($map -eq 'skyfall'){35.0}else{20.0}
    if($result.arena_stress.fixture_lights -ne 16 -or [Math]::Abs($result.arena_stress.jumbotron_height_m-$expectedJumbotron) -gt 0.01){throw "Lighting rig or jumbotron placement failed: $name"}
    if($null -ne $RasterScale){
        $expectedMode=if($RasterUpscaler -eq 'fsr2'){2}else{0}
        if($result.quality_settings.msaa_3d -ne 0 -or $result.quality_settings.scaling_3d_mode -ne $expectedMode -or [Math]::Abs($result.quality_settings.scaling_3d_scale-$RasterScale) -gt .001){throw "Raster reconstruction diagnostic mismatch: $name"}
    }
    $hitches=@($result.frame_intervals_ms | Where-Object {$_ -gt 100}).Count
    $manifest.runs+=@{name=$name;adapter=$result.adapter;fps=$result.average_fps;p95_ms=$result.frame_ms.p95;p99_ms=$result.frame_ms.p99;max_ms=$result.frame_ms.max;frames_over_100ms=$hitches;coverage=$result.arena_stress.valid}
    $manifest | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 $manifestPath
    Write-Output "RESULT $name FPS=$($result.average_fps) p95=$($result.frame_ms.p95) max=$($result.frame_ms.max) hitches=$hitches"
}}
$manifest.completed=$true
if((Get-FileHash -LiteralPath $PSCommandPath).Hash -ne $manifest.wrapper_sha256){throw 'Benchmark wrapper changed during measurement.'}
if((Get-FileHash $runtime).Hash -ne $manifest.engine_sha256 -or (Get-FileHash $pack).Hash -ne $manifest.pack_sha256){throw 'Runtime/package changed during measurement.'}
$manifest | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 $manifestPath
