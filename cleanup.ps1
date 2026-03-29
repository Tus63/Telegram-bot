# Kill all Python processes and start fresh
Write-Host "[1] Stopping all Python processes..." -ForegroundColor Yellow

# Get all python.exe processes
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue

if ($pythonProcesses) {
    Write-Host "Found $($pythonProcesses.Count) Python process(es):" -ForegroundColor Cyan
    foreach ($proc in $pythonProcesses) {
        Write-Host "  - PID $($proc.Id): $($proc.Name) (started: $($proc.StartTime))" -ForegroundColor Gray
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Write-Host "    [KILLED]" -ForegroundColor Red
    }
} else {
    Write-Host "No Python processes found" -ForegroundColor Green
}

Write-Host ""
Write-Host "[2] Waiting 45 seconds for Telegram to release the connection..." -ForegroundColor Yellow

# Wait with countdown
for ($i = 45; $i -gt 0; $i--) {
    Write-Host "`r[Waiting] $i seconds remaining..." -NoNewline -ForegroundColor Cyan
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "[3] Verifying all Python processes are gone..." -ForegroundColor Yellow
$remaining = Get-Process python -ErrorAction SilentlyContinue
if ($remaining) {
    Write-Host "[ERROR] Python processes still running!" -ForegroundColor Red
    $remaining | ForEach-Object { Write-Host "  - PID $($_.Id): $($_.Name)" }
} else {
    Write-Host "[OK] All Python processes terminated" -ForegroundColor Green
}

Write-Host ""
Write-Host "[4] Ready to start the bot!" -ForegroundColor Green
Write-Host "Run: python main.py" -ForegroundColor Cyan
