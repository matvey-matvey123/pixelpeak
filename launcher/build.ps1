# Сборка PixelPeak Launcher в один .exe
# Запуск:  powershell -ExecutionPolicy Bypass -File build.ps1

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

Write-Host "[1/3] Установка зависимостей..." -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

Write-Host "[2/3] Генерация иконки..." -ForegroundColor Cyan
python tools\make_icon.py

Write-Host "[3/3] Сборка .exe..." -ForegroundColor Cyan
python -m PyInstaller `
  --noconfirm `
  --clean `
  --noconsole `
  --onefile `
  --name "PixelPeak" `
  --icon "assets\icon.ico" `
  --add-data "assets;assets" `
  --collect-all "minecraft_launcher_lib" `
  --hidden-import "PySide6.QtSvg" `
  main.py

Write-Host ""
Write-Host "Готово! Файл: dist\PixelPeak.exe" -ForegroundColor Green
