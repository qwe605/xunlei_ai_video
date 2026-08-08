$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$backendPython = Join-Path $backend ".venv\Scripts\python.exe"
$app = Join-Path $root "app"

function Test-LocalPort {
    param([int]$Port)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $result = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $result.AsyncWaitHandle.WaitOne(150) -or -not $client.Connected) {
            return $false
        }
        $client.EndConnect($result)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

if (-not (Test-Path -LiteralPath $backendPython)) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $backend "setup.ps1")
}

$startedBackend = $null
if (-not (Test-LocalPort -Port 8000)) {
    $startedBackend = Start-Process -FilePath $backendPython `
        -ArgumentList "-m", "uvicorn", "app.app:app", "--host", "127.0.0.1", "--port", "8000", "--app-dir", $backend `
        -WindowStyle Hidden -PassThru
}

try {
    Push-Location $app
    npm.cmd run dev -- --host 127.0.0.1
}
finally {
    Pop-Location
    if ($startedBackend -and -not $startedBackend.HasExited) {
        Stop-Process -Id $startedBackend.Id -Force
    }
}
