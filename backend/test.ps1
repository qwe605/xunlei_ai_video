$ErrorActionPreference = "Stop"
$backend = Split-Path -Parent $MyInvocation.MyCommand.Path
$previousPythonPath = $env:PYTHONPATH
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }

try {
    $env:PYTHONPATH = $backend
    & $python -m unittest discover -s (Join-Path $backend "tests") -v
}
finally {
    $env:PYTHONPATH = $previousPythonPath
}
