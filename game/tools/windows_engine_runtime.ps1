# Export-time native dependencies. Dot-source this file; it launches no engine.
function Get-VerifiedStreamlineRuntimeFiles([string]$Directory,[string]$ManifestPath) {
    $manifest=Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if($manifest.schema -ne 1 -or $manifest.sdk_version -ne '2.10.0' -or $manifest.runtime_flavor -ne 'production' -or $manifest.files.Count -ne 12){
        throw 'Expected the pinned Streamline 2.10.0 production manifest.'
    }
    $names=@{}
    foreach($file in $manifest.files){
        if($file.name -notmatch '^[A-Za-z0-9_.-]+\.dll$' -or $file.sha256 -notmatch '^[a-f0-9]{64}$' -or $names.ContainsKey($file.name)){
            throw 'Invalid or duplicate Streamline runtime entry.'
        }
        $names[$file.name]=$true
        $path=Join-Path $Directory $file.name
        $hash=(Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant()
        if($hash -ne $file.sha256 -or (Get-Item -LiteralPath $path).Length -ne $file.bytes){
            throw "Streamline runtime differs from the verified production archive: $($file.name)"
        }
        $signature=Get-AuthenticodeSignature -LiteralPath $path
        if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=NVIDIA Corporation(?:,|$)'){
            throw "Streamline NVIDIA signature verification failed: $($file.name)"
        }
        @{name=$file.name;sha256=$hash;signer=$signature.SignerCertificate.Subject}
    }
}

function Get-VerifiedVCRuntimeFiles([string]$Directory) {
    # Release files from the stable VS 2026 redist folder, not System32 or a
    # debug/preview toolset. Updating this pin requires renewed deployment QA.
    $spec=@{
        'msvcp140.dll'='7c26614e1d733892c2deac7e245ce115504b1d80592dd0a01b08e3e5a55f89ca'
        'vcruntime140.dll'='d1f4225df2cd877dbf130d5668a021dce3f94118455ff5ec952061c30afc9ce7'
        'vcruntime140_1.dll'='a7146c08f89fe5b04541ab507cdb59ff7b44534d4ba3c668a426c6450a03434e'
    }
    foreach($name in $spec.Keys | Sort-Object){
        $path=Join-Path $Directory $name
        $hash=(Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant()
        $version=(Get-Item -LiteralPath $path).VersionInfo.FileVersion
        if($hash -ne $spec[$name] -or $version -ne '14.51.36247.0'){throw "VC runtime differs from the pinned 14.51.36247 release: $name"}
        $signature=Get-AuthenticodeSignature -LiteralPath $path
        if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation(?:,|$)'){
            throw "VC runtime Microsoft signature verification failed: $name"
        }
        $imports=@(Get-PEImportedLibraries $path)
        foreach($dependency in $imports | Where-Object {$_ -match '^(MSVCP|VCRUNTIME|CONCRT)'}){
            if(-not $spec.ContainsKey($dependency.ToLowerInvariant())){throw "Unstaged VC runtime dependency: $dependency"}
        }
        @{name=$name;sha256=$hash;version=$version;signer=$signature.SignerCertificate.Subject;imports=$imports}
    }
}

function Copy-VCRuntime([string]$Directory,[string]$Destination) {
    $files=@(Get-VerifiedVCRuntimeFiles $Directory)
    $notice=Join-Path $Directory 'Redist.txt'
    if(-not (Test-Path -LiteralPath $notice -PathType Leaf)){throw 'VC runtime redistribution notice is missing; prepare the dependency first.'}
    New-Item -ItemType Directory -Force $Destination | Out-Null
    foreach($file in $files){
        Copy-Item -LiteralPath (Join-Path $Directory $file.name) -Destination $Destination
        if((Get-FileHash -LiteralPath (Join-Path $Destination $file.name)).Hash.ToLowerInvariant() -ne $file.sha256){throw "VC runtime copy hash differs: $($file.name)"}
    }
    $notices=Join-Path $Destination 'licenses/engine-rtx/MSVC'
    New-Item -ItemType Directory -Force $notices | Out-Null
    Copy-Item -LiteralPath $notice -Destination $notices
    @{application_local=$true;version='14.51.36247.0';files=$files;minimum_os='Windows 10';production_qualified=$false}
}

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
