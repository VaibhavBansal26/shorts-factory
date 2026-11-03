"""Real word timings for the Studio script, from a small local speech model (faster-whisper).
Nothing leaves the machine. The model (about 140 MB) downloads once into the data folder on first use; if anything fails
the caller falls back to the estimated timing."""
import difflib
import os
import re
import subprocess

from .config import ROOT
from .ff import FFMPEG, duration

_model = None


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def _norm(w: str) -> str:
    return re.sub(r"[^\w]", "", w.lower())


def transcribe(voice, language: str = "en") -> list[tuple[str, float, float]]:
    global _model
    import numpy as np
    from faster_whisper import WhisperModel
    if _model is None:
        name = "base.en" if language == "en" else "base"
        _model = WhisperModel(name, device="cpu", compute_type="int8", download_root=str(ROOT / "models"))
    raw = subprocess.run([FFMPEG, "-loglevel", "error", "-i", str(voice), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    segs, _ = _model.transcribe(audio, word_timestamps=True, language=language if language != "hinglish" else None)
    return [(w.word.strip(), float(w.start), float(w.end)) for s in segs for w in s.words if _norm(w.word)]


def align(beats: list[dict], voice, language: str = "en") -> list[dict]:
    """Timings in the same shape as studio.align, taken from what was actually said. Words the model missed are
    placed between their neighbours."""
    heard = transcribe(voice, language)
    if len(heard) < 5:
        raise RuntimeError("no speech recognised")
    toks = [(bi, w) for bi, b in enumerate(beats) for w in b["say"].split()]
    a, b = [_norm(w) for _, w in toks], [_norm(w) for w, _, _ in heard]
    t0, t1 = [None] * len(toks), [None] * len(toks)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                t0[i1 + k], t1[i1 + k] = heard[j1 + k][1], heard[j1 + k][2]
    known = [i for i, v in enumerate(t0) if v is not None]
    if len(known) < len(toks) * 0.4:
        raise RuntimeError("the recording doesn't match the script closely enough")
    end = duration(voice)
    for i in range(len(toks)):  # fill gaps by spreading evenly between the nearest matched words
        if t0[i] is not None:
            continue
        lo = max((k for k in known if k < i), default=None)
        hi = min((k for k in known if k > i), default=None)
        s = t1[lo] if lo is not None else 0.0
        e = t0[hi] if hi is not None else end
        n = (hi if hi is not None else len(toks)) - (lo + 1 if lo is not None else 0)
        pos = i - (lo + 1 if lo is not None else 0)
        t0[i] = s + (e - s) * pos / max(1, n)
        t1[i] = s + (e - s) * (pos + 1) / max(1, n)
    out, idx = [], 0
    for bi, bt in enumerate(beats):
        n = len(bt["say"].split())
        words = [(toks[idx + k][1], t0[idx + k], max(t1[idx + k], t0[idx + k] + 0.05)) for k in range(n)]
        start = 0.0 if bi == 0 else max(0.0, words[0][1] - 0.15)
        out.append({"start": start, "words": words})
        idx += n
    for k in range(len(out)):
        out[k]["end"] = out[k + 1]["start"] if k + 1 < len(out) else end
    return out
