#!/usr/bin/env bash
# lowsticks clipper - one-time setup on Mac / Linux
set -e
cd "$(dirname "$0")"
if ! command -v ffmpeg >/dev/null; then
  if command -v brew >/dev/null; then brew install ffmpeg; else sudo apt-get update && sudo apt-get install -y ffmpeg; fi
fi
python3 -m pip install -r requirements.txt
mkdir -p fonts
curl -fsSL -o fonts/Poppins-ExtraBold.ttf https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-ExtraBold.ttf || echo "font download failed, default font will be used"
echo 'Done. Example: python3 clip.py "https://www.twitch.tv/videos/123456789" --count 3'
