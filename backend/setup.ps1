$ErrorActionPreference = "Stop"
$backend = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $backend ".venv"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    python -m venv $venv
}

& $python -m pip install --disable-pip-version-check -r (Join-Path $backend "requirements.txt")
