Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$harnessDir = Join-Path $root "harness"

function Read-JsonFile {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing Harness file: $Path"
    }
    return Get-Content -LiteralPath $Path -Raw -Encoding utf8 | ConvertFrom-Json
}

$config = Read-JsonFile (Join-Path $harnessDir "config.json")
$baseline = Read-JsonFile (Join-Path $harnessDir "baseline.json")
$train = Read-JsonFile (Join-Path $harnessDir "evals\train.json")
$holdout = Read-JsonFile (Join-Path $harnessDir "evals\holdout.json")

if ($config.schema_version -ne 1) {
    throw "Unsupported Harness schema_version: $($config.schema_version)"
}
if ($baseline.schema_version -ne 1) {
    throw "Unsupported baseline schema_version: $($baseline.schema_version)"
}

$allCases = @($train) + @($holdout)
$duplicateIds = $allCases |
    Group-Object -Property id |
    Where-Object { $_.Count -gt 1 } |
    Select-Object -ExpandProperty Name
if ($duplicateIds) {
    throw "Duplicate evaluation IDs: $($duplicateIds -join ', ')"
}

foreach ($case in $allCases) {
    foreach ($field in @("id", "split", "title", "task", "risk", "automated_checks", "human_checks")) {
        if ($null -eq $case.$field -or [string]::IsNullOrWhiteSpace([string]$case.$field)) {
            throw "Evaluation $($case.id) is missing field: $field"
        }
    }
    if (@($case.automated_checks).Count -eq 0 -or @($case.human_checks).Count -eq 0) {
        throw "Evaluation $($case.id) needs automated and human checks."
    }
}

if (@($train | Where-Object { $_.split -ne "train" }).Count -gt 0) {
    throw "train.json contains a non-train case."
}
if (@($holdout | Where-Object { $_.split -ne "holdout" }).Count -gt 0) {
    throw "holdout.json contains a non-holdout case."
}

# Read the frontmatter name because a skill folder can have a different name.
$declaredSkills = Get-ChildItem -LiteralPath (Join-Path $root ".agents\skills") -Directory |
    ForEach-Object {
        $skillPath = Join-Path $_.FullName "SKILL.md"
        if (Test-Path -LiteralPath $skillPath) {
            $head = Get-Content -LiteralPath $skillPath -Encoding utf8 -TotalCount 12
            $nameLine = $head | Where-Object { $_ -match "^name:\s*(.+)$" } | Select-Object -First 1
            if ($nameLine -and $nameLine -match "^name:\s*(.+)$") {
                $Matches[1].Trim()
            }
        }
    }

$missingSkills = @($config.required_skills | Where-Object { $_ -notin $declaredSkills })
if ($missingSkills.Count -gt 0) {
    throw "Harness references missing skills: $($missingSkills -join ', ')"
}

Write-Host "Harness passed: $($train.Count) train, $($holdout.Count) holdout, $($config.required_skills.Count) skills." -ForegroundColor Green
