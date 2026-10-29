param(
    [string]$Config,
    [switch]$Matrix,
    [ValidateRange(1,600)][int]$WarmupSeconds=15,
    [ValidateRange(1,3600)][int]$SampleSeconds=60,
    [ValidatePattern('^[A-Za-z0-9_-]+$')][string]$Name = 'mobile-profile',
    [string]$Device = 'emulator-5554',
    [string]$AndroidSdk = $(if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA 'Android/Sdk' }),
    [string]$JavaHome = $env:JAVA_HOME,
    [string]$Godot = $(if ($env:GODOT) { $env:GODOT } else { 'godot' }),
    [switch]$Rebuild,
    [ValidateRange(60,14400)][int]$TimeoutSeconds = 3600
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'godot.ps1')
$project = Split-Path -Parent $PSScriptRoot
Set-Location $project
$directory = Join-Path $project "reports/performance/$Name"
if (Test-Path -LiteralPath $directory) { throw 'Choose a fresh report name.' }
if ($Matrix -and $Config) { throw 'Choose either Matrix or Config.' }
if (-not $Matrix -and -not $Config) { throw 'Specify Matrix or a Config JSON file.' }
New-Item -ItemType Directory -Path $directory -Force | Out-Null
if ($Matrix) {
    $catalog=Get-Content (Join-Path $project 'data/maps/catalog.json') -Raw | ConvertFrom-Json
    $cases=foreach ($map in $catalog.maps) { foreach ($quality in 0..2) { foreach ($robots in @(2,4,6,8,10)) { @{map=$map.id;quality=$quality;robots=$robots} } } }
    $Config=Join-Path $directory 'config.json'
    @{seed=120;warmup=$WarmupSeconds;seconds=$SampleSeconds;costs=$false;cases=@($cases)} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $Config
}
$settings = Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
$expected = if ($settings.cases) { @($settings.cases).Count } else { 1 }
$adb = Join-Path $AndroidSdk 'platform-tools/adb.exe'
$package = 'com.vaibhavpandey.kylr'
$debugApk = Join-Path $project 'build/android/KYLR-profile.apk'
$releaseApk = Join-Path $project 'build/android/KYLR-profile-release.apk'

