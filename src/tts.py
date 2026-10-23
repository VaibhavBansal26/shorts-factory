"""Voiceover: one TTS pass per scene, with word-level timings for animated captions."""
import asyncio
import subprocess
from pathlib import Path

import edge_tts

SCENE_PAD = 0.22  # seconds of breathing room after each scene


def _probe(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out.strip())


async def _synth(text: str, voice: str, rate: str):
    com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    audio, words = bytearray(), []
    async for ch in com.stream():
        if ch["type"] == "audio":
            audio += ch["data"]
        elif ch["type"] == "WordBoundary":
            words.append((ch["text"], ch["offset"] / 1e7, ch["duration"] / 1e7))
    return bytes(audio), words


def _even_words(text: str, dur: float):
    toks = text.split()
    step = dur / max(1, len(toks))
    return [(t, i * step, step) for i, t in enumerate(toks)]


def synthesize(script: dict, cfg: dict, workdir: Path, rate: str | None = None) -> dict:
    """Writes voice.wav and returns {'audio': Path, 'scenes': [{start,end,words:[(w,t0,t1)]}], 'total': s}."""
    v = cfg["voice"]
    rate = rate or v.get("rate", "+0%")
    wavs, scenes, cursor = [], [], 0.0
    for i, sc in enumerate(script["scenes"]):
        mp3, wav = workdir / f"scene{i}.mp3", workdir / f"scene{i}.wav"
        audio, words = asyncio.run(_synth(sc["narration"], v["name"], rate))
        if not audio:
            raise RuntimeError(f"TTS returned no audio for scene {i}")
        mp3.write_bytes(audio)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-af", f"apad=pad_dur={SCENE_PAD}",
             "-ar", "44100", "-ac", "1", str(wav)], check=True)
        dur = _probe(wav)
        if not words:
            words = _even_words(sc["narration"], dur - SCENE_PAD)
        else:
            # the TTS strips punctuation; restore it so captions can break on sentences
            orig = sc["narration"].split()
            if len(orig) == len(words):
                words = [(o, t, d) for o, (_, t, d) in zip(orig, words)]
        scenes.append({
            "start": cursor, "end": cursor + dur,
            "words": [(w, cursor + t, cursor + t + d) for w, t, d in words],
        })
        wavs.append(wav)
        cursor += dur

    listing = workdir / "concat.txt"
    listing.write_text("".join(f"file '{w.name}'\n" for w in wavs))
    voice = workdir / "voice.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c", "copy", str(voice)], check=True)
    for w in wavs:
        w.unlink()
        w.with_suffix(".mp3").unlink(missing_ok=True)
    listing.unlink()
    return {"audio": voice, "scenes": scenes, "total": cursor}
