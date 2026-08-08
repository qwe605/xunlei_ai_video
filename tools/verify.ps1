param(
    [string]$TaskId = ("XL-" + (Get-Date -Format "yyyyMMdd-HHmmss")),
    [string[]]$SkillsLoaded = @("verification-before-completion"),
    [switch]$SkipE2E,
    [switch]$SkipAudit
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$appDir = Join-Path $root "app"
$runDir = Join-Path $root "output\harness-runs"
$latestReceiptPath = Join-Path $root "output\run-receipt.json"

if ($TaskId -notmatch "^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$") {
    throw "TaskId must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$"
}

$receiptPath = [System.IO.Path]::GetFullPath((Join-Path $runDir "$TaskId.json"))
$safeRunPrefix = [System.IO.Path]::GetFullPath($runDir).TrimEnd("\") + "\"
if (-not $receiptPath.StartsWith($safeRunPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe receipt path: $receiptPath"
}

$startedAt = Get-Date
$steps = [System.Collections.Generic.List[object]]::new()
$overallStatus = "running"
$failureMessage = $null
$normalizedSkills = @(
    $SkillsLoaded |
        ForEach-Object { $_ -split "," } |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ } |
        Select-Object -Unique
)

New-Item -ItemType Directory -Path $runDir -Force | Out-Null

function Add-SkippedStep {
    param([string]$Name)

    $steps.Add([pscustomobject]@{
        name = $Name
        command = $null
        status = "skipped"
        exit_code = $null
        duration_ms = 0
    })
}

function Invoke-VerificationStep {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$FilePath,
        [string[]]$Arguments
    )

    $stepStart = Get-Date
    $exitCode = -1
    $invocationError = $null
    Write-Host "`n==> $Name" -ForegroundColor Cyan
    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    }
    catch {
        $invocationError = $_.Exception.Message
    }
    finally {
        Pop-Location
    }

    $steps.Add([pscustomobject]@{
        name = $Name
        command = "$FilePath $($Arguments -join ' ')"
        status = if ($exitCode -eq 0 -and -not $invocationError) { "passed" } else { "failed" }
        exit_code = $exitCode
        duration_ms = [math]::Round(((Get-Date) - $stepStart).TotalMilliseconds)
    })

    if ($invocationError) {
        throw "Verification step failed: $Name ($invocationError)"
    }
    if ($exitCode -ne 0) {
        throw "Verification step failed: $Name (exit code $exitCode)"
    }
}

function Get-OptionalCommandVersion {
    param(
        [string]$Command,
        [string[]]$Arguments
    )

    try {
        $resolved = Get-Command $Command -ErrorAction SilentlyContinue
        if (-not $resolved) {
            return $null
        }
        $previousErrorAction = $ErrorActionPreference
        $ErrorActionPreference = "SilentlyContinue"
        $value = & $resolved.Source @Arguments 2>$null | Select-Object -First 1
        $ErrorActionPreference = $previousErrorAction
        return [string]$value
    }
    catch {
        return $null
    }
}

