#!/usr/bin/env sh
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CLIPS_DIR="${CLIPS_DIR:-./clips}"
if [ -d "$CLIPS_DIR" ] && [ "$(ls -A "$CLIPS_DIR" 2>/dev/null)" ]; then
  python -m pipeline.detect --clips-dir "$CLIPS_DIR" --output data/generated_events.jsonl
else
  python -m pipeline.detect --synthetic --output data/generated_events.jsonl
fi
echo "Feeding events to API..."
python -m pipeline.feed_api "${API_URL:-http://localhost:8000}"
