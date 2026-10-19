param(
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateSet('safe','separate')][string]$RenderThread='safe',
    [ValidateSet('raw','dlss','raster-fsr2')][string]$Backend='dlss',
    [ValidateSet('0.5','1')][string]$Scale='0.5',
    [switch]$Studio,
    [switch]$Transition,
    [switch]$EngineVerbose,
    [switch]$CameraCut,
    [switch]$CameraMotion,
    [switch]$Packaged,
    [string]$PackerGodot='',
    [string]$Godot='',
    [string]$ValidationLayerPath=''
)
$ErrorActionPreference='Stop'
if(($CameraCut -or $CameraMotion) -and -not $Backend.EndsWith('-fsr2')){throw 'Camera reset fixtures require an FSR2 backend.'}
$engine=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if(-not $Godot){$Godot=Join-Path $engine 'bin/godot.windows.editor.x86_64.console.exe'}
if(-not $ValidationLayerPath){$ValidationLayerPath=Join-Path $engine '.local/vulkan-validation-1.4.363.0/Bin'}
$OutputDirectory=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath $OutputDirectory){throw 'Use a fresh output directory; preserve previous reports.'}
if(-not(Test-Path -LiteralPath (Join-Path $ValidationLayerPath 'VkLayer_khronos_validation.json'))){throw 'Validation layer missing.'}
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
$project=Join-Path $OutputDirectory 'project'
New-Item -ItemType Directory -Path $project | Out-Null
$projectId=[Guid]::NewGuid().ToString()
@"
config_version=5
[application]
config/name="Unshaded reconstruction fixture"
[rendering]
renderer/rendering_method="forward_plus"
rendering_device/driver.windows="vulkan"
streamline/project_id="$projectId"
"@ | Set-Content -LiteralPath (Join-Path $project 'project.godot') -Encoding utf8
$probe=Join-Path $PSScriptRoot 'probe_rt_unshaded.gd'
$binary=[IO.Path]::GetFullPath(($Godot -replace '\.console\.exe$','.exe'))
$binaryHash=(Get-FileHash -LiteralPath $binary).Hash
$probeHash=(Get-FileHash -LiteralPath $probe).Hash
$wrapperHash=(Get-FileHash -LiteralPath $PSCommandPath).Hash
Copy-Item -LiteralPath $probe -Destination (Join-Path $OutputDirectory 'probe.source.gd')
Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $OutputDirectory 'wrapper.source.ps1')
if($Packaged){
    if(-not $PackerGodot){$PackerGodot=Join-Path $engine 'bin/godot.windows.editor.x86_64.console.exe'}
    $runtimeDirectory=Join-Path $OutputDirectory 'runtime'
    New-Item -ItemType Directory -Path $runtimeDirectory|Out-Null
    Copy-Item -LiteralPath $binary -Destination $runtimeDirectory
    if($Godot -ne $binary){Copy-Item -LiteralPath $Godot -Destination $runtimeDirectory}
    Get-ChildItem -LiteralPath (Split-Path $Godot) -Filter '*.dll' -File | Copy-Item -Destination $runtimeDirectory
    $pack=Join-Path $runtimeDirectory ([IO.Path]::GetFileNameWithoutExtension($binary)+'.pck')
    $packHelper=Join-Path $PSScriptRoot 'pack_rt_unshaded_fixture.gd'
    $packHelperHash=(Get-FileHash -LiteralPath $packHelper).Hash
    Copy-Item -LiteralPath $packHelper -Destination (Join-Path $OutputDirectory 'packer.source.gd')
    & $PackerGodot --headless --path $project --script $packHelper -- "--output=$pack" "--project=$(Join-Path $project 'project.godot')" "--probe=$probe" *> (Join-Path $OutputDirectory 'pack.log')
    if($LASTEXITCODE -ne 0 -or -not(Test-Path -LiteralPath $pack)){throw 'Cannot pack release fixture.'}
    $launchGodot=Join-Path $runtimeDirectory ([IO.Path]::GetFileName($Godot))
}else{$launchGodot=$Godot}
$runtime=@(Get-ChildItem -LiteralPath (Split-Path $Godot) -Filter '*.dll' -File | Sort-Object Name | ForEach-Object {@{name=$_.Name;sha256=(Get-FileHash -LiteralPath $_.FullName).Hash}})
$packHash=$null
if($Packaged){
    $packHash=(Get-FileHash -LiteralPath $pack).Hash
    foreach($file in $runtime){
        if($file.sha256 -ne (Get-FileHash -LiteralPath (Join-Path $runtimeDirectory $file.name)).Hash){throw 'Staged runtime differs from source.'}
    }
}
$saved=@{}
foreach($name in @('VK_LAYER_PATH','VK_INSTANCE_LAYERS','VK_VALIDATION_VALIDATE_SYNC')){$saved[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
try{
    $env:VK_LAYER_PATH=$ValidationLayerPath
    $env:VK_INSTANCE_LAYERS='VK_LAYER_KHRONOS_validation'
    $env:VK_VALIDATION_VALIDATE_SYNC='true'
    $arguments=@('--path',('"'+$project+'"'),'--gpu-validation','--render-thread',$RenderThread,'--script',('"'+$probe+'"'),'--',('"--output='+$OutputDirectory.Replace('\','/')+'"'),"--backend=$Backend","--scale=$Scale")
    if($Packaged){$arguments=@('--gpu-validation','--render-thread',$RenderThread,'--',('"--output='+$OutputDirectory.Replace('\','/')+'"'),"--backend=$Backend","--scale=$Scale")}
    if($Studio){$arguments+='--studio'}
    if($Transition){$arguments+='--transition'}
    if($CameraCut){$arguments+='--camera-cut'}
    if($CameraMotion){$arguments+='--camera-motion'}
    if($EngineVerbose){$arguments=@('--verbose')+$arguments}
    # Output paths may contain spaces. Each user argument must remain intact.
    $stdout=Join-Path $OutputDirectory 'probe.log';$stderr=Join-Path $OutputDirectory 'errors.log'
    $process=Start-Process -FilePath $launchGodot -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    while(-not $process.WaitForExit(1000)){}
    $process.Refresh()
    $log=(Get-Content -LiteralPath $stdout -Raw)+(Get-Content -LiteralPath $stderr -Raw)
    $unchanged=$binaryHash -eq (Get-FileHash -LiteralPath $binary).Hash -and $probeHash -eq (Get-FileHash -LiteralPath $probe).Hash -and $wrapperHash -eq (Get-FileHash -LiteralPath $PSCommandPath).Hash
    foreach($file in $runtime){if($file.sha256 -ne (Get-FileHash -LiteralPath (Join-Path (Split-Path $Godot) $file.name)).Hash){$unchanged=$false}}
    if($Packaged){
        $unchanged=$unchanged -and $packHash -eq (Get-FileHash -LiteralPath $pack).Hash -and $packHelperHash -eq (Get-FileHash -LiteralPath $packHelper).Hash
        foreach($file in $runtime){if($file.sha256 -ne (Get-FileHash -LiteralPath (Join-Path $runtimeDirectory $file.name)).Hash){$unchanged=$false}}
    }
    $passed=$process.ExitCode -eq 0 -and $unchanged -and $log -match 'RT_UNSHADED_CAPTURE_DONE' -and $log -match 'VK_LAYER_KHRONOS_validation' -and $log -notmatch 'ERROR:|SCRIPT ERROR:|VUID-|SYNC-HAZARD|ObjectDB instances were leaked|OpTypeForwardPointer is not supported yet'
    $stableHistory=$null
    if($EngineVerbose -and $Backend -eq 'dlss'){
        $begin=$log.IndexOf('RT_UNSHADED_FRAME 120')
        $end=$log.IndexOf('RT_UNSHADED_FRAME 360')
        $stableHistory=$begin -ge 0 -and $end -gt $begin
        if($stableHistory){$stableHistory=$log.Substring($begin,$end-$begin) -notmatch 'DLSS history reset:'}
        $passed=$passed -and $stableHistory
    }
    $reportPath=Join-Path $OutputDirectory 'report.json'
    $fsr2ResetCount=$null
    if($EngineVerbose -and $Backend.EndsWith('-fsr2')){
        $begin=$log.IndexOf('RT_UNSHADED_FRAME 120');$end=$log.IndexOf('RT_UNSHADED_FRAME 360')
        $stableHistory=$begin -ge 0 -and $end -gt $begin
        if($stableHistory){
            $fsr2ResetCount=[regex]::Matches($log.Substring($begin,$end-$begin),'FSR2 history reset:').Count
            $stableHistory=$fsr2ResetCount -eq $(if($CameraCut){1}else{0})
        }
        $passed=$passed -and $stableHistory
    }
    if(Test-Path -LiteralPath $reportPath){
        $report=Get-Content -LiteralPath $reportPath -Raw|ConvertFrom-Json
        $passed=$passed -and $report.captures.Count -eq $(if($CameraCut){5}else{4}) -and $report.backend -eq $Backend -and $report.scale -eq [float]$Scale -and $report.engine_sha256 -eq $binaryHash -and [bool]$report.camera_cut -eq [bool]$CameraCut -and [bool]$report.camera_motion -eq [bool]$CameraMotion
        foreach($capture in $report.captures){$passed=$passed -and $capture.colors.Count -eq 2}
        if($Backend.EndsWith('-fsr2')){$passed=$passed -and $report.passed -and $report.reactive_alpha.passed}
    }else{$passed=$false}
    $cameraFovPassed=$null
    $cameraFovValues=@()
    if($EngineVerbose -and $Backend -eq 'dlss'){
        $fovMatches=[regex]::Matches($log,'DLSS camera vertical FOV: ([0-9.eE+-]+) degrees\.')
        $cameraFovPassed=$fovMatches.Count -gt 0 -and $report.camera_fov -gt 0
        foreach($entry in $fovMatches){
            $value=[double]::Parse($entry.Groups[1].Value,[Globalization.CultureInfo]::InvariantCulture)
            $cameraFovValues+= $value
            $cameraFovPassed=$cameraFovPassed -and [Math]::Abs($value-$report.camera_fov) -lt .0001
        }
        $passed=$passed -and $cameraFovPassed
    }
    @{passed=$passed;exit_code=$process.ExitCode;engine_sha256=$binaryHash;probe_sha256=$probeHash;wrapper_sha256=$wrapperHash;unchanged=$unchanged;runtime_dlls=$runtime;packaged=[bool]$Packaged;pack_sha256=$packHash;packer_sha256=$packHelperHash;render_thread=$RenderThread;backend=$Backend;scale=$Scale;flatness_passed=$report.flatness_passed;reactive_mask_passed=$(if($Backend.EndsWith('-fsr2')){$report.reactive_alpha.passed}else{$null});stable_history=$stableHistory;fsr2_reset_count=$fsr2ResetCount;camera_cut=[bool]$CameraCut;camera_motion=[bool]$CameraMotion;camera_fov_passed=$cameraFovPassed;camera_fov_values_deg=$cameraFovValues;validation_layer_sha256=(Get-FileHash -LiteralPath (Join-Path $ValidationLayerPath 'VkLayer_khronos_validation.dll')).Hash;quality_accepted=$false;performance_accepted=$false} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'manifest.json') -Encoding utf8
    if(-not $passed){throw "Unshaded reconstruction capture failed: $OutputDirectory"}
    Write-Output "CAPTURE PASS unshaded $Backend scale=$Scale; flatness=$($report.passed). Not an FPS result."
}finally{foreach($name in $saved.Keys){[Environment]::SetEnvironmentVariable($name,$saved[$name],'Process')}}
