function Resolve-GodotExecutable([string]$Executable) {
    $binary = (Get-Command $Executable -CommandType Application -ErrorAction Stop).Source
    if ($IsWindows -and [IO.Path]::GetExtension($binary) -ne '.exe') {
        # The action caches the GUI .exe and exposes an extensionless hard link.
        # Invoke the .exe through a pipeline so PowerShell waits for its exit.
        $runtime = Join-Path (Split-Path (Split-Path $binary)) 'runtime'
        $installed = @(Get-ChildItem -LiteralPath $runtime -Filter '*.exe' -File -Recurse |
            Where-Object Name -NotLike '*_console.exe')
        if ($installed.Count -ne 1) { throw 'Expected one installed Godot executable.' }
        return $installed[0].FullName
    }
    return $binary
}
