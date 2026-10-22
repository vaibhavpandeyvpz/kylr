param([string]$Godot=$(if ($env:GODOT) { $env:GODOT } else { 'godot' }))
$ErrorActionPreference='Stop'
$Godot = (Get-Command $Godot -CommandType Application -ErrorAction Stop).Source
$project=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$fixture=Join-Path $project ('reports/render-thread-startup-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixture | Out-Null
$applicationName='Renderer Thread Probe '+[Guid]::NewGuid().ToString('N')
@"
config_version=5
[application]
config/name="$applicationName"
config/project_settings_override="user://renderer.cfg"
[rendering]
driver/threads/thread_model=1
renderer/rendering_method="gl_compatibility"
"@ | Set-Content -LiteralPath (Join-Path $fixture 'project.godot') -Encoding utf8
@'
extends SceneTree
func _initialize():
 var options:=OS.get_cmdline_user_args()
 var expected:=int(options[0])
 var configured:=int(ProjectSettings.get_setting("rendering/driver/threads/thread_model"))
 var actual:=1 if RenderingServer.is_on_render_thread() else 2
 if configured!=expected or actual!=expected:
  push_error("Thread selection mismatch: configured=%d actual=%d expected=%d"%[configured,actual,expected]);quit(2);return
 var error:=OK
 if options[1]=="clear":error=DirAccess.remove_absolute("user://renderer.cfg")
 else:
  var config:=ConfigFile.new()
  config.set_value("rendering","driver/threads/thread_model",int(options[1]))
  error=config.save("user://renderer.cfg")
 if error!=OK:push_error(error_string(error));quit(3);return
 print("RENDER_THREAD_STARTUP_PASS configured=",configured," actual=",actual)
 quit()
'@ | Set-Content -LiteralPath (Join-Path $fixture 'probe.gd') -Encoding utf8
$binary=$Godot
$hash=(Get-FileHash -LiteralPath $binary).Hash
foreach ($step in @(@('1','2'),@('2','1'),@('1','clear'))) {
    $label=$step -join '-'
    $stdout=Join-Path $fixture "$label.log"
    $stderr=Join-Path $fixture "$label-errors.log"
    # No command-line thread override: verify the early persisted setting.
    $arguments=@('--path',('"'+$fixture+'"'),'--script','res://probe.gd','--')+$step
    $process=Start-Process -FilePath $Godot -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    if (-not $process.WaitForExit(60000)) {$process.Kill($true);throw 'Rendering-thread startup probe timed out.'}
    $process.Refresh()
    $log=(Get-Content -LiteralPath $stdout -Raw)+(Get-Content -LiteralPath $stderr -Raw)
    if ($process.ExitCode -ne 0 -or $log -match 'ERROR:|SCRIPT ERROR:|ObjectDB instances were leaked' -or $log -notmatch 'RENDER_THREAD_STARTUP_PASS') {throw "Rendering-thread startup failed: $fixture"}
}
if ($hash -ne (Get-FileHash -LiteralPath $binary).Hash) {throw 'Engine changed during startup qualification.'}
@{passed=$true;engine_sha256=$hash;sequence=@('safe','separate','safe');performance_acceptance=$false} |
 ConvertTo-Json | Set-Content -LiteralPath (Join-Path $fixture 'manifest.json') -Encoding utf8
Write-Output "PASS actual rendering-thread restarts: Safe -> Separate -> Safe. $fixture"
