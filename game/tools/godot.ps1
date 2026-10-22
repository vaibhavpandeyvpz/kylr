function Resolve-GodotExecutable([string]$Executable) {
    $binary = (Get-Command $Executable -CommandType Application -ErrorAction Stop).Source
    if ($IsWindows -and -not $binary.EndsWith('_console.exe')) {
        if ([IO.Path]::GetExtension($binary) -eq '.exe') {
            $console = [IO.Path]::ChangeExtension($binary, $null) + '_console.exe'
            if (Test-Path -LiteralPath $console) { return $console }
        } else {
            # setup-godot exposes an extensionless hard link to the GUI binary.
            $runtime = Join-Path (Split-Path (Split-Path $binary)) 'runtime'
            $console = @(Get-ChildItem -LiteralPath $runtime -Filter '*_console.exe' -File -Recurse)
            if ($console.Count -ne 1) { throw 'Expected one installed Godot console executable.' }
            return $console[0].FullName
        }
    }
    return $binary
}
