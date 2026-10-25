<#
.SYNOPSIS
  Run the Ishi API (FastAPI, :8000) and web app (Next.js, :3000) together. Ctrl+C stops both.

.DESCRIPTION
  Both bind to 127.0.0.1 only. Open http://localhost:3000 and install it as an app from the
  browser's address bar (localhost counts as a secure context, so the PWA installs without HTTPS).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\start.ps1          # production build
  powershell -ExecutionPolicy Bypass -File scripts\start.ps1 -Dev     # hot reload (no service worker)
#>
param(
    [switch]$Dev,
    [int]$ApiPort = 8000,
    [int]$WebPort = 3000
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $Root "apps\api"
$WebDir = Join-Path $Root "apps\web"

if (-not (Test-Path (Join-Path $WebDir "node_modules"))) {
    Push-Location $WebDir; pnpm install; Pop-Location
}
if (-not $Dev) {
    Write-Host "Building web app..."
    Push-Location $WebDir
    try {
        pnpm build
        if ($LASTEXITCODE -ne 0) { throw "web build failed" }
    } finally { Pop-Location }
}

$env:ISHI_API_URL = "http://127.0.0.1:$ApiPort"
$apiArgs = "run uvicorn ishi.main:app --host 127.0.0.1 --port $ApiPort"
if ($Dev) { $apiArgs += " --reload" }
$webArgs = if ($Dev) { "dev -H 127.0.0.1 -p $WebPort" } else { "start -H 127.0.0.1 -p $WebPort" }

$api = Start-Process -FilePath "uv" -ArgumentList $apiArgs -WorkingDirectory $ApiDir -NoNewWindow -PassThru
$web = Start-Process -FilePath "pnpm.cmd" -ArgumentList $webArgs -WorkingDirectory $WebDir -NoNewWindow -PassThru

Write-Host ""
Write-Host "Ishi is starting:  http://localhost:$WebPort   (API health: http://localhost:$WebPort/api/health)"
Write-Host "Press Ctrl+C to stop."
try {
    while (-not $api.HasExited -and -not $web.HasExited) { Start-Sleep -Milliseconds 500 }
    if ($api.HasExited) { Write-Warning "API exited (code $($api.ExitCode))" }
    if ($web.HasExited) { Write-Warning "Web exited (code $($web.ExitCode))" }
} finally {
    foreach ($p in @($api, $web)) {
        if (-not $p.HasExited) { & taskkill.exe /PID $p.Id /T /F | Out-Null }
    }
}
