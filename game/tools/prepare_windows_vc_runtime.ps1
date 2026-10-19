param(
    [Parameter(Mandatory)][string]$RedistDirectory,
    [Parameter(Mandatory)][string]$NoticePath,
    [string]$OutputDirectory=(Join-Path $PSScriptRoot '../../engine/.local/msvc-runtime-14.51.36247')
)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'windows_engine_runtime.ps1')
if(Test-Path -LiteralPath $OutputDirectory){throw 'Use a fresh output directory; do not overwrite prepared dependencies.'}
if(-not (Test-Path -LiteralPath $NoticePath -PathType Leaf)){throw 'Supply the installed Visual Studio redistribution notice.'}
$files=@(Get-VerifiedVCRuntimeFiles $RedistDirectory)
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
foreach($file in $files){
    Copy-Item -LiteralPath (Join-Path $RedistDirectory $file.name) -Destination $OutputDirectory
    if((Get-FileHash -LiteralPath (Join-Path $OutputDirectory $file.name)).Hash.ToLowerInvariant() -ne $file.sha256){throw "Prepared DLL hash differs: $($file.name)"}
}
Copy-Item -LiteralPath $NoticePath -Destination (Join-Path $OutputDirectory 'Redist.txt')
@{version='14.51.36247.0';source_directory=[IO.Path]::GetFullPath($RedistDirectory);
    redistribution='https://learn.microsoft.com/en-us/visualstudio/releases/2026/redistribution';
    deployment='https://learn.microsoft.com/en-us/cpp/windows/determining-which-dlls-to-redistribute';
    files=$files;production_qualified=$false} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'manifest.json')
Write-Output "Prepared pinned app-local VC runtime: $OutputDirectory"
