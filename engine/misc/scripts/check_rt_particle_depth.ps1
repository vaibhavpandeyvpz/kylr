param(
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [Parameter(Mandatory=$true)][string]$ValidationLayerPath,
    [ValidateSet('safe','separate')][string]$RenderThread='safe',
    [ValidateSet('0.5','1')][string]$Scale='0.5',
    [string]$Godot=''
)
$ErrorActionPreference='Stop'
$engine=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if(-not $Godot){$Godot=Join-Path $engine 'bin/godot.windows.editor.x86_64.exe'}
$binary=[IO.Path]::GetFullPath(($Godot -replace '\.console\.exe$','.exe'))
$OutputDirectory=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath $OutputDirectory){throw 'Use a fresh output directory; preserve earlier captures.'}
if(-not(Test-Path -LiteralPath (Join-Path $ValidationLayerPath 'VkLayer_khronos_validation.json'))){throw 'Vulkan validation layer missing.'}
$source=Join-Path $PSScriptRoot 'probe_rt_particle_depth.gd'
$sourceHash=(Get-FileHash -LiteralPath $source).Hash
$binaryHash=(Get-FileHash -LiteralPath $binary).Hash
$wrapperHash=(Get-FileHash -LiteralPath $PSCommandPath).Hash
$runtime=@(Get-ChildItem -LiteralPath (Split-Path $binary) -Filter '*.dll' -File | Sort-Object Name | ForEach-Object {
    @{name=$_.Name;sha256=(Get-FileHash -LiteralPath $_.FullName).Hash}
})
New-Item -ItemType Directory -Path $OutputDirectory|Out-Null
Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $OutputDirectory 'wrapper.source.ps1')
$keys=@('GODOT_RT_OPAQUE_PARTICLE_DEPTH','GODOT_GPU_PROFILE_ALPHA_FILTER','GODOT_GPU_PROFILE_ALPHA_MASK',
    'GODOT_RT_LIGHT_GRID_CAPTURE','GODOT_DLSS_DIAGNOSTICS','VK_LAYER_PATH','VK_INSTANCE_LAYERS','VK_VALIDATION_VALIDATE_SYNC')
$saved=@{}
foreach($key in $keys){$saved[$key]=[Environment]::GetEnvironmentVariable($key,'Process');[Environment]::SetEnvironmentVariable($key,$null,'Process')}
try{
    $env:VK_LAYER_PATH=[IO.Path]::GetFullPath($ValidationLayerPath)
    $env:VK_INSTANCE_LAYERS='VK_LAYER_KHRONOS_validation'
    $env:VK_VALIDATION_VALIDATE_SYNC='true'
    $env:GODOT_DLSS_DIAGNOSTICS='1'
    $rows=@()
    foreach($mode in @('raster','rt-control','rt-candidate')){
        $folder=Join-Path $OutputDirectory $mode
        $project=Join-Path $folder 'project'
        New-Item -ItemType Directory -Path $project|Out-Null
        Copy-Item -LiteralPath $source -Destination (Join-Path $project 'probe.gd')
        $identity=[Guid]::NewGuid().ToString()
        @"
config_version=5
[application]
config/name="Particle depth fixture"
[display]
window/size/viewport_width=640
window/size/viewport_height=360
[rendering]
renderer/rendering_method="forward_plus"
rendering_device/driver.windows="vulkan"
streamline/project_id="$identity"
"@|Set-Content -LiteralPath (Join-Path $project 'project.godot') -Encoding utf8
        $backend=if($mode-eq'raster'){'raster'}else{'rt'}
        $env:GODOT_RT_OPAQUE_PARTICLE_DEPTH=if($mode-eq'rt-candidate'){'1'}else{'0'}
        $arguments=@('--path',('"'+$project+'"'),'--render-thread',$RenderThread,'--gpu-validation','--script','res://probe.gd','--',
            ('"--output='+(Join-Path $folder 'capture')+'"'),"--backend=$backend","--scale=$Scale")
        $process=Start-Process -FilePath $binary -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput "$folder/stdout.log" -RedirectStandardError "$folder/stderr.log"
        $deadline=[DateTime]::UtcNow.AddMinutes(11)
        while(-not $process.WaitForExit(1000)){
            if([DateTime]::UtcNow-ge$deadline){$process.Kill();$process.WaitForExit();throw "Particle fixture timed out: $mode"}
        }
        $process.Refresh()
        $logs=(Get-Content -LiteralPath "$folder/stdout.log" -Raw)+(Get-Content -LiteralPath "$folder/stderr.log" -Raw)
        if($process.ExitCode-ne0-or$logs-match 'ERROR:|SCRIPT ERROR|VUID-|SYNC-HAZARD|leaked at exit|Resources still in use at exit|OpTypeForwardPointer'){
            throw "Particle fixture failed: $mode; inspect $folder"
        }
        if($logs-notmatch '(?i)VK_LAYER_KHRONOS_validation|VkLayer_khronos_validation\.dll'-or$logs-notmatch 'RT_PARTICLE_DEPTH_CAPTURED'){
            throw "Missing validated completion evidence: $mode"
        }
        $ack=[bool]($logs-match '(?m)^RT_OPAQUE_PARTICLE_DEPTH active=1\r?$')
        if($ack-ne($mode-eq'rt-candidate')){throw "Unexpected native depth-path acknowledgement: $mode"}
        $report=Get-Content -LiteralPath "$folder/capture/report.json" -Raw|ConvertFrom-Json
        if(-not$report.captured-or$report.cases.Count-ne5){throw "Incomplete particle capture: $mode"}
        $rows+=@{mode=$mode;captured=$true;native_ack=$ack;cases=$report.cases}
        Write-Output "PASS particle capture $mode"
    }
    if((Get-FileHash -LiteralPath $binary).Hash-ne$binaryHash-or(Get-FileHash -LiteralPath $source).Hash-ne$sourceHash-or(Get-FileHash -LiteralPath $PSCommandPath).Hash-ne$wrapperHash){throw 'Fixture inputs changed during capture.'}
    foreach($file in $runtime){
        if((Get-FileHash -LiteralPath (Join-Path (Split-Path $binary) $file.name)).Hash-ne$file.sha256){throw 'Runtime library changed during capture.'}
    }
    @{captured=$true;qualified=$false;validation=$true;render_thread=$RenderThread;scale=$Scale;
      source_sha256=$sourceHash;engine_sha256=$binaryHash;wrapper_sha256=$wrapperHash;runtime_dlls=$runtime;runs=$rows}|
      ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $OutputDirectory 'manifest.json') -Encoding utf8
    Write-Output 'PASS captures; run compare_rt_particle_depth.py before accepting ordering correctness.'
}finally{foreach($key in $saved.Keys){[Environment]::SetEnvironmentVariable($key,$saved[$key],'Process')}}
