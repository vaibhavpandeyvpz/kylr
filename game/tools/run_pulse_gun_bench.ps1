param([string]$Godot = (Join-Path $PSScriptRoot '../../engine/bin/godot.windows.editor.x86_64.console.exe'))
$ErrorActionPreference = 'Stop'
$benchProject = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path -LiteralPath $Godot)) { throw "Godot executable not found: $Godot" }
& $Godot --path $benchProject --windowed --resolution 1280x720 res://tools/pulse_gun_bench.tscn
exit $LASTEXITCODE
