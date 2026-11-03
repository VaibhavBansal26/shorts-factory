"""Voiceover: one TTS pass per scene, with word-level timings for animated captions."""
import asyncio
import base64
import json
import os
import subprocess
from pathlib import Path

import edge_tts
import requests

from . import prefs
from .ff import FFMPEG, duration

_eleven_broken: list = []  # set once ElevenLabs fails, so we stop retrying
SCENE_PAD = 0.22  # seconds of breathing room after each scene


def _probe(path: Path) -> float:
    return duration(path)


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


ELEVEN = "https://api.elevenlabs.io/v1"
ELEVEN_MODEL = "eleven_multilingual_v2"


def eleven_key() -> str:
    return os.getenv("ELEVENLABS_API_KEY", "").strip()


def eleven_voice_id(cfg: dict, accent: str, gender: str) -> str:
    """ElevenLabs voice id for an accent + gender: the configured one, else the most-used matching English voice from the
    ElevenLabs voice library (looked up once and cached). Empty string when none exists."""
    from .config import ROOT
    fixed = ((cfg.get("elevenlabs") or {}).get("voices") or {}).get(f"{accent}_{gender}") or \
        (((cfg.get("elevenlabs") or {}).get("voices") or {}).get(gender) if accent == "indian" else "")
    if fixed:
        return fixed
    cache = ROOT / "data" / "eleven_voices.json"
    got = dict(json.loads(cache.read_text())) if cache.exists() else {}
    key = f"{accent}_{gender}"
    if key not in got:
        r = requests.get(f"{ELEVEN}/shared-voices", headers={"xi-api-key": eleven_key()}, timeout=30,
                         params={"page_size": 5, "gender": gender, "language": "en", "sort": "usage_character_count_7d",
                                 "accent": (cfg.get("eleven_accents") or {}).get(accent, accent)})
        r.raise_for_status()
        voices = r.json().get("voices", [])
        got[key] = voices[0]["voice_id"] if voices else ""
        if voices:
            print(f"  ElevenLabs {accent} {gender} voice: {voices[0].get('name')}")
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(json.dumps(got))
    return got[key]


