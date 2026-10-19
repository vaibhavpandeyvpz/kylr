param(
    [ValidateSet('skyfall','faceoff')][string[]]$Maps=@('skyfall','faceoff'),
    [ValidateRange(12,60)][int]$Seconds=12,
    [ValidateRange(1,1000)][int]$TargetFPS=30,
    [ValidateSet('project','off','on')][string]$VSync='project',
    [ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$ReportName='dlss-benchmark',
    [string]$RuntimeDirectory='reports/performance/release-diagnostic',
    [ValidateRange(1,16)][Nullable[int]]$DecisionPhases=$null,
    [switch]$QueryShadows,
    [switch]$LightGrid,
    [switch]$OpaqueParticleDepth,
    [switch]$OpaqueParticleGuides,
    [switch]$MaterialAudit,
    [switch]$AlphaIsolation,
    [ValidateSet('overview','effects','layered')][string]$AlphaGroups='overview',
    [switch]$GpuValidation,
    [switch]$GpuProfile,
    [switch]$Costs,
    [switch]$DisableUpscaling,
    [switch]$DisablePrimaryTextureGradients,
    [switch]$Repack,
    [ValidateSet('?','D','E')][string]$RRPreset='?'
)
$ErrorActionPreference='Stop'
if($OpaqueParticleGuides){throw 'The unqualified particle-guide experiment has been removed from the engine.'}
if($AlphaIsolation -and (-not $GpuProfile -or $Seconds -ne 56)){throw 'Alpha isolation requires -GpuProfile -Seconds 56; it is not FPS acceptance.'}
$queryOverride=$PSBoundParameters.ContainsKey('QueryShadows')
$opaqueDepthOverride=$PSBoundParameters.ContainsKey('OpaqueParticleDepth')
$wrapperHash=(Get-FileHash -LiteralPath $PSCommandPath).Hash
$gameRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $gameRoot
$engine=(Resolve-Path '../engine').Path
$editor=Join-Path $engine 'bin/godot.windows.editor.x86_64.console.exe'
$RuntimeDirectory=[IO.Path]::GetFullPath($RuntimeDirectory,$gameRoot)
$interference=@(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -like 'godot*' -or $_.Name -eq 'KylrRTXDiagnostic.exe' -or ($_.Name -eq 'python.exe' -and $_.CommandLine -like '*SCons*')
})
if($interference.Count){throw 'Finish other engine builds and renderer jobs before this serial benchmark.'}
if($Repack){
    & $editor --headless --path $gameRoot -s res://tools/pack_rendered_profile.gd -- "--output=$RuntimeDirectory" *> "reports/performance/$ReportName-pack.log"
    if($LASTEXITCODE -ne 0){throw 'Diagnostic pack failed'}
}
$runtime=(Resolve-Path (Join-Path $RuntimeDirectory 'KylrRTXDiagnostic.exe')).Path
$runtimeHash=(Get-FileHash -LiteralPath $runtime).Hash
$packHash=(Get-FileHash -LiteralPath ([IO.Path]::ChangeExtension($runtime,'.pck'))).Hash
$package=Get-Content -LiteralPath (Join-Path $RuntimeDirectory 'manifest.json') -Raw | ConvertFrom-Json
if($package.pack_content_verified -ne $true -or $package.verified_payloads -ne $package.files -or $package.files -lt 1 -or $package.engine_sha256 -ne $runtimeHash -or $package.pack_sha256 -ne $packHash){throw 'Diagnostic package lacks matching payload verification. Repack before benchmarking.'}
$report=Join-Path $gameRoot "reports/performance/$ReportName"
if(Test-Path -LiteralPath $report){throw 'Use a fresh report name to preserve prior evidence.'}
New-Item -ItemType Directory -Path $report | Out-Null
$scale=if($DisableUpscaling){1.0}else{0.5}
$runtimeRoot=Split-Path $runtime
$runtimeDependencies=@(Get-ChildItem -LiteralPath $runtimeRoot -Filter '*.dll' -File -Recurse | Sort-Object FullName)
$manifest=@{completed=$false;quality_acceptance=$false;performance_acceptance=$false;gpu_validation=[bool]$GpuValidation;gpu_profile_instrumented=[bool]$GpuProfile;monitor_instrumented=[bool]$MaterialAudit;cost_instrumented=[bool]$Costs;wrapper_sha256=$wrapperHash;
    runtime_directory=$RuntimeDirectory;started_at=(Get-Date).ToString('o');output_resolution=@(1920,1080);sample_seconds=$Seconds;target_fps=$TargetFPS;vsync_policy=$VSync;light_grid_requested=[bool]$LightGrid;opaque_particle_depth_requested=$(if($opaqueDepthOverride){[bool]$OpaqueParticleDepth}else{$null});opaque_particle_depth_active_by_map=@{};material_audit_requested=[bool]$MaterialAudit;alpha_isolation=[bool]$AlphaIsolation;alpha_groups=$AlphaGroups;
    engine_sha256=$runtimeHash;pack_sha256=$packHash;pack_content_verified=$true;verified_payloads=$package.verified_payloads;
    game_head=(git rev-parse HEAD);engine_head=(git -C $engine rev-parse HEAD);decision_phases_requested=$DecisionPhases;query_shadows_requested=$(if($queryOverride){[bool]$QueryShadows}else{$null});
    primary_texture_gradients_requested=(-not [bool]$DisablePrimaryTextureGradients);rr_preset_requested=$RRPreset;runs=@();
    runtime_dlls=@($runtimeDependencies | ForEach-Object {@{relative_path=[IO.Path]::GetRelativePath($runtimeRoot,$_.FullName);sha256=(Get-FileHash -LiteralPath $_.FullName).Hash}})}
