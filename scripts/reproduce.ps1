# Rebuild every published result from public CDC files (Windows PowerShell).
$ErrorActionPreference = "Stop"
foreach ($step in @("download", "cohort", "bench -B 200", "sensitivity -B 200")) {
    Write-Host "== equicvd $step"
    python -m equicvd.cli @($step -split " ")
    if ($LASTEXITCODE -ne 0) { throw "step '$step' failed" }
}