def _synth_eleven(text: str, voice_id: str):
    """Returns (mp3 bytes, [(word, start, duration)]) using ElevenLabs' character timings."""
    r = requests.post(f"{ELEVEN}/text-to-speech/{voice_id}/with-timestamps", timeout=120,
                      params={"output_format": "mp3_44100_128"},
                      headers={"xi-api-key": eleven_key()},
                      json={"text": text, "model_id": ELEVEN_MODEL,
                            "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.25, "speed": 1.05}})
    r.raise_for_status()
    j = r.json()
    al = j["alignment"]
    words, cur, t0, t1 = [], "", 0.0, 0.0
    for ch, a, b in zip(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]):
        if ch.isspace():
            if cur:
                words.append((cur, t0, t1 - t0))
            cur = ""
            continue
        if not cur:
            t0 = a
        cur += ch
        t1 = b
    if cur:
        words.append((cur, t0, t1 - t0))
    return base64.b64decode(j["audio_base64"]), words


HINDI_VOICES = {"male": {"name": "hi-IN-MadhurNeural", "rate": "+4%", "pitch": "+0Hz"},
                "female": {"name": "hi-IN-SwaraNeural", "rate": "+4%", "pitch": "+0Hz"}}


def gender_for(script: dict, scene: dict) -> str:
    chars = {c["id"]: c for c in script.get("characters", [])}
    if scene.get("speaker") in chars:
        return "female" if chars[scene["speaker"]].get("gender") == "female" else "male"
    if scene.get("voice") in ("male", "female"):
        return scene["voice"]
    return prefs.load().get("narrator", "male")


def accent_of(script: dict) -> str:
    return script.get("accent") or prefs.load().get("accent", "indian")


def voice_for(script: dict, cfg: dict, scene: dict, rate_override: str | None):
    """Pick (voice, rate, pitch) for a scene from the chosen accent and the speaker's gender."""
    base = cfg["voice"]
    spec = {"name": base["name"], "rate": base.get("rate", "+0%"), "pitch": "+0Hz"}
    gender = gender_for(script, scene)
    chars = {c["id"]: c for c in script.get("characters", [])}
    if script.get("language") == "hi":  # Hindi script: Microsoft's Hindi neural voices
        spec.update(cfg.get("voices", {}).get(f"hi_{gender}") or HINDI_VOICES[gender])
    elif script.get("language") == "ko":  # scripts that explicitly want Korean speech
        spec.update(cfg["voices"][f"ko_{gender}"])
    else:
        spec.update((cfg.get("accents") or {}).get(accent_of(script), {}).get(gender, {}))
        if script.get("format") == "sigma_reel":  # slower, deeper delivery on top of the chosen accent
            spec.update({"rate": cfg["voices"]["sigma"]["rate"], "pitch": cfg["voices"]["sigma"]["pitch"]})
    speaker = scene.get("speaker")
    if speaker in chars:
        spec.update({k: chars[speaker][k] for k in ("voice", "pitch", "rate") if chars[speaker].get(k)})
    if rate_override:
        spec["rate"] = rate_override
    return spec.get("voice") or spec["name"], spec["rate"], spec.get("pitch", "+0Hz")


def _even_words(text: str, dur: float):
    toks = text.split()
    step = dur / max(1, len(toks))
    return [(t, i * step, step) for i, t in enumerate(toks)]


def synthesize(script: dict, cfg: dict, workdir: Path, rate: str | None = None) -> dict:
    """Writes voice.wav and returns {'audio': Path, 'scenes': [{start,end,words:[(w,t0,t1)]}], 'total': s}."""
    _eleven_broken.clear()
    wavs, scenes, cursor = [], [], 0.0
    for i, sc in enumerate(script["scenes"]):
        mp3, wav = workdir / f"scene{i}.mp3", workdir / f"scene{i}.wav"
        name, srate, pitch = voice_for(script, cfg, sc, rate)
        audio, words = None, []
        if eleven_key() and not _eleven_broken and script.get("language") != "hi":  # the library voices are English-accent
            try:
                vid = eleven_voice_id(cfg, accent_of(script), gender_for(script, sc))
                if vid:
                    audio, words = _synth_eleven(sc["narration"], vid)
            except Exception as e:  # e.g. library voices need a paid plan: fall back to the free Indian voices
                print(f"  ElevenLabs unavailable ({str(e)[:90]}); using free Indian voices")
                _eleven_broken.append(1)
        if not audio:
            audio, words = asyncio.run(_synth(sc["narration"], name, srate, pitch))
        if not audio:
            raise RuntimeError(f"TTS returned no audio for scene {i}")
        mp3.write_bytes(audio)
        pre, lead, ratio = "", 0.0, 1.0
        if sc.get("speech_len"):  # a dub over a talking clip: start with the speaker and finish with them
            raw = _probe(mp3)
            ratio = min(1.4, max(0.8, raw / max(0.5, sc["speech_len"])))
            lead = float(sc.get("speech_lead", 0.0))
            if abs(ratio - 1) > 0.03:
                pre += f"atempo={ratio:.3f},"
            if lead > 0.02:
                pre += f"adelay={int(lead * 1000)}:all=1,"
        subprocess.run(
            [FFMPEG, "-y", "-loglevel", "error", "-i", str(mp3), "-af", pre + f"apad=pad_dur={SCENE_PAD}" + (f",apad=whole_dur={sc['min_duration']}" if sc.get("min_duration") else ""),
             "-ar", "44100", "-ac", "1", str(wav)], check=True)
        dur = _probe(wav)
        if words and (ratio != 1.0 or lead):
            words = [(w, t / ratio + lead, d / ratio) for w, t, d in words]
        if not words:
            words = [(w, t + lead, d) for w, t, d in _even_words(sc["narration"], max(0.5, dur - SCENE_PAD - lead))]
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
        [FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c", "copy", str(voice)], check=True)
    for w in wavs:
        w.unlink()
        w.with_suffix(".mp3").unlink(missing_ok=True)
    listing.unlink()
    return {"audio": voice, "scenes": scenes, "total": cursor}
