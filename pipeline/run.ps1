$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$ClipsDir = if ($env:CLIPS_DIR) { $env:CLIPS_DIR } else { ".\clips" }
$hasVideo = (Test-Path $ClipsDir) -and (Get-ChildItem $ClipsDir -Recurse -Include *.mp4,*.avi,*.mov,*.mkv -ErrorAction SilentlyContinue)
if ($hasVideo) {
  python -m pipeline.detect --clips-dir $ClipsDir --output data/generated_events.jsonl
} else {
  Write-Host "No videos in $ClipsDir — running synthetic until you add CCTV footage (see clips/README.md)"
  python -m pipeline.detect --synthetic --output data/generated_events.jsonl
}
$env:API_URL = if ($env:API_URL) { $env:API_URL } else { "http://localhost:8000" }
python -m pipeline.feed_api
