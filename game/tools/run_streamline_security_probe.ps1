param(
    [string]$Godot=(Join-Path $PSScriptRoot '../../engine/bin/godot.windows.editor.x86_64.console.exe'),
    [ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Prefix=('streamline-security-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
)
$ErrorActionPreference='Stop'
$project=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$source=[IO.Path]::GetFullPath((Split-Path $Godot))
$output=Join-Path $project "reports/performance/$Prefix"
if(Test-Path -LiteralPath $output){throw 'Choose a fresh report prefix.'}
New-Item -ItemType Directory $output | Out-Null
$cases=@()
foreach($case in @('genuine','tampered','missing')){
    $runtime=Join-Path $output $case
    New-Item -ItemType Directory $runtime | Out-Null
    foreach($file in Get-ChildItem -LiteralPath $source -File | Where-Object {$_.Extension -eq '.dll' -or $_.Name -in @('godot.windows.editor.x86_64.exe','godot.windows.editor.x86_64.console.exe')}){
        Copy-Item -LiteralPath $file.FullName -Destination $runtime
    }
    $interposer=Join-Path $runtime 'sl.interposer.dll'
    $originalHash=(Get-FileHash -LiteralPath $interposer).Hash
    if($case -eq 'tampered'){
        # Modify only the isolated test copy, in hashed PE contents. Never load
        # it: the engine must reject its invalid signature before LoadLibrary.
        $bytes=[IO.File]::ReadAllBytes($interposer)
        $peOffset=[BitConverter]::ToInt32($bytes,0x3c)
        # COFF timestamp is signed but is not executable code or loader layout.
        # Keep a loadable PE so OS rejection cannot make a broken loader pass.
        $bytes[$peOffset+8]=$bytes[$peOffset+8] -bxor 1
        [IO.File]::WriteAllBytes($interposer,$bytes)
        if((Get-AuthenticodeSignature -LiteralPath $interposer).Status -eq 'Valid'){throw 'Tamper fixture still has a valid signature.'}
    }elseif($case -eq 'missing'){
        Remove-Item -LiteralPath $interposer
    }elseif((Get-AuthenticodeSignature -LiteralPath $interposer).Status -ne 'Valid'){
        throw 'Genuine interposer does not have a trusted signature.'
    }
    $stdout=Join-Path $runtime 'probe.log';$stderr=Join-Path $runtime 'errors.log'
    $arguments=@('--path',('"'+$project+'"'),'--render-thread','safe','--script','res://tools/probe_streamline_startup.gd','--','--module-check')
    if($case -eq 'genuine'){$arguments+='--expect-dlss'}
    # Inspect the actual engine process, not the console launcher parent.
    $process=Start-Process -FilePath (Join-Path $runtime 'godot.windows.editor.x86_64.exe') -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $deadline=[DateTime]::UtcNow.AddSeconds(30)
    $ready=$false
    while(-not $process.HasExited -and [DateTime]::UtcNow -lt $deadline){
        if((Get-Content -LiteralPath $stdout -Raw) -match ('STREAMLINE_MODULE_CHECK_READY pid='+$process.Id)){$ready=$true;break}
        Start-Sleep -Milliseconds 20
    }
    if(-not $ready){if(-not $process.HasExited){$process.Kill($true)};throw "Module inspection checkpoint missing: $case"}
    $process.Refresh()
    $modules=@($process.Modules|Where-Object {$_.ModuleName -ieq 'sl.interposer.dll'})
    $loaded=$modules.Count -gt 0
    if($loaded -ne ($case -eq 'genuine')){$process.Kill($true);throw "Unexpected interposer module load: $case"}
    if($loaded -and ($modules.Count -ne 1 -or $modules[0].FileName -ine $interposer)){$process.Kill($true);throw 'Interposer was loaded from an unexpected location.'}
    if(-not $process.WaitForExit(60000)){$process.Kill($true);throw "Startup timed out: $case"}
    $process.Refresh()
    $log=(Get-Content -LiteralPath $stdout -Raw)+(Get-Content -LiteralPath $stderr -Raw)
    if($process.ExitCode -ne 0 -or $log -notmatch 'STREAMLINE_STARTUP_PASS' -or $log -match 'SCRIPT ERROR:|VUID-|SYNC-HAZARD|ObjectDB instances were leaked'){throw "Startup failed: $case"}
    if($case -eq 'tampered'){
        if($log -notmatch 'ERROR: Streamline interposer signature verification failed\.'){throw 'Tampered interposer was not explicitly rejected.'}
        $otherErrors=@($log -split "`r?`n" | Where-Object {$_ -match '^ERROR:' -and $_ -notmatch '^ERROR: Streamline interposer signature verification failed\.'})
        if($otherErrors.Count){throw 'Unexpected errors in tampered interposer test.'}
    }elseif($log -match 'ERROR:'){throw "Unexpected startup error: $case"}
    $cases+=@{case=$case;passed=$true;interposer_module_loaded=$loaded;original_interposer_sha256=$originalHash}
}
@{passed=$true;cases=$cases;engine_sha256=(Get-FileHash -LiteralPath (Join-Path $source 'godot.windows.editor.x86_64.exe')).Hash;visual_quality_acceptance=$false;performance_acceptance=$false}|
    ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $output 'manifest.json') -Encoding utf8
Write-Output 'PASS genuine, tampered and missing interposer startup.'
