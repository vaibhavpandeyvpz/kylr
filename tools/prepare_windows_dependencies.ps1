param(
    [string]$VisualStudioPath = '',
    [string]$SDKArchive = '',
    [string]$VCRuntimeSource = ''
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$engineRoot = Join-Path $root 'engine'
. (Join-Path $root 'game/tools/windows_engine_runtime.ps1')
. (Join-Path $engineRoot 'misc/scripts/windows_build_environment.ps1')
$manifestPath = Join-Path $engineRoot 'drivers/streamline/runtime_manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$sdk = Join-Path $engineRoot '.local/streamline-sdk-v2.10.0'
if ($manifest.sdk_version -ne '2.10.0' -or $manifest.runtime_flavor -ne 'production') { throw 'Unexpected Streamline manifest.' }
if (-not (Test-Path -LiteralPath (Join-Path $sdk 'license.txt'))) {
    if (-not $SDKArchive) {
        $SDKArchive = Join-Path $engineRoot '.local/streamline-sdk-v2.10.0.zip'
        New-Item -ItemType Directory -Force (Split-Path $SDKArchive) | Out-Null
        if (-not (Test-Path -LiteralPath $SDKArchive)) {
            Invoke-WebRequest -Uri $manifest.source_url -OutFile $SDKArchive
        }
    }
    if ((Get-FileHash -LiteralPath $SDKArchive).Hash.ToLowerInvariant() -ne $manifest.archive_sha256) { throw 'Streamline archive checksum mismatch.' }
    Expand-Archive -LiteralPath $SDKArchive -DestinationPath $sdk -Force
}
$runtimeFiles = @(Get-VerifiedStreamlineRuntimeFiles -Directory (Join-Path $sdk 'bin/x64') -ManifestPath $manifestPath)
foreach ($notice in $manifest.notices) {
    $path = [IO.Path]::GetFullPath((Join-Path $sdk $notice.source))
    if (-not $path.StartsWith($sdk + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or
        (Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant() -ne $notice.sha256) { throw 'Streamline notice mismatch.' }
}
$bin = Join-Path $engineRoot 'bin'
New-Item -ItemType Directory -Force $bin | Out-Null
foreach ($runtime in $runtimeFiles) {
    Copy-Item -LiteralPath (Join-Path $sdk "bin/x64/$($runtime.name)") -Destination $bin
}
$null = @(Get-VerifiedStreamlineRuntimeFiles -Directory $bin -ManifestPath $manifestPath)

$vcDestination = Join-Path $engineRoot '.local/msvc-runtime-14.51.36247'
if ($VCRuntimeSource -or -not (Test-Path -LiteralPath (Join-Path $vcDestination 'Redist.txt'))) {
    $candidates = @()
    if ($VCRuntimeSource) {
        $candidates = @($VCRuntimeSource)
    } else {
        $installation = Resolve-VisualStudioPath $VisualStudioPath
        $redist = Join-Path $installation 'VC/Redist/MSVC'
        $candidates = @(Get-ChildItem -LiteralPath $redist -Directory | Sort-Object Name -Descending |
            ForEach-Object { Get-ChildItem -LiteralPath (Join-Path $_.FullName 'x64') -Directory -Filter 'Microsoft.VC*.CRT' -ErrorAction SilentlyContinue } |
            Select-Object -ExpandProperty FullName)
    }
    $source = $null
    foreach ($candidate in $candidates) {
        try {
            $null = @(Get-VerifiedVCRuntimeFiles -Directory $candidate)
            $source = $candidate
            break
        } catch { continue }
    }
    if (-not $source) { throw 'Pinned Microsoft C++ runtime 14.51.36247 was not found. Install the matching stable Visual Studio redist or pass -VCRuntimeSource; do not substitute unverified files.' }
    New-Item -ItemType Directory -Force $vcDestination | Out-Null
    foreach ($file in @(Get-VerifiedVCRuntimeFiles -Directory $source)) {
        Copy-Item -LiteralPath (Join-Path $source $file.name) -Destination $vcDestination
    }
    # Microsoft's redistributable-file list is the authority for these CRT files.
    "Distributable Code for Microsoft Visual Studio 2026`nhttps://learn.microsoft.com/en-us/visualstudio/releases/2026/redistribution`n" |
        Set-Content -LiteralPath (Join-Path $vcDestination 'Redist.txt') -Encoding utf8
}
$null = @(Get-VerifiedVCRuntimeFiles -Directory $vcDestination)
Write-Host 'PASS pinned Streamline production runtimes/notices and Microsoft C++ runtime'
