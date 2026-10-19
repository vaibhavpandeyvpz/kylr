param(
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateSet('safe','separate')][string]$RenderThread='safe',
    [switch]$QueryShadows,
    [string]$Godot='',
    [string]$ValidationLayerPath=''
)
$ErrorActionPreference='Stop'
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
config/name="Ray-traced light shadow fixture"
[rendering]
renderer/rendering_method="forward_plus"
rendering_device/driver.windows="vulkan"
streamline/project_id="$projectId"
"@ | Set-Content -LiteralPath (Join-Path $project 'project.godot') -Encoding utf8
$probe=Join-Path $PSScriptRoot 'probe_rt_light_shadows.gd'
$binary=Join-Path (Split-Path $Godot) 'godot.windows.editor.x86_64.exe'
$binaryHash=(Get-FileHash -LiteralPath $binary).Hash
$probeHash=(Get-FileHash -LiteralPath $probe).Hash
$wrapperHash=(Get-FileHash -LiteralPath $PSCommandPath).Hash
Copy-Item -LiteralPath $probe -Destination (Join-Path $OutputDirectory 'probe.source.gd')
Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $OutputDirectory 'wrapper.source.ps1')
$runtime=@(Get-ChildItem -LiteralPath (Split-Path $Godot) -Filter '*.dll' -File | Sort-Object Name | ForEach-Object {@{name=$_.Name;sha256=(Get-FileHash -LiteralPath $_.FullName).Hash}})
$saved=@{}
foreach($name in @('VK_LAYER_PATH','VK_INSTANCE_LAYERS','VK_VALIDATION_VALIDATE_SYNC')){$saved[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
try{
    $env:VK_LAYER_PATH=$ValidationLayerPath
    $env:VK_INSTANCE_LAYERS='VK_LAYER_KHRONOS_validation'
    $env:VK_VALIDATION_VALIDATE_SYNC='true'
    $arguments=@('--path',('"'+$project+'"'),'--gpu-validation','--render-thread',$RenderThread,'--script',('"'+$probe+'"'),'--',('--output='+$OutputDirectory.Replace('\','/')),('--query-shadows='+[int][bool]$QueryShadows))
    # Output paths may contain spaces. Each user argument must remain intact.
    $arguments[-2]='"'+$arguments[-2]+'"'
    $stdout=Join-Path $OutputDirectory 'probe.log';$stderr=Join-Path $OutputDirectory 'errors.log'
    $process=Start-Process -FilePath $Godot -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    while(-not $process.WaitForExit(1000)){}
    $process.Refresh()
    $log=(Get-Content -LiteralPath $stdout -Raw)+(Get-Content -LiteralPath $stderr -Raw)
    $unchanged=$binaryHash -eq (Get-FileHash -LiteralPath $binary).Hash -and $probeHash -eq (Get-FileHash -LiteralPath $probe).Hash -and $wrapperHash -eq (Get-FileHash -LiteralPath $PSCommandPath).Hash
    foreach($file in $runtime){if($file.sha256 -ne (Get-FileHash -LiteralPath (Join-Path (Split-Path $Godot) $file.name)).Hash){$unchanged=$false}}
    $passed=$process.ExitCode -eq 0 -and $unchanged -and $log -match 'RT_LIGHT_SHADOW_TOGGLE_PASS' -and $log -match 'VK_LAYER_KHRONOS_validation' -and $log -notmatch 'ERROR:|SCRIPT ERROR:|VUID-|SYNC-HAZARD|ObjectDB instances were leaked'
    $reportPath=Join-Path $OutputDirectory 'report.json'
    if(Test-Path -LiteralPath $reportPath){
        $report=Get-Content -LiteralPath $reportPath -Raw|ConvertFrom-Json
        $passed=$passed -and $report.passed -and $report.cases.Count -eq 5 -and [bool]$report.query_shadows -eq [bool]$QueryShadows
        foreach($case in $report.cases){$passed=$passed -and $case.passed -and $case.phases.Count -eq 3}
    }else{$passed=$false}
    @{passed=$passed;exit_code=$process.ExitCode;engine_sha256=$binaryHash;probe_sha256=$probeHash;wrapper_sha256=$wrapperHash;unchanged=$unchanged;runtime_dlls=$runtime;render_thread=$RenderThread;query_shadows=[bool]$QueryShadows;validation_layer_sha256=(Get-FileHash -LiteralPath (Join-Path $ValidationLayerPath 'VkLayer_khronos_validation.dll')).Hash;quality_accepted=$false;performance_accepted=$false} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'manifest.json') -Encoding utf8
    if(-not $passed){throw "Ray-traced shadow control failed: $OutputDirectory"}
    Write-Output "PASS four light types and mixed lights, $RenderThread, query=$([bool]$QueryShadows). Not an FPS result."
}finally{foreach($name in $saved.Keys){[Environment]::SetEnvironmentVariable($name,$saved[$name],'Process')}}
