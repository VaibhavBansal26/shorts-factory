#!/usr/bin/env python3
"""Shorts Factory desktop app: the portal in a native window. All your data lives outside the app, in
~/Library/Application Support/Shorts Factory (macOS), so updating or deleting the app never touches your videos."""
import os
import shutil
import sys
import threading
from pathlib import Path


def data_home() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Shorts Factory"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home())) / "Shorts Factory"
    return Path.home() / ".local" / "share" / "shorts-factory"


HOME = data_home()
HOME.mkdir(parents=True, exist_ok=True)
os.environ["SF_HOME"] = str(HOME)
os.environ["SF_DESKTOP"] = "1"
if getattr(sys, "frozen", False):
    os.environ["SF_BUNDLED"] = "1"  # use the ffmpeg shipped inside the app
    log = open(HOME / "app.log", "a", buffering=1)  # a windowed app has no console
    sys.stdout = sys.stderr = log

if sys.platform == "win32":  # a windowed app: stop ffmpeg and friends from flashing console windows
    import subprocess
    _popen = subprocess.Popen

    class _QuietPopen(_popen):
        def __init__(self, *a, **kw):
            kw["creationflags"] = kw.get("creationflags", 0) | 0x08000000  # CREATE_NO_WINDOW
            super().__init__(*a, **kw)

    subprocess.Popen = _QuietPopen

from src.config import CODE  # noqa: E402  (must come after SF_HOME is set)


def seed():
    """First run: copy the editable defaults (config, logo, series bible) into the data folder."""
    if not (HOME / "config.yaml").exists():
        shutil.copy2(CODE / "config.yaml", HOME / "config.yaml")
    else:  # existing install: pull in new voice defaults when the bundled config is newer
        import yaml
        mine, new = yaml.safe_load((HOME / "config.yaml").read_text()), yaml.safe_load((CODE / "config.yaml").read_text())
        if (mine.get("config_version") or 1) < new.get("config_version", 1):
            shutil.copy2(HOME / "config.yaml", HOME / "config.yaml.bak")
            for k in ("voice", "voices", "elevenlabs", "accents", "eleven_accents"):
                mine[k] = new[k]
            mine["config_version"] = new["config_version"]
            (HOME / "config.yaml").write_text(yaml.safe_dump(mine, sort_keys=False, allow_unicode=True))
    (HOME / "assets").mkdir(exist_ok=True)
    bundled = CODE / "assets" / "music" / "main"
    if bundled.exists():  # the channel's default EDM bed, copied once
        dest = HOME / "assets" / "music" / "main"
        dest.mkdir(parents=True, exist_ok=True)
        for f in bundled.glob("*.mp3"):
            if not (dest / f.name).exists():
                shutil.copy2(f, dest / f.name)
    if not (HOME / "assets" / "logo.png").exists() and (CODE / "assets" / "logo.png").exists():
        shutil.copy2(CODE / "assets" / "logo.png", HOME / "assets" / "logo.png")
    (HOME / "assets" / "memes").mkdir(parents=True, exist_ok=True)  # your own meme pack (images) goes here
    (HOME / "series").mkdir(exist_ok=True)
    for f in (CODE / "series").glob("*.json"):
        if not (HOME / "series" / f.name).exists():
            shutil.copy2(f, HOME / "series" / f.name)


class Api:
    def open(self, url: str):
        import webbrowser
        webbrowser.open(url)

    def reveal_data(self):
        from src.osopen import open_path
        open_path(HOME)


def main():
    seed()
    import app as portal  # noqa: E402
    from waitress import create_server  # HTTP/1.1 keep-alive: macOS's video player needs it (Werkzeug sends Connection: close)

    threading.Thread(target=portal.scheduler_loop, daemon=True).start()
    server = create_server(portal.app, host="127.0.0.1", port=0, threads=8)
    port = server.effective_port
    (HOME / "port.txt").write_text(str(port))
    threading.Thread(target=server.run, daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    try:
        import webview
        webview.create_window("Shorts Factory", url, width=1360, height=880, min_size=(980, 640), js_api=Api())
        webview.start()
    except Exception as e:  # no native web view available: fall back to the default browser
        print("native window unavailable, opening browser:", e)
        import webbrowser
        webbrowser.open(url)
        threading.Event().wait()
    server.close()


if __name__ == "__main__":
    main()
