# Локальный запуск бэкенда PixelPeak + сайта
# Запуск: powershell -ExecutionPolicy Bypass -File run_server.ps1

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

python -m pip install -r requirements.txt
if (-not $env:PIXELPEAK_SECRET) { $env:PIXELPEAK_SECRET = "pixelpeak-local-secret" }

Write-Host "API и сайт: http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Регистрация: http://127.0.0.1:8000/register.html" -ForegroundColor Green
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
