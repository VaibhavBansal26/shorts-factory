"""Open a file in the default app, or show it in Finder / Explorer / the file manager."""
import subprocess
import sys
from pathlib import Path


def open_path(path, reveal: bool = False) -> None:
    p = str(path)
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", p] if reveal else ["open", p])
    elif sys.platform == "win32":
        import os
        if reveal:
            subprocess.run(["explorer", "/select,", str(Path(p))])  # explorer returns 1 even on success
        else:
            os.startfile(p)
    else:
        subprocess.run(["xdg-open", str(Path(p).parent if reveal else p)])
