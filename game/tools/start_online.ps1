param([switch]$Build)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$secretPath=Join-Path $projectRoot 'reports/online/local.env'
if (-not (Test-Path -LiteralPath $secretPath)) {
    New-Item -ItemType Directory -Force (Split-Path -Parent $secretPath) | Out-Null
    $accessSecret=[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    $controlSecret=[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    Set-Content -LiteralPath $secretPath -Value @("JWT_SECRET=$accessSecret","CONTROL_TOKEN=$controlSecret")
}
if ($Build) {
    & docker build -t kylr-game-server:local -f (Join-Path $projectRoot 'services/deploy/Dockerfile.edgegap') (Split-Path -Parent $projectRoot)
    if ($LASTEXITCODE -ne 0) { throw 'Game server image build failed.' }
}
& docker compose --env-file $secretPath -f (Join-Path $projectRoot 'services/deploy/compose.yaml') up -d --build --wait
if ($LASTEXITCODE -ne 0) { throw 'Local online services did not start.' }
Write-Host 'Local API ready at http://127.0.0.1:8080. Credentials and game accounts remain local.'
