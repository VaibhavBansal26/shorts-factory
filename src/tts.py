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


async def _synth(text: str, voice: str, rate: str, pitch: str = "+0Hz", tries: int = 4):
    for attempt in range(tries):
        try:
            audio, words = await _synth_once(text, voice, rate, pitch)
            if audio:
                return audio, words
        except edge_tts.exceptions.NoAudioReceived:
            pass
        await asyncio.sleep(1.5 * (attempt + 1))  # the free endpoint occasionally drops a request
    raise RuntimeError(f"TTS failed after {tries} attempts: {text[:50]!r}")


async def _synth_once(text: str, voice: str, rate: str, pitch: str = "+0Hz"):
    com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
    audio, words = bytearray(), []
    async for ch in com.stream():
        if ch["type"] == "audio":
            audio += ch["data"]
        elif ch["type"] == "WordBoundary":
            words.append((ch["text"], ch["offset"] / 1e7, ch["duration"] / 1e7))
    return bytes(audio), words


def voice_for(script: dict, cfg: dict, scene: dict, rate_override: str | None):
    """Pick (voice, rate, pitch) for a scene: character voices for dialogue, sigma voice for sigma reels."""
    base = cfg["voice"]
    spec = {"name": base["name"], "rate": base.get("rate", "+0%"), "pitch": "+0Hz"}
    speaker = scene.get("speaker")
    chars = {c["id"]: c for c in script.get("characters", [])}
    if speaker in chars:
        prefix = "ko" if script.get("language") == "ko" else "dub"
        key = f"{prefix}_{'female' if chars[speaker].get('gender') == 'female' else 'male'}"
        spec.update(cfg["voices"][key])
        spec.update({k: chars[speaker][k] for k in ("voice", "pitch", "rate") if chars[speaker].get(k)})
    elif scene.get("voice") in ("male", "female"):  # clip_dub scenes: a generic dub voice, no real actor
        spec.update(cfg["voices"][f"dub_{scene['voice']}"])
    elif script.get("format") == "sigma_reel":
        spec.update(cfg["voices"]["sigma"])
    if rate_override:
        spec["rate"] = rate_override
    return spec.get("voice") or spec["name"], spec["rate"], spec.get("pitch", "+0Hz")


def _even_words(text: str, dur: float):
    toks = text.split()
    step = dur / max(1, len(toks))
    return [(t, i * step, step) for i, t in enumerate(toks)]


def synthesize(script: dict, cfg: dict, workdir: Path, rate: str | None = None) -> dict:
    """Writes voice.wav and returns {'audio': Path, 'scenes': [{start,end,words:[(w,t0,t1)]}], 'total': s}."""
    wavs, scenes, cursor = [], [], 0.0
    for i, sc in enumerate(script["scenes"]):
        mp3, wav = workdir / f"scene{i}.mp3", workdir / f"scene{i}.wav"
        name, srate, pitch = voice_for(script, cfg, sc, rate)
        audio, words = asyncio.run(_synth(sc["narration"], name, srate, pitch))
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
