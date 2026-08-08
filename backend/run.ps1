param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$backend = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "本地 AI 环境尚未安装，请先运行 backend\setup.ps1"
}

& $python -m uvicorn app.app:app --host 127.0.0.1 --port $Port --app-dir $backend
