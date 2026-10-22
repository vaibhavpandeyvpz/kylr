function Get-PEImportedLibraries([string]$Path) {
    $stream=[IO.File]::OpenRead([IO.Path]::GetFullPath($Path))
    $image=$null
    try {
        $image=[System.Reflection.PortableExecutable.PEReader]::new($stream)
        $header=$image.PEHeaders.PEHeader
        if($null -eq $header){throw "Not a Windows PE image: $Path"}
        $directory=$header.ImportTableDirectory
        if($directory.RelativeVirtualAddress -eq 0){return}
        $reader=$image.GetSectionData($directory.RelativeVirtualAddress).GetReader()
        $terminated=$false
        for($index=0;$index -lt [Math]::Min(4096,[int]($directory.Size/20));$index++){
            $descriptor=@(1..5 | ForEach-Object {$reader.ReadUInt32()})
            if(-not ($descriptor | Where-Object {$_ -ne 0})){$terminated=$true;break}
            if($descriptor[3] -eq 0){throw "Invalid import descriptor: $Path"}
            $nameReader=$image.GetSectionData([int]$descriptor[3]).GetReader()
            $name=[Text.StringBuilder]::new()
            $nameTerminated=$false
            for($offset=0;$offset -lt 256;$offset++){
                $value=$nameReader.ReadByte()
                if($value -eq 0){$nameTerminated=$true;break}
                if($value -gt 127){throw "Invalid import name: $Path"}
                $null=$name.Append([char]$value)
            }
            if(-not $nameTerminated -or $name.Length -eq 0){throw "Unterminated import name: $Path"}
            $name.ToString()
        }
        if(-not $terminated){throw "Unterminated import table: $Path"}
    } finally {
        if($null -ne $image){$image.Dispose()}
        $stream.Dispose()
    }
}
