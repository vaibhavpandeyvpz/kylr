param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._+-]*$')]
    [string]$Version = '0.1.0',
    [string]$Godot = (Join-Path $PSScriptRoot '../../engine/bin/godot.windows.editor.x86_64.console.exe'),
    [string]$VCRuntimeDirectory = (Join-Path $PSScriptRoot '../../engine/.local/msvc-runtime-14.51.36247')
)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'check_local_assets.ps1')
$projectRoot = Split-Path -Parent $PSScriptRoot
$workspaceRoot = Split-Path -Parent $projectRoot
$buildId = [guid]::NewGuid().ToString('N')
# A fresh staging directory prevents obsolete DLLs or local reports shipping.
$outputDirectory = Join-Path $projectRoot "build/package-$buildId/windows"
$reportDirectory = Join-Path $projectRoot "reports/packaging/$buildId"
New-Item -ItemType Directory -Force $outputDirectory,$reportDirectory | Out-Null

function Invoke-GodotCheck([string]$Name, [string]$Executable, [string[]]$Arguments) {
    $log = Join-Path $reportDirectory "$Name.log"
    # A pipeline also makes PowerShell wait for GUI-subsystem executables.
    & $Executable @Arguments 2>&1 | Out-File -LiteralPath $log -Encoding utf8
    $engineExit = $LASTEXITCODE
    if ($engineExit -ne 0 -or (Select-String -LiteralPath $log -Pattern 'SCRIPT ERROR:|ERROR:|VUID-|SYNC-HAZARD|ObjectDB.*leaked at exit|Resources still in use at exit')) {
        Get-Content -LiteralPath $log -Tail 40
        throw "$Name failed. See $log"
    }
    Write-Host "PASS $Name"
}

$engineVersion = (& $Godot --version | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $engineVersion -notmatch '^4\.7\.2\.') {
    throw "Expected Godot 4.7.2, got: $engineVersion"
}
Invoke-GodotCheck 'import' $Godot @('--headless','--path',$projectRoot,'--editor','--import','--quit')
$executable = Join-Path $outputDirectory 'KYLR.exe'
$pack = Join-Path $outputDirectory 'KYLR.pck'
Invoke-GodotCheck 'export' $Godot @('--headless','--path',$projectRoot,'--export-release','Windows Desktop',$executable)
foreach ($required in @($executable,$pack)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing export: $required" }
}
if (-not (Get-ChildItem -LiteralPath $outputDirectory -Recurse -File -Filter 'liblimboai.windows.template_release.x86_64.dll')) {
    throw 'Export is missing the LimboAI release DLL.'
}
Invoke-GodotCheck 'licenses' $Godot @('--headless','--path',$projectRoot,'--script','res://tools/write_licenses.gd','--',"--output=$outputDirectory/ENGINE-LICENSES.txt")
Copy-Item -LiteralPath (Join-Path $projectRoot 'THIRD_PARTY.md') -Destination $outputDirectory
foreach ($projectNotice in @('LICENSE','NOTICE')) {
    Copy-Item -LiteralPath (Join-Path $projectRoot "../$projectNotice") -Destination $outputDirectory
}
# Exporting the executable/PCK does not copy the optional engine SDK runtimes.
# Match the pinned production SDK, never a development/watermarked directory.
$engineRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot '../engine'))
$runtimeDirectory = Split-Path ([IO.Path]::GetFullPath($Godot))
. (Join-Path $PSScriptRoot 'windows_engine_runtime.ps1')
$sdk = Join-Path $engineRoot '.local/streamline-sdk-v2.10.0'
$sdkManifestPath = Join-Path $engineRoot 'drivers/streamline/runtime_manifest.json'
$sdkManifest = Get-Content -LiteralPath $sdkManifestPath -Raw | ConvertFrom-Json
$runtimeManifest = @(Get-VerifiedStreamlineRuntimeFiles -Directory $runtimeDirectory -ManifestPath $sdkManifestPath)
foreach ($runtime in $runtimeManifest) {
    $destination=Join-Path $outputDirectory $runtime.name
    Copy-Item -LiteralPath (Join-Path $runtimeDirectory $runtime.name) -Destination $destination
    if((Get-FileHash -LiteralPath $destination).Hash.ToLowerInvariant() -ne $runtime.sha256){
        throw "RTX runtime copy differs: $($runtime.name)"
    }
}
$vcRuntime=Copy-VCRuntime -Directory $VCRuntimeDirectory -Destination $outputDirectory
$noticeDirectory = Join-Path $outputDirectory 'licenses/engine-rtx'
New-Item -ItemType Directory -Path $noticeDirectory -Force | Out-Null
if($sdkManifest.notices.Count -ne 5){throw 'Streamline production notices are incomplete.'}
foreach ($notice in $sdkManifest.notices) {
    $source=[IO.Path]::GetFullPath((Join-Path $sdk $notice.source))
    $sdkRoot=[IO.Path]::GetFullPath($sdk).TrimEnd([IO.Path]::DirectorySeparatorChar)+[IO.Path]::DirectorySeparatorChar
    if(-not $source.StartsWith($sdkRoot,[StringComparison]::OrdinalIgnoreCase) -or $notice.name -notmatch '^[A-Za-z0-9_.-]+$'){
        throw 'Invalid Streamline notice path.'
    }
    if((Get-FileHash -LiteralPath $source).Hash.ToLowerInvariant() -ne $notice.sha256){throw "Streamline notice differs: $($notice.name)"}
    Copy-Item -LiteralPath $source -Destination (Join-Path $noticeDirectory $notice.name)
}
$notices = @('addons/limboai/LICENSE.md','addons/limboai/LOGO_LICENSE.md','addons/phantom_camera/LICENSE','addons/proton_scatter/LICENSE','addons/proton_scatter/LICENSE.md')
$notices += 'addons/shaker/LICENSE'
$notices += Get-ChildItem -LiteralPath (Join-Path $projectRoot 'assets') -Recurse -File |
    Where-Object { $_.Name -match '(?i)license' -and $_.Extension -ne '.import' } |
    ForEach-Object { [IO.Path]::GetRelativePath($projectRoot,$_.FullName) }
