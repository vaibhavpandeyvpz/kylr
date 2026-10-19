# Shared Windows compiler discovery. No consumer project is required.
function Resolve-VisualStudioPath([string]$Path = '') {
    if ($Path) {
        $resolved = [IO.Path]::GetFullPath($Path)
    } else {
        $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
        if (-not (Test-Path -LiteralPath $vswhere)) { throw 'Visual Studio Installer/vswhere.exe is required.' }
        $resolved = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $resolved) { throw 'Install Visual Studio C++ tools and a Windows SDK.' }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $resolved 'Common7/Tools/Microsoft.VisualStudio.DevShell.dll'))) {
        throw 'Visual Studio developer shell is missing.'
    }
    return $resolved
}

function Initialize-WindowsCompiler([string]$VisualStudioPath = '') {
    $installation = Resolve-VisualStudioPath $VisualStudioPath
    Import-Module (Join-Path $installation 'Common7/Tools/Microsoft.VisualStudio.DevShell.dll')
    Enter-VsDevShell -VsInstallPath $installation -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64' | Out-Null
}