$envNames=@('GODOT_DLSS_DIAGNOSTICS','GODOT_RT_PRIMARY_TEXTURE_GRADIENTS','GODOT_RT_LIGHT_PROPOSALS','GODOT_RT_LIGHT_GRID','GODOT_RT_LIGHT_GRID_DIAGNOSTICS','GODOT_RT_OPAQUE_PARTICLE_DEPTH','GODOT_DLSS_RR_OPAQUE_PARTICLE_GUIDES','GODOT_DLSS_RR_TRANSPARENCY_LAYER','GODOT_GPU_PROFILE_ALPHA_FILTER','GODOT_GPU_PROFILE_ALPHA_MASK','GODOT_DLSS_RR_HISTORY_REJECTION','VK_LAYER_PATH','VK_INSTANCE_LAYERS','VK_VALIDATION_VALIDATE_SYNC')
$saved=@{}
foreach($name in $envNames){$saved[$name]=[Environment]::GetEnvironmentVariable($name,'Process');[Environment]::SetEnvironmentVariable($name,$null,'Process')}
try {
	$env:GODOT_DLSS_DIAGNOSTICS='1'
    if($OpaqueParticleGuides){$env:GODOT_DLSS_RR_OPAQUE_PARTICLE_GUIDES='1'}
    $env:GODOT_RT_PRIMARY_TEXTURE_GRADIENTS=if($DisablePrimaryTextureGradients){'0'}else{'1'}
    if($LightGrid){$env:GODOT_RT_LIGHT_GRID='1';$env:GODOT_RT_LIGHT_GRID_DIAGNOSTICS='1'}
    if($opaqueDepthOverride){$env:GODOT_RT_OPAQUE_PARTICLE_DEPTH=if($OpaqueParticleDepth){'1'}else{'0'}}
    if($AlphaIsolation){$env:GODOT_GPU_PROFILE_ALPHA_FILTER='1';$env:GODOT_GPU_PROFILE_ALPHA_MASK=''}
    foreach($map in $Maps){
        $name="dlss-$map"
        $argsList=@('--render-thread','safe')
        if($GpuProfile){$argsList+='--gpu-profile'}
        if($GpuValidation){
            $env:VK_LAYER_PATH=Join-Path $engine '.local/vulkan-validation-1.4.363.0/Bin'
            if(-not(Test-Path -LiteralPath (Join-Path $env:VK_LAYER_PATH 'VkLayer_khronos_validation.json'))){throw 'Pinned validation layer missing.'}
            $argsList+='--gpu-validation';$env:VK_INSTANCE_LAYERS='VK_LAYER_KHRONOS_validation';$env:VK_VALIDATION_VALIDATE_SYNC='true'
        }
        $argsList+=@('--','--denoiser=dlss','--arena-stress=1',"--map=$map",'--mode=DM','--robots=10','--quality=3','--width=1920','--height=1080','--warmup=6','--combat-warmup=5',"--seconds=$Seconds",'--seed=120',"--name=$name","--report-dir=$($report.Replace('\','/'))","--target-fps=$TargetFPS","--rt-scale=$scale")
        if($Costs){$argsList+='--costs=1'}
        $argsList+="--vsync=$VSync"
        if($null -ne $DecisionPhases){$argsList+="--decision-phases=$DecisionPhases"}
        if($GpuProfile){$argsList+='--gpu-profile-markers=1'}
        $argsList+='--verify-native-rr=1'
        if($RRPreset-ne'?'){$argsList+="--rr-preset=$RRPreset"}
        if($AlphaIsolation){$argsList+="--alpha-isolation=$AlphaGroups"}
        if($MaterialAudit){$argsList+=@('--material-audit=1','--draw-stats=1')}else{$argsList+='--frame-times-only=1'}
        if($queryOverride){$argsList+=("--query-shadows="+[int][bool]$QueryShadows)}
        $stdout=Join-Path $report "$name.stdout.log";$stderr=Join-Path $report "$name.stderr.log"
        Write-Output "RUN $name internal_scale=$scale"
        $run=Start-Process -FilePath $runtime -ArgumentList $argsList -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        $deadline=[DateTime]::UtcNow.AddSeconds(300+$Seconds)
        while(-not $run.WaitForExit(1000)){
            if([DateTime]::UtcNow -gt $deadline){$run.Kill();$run.WaitForExit();throw "Timeout: $name"}
        }
        if($run.ExitCode -ne 0 -or (Select-String -LiteralPath $stdout,$stderr -Pattern '^ERROR:|SCRIPT ERROR|VUID-|SYNC-HAZARD|leaked at exit|Resources still in use at exit')){throw "Run failed: $name"}
        $result=Get-Content -LiteralPath (Join-Path $report "$name.json") -Raw | ConvertFrom-Json
        if($Costs -and $result.cost_instrumentation -ne 'inline_timers_v2'){throw "Missing requested CPU stage instrumentation: $name"}
        $native=$result.native_reconstruction
        if($null -eq $native -or -not $native.after.adapter.evaluation_succeeded -or -not $native.after.adapter.viewport_renderer -or $native.after.adapter.backend -ne 'DLSS' -or $native.evaluation_delta -lt ($result.frames - 4) -or $native.evaluation_delta -gt ($result.frames + 4)){throw "Native RR did not cover the measured frames. Repack if needed: $name"}
        if($native.after.adapter.size[0] -ne [int](1920*$scale) -or $native.after.adapter.size[1] -ne [int](1080*$scale) -or $native.after.adapter.output_size[0] -ne 1920 -or $native.after.adapter.output_size[1] -ne 1080){throw "Native RR dimensions differ: $name"}
        $opaqueDepthActive=[bool](Select-String -LiteralPath $stdout -Pattern '^RT_OPAQUE_PARTICLE_DEPTH active=1$')
        $opaqueGuidesActive=[bool](Select-String -LiteralPath $stdout -Pattern '^DLSS_RR_OPAQUE_PARTICLE_GUIDES active=1$')
        if($opaqueGuidesActive -ne [bool]$OpaqueParticleGuides){throw "Opaque particle guide configuration mismatch: $name"}
        $manifest.opaque_particle_guides=$opaqueGuidesActive
        $expectedOpaqueDepth= -not $opaqueDepthOverride -or [bool]$OpaqueParticleDepth
        # The native marker reports eligible opaque particle draws, not whether
        # the feature is enabled. Transparent-only scenes legitimately omit it.
        if(($opaqueDepthActive -and -not $expectedOpaqueDepth) -or ($opaqueDepthOverride -and $expectedOpaqueDepth -and -not $opaqueDepthActive)){throw "Unexpected native opaque particle depth coverage: $name; explicit enable requires an eligible opaque particle draw."}
        $manifest.opaque_particle_depth_active_by_map[$map]=$opaqueDepthActive
        if($AlphaIsolation){
            if(-not $result.alpha_isolation.restored -or $result.alpha_isolation.phases.Count -ne 7 -or $result.alpha_isolation.groups -ne $AlphaGroups){throw "Incomplete alpha-isolation capture: $name"}
            foreach($phase in $result.alpha_isolation.phases){
                $pattern='^GPU_ALPHA_FILTER mask='+[regex]::Escape($phase.mask)+' skipped_elements=(\d+)$'
                if($phase.frames -lt 30 -or $phase.end_seconds-$phase.start_seconds -lt 6.5 -or -not(Select-String -LiteralPath $stdout -Pattern $pattern)){throw "Uncovered alpha-isolation phase: $($phase.label)"}
            }
        }
        if($MaterialAudit -and ($null -eq $result.material_audit -or $null -eq $result.draw_calls_distribution)){throw "Diagnostic pack lacks material/draw statistics. Repack: $name"}
        if($LightGrid){
            $gridStates=@(Select-String -LiteralPath $stdout -Pattern '^RT_LIGHT_GRID enabled=(\d+) lights=(\d+) cells=(\d+)$')
            if(-not $gridStates.Count -or $gridStates[-1].Matches[0].Groups[1].Value -ne '1'){throw "Requested light index was not active: $name"}
        }
        if($null -eq $result.measurement_wall_seconds -or $null -eq $result.display.requested_vsync){throw "Diagnostic pack predates wall-time/presentation reporting. Repack: $name"}
        if($result.display.vsync -ne $result.display.requested_vsync -or ($VSync -eq 'off' -and $result.display.vsync -ne 0) -or ($VSync -eq 'on' -and $result.display.vsync -ne 1)){throw "Presentation mismatch: $name"}
        if($result.measurement_wall_seconds -lt $Seconds -or $result.measurement_wall_seconds-$Seconds -gt [Math]::Max(1.0,$result.frame_ms.max/1000.0+0.1)){throw "Measurement exceeded the wall-time contract: $name"}
        $environments=@($result.environments | Where-Object {$_.pathtracing_enabled})
        if($result.quality_settings.rr_preset_requested-ne$RRPreset){throw 'Unexpected RR preset in benchmark capture.'}
        if(-not $result.release -or -not $result.arena_stress.valid -or -not $result.rendering_preparation.ready -or $environments.Count -ne 1 -or $environments[0].pathtracing_denoiser -ne 1 -or $environments[0].pathtracing_samples_per_pixel -ne 1 -or $environments[0].pathtracing_max_bounces -ne 3){throw "Scene/backend coverage failed: $name"}
        if($result.fixture_light_state.total -lt 16 -or $result.fixture_light_state.illuminating -ne $result.fixture_light_state.total -or $result.fixture_light_state.shadow_casting -ne $result.fixture_light_state.total){throw "Fixture illumination/shadow coverage failed: $name"}
        if($result.target_fps -ne $TargetFPS -or ([bool]$result.gpu_timing_sampled -ne [bool]$MaterialAudit) -or ($null -ne $DecisionPhases -and $result.decision_phases -ne $DecisionPhases) -or ($queryOverride -and [bool]$result.query_shadows_requested -ne [bool]$QueryShadows) -or [Math]::Abs($result.quality_settings.scaling_3d_scale-$scale) -gt .001 -or $result.separate_render_thread -or -not $result.quality_settings.active_renderer.StartsWith('DLSS Ray Reconstruction /')){throw "Configuration mismatch: $name"}
        $manifest.runs+=@{name=$name;fps=$result.average_fps;target_fps=$TargetFPS;p95_ms=$result.frame_ms.p95;p99_ms=$result.frame_ms.p99;max_ms=$result.frame_ms.max;measurement_wall_seconds=$result.measurement_wall_seconds;vsync=$result.display.vsync;over_target_budget_percent=$result.over_target_budget_percent;meets_target_every_frame=$result.meets_target_every_frame;process_ms=$result.process_ms;physics_ms=$result.physics_ms;internal_scale=$scale;decision_phases=$result.decision_phases;query_shadows=[bool]$result.query_shadows_requested;fixture_lights=$result.fixture_light_state}
        $manifest|ConvertTo-Json -Depth 15|Set-Content -LiteralPath (Join-Path $report 'matrix.json')
        Write-Output "RESULT $name FPS=$($result.average_fps) p95=$($result.frame_ms.p95)"
    }
    if((Get-FileHash -LiteralPath $runtime).Hash -ne $runtimeHash -or (Get-FileHash -LiteralPath ([IO.Path]::ChangeExtension($runtime,'.pck'))).Hash -ne $packHash){throw 'Executable/pack changed during measurement.'}
    $paths=@(Get-ChildItem -LiteralPath $runtimeRoot -Filter '*.dll' -File -Recurse | Sort-Object FullName | Select-Object -ExpandProperty FullName)
    if(Compare-Object @($runtimeDependencies.FullName) $paths){throw 'Runtime DLL paths changed during measurement.'}
    foreach($dependency in $manifest.runtime_dlls){if((Get-FileHash -LiteralPath (Join-Path $runtimeRoot $dependency.relative_path)).Hash -ne $dependency.sha256){throw 'Runtime SDK changed during measurement.'}}
    if((Get-FileHash -LiteralPath $PSCommandPath).Hash -ne $wrapperHash){throw 'Benchmark wrapper changed during measurement.'}
    $manifest.completed=$true;$manifest.completed_at=(Get-Date).ToString('o')
    $manifest|ConvertTo-Json -Depth 15|Set-Content -LiteralPath (Join-Path $report 'matrix.json')
} finally {foreach($name in $saved.Keys){[Environment]::SetEnvironmentVariable($name,$saved[$name],'Process')}}
