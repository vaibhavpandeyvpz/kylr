param(
    [string]$Godot = (Join-Path $PSScriptRoot '../../engine/bin/godot.windows.editor.x86_64.console.exe'),
    [ValidateSet('both','raster','rt')][string]$Mode = 'both',
    [ValidateSet('Low','Medium','High','Ultra')][string]$Preset = 'Ultra',
    [ValidateSet('dlss')][string]$Denoiser = 'dlss',
    [ValidateSet('?','D','E')][string]$RRPreset='?',
    [switch]$Validation,
    [ValidateSet('safe','separate')][string]$RenderThread,
    [switch]$QueryShadows,
    [switch]$TransparencyLayer,
    [switch]$OpaqueParticleGuides,
    [switch]$UnshadedSettling,
    [switch]$EngineVerbose,
    [switch]$FlameOnly,
    [switch]$CoreOnly,
    [ValidatePattern('^[a-zA-Z0-9_-]*$')][string]$ReportPrefix=''
)
$ErrorActionPreference = 'Stop'
if($TransparencyLayer -or $OpaqueParticleGuides){throw 'The unqualified transparency-layer and particle-guide experiments have been removed from the engine.'}
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if($FlameOnly -and $CoreOnly){throw 'Choose either flame-only or core-only captures.'}
if($CoreOnly -and $UnshadedSettling){throw 'Unshaded settling requires the full effects capture.'}
$expectedCases=if($CoreOnly){3}elseif($FlameOnly){5}else{43}
New-Item -ItemType Directory -Force (Join-Path $project 'reports') | Out-Null
$savedEnvironment=@{}
foreach($key in @('GODOT_DLSS_DIAGNOSTICS','GODOT_DLSS_RR_TRANSPARENCY_LAYER','GODOT_DLSS_RR_OPAQUE_PARTICLE_GUIDES','VK_LAYER_PATH','VK_INSTANCE_LAYERS','VK_VALIDATION_VALIDATE_SYNC')){
    $savedEnvironment[$key]=[Environment]::GetEnvironmentVariable($key,'Process')
}
try {
$env:GODOT_DLSS_DIAGNOSTICS='1'
$env:GODOT_DLSS_RR_TRANSPARENCY_LAYER=if($TransparencyLayer){'1'}else{'0'}
$env:GODOT_DLSS_RR_OPAQUE_PARTICLE_GUIDES=if($OpaqueParticleGuides){'1'}else{'0'}
if ($Validation) {
    $layerDirectory = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../engine/.local/vulkan-validation-1.4.363.0/Bin'))
    if (-not (Test-Path (Join-Path $layerDirectory 'VkLayer_khronos_validation.json'))) { throw 'Pinned Vulkan validation layer is missing.' }
    $env:VK_LAYER_PATH = $layerDirectory
    $env:VK_INSTANCE_LAYERS = 'VK_LAYER_KHRONOS_validation'
    $env:VK_VALIDATION_VALIDATE_SYNC = 'true'
}
$modes = if ($Mode -eq 'both') { @('raster','rt') } else { @($Mode) }
foreach ($mode in $modes) {
    $label = $mode
    $directory=Join-Path $project 'reports'
    if($ReportPrefix){
        $directory=Join-Path $project "reports/performance/$ReportPrefix-$label"
        if(Test-Path -LiteralPath $directory){throw 'Use a fresh effects prefix; preserve prior captures.'}
        New-Item -ItemType Directory -Path $directory | Out-Null
    }
    $stdout = Join-Path $directory "effects-$label.log"
    $stderr = Join-Path $directory "effects-$label-errors.log"
    $reportPath = Join-Path $directory "effects-$label.json"
    if (Test-Path -LiteralPath $reportPath) { Remove-Item -LiteralPath $reportPath }
    $manifestPath = Join-Path $directory "effects-$label-manifest.json"
    if (Test-Path -LiteralPath $manifestPath) { Remove-Item -LiteralPath $manifestPath }
    $binary = Join-Path (Split-Path $Godot) 'godot.windows.editor.x86_64.exe'
    $probe = Join-Path $project 'tools/probe_rt_effects.gd'
    $binaryHash = (Get-FileHash -LiteralPath $binary).Hash
    $probeHash = (Get-FileHash -LiteralPath $probe).Hash
    $observer=Join-Path $project 'scripts/debug/reconstruction_observer.gd'
    $observerHash=(Get-FileHash -LiteralPath $observer).Hash
    $runtime=@(Get-ChildItem -LiteralPath (Split-Path $Godot) -Filter '*.dll' -File | Sort-Object Name | ForEach-Object {@{name=$_.Name;sha256=(Get-FileHash -LiteralPath $_.FullName).Hash}})
    if($ReportPrefix){Copy-Item -LiteralPath $probe -Destination (Join-Path $directory 'probe.source.gd')}
    $arguments = @('--path',('"'+$project+'"'),'--windowed','--resolution','1280x720','--fixed-fps','60','-s','res://tools/probe_rt_effects.gd')
    if ($EngineVerbose) { $arguments=@('--verbose')+$arguments }
    if ($RenderThread) { $arguments += @('--render-thread',$RenderThread) }
    if ($Validation) { $arguments += '--gpu-validation' }
    $userArguments = @(('"--report-dir='+$directory.Replace('\','/')+'"'))
    if ($mode -eq 'rt') { $userArguments += '--rt' }
    $userArguments += "--rr-preset=$RRPreset"
    $userArguments += "--quality-preset=$(@('Low','Medium','High','Ultra').IndexOf($Preset))"
    if($FlameOnly){$userArguments += '--flame-only'}
    if($CoreOnly){$userArguments += '--core-only'}
    if ($QueryShadows) { $userArguments += '--query-shadows' }
    if ($UnshadedSettling) { $userArguments += '--unshaded-settling' }
    if ($userArguments.Count) { $arguments += @('--') + $userArguments }
    $process = Start-Process -FilePath $Godot -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    if (-not $process.WaitForExit(600000)) { $process.Kill($true); throw "$mode effects capture timed out" }
    $process.Refresh()
    $output = (Get-Content $stdout -Raw) + (Get-Content $stderr -Raw)
    $validationActive = $output -match 'VK_LAYER_KHRONOS_validation'
    if ($Validation -and -not $validationActive) { throw "$mode effects capture did not confirm the validation layer." }
    if ($process.ExitCode -ne 0 -or $output -match 'ERROR:|SCRIPT ERROR:|VUID-|SYNC-HAZARD|ObjectDB instances were leaked' -or $output -notmatch "EFFECTS_CAPTURE_DONE $label cases=$expectedCases\b") { throw "$label effects capture failed: $stderr" }
    if($TransparencyLayer -and $mode -eq 'rt' -and $output -notmatch 'DLSS_RR_TRANSPARENCY_LAYER active=1'){throw 'Requested transparency layer did not execute.'}
    if($OpaqueParticleGuides -and $mode -eq 'rt' -and $output -notmatch 'DLSS_RR_OPAQUE_PARTICLE_GUIDES active=1'){throw 'Requested opaque particle guides did not execute.'}
    $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
    if ($report.Count -ne $expectedCases) { throw 'Missing effects cases.' }
    if($mode-eq'rt' -and $output-notmatch ('EFFECTS_RR_PRESET '+[regex]::Escape($RRPreset))){throw 'Requested RR preset was not configured.'}
    foreach($row in $report){
        if($row.quality_preset-ne@('Low','Medium','High','Ultra').IndexOf($Preset)-or$row.graphics_device-notmatch'NVIDIA'){throw 'Effects capture used the wrong preset or GPU.'}
        if($row.rr_preset_requested-ne$RRPreset){throw 'Effect capture requested a different RR preset.'}
        if(-not$row.fixed_particle_seeds-or$null-eq$row.simulation_step_seconds-or[Math]::Abs($row.simulation_step_seconds.min-1.0/60)-gt0.000001-or[Math]::Abs($row.simulation_step_seconds.max-1.0/60)-gt0.000001){throw "Unequal effect simulation timing: $($row.case)"}
    }
    if($mode-eq'rt'){
        foreach($row in $report){
            $native=$row.native_reconstruction.adapter
            if($row.native_reconstruction.error-or$native.backend-ne'DLSS'-or-not$native.viewport_renderer-or-not$native.evaluation_succeeded-or$native.frames-le0){throw "Missing native DLSS evaluation evidence: $($row.case)"}
        }
    }
    $armor=@($report|Where-Object case -eq 'armor-hit')
    if(-not $FlameOnly -and ($armor.Count -ne 1 -or -not $armor[0].hit_accepted -or $armor[0].armor_overlay_meshes -le 0 -or $armor[0].armor_strength -ne .5 -or $armor[0].armor_shader -ne 'res://shaders/combat/energy_surface.gdshader')){throw 'Missing actual armor damage-overlay coverage.'}
    $core=@($report|Where-Object case -eq 'dropped-energy-core')
    if(-not $FlameOnly -and ($core.Count -ne 1 -or $core[0].first_frames -ne 2 -or $core[0].visible_emissive_pixels -lt 3)){throw 'Missing immediate dropped-core visibility coverage.'}
    $unshadedFlatness=$null
    if($UnshadedSettling){
        $settling=Get-Content -LiteralPath (Join-Path $directory 'unshaded-settling.json') -Raw | ConvertFrom-Json
        $unshadedFlatness=$settling.observations.Count -eq 3
        foreach($observation in $settling.observations){
            $unshadedFlatness=$unshadedFlatness -and $observation.colors.Count -eq 2
            foreach($color in $observation.colors){$unshadedFlatness=$unshadedFlatness -and $color.passed}
        }
        if(-not $unshadedFlatness){throw 'Unshaded colors retained stale history or lost spatial constancy.'}
    }
    if($ReportPrefix -and @(Get-ChildItem -LiteralPath $directory -Filter "effects-$label-*.png" -File).Count -ne $expectedCases){throw 'Missing effect screenshots.'}
    if ($binaryHash -ne (Get-FileHash -LiteralPath $binary).Hash -or $probeHash -ne (Get-FileHash -LiteralPath $probe).Hash) { throw 'Engine or effects probe changed during the run.' }
    if($observerHash-ne(Get-FileHash -LiteralPath $observer).Hash){throw 'Reconstruction observer changed during capture.'}
    foreach($file in $runtime){if($file.sha256 -ne (Get-FileHash -LiteralPath (Join-Path (Split-Path $Godot) $file.name)).Hash){throw 'Runtime libraries changed during effects capture.'}}
    @{ engine_sha256=$binaryHash; probe_sha256=$probeHash; denoiser=$Denoiser; cases=$expectedCases; flame_only=[bool]$FlameOnly;core_only=[bool]$CoreOnly;quality_preset=$Preset;
       fixed_simulation_fps=60;fixed_particle_seeds=$true;rr_preset_requested=$RRPreset;observer_sha256=$observerHash;native_rr_verified=($mode-eq'rt');runtime_dlls=$runtime;render_thread=$RenderThread;query_shadows=[bool]$QueryShadows;unshaded_flatness_passed=$unshadedFlatness;
       opaque_particle_guides=[bool]$OpaqueParticleGuides;transparency_layer=[bool]$TransparencyLayer;capture_passed=$true; validation=[bool]$Validation; visual_quality_acceptance=$false; performance_acceptance=$false } |
       ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding utf8
    Write-Output "PASS $label effects capture; inspect the images for visual correctness."
}
} finally {
    foreach($key in $savedEnvironment.Keys){[Environment]::SetEnvironmentVariable($key,$savedEnvironment[$key],'Process')}
}
