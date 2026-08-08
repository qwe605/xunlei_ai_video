param(
    [string]$VideoPath,
    [string]$PythonPath = "python",
    [string]$TaskId = ("XL-SUBMISSION-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$appDir = Join-Path $root "app"
$outputDir = Join-Path $root "output"
$pdfDir = Join-Path $outputDir "submission"
$stageDir = Join-Path $outputDir "submission-build"
$offlineDir = Join-Path $stageDir "offline"
$finalDir = Join-Path $stageDir "final"
$offlineZip = Join-Path $finalDir "xunlei-ai-video-library-offline.zip"
$finalZip = Join-Path $outputDir "xunlei-ai-video-library-submission.zip"
$launcherCompiler = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

function Assert-LastExitCode {
    param([string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

function Test-LocalPort {
    param([int]$Port)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne(100) -or -not $client.Connected) {
            return $false
        }
        $client.EndConnect($connect)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

if ([string]::IsNullOrWhiteSpace($VideoPath)) {
    throw "VideoPath is required for a complete submission build."
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "verify.ps1") `
    -TaskId $TaskId `
    -SkillsLoaded "documentation-and-adrs,playwright-best-practices,verification-before-completion"
Assert-LastExitCode "Canonical verification"

& $PythonPath (Join-Path $PSScriptRoot "build_submission_pdf.py")
Assert-LastExitCode "PDF generation"

if (-not (Test-Path -LiteralPath $launcherCompiler)) {
    throw "C# compiler not found: $launcherCompiler"
}

# The staging path is verified before recursive cleanup to protect other output artifacts.
$resolvedOutput = [System.IO.Path]::GetFullPath($outputDir).TrimEnd("\") + "\"
$resolvedStage = [System.IO.Path]::GetFullPath($stageDir).TrimEnd("\") + "\"
if (-not $resolvedStage.StartsWith($resolvedOutput, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe staging path: $resolvedStage"
}
if (Test-Path -LiteralPath $stageDir) {
    $stageItem = Get-Item -LiteralPath $stageDir -Force
    if (($stageItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refusing to delete a reparse-point staging directory: $stageDir"
    }
    Remove-Item -LiteralPath $stageDir -Recurse -Force
}
New-Item -ItemType Directory -Path (Join-Path $offlineDir "www") -Force | Out-Null
New-Item -ItemType Directory -Path $finalDir -Force | Out-Null

Copy-Item -Path (Join-Path $appDir "dist\*") -Destination (Join-Path $offlineDir "www") `
    -Recurse -Force
Copy-Item -Path (Join-Path $root "packaging\*.txt") -Destination $offlineDir -Force

$launcherOutput = Join-Path $offlineDir "XunleiAIVideoLibraryDemo.exe"
& $launcherCompiler /nologo /target:exe "/out:$launcherOutput" `
    (Join-Path $root "packaging\DemoLauncher.cs")
Assert-LastExitCode "Offline launcher compilation"

# Only a newly opened port can belong to this launcher; other local tools may use the range.
$occupiedPorts = @(18080..18089 | Where-Object { Test-LocalPort -Port $_ })
$launcherProcess = Start-Process -FilePath $launcherOutput -ArgumentList "--no-open" `
    -WindowStyle Hidden -PassThru
$demoPort = $null
try {
    for ($attempt = 0; $attempt -lt 50 -and -not $demoPort; $attempt++) {
        Start-Sleep -Milliseconds 200
        foreach ($port in 18080..18089) {
            if ($port -notin $occupiedPorts -and (Test-LocalPort -Port $port)) {
                $demoPort = $port
                break
            }
        }
    }
    if (-not $demoPort) {
        throw "Offline launcher did not open a port in 18080-18089."
    }

    $previousBaseUrl = $env:DEMO_BASE_URL
    $env:DEMO_BASE_URL = "http://127.0.0.1:$demoPort"
    try {
        Push-Location $appDir
        & npm.cmd run test:e2e:core
        Assert-LastExitCode "Offline package E2E"
    }
    finally {
        Pop-Location
        $env:DEMO_BASE_URL = $previousBaseUrl
    }
}
finally {
    if ($launcherProcess -and -not $launcherProcess.HasExited) {
        Stop-Process -Id $launcherProcess.Id -Force
        $launcherProcess.WaitForExit()
    }
}

Compress-Archive -Path (Join-Path $offlineDir "*") -DestinationPath $offlineZip -Force

$pdfFiles = @(Get-ChildItem -LiteralPath $pdfDir -Filter "*.pdf" -File)
$flowFiles = @(Get-ChildItem -LiteralPath $pdfDir -Filter "*.png" -File)
if ($pdfFiles.Count -ne 1 -or $flowFiles.Count -ne 1) {
    throw "Expected exactly one PDF and one flow image in $pdfDir"
}
Copy-Item -LiteralPath $pdfFiles[0].FullName `
    -Destination (Join-Path $finalDir "product-specification.pdf")
Copy-Item -LiteralPath $flowFiles[0].FullName `
    -Destination (Join-Path $finalDir "product-flow.png")
$noteIndex = 0
Get-ChildItem -Path (Join-Path $root "packaging\*.txt") -File |
    Sort-Object -Property Name |
    ForEach-Object {
        $noteIndex++
        Copy-Item -LiteralPath $_.FullName `
            -Destination (Join-Path $finalDir "packaging-note-$noteIndex.txt")
    }

$resolvedVideo = (Resolve-Path -LiteralPath $VideoPath).Path
Copy-Item -LiteralPath $resolvedVideo -Destination (Join-Path $finalDir "demo-video.mp4")

$hashLines = Get-ChildItem -LiteralPath $finalDir -File |
    Where-Object { $_.Name -ne "SHA256SUMS.txt" } |
    Sort-Object -Property Name |
    ForEach-Object {
        $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
        "$($hash.Hash.ToLowerInvariant())  $($_.Name)"
    }
$hashLines | Set-Content -LiteralPath (Join-Path $finalDir "SHA256SUMS.txt") -Encoding ascii

Compress-Archive -Path (Join-Path $finalDir "*") -DestinationPath $finalZip -Force
Write-Host "Submission build complete: $finalZip" -ForegroundColor Green
