"""Locate ffmpeg (system, env override, or the static build shipped with imageio-ffmpeg) and probe durations."""
import os
import re
import shutil
import subprocess


def _find() -> str:
    if os.getenv("FFMPEG_BIN"):
        return os.environ["FFMPEG_BIN"]
    if os.getenv("SF_BUNDLED") != "1" and shutil.which("ffmpeg"):  # dev machines: prefer the system build
        return shutil.which("ffmpeg")
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


FFMPEG = _find()


def duration(path) -> float:
    """Media duration in seconds (parsed from ffmpeg's banner, so no ffprobe is needed)."""
    err = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if not m:
        raise RuntimeError(f"Could not read duration of {path}")
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)
