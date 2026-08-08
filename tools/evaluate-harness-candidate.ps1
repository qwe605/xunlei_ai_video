param(
    [Parameter(Mandatory = $true)]
    [string]$CandidatePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$baselinePath = Join-Path $root "harness\baseline.json"
$configPath = Join-Path $root "harness\config.json"

$baseline = Get-Content -LiteralPath $baselinePath -Raw -Encoding utf8 | ConvertFrom-Json
$config = Get-Content -LiteralPath $configPath -Raw -Encoding utf8 | ConvertFrom-Json
$candidate = Get-Content -LiteralPath (Resolve-Path -LiteralPath $CandidatePath) `
    -Raw -Encoding utf8 | ConvertFrom-Json

foreach ($field in @("candidate_id", "primary_change", "train_passed", "train_total", "holdout_passed", "holdout_total", "independent_review_passed")) {
    if ($null -eq $candidate.$field) {
        throw "Candidate is missing field: $field"
    }
}

if ($null -eq $baseline.eval_score.train_passed -or $null -eq $baseline.eval_score.holdout_passed) {
    throw "No task-evaluation baseline exists. Run train and holdout evaluations before promotion."
}
if ($candidate.train_total -ne $baseline.eval_score.train_total) {
    throw "Candidate train_total does not match the baseline."
}
if ($candidate.holdout_total -ne $baseline.eval_score.holdout_total) {
    throw "Candidate holdout_total does not match the baseline."
}

$reasons = [System.Collections.Generic.List[string]]::new()
if ($config.promotion_policy.train_must_not_regress -and $candidate.train_passed -lt $baseline.eval_score.train_passed) {
    $reasons.Add("train score regressed")
}
if ($config.promotion_policy.holdout_must_not_regress -and $candidate.holdout_passed -lt $baseline.eval_score.holdout_passed) {
    $reasons.Add("holdout score regressed")
}
$baselineCombined = $baseline.eval_score.train_passed + $baseline.eval_score.holdout_passed
$candidateCombined = $candidate.train_passed + $candidate.holdout_passed
if ($config.promotion_policy.combined_pass_count_must_increase -and $candidateCombined -le $baselineCombined) {
    $reasons.Add("combined pass count did not increase")
}
if ($config.promotion_policy.high_risk_changes_require_independent_review -and -not $candidate.independent_review_passed) {
    $reasons.Add("independent review did not pass")
}

$decision = [ordered]@{
    candidate_id = $candidate.candidate_id
    decision = if ($reasons.Count -eq 0) { "promote" } else { "reject" }
    baseline_combined = $baselineCombined
    candidate_combined = $candidateCombined
    reasons = @($reasons)
}
$decision | ConvertTo-Json -Depth 4

if ($reasons.Count -gt 0) {
    exit 1
}

