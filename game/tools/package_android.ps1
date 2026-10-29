param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._+-]*$')][string]$Version='dev-local',
    [ValidateRange(1,2100000000)][int]$VersionCode=1,
    [string]$Godot=$(if ($env:GODOT) {$env:GODOT} else {'godot'}),
    [string]$AndroidSdk=$(if ($env:ANDROID_HOME) {$env:ANDROID_HOME} elseif ($env:ANDROID_SDK_ROOT) {$env:ANDROID_SDK_ROOT} elseif ($IsWindows) {Join-Path $env:LOCALAPPDATA 'Android/Sdk'}),
    [string]$JavaHome=$env:JAVA_HOME,
    [string]$Keystore=$env:ANDROID_KEYSTORE_PATH,
    [ValidatePattern('^[a-z][a-z0-9-]+$')][string]$Alias=$(if ($env:ANDROID_KEY_ALIAS) {$env:ANDROID_KEY_ALIAS} else {'kylr-release'}),
    [string]$BuildToolsVersion='36.0.0'
)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'godot.ps1')
$Godot=Resolve-GodotExecutable $Godot
if (-not $Keystore -or -not (Test-Path -LiteralPath $Keystore -PathType Leaf) -or -not $env:ANDROID_KEYSTORE_PASSWORD) { throw 'Set ANDROID_KEYSTORE_PATH and ANDROID_KEYSTORE_PASSWORD before packaging.' }
if (-not $JavaHome -or -not (Test-Path -LiteralPath $JavaHome -PathType Container)) { throw 'JAVA_HOME must identify an installed JDK.' }
$Keystore=(Resolve-Path -LiteralPath $Keystore).Path
$sdkTools=Join-Path $AndroidSdk "build-tools/$BuildToolsVersion"
$signer=Join-Path $sdkTools "apksigner$(if ($IsWindows) {'.bat'})"
$align=Join-Path $sdkTools "zipalign$(if ($IsWindows) {'.exe'})"
$aapt=Join-Path $sdkTools "aapt2$(if ($IsWindows) {'.exe'})"
foreach ($tool in @($signer,$align,$aapt)) { if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) { throw "Missing Android build tool: $tool" } }
$project=Split-Path -Parent $PSScriptRoot
$workspace=Split-Path -Parent $project
Set-Location $project
& (Join-Path $PSScriptRoot 'check_local_assets.ps1')
$buildId=[guid]::NewGuid().ToString('N')
$reports=Join-Path $project "reports/packaging/android-$buildId"
$staging=Join-Path $project "build/android-release-$buildId"
New-Item -ItemType Directory -Force $reports,$staging | Out-Null
$engineVersion=(& $Godot --version | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $engineVersion -notmatch '^4\.7\.2\.') { throw 'Official Godot 4.7.2 is required.' }
$displayVersion=if ($Version -match '^v(?=\d+\.)') {$Version.Substring(1)} else {$Version}
$apk=Join-Path $project "build/KYLR-Android-arm64-$Version.apk"
$manifestPath=Join-Path $project "build/KYLR-Android-arm64-$Version.manifest.json"
$presets=Join-Path $project 'export_presets.cfg'
$originalPresets=[IO.File]::ReadAllBytes($presets)
$environment=@{}
foreach ($key in @('ANDROID_HOME','JAVA_HOME','PATH','KYLR_ANDROID_EXPORT','KYLR_ANDROID_VERSION_NAME','KYLR_ANDROID_VERSION_CODE')) { $environment[$key]=[Environment]::GetEnvironmentVariable($key,'Process') }
function Invoke-GodotAndroid([string]$Name,[string[]]$Arguments) {
    $log=Join-Path $reports "$Name.log"
    & $Godot --headless --path $project --log-file $log @Arguments 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0 -or (Select-String -LiteralPath $log -Pattern 'SCRIPT ERROR:|ERROR:|VUID-|SYNC-HAZARD')) { throw "Android $Name failed; see $log" }
}
try {
    $env:ANDROID_HOME=[IO.Path]::GetFullPath($AndroidSdk)
    $env:JAVA_HOME=[IO.Path]::GetFullPath($JavaHome)
    $env:PATH=(Join-Path $JavaHome 'bin')+[IO.Path]::PathSeparator+$env:PATH
    $env:KYLR_ANDROID_VERSION_NAME=$displayVersion
    $env:KYLR_ANDROID_VERSION_CODE=[string]$VersionCode
    $env:KYLR_ANDROID_EXPORT='1'
    Invoke-GodotAndroid 'import' @('--editor','--import','--quit')
    Invoke-GodotAndroid 'configure' @('--script','res://tools/configure_android_export.gd')
    $unsigned=Join-Path $staging 'unsigned.apk'
    Invoke-GodotAndroid 'export' @('--export-release','Android Release',$unsigned)
    & $align -P 16 -f 4 $unsigned $apk
    if ($LASTEXITCODE) { throw 'APK alignment failed.' }
    & $signer sign --ks $Keystore --ks-key-alias $Alias --ks-pass env:ANDROID_KEYSTORE_PASSWORD --key-pass env:ANDROID_KEYSTORE_PASSWORD --v2-signing-enabled true --v3-signing-enabled true --v4-signing-enabled false $apk 2>&1 | Set-Content (Join-Path $reports 'sign.log')
    if ($LASTEXITCODE) { throw 'Release signing failed.' }
    $verification=& $signer verify --verbose --print-certs $apk 2>&1
    $verification | Set-Content (Join-Path $reports 'signature.log')
    if ($LASTEXITCODE -ne 0 -or ($verification -join "`n") -notmatch 'Verified using v2 scheme.*true') { throw 'APK signature verification failed.' }
    $certificate=[regex]::Match(($verification -join "`n"),'Signer #1 certificate SHA-256 digest: ([0-9a-fA-F]{64})').Groups[1].Value.ToLowerInvariant()
    if (-not $certificate) { throw 'Cannot identify signing certificate.' }
    & $align -c -P 16 4 $apk | Out-Null
    if ($LASTEXITCODE) { throw 'Signed APK alignment verification failed.' }
    & (Join-Path $PSScriptRoot 'inspect_android_apk.ps1') -Path $apk
    $badging=& $aapt dump badging $apk 2>&1
    $badging | Set-Content (Join-Path $reports 'manifest.log')
    if ($LASTEXITCODE -ne 0 -or ($badging -join "`n") -notmatch ("package: name='com\.vaibhavpandey\.kylr' versionCode='$VersionCode' versionName='"+[regex]::Escape($displayVersion)+"'") -or ($badging -join "`n") -match '(?m)^application-debuggable') { throw 'APK package/version/release manifest validation failed.' }
    $revision=if ($env:GITHUB_SHA) {$env:GITHUB_SHA} else {(& git -C $workspace rev-parse HEAD).Trim()}
    if ($revision -notmatch '^[0-9a-f]{40}$') { throw 'Cannot identify package revision.' }
    @{version=$displayVersion;version_code=$VersionCode;revision=$revision;godot=$engineVersion;platform='Android';abi='arm64-v8a';package='com.vaibhavpandey.kylr';signing_certificate_sha256=$certificate;device_tested=$false;apk_sha256=(Get-FileHash -LiteralPath $apk).Hash.ToLowerInvariant()} | ConvertTo-Json | Set-Content -LiteralPath $manifestPath
    $checksums=foreach ($file in @($apk,$manifestPath)) { (Get-FileHash -LiteralPath $file).Hash.ToLowerInvariant()+'  '+[IO.Path]::GetFileName($file) }
    [IO.File]::WriteAllText($apk+'.sha256',($checksums -join "`n")+"`n",[Text.UTF8Encoding]::new($false))
    Write-Output "Signed and verified: $apk"
} finally {
    [IO.File]::WriteAllBytes($presets,$originalPresets)
    foreach ($key in $environment.Keys) { [Environment]::SetEnvironmentVariable($key,$environment[$key],'Process') }
}