function Get-SourceState {
    $emptyState = [ordered]@{
        git_revision = $null
        git_dirty = $null
        source_fingerprint = $null
        source_file_count = 0
    }
    $git = Get-Command "git" -ErrorAction SilentlyContinue
    if (-not $git -or -not (Test-Path -LiteralPath (Join-Path $root ".git"))) {
        return $emptyState
    }

    Push-Location $root
    try {
        $previousErrorAction = $ErrorActionPreference
        $ErrorActionPreference = "SilentlyContinue"
        $revision = & $git.Source rev-parse --verify HEAD 2>$null
        if ($LASTEXITCODE -ne 0) {
            $revision = $null
        }
        $statusLines = @(& $git.Source status --porcelain=v1 2>$null)
        $ErrorActionPreference = $previousErrorAction

        # Use filesystem paths instead of git's quoted path output, which is not
        # decoded reliably by Windows PowerShell 5.1 for non-ASCII filenames.
        $sourceInputs = @(
            Get-ChildItem -LiteralPath $root -File -Force
            Get-ChildItem -LiteralPath (Join-Path $root ".agents") -File -Recurse -Force
            Get-ChildItem -LiteralPath (Join-Path $root ".github") -File -Recurse -Force
            Get-ChildItem -LiteralPath (Join-Path $root "app") -File -Force
            Get-ChildItem -LiteralPath (Join-Path $root "app\e2e") -File -Recurse -Force
            Get-ChildItem -LiteralPath (Join-Path $root "app\public") -File -Recurse -Force
            Get-ChildItem -LiteralPath (Join-Path $root "app\scripts") -File -Recurse -Force
            Get-ChildItem -LiteralPath (Join-Path $root "app\src") -File -Recurse -Force
            Get-ChildItem -LiteralPath (Join-Path $root "docs") -File -Recurse -Force
            Get-ChildItem -LiteralPath (Join-Path $root "harness") -File -Recurse -Force
            Get-ChildItem -LiteralPath (Join-Path $root "packaging") -File -Recurse -Force
            Get-ChildItem -LiteralPath (Join-Path $root "tools") -File -Recurse -Force
            (Get-Item -LiteralPath (Join-Path $root "references\README.md"))
        ) | Sort-Object -Property FullName -Unique

        $records = foreach ($sourceFile in $sourceInputs) {
            if ($sourceFile -and (Test-Path -LiteralPath $sourceFile.FullName -PathType Leaf)) {
                $relativePath = $sourceFile.FullName.Substring($root.Length).TrimStart("\").Replace("\", "/")
                $fileHash = Get-FileHash -LiteralPath $sourceFile.FullName -Algorithm SHA256
                "$relativePath|$($fileHash.Hash.ToLowerInvariant())"
            }
        }
        $aggregate = [string]::Join("`n", @($records))
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        try {
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($aggregate)
            $fingerprint = [System.BitConverter]::ToString($sha256.ComputeHash($bytes)).Replace("-", "").ToLowerInvariant()
        }
        finally {
            $sha256.Dispose()
        }

        return [ordered]@{
            git_revision = if ($revision) { [string]$revision } else { $null }
            git_dirty = ($statusLines.Count -gt 0)
            source_fingerprint = $fingerprint
            source_file_count = @($records).Count
        }
    }
    catch {
        return $emptyState
    }
    finally {
        Pop-Location
    }
}

try {
    Invoke-VerificationStep -Name "Environment preflight" -WorkingDirectory $root `
        -FilePath "powershell.exe" `
        -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $PSScriptRoot "preflight.ps1"))
    Invoke-VerificationStep -Name "Harness structure" -WorkingDirectory $root `
        -FilePath "powershell.exe" `
        -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $PSScriptRoot "check_harness.ps1"))
    Invoke-VerificationStep -Name "Backend unit tests" -WorkingDirectory $root `
        -FilePath "powershell.exe" `
        -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $root "backend\test.ps1"))
    Invoke-VerificationStep -Name "Frontend lint" -WorkingDirectory $appDir `
        -FilePath "npm.cmd" -Arguments @("run", "lint")
    Invoke-VerificationStep -Name "Unit tests" -WorkingDirectory $appDir `
        -FilePath "npm.cmd" -Arguments @("run", "test")
    Invoke-VerificationStep -Name "Production build" -WorkingDirectory $appDir `
        -FilePath "npm.cmd" -Arguments @("run", "build")

    if ($SkipAudit) {
        Add-SkippedStep -Name "Dependency audit"
    }
    else {
        Invoke-VerificationStep -Name "Dependency audit" -WorkingDirectory $appDir `
            -FilePath "npm.cmd" -Arguments @("audit", "--audit-level=high")
    }
    if ($SkipE2E) {
        Add-SkippedStep -Name "Desktop and mobile E2E"
    }
    else {
        Invoke-VerificationStep -Name "Desktop and mobile E2E" -WorkingDirectory $appDir `
            -FilePath "npm.cmd" -Arguments @("run", "test:e2e")
    }

    $overallStatus = if ($SkipAudit -or $SkipE2E) { "partial" } else { "passed" }
}
catch {
    $overallStatus = "failed"
    $failureMessage = $_.Exception.Message
    Write-Error $failureMessage
}
finally {
    $endedAt = Get-Date
    $sourceState = Get-SourceState
    $receipt = [ordered]@{
        schema_version = 1
        task_id = $TaskId
        status = $overallStatus
        started_at = $startedAt.ToUniversalTime().ToString("o")
        ended_at = $endedAt.ToUniversalTime().ToString("o")
        duration_ms = [math]::Round(($endedAt - $startedAt).TotalMilliseconds)
        git_revision = $sourceState.git_revision
        git_dirty = $sourceState.git_dirty
        source_fingerprint = $sourceState.source_fingerprint
        source_file_count = $sourceState.source_file_count
        environment = [ordered]@{
            os = [System.Environment]::OSVersion.VersionString
            powershell = $PSVersionTable.PSVersion.ToString()
            node = Get-OptionalCommandVersion -Command "node" -Arguments @("--version")
            npm = Get-OptionalCommandVersion -Command "npm.cmd" -Arguments @("--version")
        }
        skills_loaded = @($normalizedSkills)
        steps = @($steps)
        failure = $failureMessage
    }

    $receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $receiptPath -Encoding utf8
    Copy-Item -LiteralPath $receiptPath -Destination $latestReceiptPath -Force
    Write-Host "`nRun receipt: $receiptPath"
}

if ($overallStatus -eq "failed") {
    exit 1
}
if ($overallStatus -eq "partial") {
    Write-Warning "Verification completed with skipped gates."
    exit 2
}

Write-Host "All verification steps passed." -ForegroundColor Green
