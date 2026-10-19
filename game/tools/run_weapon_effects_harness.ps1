param([string]$Godot = (Join-Path $PSScriptRoot '../../engine/bin/godot.windows.editor.x86_64.console.exe'))

$ErrorActionPreference = 'Stop'
$harnessProject = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path -LiteralPath $Godot)) { throw "Godot executable not found: $Godot" }
& $Godot --path $harnessProject --windowed --resolution 1280x720 res://tools/weapon_effects_harness.tscn
exit $LASTEXITCODE
