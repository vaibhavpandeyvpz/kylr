param([string]$Godot = $(if ($env:GODOT) { $env:GODOT } else { 'godot' }))

$ErrorActionPreference = 'Stop'
$Godot = (Get-Command $Godot -CommandType Application -ErrorAction Stop).Source
$harnessProject = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path -LiteralPath $Godot)) { throw "Godot executable not found: $Godot" }
& $Godot --path $harnessProject --windowed --resolution 1280x720 res://tools/weapon_effects_harness.tscn
exit $LASTEXITCODE
