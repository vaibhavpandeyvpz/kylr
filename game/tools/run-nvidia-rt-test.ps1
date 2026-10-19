param([switch]$Simple, [switch]$Raster, [switch]$RayReconstruction, [switch]$Import, [switch]$Validation, [switch]$Acceptance, [switch]$Soak, [switch]$Lifecycle, [switch]$Skyfall, [switch]$TenRobots, [ValidateRange(0.25,1.0)][double]$Scale = 0.5, [switch]$Timings, [switch]$Costs, [ValidateSet('safe','separate')][string]$RenderThread)
$ErrorActionPreference = 'Stop'
$engine = Join-Path $PSScriptRoot '../../engine/bin/godot.windows.editor.x86_64.console.exe'
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$name = if ($Import) { 'import' } elseif ($Simple) { 'simple' } elseif ($Skyfall) { 'skyfall' } else { 'faceoff' }
$name += if ($Raster) { '-raster' } elseif ($RayReconstruction) { '-rr' } else { '-raw' }
if ($Validation) { $name += '-validation' }
if ($Acceptance) { $name += '-acceptance-fixed' }
if ($TenRobots) { $name += '-10robots' }
if ($Soak) { $name += '-soak' }
if ($Lifecycle) { $name += '-lifecycle' }
if ($Scale -ne 0.5) { $name += "-scale" + [math]::Round($Scale * 100) }
if ($Timings) { $name += "-timings" }
if ($Costs) { $name += "-costs" }
if ($RenderThread) { $name += "-thread-$RenderThread" }
if ($Validation) {
    $layerDirectory = Join-Path $PSScriptRoot '../../engine/.local/vulkan-validation-1.4.363.0/Bin'
    if (-not (Test-Path (Join-Path $layerDirectory 'VkLayer_khronos_validation.json'))) { throw 'Pinned Vulkan validation layer is missing.' }
    $env:VK_LAYER_PATH = $layerDirectory
    $env:VK_INSTANCE_LAYERS = 'VK_LAYER_KHRONOS_validation'
    $env:VK_VALIDATION_VALIDATE_SYNC = 'true'
}
$binaryHash = (Get-FileHash $engine.Replace('.console.exe','.exe') -Algorithm SHA256).Hash
$reportDirectory = Join-Path $project 'reports'
New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null
$stdout = Join-Path $reportDirectory "$name.stdout.log"
$stderr = Join-Path $reportDirectory "$name.stderr.log"
$arguments = @('--path', ('"' + $project + '"'), '--rendering-method', 'forward_plus', '--rendering-driver', 'vulkan', '--disable-crash-handler')
if ($RenderThread) { $arguments += @('--render-thread',$RenderThread) }
if ($Import) { $arguments += @('--headless','--editor','--import','--quit') }
else {
    $testScript = if ($Acceptance) { 'res://tools/nvidia_rt_acceptance.gd' } else { 'res://tools/nvidia_rt_smoke.gd' }
    $arguments += @('--script', $testScript)
    if ($Validation) { $arguments += '--gpu-validation' }
    $arguments += '--'
    if ($Simple) { $arguments += '--simple' }
    if ($Raster) { $arguments += '--raster' }
    if ($RayReconstruction) { $arguments += '--rr' }
    if ($Validation) { $arguments += '--validation' }
    if ($Soak) { $arguments += '--soak' }
    if ($Timings) { $arguments += "--timings" }
    if ($Costs) { $arguments += "--costs" }
    if ($Acceptance) { $arguments += "--scale=" + $Scale.ToString([cultureinfo]::InvariantCulture) }
    if ($Lifecycle) { $arguments += '--lifecycle' }
    if ($Skyfall) { $arguments += '--skyfall' }
    if ($TenRobots) { $arguments += '--ten-robots' }
}
$process = Start-Process -FilePath $engine -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
$timedOut = -not $process.WaitForExit(300000)
if ($timedOut) { $process.Kill($true); $process.WaitForExit() }
$process.Refresh()
$output = (Get-Content $stdout -Raw) + (Get-Content $stderr -Raw)
$diagnosticsFailed = $output -match 'SCRIPT ERROR:|ERROR:|VUID-|SYNC-HAZARD|CrashHandlerException|produce undefined values|Dumped failed shader|RID of type.*was leaked'
$validationActive = $Validation -and ($output -match 'VK_LAYER_KHRONOS_validation')
if ($Validation -and -not $validationActive) { $diagnosticsFailed = $true }
$result = [ordered]@{name=$name; binary_sha256=$binaryHash; validation_active=[bool]$validationActive; exit_code=$process.ExitCode; timed_out=$timedOut; diagnostics_failed=$diagnosticsFailed; validation_requested=[bool]$Validation; stdout=$stdout; stderr=$stderr}
$result | ConvertTo-Json | Set-Content (Join-Path $reportDirectory "$name.process.json")
$result | ConvertTo-Json
if ($timedOut -or $process.ExitCode -ne 0 -or $diagnosticsFailed) { exit 1 }
