"""Original synthesized 'sigma' background music: dark phonk-style loop (808 bass, cowbell, hats, minor pluck).

Everything is generated from scratch with numpy, so it carries no licence baggage. It is a stand-in for the
trending edits you may know; drop real tracks you hold the rights to into assets/music/sigma/ to use those instead.
"""
import wave
from pathlib import Path

import numpy as np

from .config import resolve

SR = 44100

# (bpm, per-bar 808 roots in Hz, minor-pentatonic pluck scale in Hz, seed)
VARIANTS = {
    "sigma_phonk_140": (140, [55.0, 43.65, 49.0, 41.2], [220.0, 261.6, 293.7, 329.6, 392.0], 7),
    "sigma_drift_132": (132, [41.2, 41.2, 49.0, 36.7], [164.8, 196.0, 220.0, 246.9, 293.7], 21),
    "sigma_grind_150": (150, [49.0, 55.0, 43.65, 49.0], [246.9, 293.7, 329.6, 392.0, 440.0], 33),
}


def _t(n):
    return np.arange(n) / SR


def _kick():
    t = _t(int(0.38 * SR))
    ph = 2 * np.pi * np.cumsum(45 + 95 * np.exp(-t * 30)) / SR
    return np.sin(ph) * np.exp(-t * 9) * 1.1


def _snare(rng):
    t = _t(int(0.3 * SR))
    noise = rng.standard_normal(len(t)) * np.exp(-t * 20)
    return 0.55 * noise + 0.4 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 28)


def _hat(rng, open_=False):
    t = _t(int((0.22 if open_ else 0.06) * SR))
    n = np.diff(rng.standard_normal(len(t) + 1))
    return n * np.exp(-t * (16 if open_ else 70)) * 0.32


def _cowbell(f1, f2):
    t = _t(int(0.25 * SR))
    sq = np.sign(np.sin(2 * np.pi * f1 * t)) + np.sign(np.sin(2 * np.pi * f2 * t))
    sq = np.convolve(sq, np.ones(6) / 6, mode="same")  # take the edge off
    return sq * np.exp(-t * 13) * 0.18


def _bass808(freq, dur):
    n = int(dur * SR)
    t = _t(n)
    ph = 2 * np.pi * np.cumsum(freq * (1 + 0.6 * np.exp(-t * 35))) / SR
    s = np.tanh(1.5 * np.sin(ph) * np.exp(-t / (dur * 0.55)))
    fade = np.minimum(1, (n - np.arange(n)) / (0.04 * SR))
    return s * fade * 0.9


def _pluck(freq):
    t = _t(int(0.5 * SR))
    s = sum(np.sin(2 * np.pi * freq * k * t) / k for k in range(1, 6))
    s += 0.6 * sum(np.sin(2 * np.pi * freq * 1.004 * k * t) / k for k in range(1, 4))
    return s * np.exp(-t * 6) * 0.07


def _reverb(x, rng, secs=1.6):
    n = int(secs * SR)
    ir = rng.standard_normal(n) * np.exp(-_t(n) * 3.2)
    ir /= np.sqrt(np.sum(ir**2))  # unit-energy impulse response
    size = 1 << int(np.ceil(np.log2(len(x) + n)))
    y = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x) + n]
    return y


def _place(buf, sample, start):
    end = min(len(buf), start + len(sample))
    if start < len(buf):
        buf[start:end] += sample[: end - start]


def render(bpm, roots, scale, seed, bars=16) -> np.ndarray:
    rng = np.random.default_rng(seed)
    step = int(60 / bpm / 4 * SR)
    total = bars * 16 * step
    drums, bass, tone = (np.zeros(total) for _ in range(3))
    kick = _kick()
    for bar in range(bars):
        base = bar * 16 * step
        fill = bar % 4 == 3
        for s in ([0, 3, 6, 10, 13] if fill else [0, 6, 10]):
            _place(drums, kick, base + s * step)
        for s in (4, 12):
            _place(drums, _snare(rng), base + s * step)
        for s in range(0, 16, 2):
            _place(drums, _hat(rng), base + s * step)
        if bar % 2 == 1:
            for s in (14, 15):
                _place(drums, _hat(rng), base + s * step)
        _place(drums, _hat(rng, True), base + 7 * step)
        root = roots[bar % len(roots)]
        _place(bass, _bass808(root, 0.95), base)
        _place(bass, _bass808(root * (2 if fill else 1), 0.4), base + 6 * step)
        _place(bass, _bass808(root, 0.4), base + 10 * step)
        for i, s in enumerate((0, 3, 6, 10, 14)):
            _place(tone, _cowbell(540 if i % 2 == 0 else 400, 800), base + s * step)
        for s in range(16):
            if rng.random() < 0.38:
                _place(tone, _pluck(float(rng.choice(scale)) * (2 if s % 8 == 7 else 1)), base + s * step)
        pad_t = _t(16 * step)  # dark minor pad: root, minor third, fifth
        pad = sum(np.sin(2 * np.pi * root * 4 * r * pad_t) for r in (1, 1.189, 1.498)) * 0.025
        pad *= 0.6 + 0.4 * np.sin(2 * np.pi * 0.25 * pad_t)
        _place(tone, pad, base)
    wet = _reverb(tone, rng)
    mix = 0.6 * drums + 0.3 * bass + 0.9 * tone + 0.5 * wet[:total]
    mix[: len(wet) - total] += 0.5 * wet[total:]  # fold the reverb tail onto the start so it loops cleanly
    mix = np.tanh(mix)
    return (mix / np.max(np.abs(mix)) * 0.8).astype(np.float32)


def _write(path: Path, x: np.ndarray):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def ensure(cfg: dict) -> list[Path]:
    """Generate the sigma tracks once into assets/music/sigma/."""
    d = resolve(cfg, cfg["video"]["music_dir"]) / "sigma"
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for name, (bpm, roots, scale, seed) in VARIANTS.items():
        p = d / f"{name}.wav"
        if not p.exists():
            print(f"  synthesizing {name} …")
            _write(p, render(bpm, roots, scale, seed))
        out.append(p)
    return out
