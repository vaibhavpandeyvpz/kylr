param(
    [ValidateSet('editor','template_debug','template_release')][string]$Target = 'editor',
    [string]$Python = (Join-Path $PSScriptRoot '../../.local/build-venv/Scripts/python.exe'),
    [string]$VisualStudioPath = '',
    [ValidateRange(1,256)][int]$Jobs = 6
)
$ErrorActionPreference = 'Stop'
$engineRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$Python = (Get-Command $Python -ErrorAction Stop).Source
. (Join-Path $PSScriptRoot 'windows_build_environment.ps1')
Initialize-WindowsCompiler $VisualStudioPath
Push-Location $engineRoot
try {
    & $Python -m SCons platform=windows "target=$Target" arch=x86_64 dev_build=no debug_symbols=no optimize=speed d3d12=no use_streamline=yes use_aftermath=no "-j$Jobs"
    if ($LASTEXITCODE -ne 0) { throw "Engine $Target build failed ($LASTEXITCODE)." }
    $binary = Join-Path $engineRoot "bin/godot.windows.$Target.x86_64.exe"
    if (-not (Test-Path -LiteralPath $binary)) { throw "Build did not produce $binary" }
} finally {
    Pop-Location
}
