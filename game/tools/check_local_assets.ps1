$ErrorActionPreference = 'Stop'
$workspaceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$assetsRoot = Join-Path $workspaceRoot 'game/assets'
$required = [Collections.Generic.HashSet[string]]::new()
foreach ($role in @('albedo','normal','orm')) {
    $null = $required.Add("game/assets/textures/lunar_surface/regolith_$role.png")
}
$animations = Get-Content -LiteralPath (Join-Path $assetsRoot 'animations/manifest.json') -Raw | ConvertFrom-Json
foreach ($clip in $animations.PSObject.Properties.Value) {
    foreach ($field in @('file','weapon_file')) {
        if ($clip.$field) { $null = $required.Add("game/assets/animations/$($clip.$field)") }
    }
}
$audio = Get-Content -LiteralPath (Join-Path $workspaceRoot 'library/sounds/epidemic_manifest.json') -Raw | ConvertFrom-Json
foreach ($cue in $audio.game) { $null = $required.Add($cue.file) }
$catalog = Get-Content -LiteralPath (Join-Path $assetsRoot 'audio/catalog.json') -Raw | ConvertFrom-Json
foreach ($entry in $catalog.PSObject.Properties.Value) {
    foreach ($path in @($entry.file)+@($entry.files)) {
        if ($path) { $null = $required.Add($path.Replace('res://assets/','game/assets/')) }
    }
}
$missing = @($required | Where-Object { -not (Test-Path -LiteralPath (Join-Path $workspaceRoot $_) -PathType Leaf) })
if ($missing.Count) {
    throw "Missing $($missing.Count) required game assets. Follow docs/ASSET_SETUP.md before import. Examples: $($missing[0..([Math]::Min(4,$missing.Count-1))] -join ', ')"
}
Write-Host "PASS required local game assets ($($required.Count) files)"
