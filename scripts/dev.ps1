# اجرای محیط توسعه (API + دیتابیس)
#   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 -Reload      # با autoreload
#   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 -SkipDb      # دیتابیس از قبل بالا است

param(
    [switch]$SkipDb,
    [switch]$Reload
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$api = Join-Path $root 'services\api'

$env:PYTHONIOENCODING = 'utf-8'

if (-not $SkipDb) {
    Write-Host '> starting local PostgreSQL (pgserver) + writing .env.local' -ForegroundColor Cyan
    & python (Join-Path $PSScriptRoot 'devdb.py')
    if ($LASTEXITCODE -ne 0) { throw 'devdb.py failed' }
}

Push-Location $api
try {
    Write-Host '> alembic upgrade head' -ForegroundColor Cyan
    & python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'migrations failed' }

    Write-Host '> seed defaults (idempotent)' -ForegroundColor Cyan
    & python -m app.seeding
    if ($LASTEXITCODE -ne 0) { throw 'seed failed' }

    Write-Host '> uvicorn on http://127.0.0.1:8000  (docs: /docs)' -ForegroundColor Green
    $uvicornArgs = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000')
    if ($Reload) { $uvicornArgs += '--reload' }
    & python @uvicornArgs
}
finally {
    Pop-Location
}
