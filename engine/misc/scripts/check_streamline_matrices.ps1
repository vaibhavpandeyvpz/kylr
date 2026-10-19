param(
    [string]$OutputDirectory='',
    [string]$SourceFile='',
    [string]$Python='',
    [string]$VsDevCmd=''
)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if(-not $OutputDirectory){$OutputDirectory=Join-Path $root ('.local/streamline-matrix-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
$OutputDirectory=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath $OutputDirectory){throw 'Choose a fresh matrix-probe output directory.'}
if(-not $SourceFile){$SourceFile=Join-Path $root 'servers/rendering/renderer_rd/effects/dlss.cpp'}
if(-not $Python){$Python=Join-Path $root '.local/build-venv/Scripts/python.exe'}
if(-not $VsDevCmd){
    $vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    if(-not(Test-Path -LiteralPath $vswhere)){throw 'Pass VsDevCmd for the installed MSVC toolchain.'}
    $installation=& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if(-not $installation){throw 'MSVC C++ tools are unavailable.'}
    $VsDevCmd=Join-Path $installation 'Common7/Tools/VsDevCmd.bat'
}
$headers=Join-Path $root 'thirdparty/streamline/include'
$probe=Join-Path $PSScriptRoot 'probe_streamline_matrix_conversion.cpp'
$sourceHash=(Get-FileHash -LiteralPath $SourceFile).Hash
$probeHash=(Get-FileHash -LiteralPath $probe).Hash
$headerHashes=@{}
foreach($name in @('sl_consts.h','sl_matrix_helpers.h')){$headerHashes[$name]=(Get-FileHash -LiteralPath (Join-Path $headers $name)).Hash}
& $Python (Join-Path $PSScriptRoot 'extract_streamline_matrix_probe.py') $SourceFile $OutputDirectory
if($LASTEXITCODE -ne 0){throw 'Converter extraction failed.'}
$command=@"
@echo off
call "$VsDevCmd" -arch=x64 -host_arch=x64
if errorlevel 1 exit /b 1
cl /nologo /EHsc /std:c++17 /MD /I"$headers" /I"$OutputDirectory" "$probe" /Fe"$OutputDirectory/probe.exe" /Fo"$OutputDirectory/probe.obj"
"@
$build=Join-Path $OutputDirectory 'build.cmd'
[IO.File]::WriteAllText($build,$command,[Text.ASCIIEncoding]::new())
& $build *> (Join-Path $OutputDirectory 'build.log')
if($LASTEXITCODE -ne 0){throw "Matrix probe compilation failed; see $OutputDirectory/build.log"}
& (Join-Path $OutputDirectory 'probe.exe') | Set-Content -LiteralPath (Join-Path $OutputDirectory 'report.json')
if($LASTEXITCODE -ne 0){throw "Matrix convention probe failed; see $OutputDirectory/report.json"}
if($sourceHash -ne (Get-FileHash -LiteralPath $SourceFile).Hash -or $probeHash -ne (Get-FileHash -LiteralPath $probe).Hash){throw 'Source changed during matrix probe.'}
foreach($name in $headerHashes.Keys){if($headerHashes[$name] -ne (Get-FileHash -LiteralPath (Join-Path $headers $name)).Hash){throw 'SDK headers changed during matrix probe.'}}
@{passed=$true;source_sha256=$sourceHash;probe_sha256=$probeHash;sdk_headers=$headerHashes;quality_accepted=$false;performance_accepted=$false}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $OutputDirectory 'manifest.json')
Write-Output "PASS Streamline matrix convention: $OutputDirectory (numerical correctness only)."