function Invoke-Adb([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments) {
    for ($attempt=0; $attempt -lt 3; $attempt++) {
        $output = & $adb -s $Device @Arguments 2>&1
        if ($LASTEXITCODE -eq 0) { return $output }
        if (($output -join "`n") -notmatch 'offline|not found|no devices') { throw ($output -join "`n") }
        Start-Sleep -Seconds 2
    }
    throw "ADB failed: $($Arguments -join ' ')"
}

if ($Rebuild) {
    $Godot = Resolve-GodotExecutable $Godot
    & $Godot --headless --path $project --editor --import --quit 2>&1 | Set-Content (Join-Path $directory 'import.log')
    if ($LASTEXITCODE -ne 0) { throw 'Asset import failed.' }
    & $Godot --headless --path $project --check-only --script 'scripts/debug/mobile_benchmark.gd' 2>&1 | Set-Content (Join-Path $directory 'benchmark-check.log')
    if ($LASTEXITCODE -ne 0) { throw 'Benchmark script validation failed.' }
    foreach ($job in @(@('Android Profile','--export-debug',$debugApk),@('Android Profile Release','--export-release',$releaseApk))) {
        & $Godot --headless --path $project $job[1] $job[0] $job[2] 2>&1 | Set-Content (Join-Path $directory "$($job[0]).log")
        if ($LASTEXITCODE -ne 0) { throw "Export failed: $($job[0])" }
    }
    if ($JavaHome) { $env:JAVA_HOME=$JavaHome; $env:PATH=(Join-Path $JavaHome 'bin')+';'+$env:PATH }
    $signer = Get-ChildItem (Join-Path $AndroidSdk 'build-tools') -Filter apksigner.bat -Recurse | Sort-Object FullName -Descending | Select-Object -First 1
    $key = Join-Path $env:APPDATA 'Godot/keystores/debug.keystore'
    & $signer.FullName sign --ks $key --ks-pass pass:android --ks-key-alias androiddebugkey $releaseApk 2>&1 | Set-Content (Join-Path $directory 'signing.log')
    if ($LASTEXITCODE -ne 0) { throw 'Diagnostic signing failed.' }
}

if (-not $Matrix) { Copy-Item -LiteralPath $Config -Destination (Join-Path $directory 'config.json') }
@{config=(Get-FileHash -LiteralPath $Config).Hash; apk=(Get-FileHash -LiteralPath $releaseApk).Hash; device=$Device} | ConvertTo-Json | Set-Content (Join-Path $directory 'identity.json')
Invoke-Adb @('shell','am','force-stop',$package) | Out-Null
# The data remains on package replacement. Use the debug shell only for file
# handoff; all timed runs use the signed release engine and release LimboAI.
Invoke-Adb @('install','--no-streaming','--no-incremental','-r',$debugApk) | Out-Null
Invoke-Adb @('push',(Join-Path $directory 'config.json'),'/data/local/tmp/kylr-mobile-profile.json') | Out-Null
Invoke-Adb @('shell','run-as',$package,'cp','/data/local/tmp/kylr-mobile-profile.json','files/mobile-profile.json') | Out-Null
Invoke-Adb @('shell','run-as',$package,'rm','-f','files/mobile-profile-batch.json','files/mobile-profile-result.json') | Out-Null
Invoke-Adb @('install','--no-streaming','--no-incremental','-r',$releaseApk) | Out-Null
Invoke-Adb @('logcat','-c') | Out-Null
Invoke-Adb @('shell','am','start','-n',"$package/com.godot.game.GodotAppLauncher") | Out-Null
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$complete = $false
$seen = 0
while ((Get-Date) -lt $deadline) {
    $log = Invoke-Adb @('logcat','-d','-s','godot')
    if (($log -join "`n") -match 'SCRIPT ERROR:|ERROR:') { throw ($log -join "`n") }
    $done = @($log | Select-String 'MOBILE_BENCHMARK_DONE').Count
    if ($done -gt $seen) { Write-Output "$Name cases $done/$expected"; $seen=$done }
    if (($log -join "`n") -match 'MOBILE_BATCH_DONE') { $complete=$true; break }
    Start-Sleep -Seconds 2
}
$log | Set-Content (Join-Path $directory 'android.log')
Invoke-Adb @('shell','am','force-stop',$package) | Out-Null
Invoke-Adb @('install','--no-streaming','--no-incremental','-r',$debugApk) | Out-Null
$raw = Invoke-Adb @('shell','run-as',$package,'cat','files/mobile-profile-batch.json')
$raw | Set-Content (Join-Path $directory 'results.json')
$results = ($raw -join "`n") | ConvertFrom-Json
Invoke-Adb @('shell','run-as',$package,'rm','-f','files/mobile-profile.json') | Out-Null
if (-not $complete -or @($results).Count -ne $expected) { throw "Incomplete benchmark: $seen/$expected cases; retained available results." }
$summary = foreach ($result in $results) {
    [pscustomobject]@{map=$result.config.map; quality=$result.config.quality; robots=$result.config.robots; rendered=($result.config.render_loop -ne $false); fps=$result.fps; min_1s_fps=$result.min_1s_window_fps; passes_30fps=$result.passes_30fps; render_resolution=$result.rendered_3d_resolution; physics_hz=($result.physics_ticks/$result.seconds); p50_ms=$result.frame_ms.'50'; p95_ms=$result.frame_ms.'95'; p99_ms=$result.frame_ms.'99'; max_ms=$result.frame_ms.'100'; batches=$result.fixed_mesh_batches}
}
$summary | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $directory 'summary.json')
$summary | Format-Table -AutoSize
