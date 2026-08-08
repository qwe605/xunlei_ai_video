param(
    [switch]$IncludeSubmission,
    [switch]$IncludeVideoProduction,
    [string]$PythonPath = "python"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$results = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param(
        [string]$Name,
        [bool]$Required,
        [bool]$Passed,
        [string]$Detail
    )

    $results.Add([pscustomobject]@{
        Name = $Name
        Required = $Required
        Status = if ($Passed) { "PASS" } else { "FAIL" }
        Detail = $Detail
    })
}

function Get-CommandVersion {
    param(
        [string]$Command,
        [string[]]$Arguments
    )

    $resolved = Get-Command $Command -ErrorAction SilentlyContinue
    if (-not $resolved) {
        return $null
    }

    # Windows PowerShell can report -1 for successful .cmd/native pipelines.
    # A resolved command with non-empty version output is the stable signal here.
    $value = & $resolved.Source @Arguments 2>$null | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace([string]$value)) {
        return $null
    }
    return [string]$value
}

$nodeVersion = Get-CommandVersion -Command "node" -Arguments @("--version")
$nodeMajor = if ($nodeVersion -match "^v(\d+)") { [int]$Matches[1] } else { 0 }
Add-Check -Name "Node.js" -Required $true -Passed ($nodeMajor -eq 22) `
    -Detail $(if ($nodeVersion) { "$nodeVersion; required: 22.x" } else { "node not found" })

$npmVersion = Get-CommandVersion -Command "npm.cmd" -Arguments @("--version")
$npmMajor = if ($npmVersion -match "^(\d+)") { [int]$Matches[1] } else { 0 }
Add-Check -Name "npm" -Required $true -Passed ($npmMajor -eq 10) `
    -Detail $(if ($npmVersion) { "$npmVersion; required: 10.x" } else { "npm.cmd not found" })

$gitVersion = Get-CommandVersion -Command "git" -Arguments @("--version")
Add-Check -Name "Git" -Required $true -Passed ([bool]$gitVersion) `
    -Detail $(if ($gitVersion) { $gitVersion } else { "git not found" })

$lockPath = Join-Path $root "app\package-lock.json"
Add-Check -Name "Dependency lock" -Required $true -Passed (Test-Path -LiteralPath $lockPath) `
    -Detail $lockPath

$chromeCandidates = @(
    (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"),
    (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
) | Where-Object { $_ }
$chromePath = $chromeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
Add-Check -Name "Google Chrome" -Required $true -Passed ([bool]$chromePath) `
    -Detail $(if ($chromePath) { $chromePath } else { "Chrome required by Playwright channel=chrome" })

if ($IncludeSubmission) {
    $pythonVersion = Get-CommandVersion -Command $PythonPath -Arguments @("--version")
    Add-Check -Name "Python" -Required $true -Passed ([bool]$pythonVersion) `
        -Detail $(if ($pythonVersion) { $pythonVersion } else { "python not found" })

    $pdfPackages = $null
    if ($pythonVersion) {
        $pdfPackages = & $PythonPath -c "import PIL, reportlab; print(PIL.__version__ + '; ' + reportlab.Version)" 2>$null
    }
    Add-Check -Name "PDF Python packages" -Required $true -Passed ([bool]$pdfPackages) `
        -Detail $(if ($pdfPackages) { "Pillow; reportlab: $pdfPackages" } else { "install tools/requirements-submission.txt" })

    $regularFont = "C:\Windows\Fonts\msyh.ttc"
    $boldFont = "C:\Windows\Fonts\msyhbd.ttc"
    Add-Check -Name "Microsoft YaHei fonts" -Required $true `
        -Passed ((Test-Path -LiteralPath $regularFont) -and (Test-Path -LiteralPath $boldFont)) `
        -Detail "$regularFont; $boldFont"

    Add-Check -Name "C# launcher compiler" -Required $true `
        -Passed (Test-Path -LiteralPath "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe") `
        -Detail "Required for the offline launcher"
}

if ($IncludeVideoProduction) {
    $speechAvailable = $true
    try {
        Add-Type -AssemblyName System.Speech
    }
    catch {
        $speechAvailable = $false
    }
    Add-Check -Name "Windows SAPI" -Required $true -Passed $speechAvailable `
        -Detail "System.Speech is required for submission narration"

    $ffmpegVersion = Get-CommandVersion -Command "ffmpeg" -Arguments @("-version")
    Add-Check -Name "FFmpeg" -Required $true -Passed ([bool]$ffmpegVersion) `
        -Detail $(if ($ffmpegVersion) { $ffmpegVersion } else { "ffmpeg not found" })
}

$results | Format-Table -AutoSize
$failedRequired = @($results | Where-Object { $_.Required -and $_.Status -ne "PASS" })
if ($failedRequired.Count -gt 0) {
    Write-Error "Preflight failed: $($failedRequired.Name -join ', ')"
    exit 1
}

Write-Host "Preflight passed." -ForegroundColor Green
