param([Parameter(Mandatory)][string]$Path)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip=[IO.Compression.ZipFile]::OpenRead([IO.Path]::GetFullPath($Path))
try {
    $names=@($zip.Entries | ForEach-Object FullName)
    foreach ($required in @('AndroidManifest.xml','assets/assets.sparsepck','assets/data/render_mesh_lods.bin','assets/assets/ui/icons/touch/LICENSE','assets/assets/ui/icons/touch/NOTICE.txt','lib/arm64-v8a/libgodot_android.so','lib/arm64-v8a/liblimboai.android.template_release.arm64.so')) {
        if ($required -notin $names) { throw "APK is missing $required" }
    }
    foreach ($name in $names) {
        if ($name -match '^lib/(?!arm64-v8a/)' -or $name -match '(?i)liblimboai.*(editor|template_debug)' -or
            $name -match '(^|/)(\.env(?:\.[^/]*)?|[^/]+\.(p12|jks|keystore|pk8))$' -or
            $name -match '(^|/)(tests|tools|reports|\.local)/' -or
            $name -match '(mobile_benchmark|rendered_combat_profile)\.(gd|gdc)$') { throw "Unexpected APK payload: $name" }
    }
    foreach ($name in @('lib/arm64-v8a/libgodot_android.so','lib/arm64-v8a/liblimboai.android.template_release.arm64.so')) {
        $reader=[IO.BinaryReader]::new($zip.GetEntry($name).Open())
        try { $header=$reader.ReadBytes(20) } finally { $reader.Dispose() }
        if ($header.Length -ne 20 -or $header[0] -ne 127 -or $header[1] -ne 69 -or $header[2] -ne 76 -or $header[3] -ne 70 -or $header[4] -ne 2 -or $header[5] -ne 1 -or [BitConverter]::ToUInt16($header,18) -ne 183) {
            throw "Expected an ARM64 ELF library: $name"
        }
    }
    Write-Output 'PASS ARM64 release payload, LOD metadata, notices and secret/debug exclusions'
} finally { $zip.Dispose() }
