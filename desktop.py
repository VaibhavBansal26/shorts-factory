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

from src.config import CODE  # noqa: E402  (must come after SF_HOME is set)


def seed():
    """First run: copy the editable defaults (config, logo, series bible) into the data folder."""
    if not (HOME / "config.yaml").exists():
        shutil.copy2(CODE / "config.yaml", HOME / "config.yaml")
    (HOME / "assets").mkdir(exist_ok=True)
    if not (HOME / "assets" / "logo.png").exists() and (CODE / "assets" / "logo.png").exists():
        shutil.copy2(CODE / "assets" / "logo.png", HOME / "assets" / "logo.png")
    (HOME / "series").mkdir(exist_ok=True)
    for f in (CODE / "series").glob("*.json"):
        if not (HOME / "series" / f.name).exists():
            shutil.copy2(f, HOME / "series" / f.name)


class Api:
    def open(self, url: str):
        import webbrowser
        webbrowser.open(url)

    def reveal_data(self):
        import subprocess
        subprocess.run(["open", str(HOME)] if sys.platform == "darwin" else ["xdg-open", str(HOME)])


def main():
    seed()
    import app as portal  # noqa: E402
    from werkzeug.serving import make_server

    threading.Thread(target=portal.scheduler_loop, daemon=True).start()
    server = make_server("127.0.0.1", 0, portal.app, threaded=True)
    port = server.server_port
    (HOME / "port.txt").write_text(str(port))
    threading.Thread(target=server.serve_forever, daemon=True).start()
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
    server.shutdown()


if __name__ == "__main__":
    main()
