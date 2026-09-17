$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Test-Path '.venv')) {
    python -m venv .venv
}

if (Test-Path '.venv\Scripts\python.exe') {
    & '.venv\Scripts\python.exe' -m pip install --upgrade pip
    & '.venv\Scripts\python.exe' -m pip install -r requirements.txt
    & '.venv\Scripts\python.exe' main.py
} else {
    python -m pip install -r requirements.txt
    python main.py
}
