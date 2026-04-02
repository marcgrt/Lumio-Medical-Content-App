#!/usr/bin/env bash
# Render all Remotion compositions to MP4 files in static/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WEB_DIR="$PROJECT_DIR/lumio-web"
OUT_DIR="$PROJECT_DIR/static"

echo "=== Remotion Render Pipeline ==="
echo "Output: $OUT_DIR"
echo ""

cd "$WEB_DIR"

# SplashScreen (highest priority)
echo "1/3 Rendering SplashScreen..."
npx remotion render src/remotion/index.ts SplashScreen "$OUT_DIR/splash-remotion.mp4" \
  --codec h264 --image-format jpeg --quality 90 2>&1 | tail -3

# WeeklyDigestOpener
echo "2/3 Rendering WeeklyDigestOpener..."
npx remotion render src/remotion/index.ts WeeklyDigestOpener "$OUT_DIR/weekly-digest-opener.mp4" \
  --codec h264 --image-format jpeg --quality 90 2>&1 | tail -3

# ScoreRingReveal (small, fast)
echo "3/3 Rendering ScoreRingReveal..."
npx remotion render src/remotion/index.ts ScoreRingReveal "$OUT_DIR/score-ring-reveal.mp4" \
  --codec h264 --image-format jpeg --quality 90 2>&1 | tail -3

echo ""
echo "=== Done ==="
ls -lh "$OUT_DIR"/splash-remotion.mp4 "$OUT_DIR"/weekly-digest-opener.mp4 "$OUT_DIR"/score-ring-reveal.mp4 2>/dev/null
