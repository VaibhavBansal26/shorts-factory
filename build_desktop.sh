#!/bin/bash
# Builds "Shorts Factory.app" (macOS) into dist/. Run from the project folder with the venv active or via .venv/bin.
set -e
cd "$(dirname "$0")"
PY=${PY:-.venv/bin/python}
MP=""
if $PY -c "import mediapipe" 2>/dev/null; then MP="--collect-all mediapipe --add-data assets/models:assets/models"; else echo "mediapipe not available: building without background replacement"; fi
if $PY -c "import faster_whisper" 2>/dev/null; then MP="$MP --collect-all faster_whisper --collect-all ctranslate2 --hidden-import src.asr"; else echo "faster-whisper not available: Studio will estimate caption timing"; fi
$PY -m PyInstaller --noconfirm --clean --windowed --name "Shorts Factory" --icon desktop-icon.icns \
  --osx-bundle-identifier com.vaibhavbansal.shortsfactory \
  --add-data "ui.html:." --add-data "config.yaml:." --add-data "examples:examples" --add-data "series:series" \
  --add-data "assets/logo.png:assets" --add-data "assets/fonts:assets/fonts" --add-data "assets/music/main:assets/music/main" \
  --collect-all imageio_ffmpeg  --collect-all webview --collect-all googleapiclient --collect-all google_auth_oauthlib \
  --collect-submodules edge_tts --collect-submodules anthropic \
  --hidden-import src.series --hidden-import src.remix --hidden-import src.sigma_bgm --hidden-import src.studio --hidden-import src.enhance --hidden-import src.edm_bgm --hidden-import src.misc --hidden-import src.channels --hidden-import src.prefs --hidden-import src.memes \
  $MP desktop.py
echo "Built: dist/Shorts Factory.app"
