param([string]$Godot = $(if ($env:GODOT) { $env:GODOT } else { 'godot' }))
$ErrorActionPreference = 'Stop'
$Godot = (Get-Command $Godot -CommandType Application -ErrorAction Stop).Source
$benchProject = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path -LiteralPath $Godot)) { throw "Godot executable not found: $Godot" }
& $Godot --path $benchProject --windowed --resolution 1280x720 res://tools/pulse_gun_bench.tscn
exit $LASTEXITCODE
