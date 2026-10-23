#!/bin/bash
# Builds "Shorts Factory.app" (macOS) into dist/. Run from the project folder with the venv active or via .venv/bin.
set -e
cd "$(dirname "$0")"
PY=.venv/bin/python
$PY -m PyInstaller --noconfirm --clean --windowed --name "Shorts Factory" --icon desktop-icon.icns \
  --osx-bundle-identifier com.vaibhavbansal.shortsfactory \
  --add-data "ui.html:." --add-data "config.yaml:." --add-data "examples:examples" --add-data "series:series" \
  --add-data "assets/logo.png:assets" \
  --collect-all imageio_ffmpeg --collect-all webview --collect-all googleapiclient --collect-all google_auth_oauthlib \
  --collect-submodules edge_tts --collect-submodules anthropic \
  --hidden-import src.series --hidden-import src.remix --hidden-import src.sigma_bgm \
  desktop.py
echo "Built: dist/Shorts Factory.app"
