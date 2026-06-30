# start.ps1 - Launch EI-OS (FastAPI + Next.js) on Windows
Write-Host ""
Write-Host "  [======= Enterprise Intelligence OS =======]" -ForegroundColor Cyan
Write-Host "  [           Powered by Lemma SDK           ]" -ForegroundColor Cyan
Write-Host ""

$root = $PSScriptRoot
if (-not $root) { $root = Get-Location }

# Start FastAPI in background
Write-Host "  Starting API server on :8000..." -ForegroundColor Yellow
$api = Start-Process -NoNewWindow -PassThru -FilePath "python" -ArgumentList "-m", "uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000" -WorkingDirectory $root

Start-Sleep -Seconds 3

# Start Next.js in background
Write-Host "  Starting dashboard on :3000..." -ForegroundColor Yellow
$dashboard = Start-Process -NoNewWindow -PassThru -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev" -WorkingDirectory "$root\dashboard"

# Start file watcher in background
Write-Host "  Starting file watcher on data/..." -ForegroundColor Yellow
$watcher = Start-Process -NoNewWindow -PassThru -FilePath "python" -ArgumentList "-u", "-m", "ingestion.watcher" -WorkingDirectory $root

Write-Host ""
Write-Host "  Dashboard -> http://localhost:3000" -ForegroundColor Green
Write-Host "  API       -> http://localhost:8000/docs" -ForegroundColor Green
Write-Host "  Lemma UI  -> http://localhost:3711" -ForegroundColor Green
Write-Host ""
Write-Host "  Press Ctrl+C to stop all services" -ForegroundColor DarkGray
Write-Host ""

# Wait and cleanup on exit
try {
    $api.WaitForExit()
} finally {
    if ($api -and !$api.HasExited) { $api.Kill() }
    if ($dashboard -and !$dashboard.HasExited) { $dashboard.Kill() }
    if ($watcher -and !$watcher.HasExited) { $watcher.Kill() }
}
