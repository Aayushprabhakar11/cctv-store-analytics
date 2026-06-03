# Process CCTV clips and ingest into Store Intelligence API
# Default mode is evaluation-safe: isolated DB per run.
param(
    [string]$ClipsDir = ".\clips",
    [string]$ApiUrl = "http://127.0.0.1:8004",
    [string]$DbUrl = "sqlite+aiosqlite:///./data/store_intel_eval.db",
    [switch]$Synthetic,
    [switch]$NoResetDb
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:STORE_INTEL_DATABASE_URL = $DbUrl

if ($Synthetic) {
    python -m pipeline.detect --synthetic --output data/generated_events.jsonl
} else {
    $env:CLIPS_DIR = $ClipsDir
    python -m pipeline.detect --clips-dir $ClipsDir --output data/generated_events.jsonl
}

if ($NoResetDb) {
    python scripts/ingest_local.py
} else {
    python scripts/ingest_local.py --reset-db
}

Write-Host ""
Write-Host "Events generated + ingested into DB: $DbUrl"
Write-Host "Start API:"
Write-Host "  `$env:STORE_INTEL_DATABASE_URL='$DbUrl'; python -m uvicorn app.main:app --host 127.0.0.1 --port 8004"
Write-Host "Dashboard:"
Write-Host "  $ApiUrl/"
Write-Host "Metrics:"
Write-Host "  $ApiUrl/stores/STORE_BLR_002/metrics"
