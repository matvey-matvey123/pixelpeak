# Быстрый запуск лаунчера из исходников (Windows)
# Запуск:  powershell -ExecutionPolicy Bypass -File run.ps1

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

python -m pip install -r requirements.txt
python main.py
