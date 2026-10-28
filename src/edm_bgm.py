"""Original synthesized EDM background music (four-on-the-floor, offbeat bass, supersaw chords, snare-roll builds).

Generated from scratch with numpy, so there is no licence baggage. Reuses the drum voices from sigma_bgm.
"""
import numpy as np

from . import sigma_bgm as sb
from .config import resolve

SR = sb.SR

# (bpm, chord roots in Hz per bar (minor-key progression), seed)
VARIANTS = {
    "edm_drop_128": (128, [110.0, 87.31, 130.81, 98.0], 5),
    "edm_neon_124": (124, [98.0, 110.0, 87.31, 82.41], 11),
    "edm_rave_130": (130, [123.47, 98.0, 110.0, 82.41], 17),
}


def _supersaw(freq, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = sum(((2 * ((freq * (1 + d) * t) % 1)) - 1) for d in (-0.012, -0.006, 0, 0.006, 0.012))
    env = np.minimum(1, t / 0.01) * np.minimum(1, (dur - t) / 0.05)
    return s * env * 0.035


def _sidechain(n_step, step, bars):
    """Volume dip on every kick so chords and bass 'pump'."""
    env = np.ones(bars * 16 * step)
    dip = 1 - 0.85 * np.exp(-np.arange(step * 4) / (step * 1.1))
    for beat in range(bars * 4):
        a = beat * 4 * step
        env[a:a + len(dip)] = np.minimum(env[a:a + len(dip)], dip[: len(env) - a])
    return env


def render(bpm, roots, seed, bars=16) -> np.ndarray:
    rng = np.random.default_rng(seed)
    step = int(60 / bpm / 4 * SR)
    total = bars * 16 * step
    drums, bass, lead = (np.zeros(total) for _ in range(3))
    kick = sb._kick()
    chord_ratios = (1, 1.189, 1.498, 2)
    for bar in range(bars):
        base = bar * 16 * step
        build = bar % 8 == 7  # last bar of each 8: snare roll, no kick on the last beat
        root = roots[bar % len(roots)]
        for beat in range(4):
            if not (build and beat == 3):
                sb._place(drums, kick, base + beat * 4 * step)
            sb._place(drums, sb._hat(rng, True), base + (beat * 4 + 2) * step)  # offbeat open hat
        for s in (4, 12):
            sb._place(drums, sb._snare(rng), base + s * step)
        if build:
            for s in range(8, 16):
                sb._place(drums, sb._snare(rng) * (0.4 + 0.08 * s), base + s * step)
        for s in range(1, 16, 2):
            sb._place(drums, sb._hat(rng), base + s * step)
        for beat in range(4):  # offbeat bass
            sb._place(bass, sb._bass808(root / 2, 0.22), base + (beat * 4 + 2) * step)
        for r in chord_ratios:
            sb._place(lead, _supersaw(root * 2 * r, 16 * step / SR), base)
        for i, s in enumerate((0, 3, 6, 8, 11, 14)):  # arpeggio
            sb._place(lead, _supersaw(root * 4 * chord_ratios[i % 4], 0.14) * 1.3, base + s * step)
    duck = _sidechain(4, step, bars)
    wet = sb._reverb(lead * duck, rng, 1.2)
    mix = 0.7 * drums + 0.45 * bass * duck + 1.0 * lead * duck + 0.35 * wet[:total]
    mix[: len(wet) - total] += 0.35 * wet[total:]
    mix = np.tanh(mix)
    return (mix / np.max(np.abs(mix)) * 0.8).astype(np.float32)


def ensure(cfg: dict):
    d = resolve(cfg, cfg["video"]["music_dir"]) / "edm"
    d.mkdir(parents=True, exist_ok=True)
    for name, (bpm, roots, seed) in VARIANTS.items():
        p = d / f"{name}.wav"
        if not p.exists():
            print(f"  synthesizing {name} …")
            sb._write(p, render(bpm, roots, seed))
