# Builds "Shorts Factory" for Windows into dist\Shorts Factory\ (run from the project folder, venv active or PY set).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = if ($env:PY) { $env:PY } else { ".venv\Scripts\python.exe" }

& $py -c "from PIL import Image; Image.open('assets/logo.png').convert('RGBA').save('desktop-icon.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"

$mp = @()
& $py -c "import mediapipe" 2>$null
if ($LASTEXITCODE -eq 0) { $mp = @("--collect-all", "mediapipe", "--add-data", "assets/models;assets/models") }
else { Write-Host "mediapipe not available: building without background replacement" }

& $py -c "import faster_whisper" 2>$null
if ($LASTEXITCODE -eq 0) { $mp += @("--collect-all", "faster_whisper", "--collect-all", "ctranslate2", "--hidden-import", "src.asr") }
else { Write-Host "faster-whisper not available: Studio will estimate caption timing" }

$pyiArgs = @(
  "--noconfirm", "--clean", "--windowed", "--name", "Shorts Factory", "--icon", "desktop-icon.ico",
  "--add-data", "ui.html;.", "--add-data", "config.yaml;.", "--add-data", "examples;examples", "--add-data", "series;series",
  "--add-data", "assets/logo.png;assets", "--add-data", "assets/fonts;assets/fonts", "--add-data", "assets/music/main;assets/music/main",
  "--collect-all", "imageio_ffmpeg", "--collect-all", "webview", "--collect-all", "googleapiclient", "--collect-all", "google_auth_oauthlib",
  "--collect-submodules", "edge_tts", "--collect-submodules", "anthropic",
  "--hidden-import", "src.series", "--hidden-import", "src.remix", "--hidden-import", "src.sigma_bgm", "--hidden-import", "src.studio",
  "--hidden-import", "src.enhance", "--hidden-import", "src.edm_bgm", "--hidden-import", "src.misc", "--hidden-import", "src.channels",
  "--hidden-import", "src.prefs", "--hidden-import", "src.memes", "--hidden-import", "src.mage", "--hidden-import", "src.mage_worlds", "--hidden-import", "src.icons"
) + $mp + @("desktop.py")
& $py -m PyInstaller @pyiArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
Write-Host "Built: dist\Shorts Factory\Shorts Factory.exe"
