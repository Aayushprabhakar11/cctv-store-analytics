# Process CCTV clips and ingest into Store Intelligence API
param(
    [string]$ClipsDir = ".\clips",
    [string]$ApiUrl = "http://localhost:8000",
    [switch]$Synthetic
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if ($Synthetic) {
    python -m pipeline.detect --synthetic --feed
} else {
    $env:CLIPS_DIR = $ClipsDir
    $env:API_URL = $ApiUrl
    python -m pipeline.detect --clips-dir $ClipsDir --feed
}

Write-Host "Done. Metrics: $ApiUrl/stores/STORE_BLR_002/metrics"
