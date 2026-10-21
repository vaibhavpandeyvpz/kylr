param(
 [ValidateSet('raster','dlss')][string]$Mode='dlss',
 [ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Prefix=('armor-overlay-'+(Get-Date -Format 'yyyyMMdd-HHmmss')),
 [switch]$Validation,
 [ValidateSet('authored','no-depth','offset-10mm','double-sided')][string]$Variant='authored',
 [switch]$SMAA,
 [string]$Godot=(Join-Path $PSScriptRoot '../../engine/bin/godot.windows.editor.x86_64.console.exe')
)
$ErrorActionPreference='Stop'
$project=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$output=Join-Path $project "reports/performance/$Prefix-$Mode"
if (Test-Path -LiteralPath $output) {throw 'Choose a fresh capture prefix.'}
$paths=@((Join-Path (Split-Path $Godot) 'godot.windows.editor.x86_64.exe'),
 (Join-Path $project 'tools/probe_armor_overlay.gd'),(Join-Path $project 'shaders/combat/energy_surface.gdshader'))
$hashes=@($paths | ForEach-Object {(Get-FileHash -LiteralPath $_).Hash})
$saved=@{}
foreach ($name in @('VK_LAYER_PATH','VK_INSTANCE_LAYERS','VK_VALIDATION_VALIDATE_SYNC')) {
 $saved[$name]=[Environment]::GetEnvironmentVariable($name,'Process')
}
try {
 $arguments=@('--path',('"'+$project+'"'),'--script','res://tools/probe_armor_overlay.gd')
 if ($Validation) {
  $env:VK_LAYER_PATH=[IO.Path]::GetFullPath((Join-Path $project '../engine/.local/vulkan-validation-1.4.363.0/Bin'))
  if (-not (Test-Path -LiteralPath (Join-Path $env:VK_LAYER_PATH 'VkLayer_khronos_validation.json'))) {throw 'Pinned validation layer missing.'}
  $env:VK_INSTANCE_LAYERS='VK_LAYER_KHRONOS_validation';$env:VK_VALIDATION_VALIDATE_SYNC='true'
  $arguments+='--gpu-validation'
 }
 $arguments+=@('--',"--mode=$Mode","--prefix=$Prefix","--variant=$Variant")
 if($SMAA){$arguments+='--smaa'}
 $started=[DateTime]::UtcNow
 $stdout="$output.log";$stderr="$output-errors.log"
 $process=Start-Process -FilePath $Godot -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
 if (-not $process.WaitForExit(180000)) {$process.Kill($true);throw 'Armor overlay capture timed out.'}
 $process.Refresh()
 $log=(Get-Content -LiteralPath $stdout -Raw)+(Get-Content -LiteralPath $stderr -Raw)
 if ($process.ExitCode -ne 0 -or $log -match 'ERROR:|SCRIPT ERROR:|VUID-|SYNC-HAZARD|ObjectDB instances were leaked' -or $log -notmatch "ARMOR_OVERLAY_CAPTURE_PASS $Mode") {throw "Armor overlay capture failed: $stderr"}
 if ($Validation -and $log -notmatch 'VK_LAYER_KHRONOS_validation') {throw 'Validation layer was not confirmed.'}
 foreach ($name in @('base.png','flash.png','occluded.png','report.json')) {
  $file=Get-Item -LiteralPath (Join-Path $output $name)
  if ($file.LastWriteTimeUtc -lt $started -or $file.Length -eq 0) {throw 'Stale or missing overlay capture.'}
 }
 for ($i=0;$i -lt $paths.Count;$i++) {
  if ($hashes[$i] -ne (Get-FileHash -LiteralPath $paths[$i]).Hash) {throw 'Engine, probe or shader changed during capture.'}
 }
 @{capture_passed=$true;mode=$Mode;smaa=[bool]$SMAA;variant=$Variant;diagnostic_variant=($Variant -ne 'authored');engine_sha256=$hashes[0];probe_sha256=$hashes[1];shader_sha256=$hashes[2];
   validation=[bool]$Validation;visual_quality_acceptance=$false;performance_acceptance=$false} |
  ConvertTo-Json | Set-Content -LiteralPath (Join-Path $output 'manifest.json') -Encoding utf8
 Write-Output "PASS $Mode overlay captures; visual comparison required: $output"
} finally {
 foreach ($name in $saved.Keys) {[Environment]::SetEnvironmentVariable($name,$saved[$name],'Process')}
}