foreach ($notice in $notices) {
    $destination = Join-Path $outputDirectory (Join-Path 'licenses' $notice)
    New-Item -ItemType Directory -Force (Split-Path -Parent $destination) | Out-Null
    Copy-Item -LiteralPath (Join-Path $projectRoot $notice) -Destination $destination
}
# Start from an empty project, then mount the PCK inside the inspector. Booting
# an editor with --main-pack selects debug GDExtensions from a release package.
$inspectionProject = Join-Path $reportDirectory 'inspection-project'
New-Item -ItemType Directory -Path $inspectionProject | Out-Null
'config_version=5' | Set-Content -LiteralPath (Join-Path $inspectionProject 'project.godot') -Encoding utf8
Invoke-GodotCheck 'inspect' $Godot @('--headless','--path',$inspectionProject,'--script',(Join-Path $PSScriptRoot 'inspect_package.gd'),'--',"--pack=$pack")
# GUI-subsystem release executables may emit no redirected stdout on Windows.
# Read Godot's explicit file log too, rather than accepting an empty log.
$startupLog = Join-Path $reportDirectory 'game-startup.log'
Invoke-GodotCheck 'smoke' $executable @('--headless','--log-file',$startupLog,'--quit-after','2')
if (-not (Test-Path -LiteralPath $startupLog) -or
    -not (Select-String -LiteralPath $startupLog -Pattern '^Godot Engine v4\.7\.2\.') -or
    (Select-String -LiteralPath $startupLog -Pattern 'SCRIPT ERROR:|ERROR:|VUID-|SYNC-HAZARD|ObjectDB.*leaked at exit|Resources still in use at exit')) {
    throw "Exported startup log is missing or contains errors: $startupLog"
}

$revision = (& git -C $workspaceRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot identify package revision.' }
$manifest = @{version=$Version;revision=$revision;godot=$engineVersion;development=([bool](& git -C $workspaceRoot status --porcelain));streamline_manifest_sha256=(Get-FileHash -LiteralPath $sdkManifestPath).Hash.ToLowerInvariant();rtx_runtime=$runtimeManifest;vc_runtime=$vcRuntime;files=@()}
foreach ($file in Get-ChildItem -LiteralPath $outputDirectory -File -Recurse | Sort-Object FullName) {
    $manifest.files += @{
        name=[IO.Path]::GetRelativePath($outputDirectory,$file.FullName).Replace('\','/')
        bytes=$file.Length
        sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $outputDirectory 'manifest.json') -Encoding utf8
$archive = Join-Path $projectRoot "build/KYLR-Windows-$Version.zip"
Compress-Archive -LiteralPath $outputDirectory -DestinationPath $archive -Force
$digest = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText("$archive.sha256", "$digest  $([IO.Path]::GetFileName($archive))`n", [Text.UTF8Encoding]::new($false))
Write-Output $archive
