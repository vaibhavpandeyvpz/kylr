param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '../../.local/android-signing'),
    [string]$JavaHome = $env:JAVA_HOME,
    [ValidatePattern('^[a-z][a-z0-9-]+$')][string]$Alias = 'kylr-release'
)
$ErrorActionPreference='Stop'
$keytool=if ($JavaHome) { Join-Path $JavaHome "bin/keytool$(if ($IsWindows) { '.exe' })" } else { (Get-Command keytool -ErrorAction Stop).Source }
$directory=[IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $directory) { throw 'Choose a new directory; existing signing material is never replaced.' }
New-Item -ItemType Directory -Path $directory | Out-Null
if ($IsWindows) {
    $acl=Get-Acl -LiteralPath $directory
    $acl.SetAccessRuleProtection($true,$false)
    $owner=[Security.Principal.WindowsIdentity]::GetCurrent().User
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($owner,'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-5-18'),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
    Set-Acl -LiteralPath $directory -AclObject $acl
} else { & chmod 700 $directory; if ($LASTEXITCODE) { throw 'Cannot protect signing directory' } }
$password=[Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
$previous=$env:KYLR_NEW_KEY_PASSWORD
try {
    $env:KYLR_NEW_KEY_PASSWORD=$password
    $store=Join-Path $directory 'kylr-release.p12'
    & $keytool -genkeypair -noprompt -storetype PKCS12 -keystore $store -storepass:env KYLR_NEW_KEY_PASSWORD -keypass:env KYLR_NEW_KEY_PASSWORD -alias $Alias -keyalg RSA -keysize 3072 -validity 10000 -dname 'CN=KYLR Android Release' 2>&1 | Set-Content (Join-Path $directory 'generation.log')
    if ($LASTEXITCODE) { throw 'Key generation failed; see private generation.log.' }
    [IO.File]::WriteAllText((Join-Path $directory 'keystore.base64.txt'),[Convert]::ToBase64String([IO.File]::ReadAllBytes($store)))
    [IO.File]::WriteAllText((Join-Path $directory 'keystore-password.txt'),$password)
    & $keytool -exportcert -rfc -keystore $store -storepass:env KYLR_NEW_KEY_PASSWORD -alias $Alias -file (Join-Path $directory 'certificate.pem') 2>&1 | Out-Null
    if ($LASTEXITCODE) { throw 'Certificate export failed.' }
    @"
GitHub repository Settings > Secrets and variables > Actions > Secrets:

ANDROID_KEYSTORE_BASE64: contents of keystore.base64.txt
ANDROID_KEYSTORE_PASSWORD: contents of keystore-password.txt

The signing alias is $Alias. The workflow defaults to kylr-release; set the
ANDROID_KEY_ALIAS repository variable only if using another alias.

Back up this directory securely. Keep the same key and password for future
updates. Never commit or upload these files as release/Actions artifacts.
certificate.pem contains only the public certificate.
"@ | Set-Content (Join-Path $directory 'GITHUB-SETUP.txt')
    if (-not $IsWindows) { Get-ChildItem -LiteralPath $directory -File | ForEach-Object { & chmod 600 $_.FullName } }
    Write-Output "Signing material created in $directory (alias: $Alias). Secret values were not printed."
} finally { $env:KYLR_NEW_KEY_PASSWORD=$previous }
