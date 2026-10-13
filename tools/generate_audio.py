#!/usr/bin/env python3
"""Generates all of Jungleman's music and sound effects.

Everything is synthesized from scratch (oscillators, filtered noise and simple
physical-ish models), so the audio is original and can be regenerated or
tweaked at any time:

    python3 tools/generate_audio.py

Outputs:
    assets/audio/music/jungle_theme.ogg   seamless background loop
    assets/audio/sfx/*.wav                one file per sound effect

The music is rendered to WAV and encoded to Ogg Vorbis with ffmpeg. Requires
NumPy (pip install numpy) and ffmpeg on the PATH.
"""
import math
import os
import shutil
import subprocess
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSIC = os.path.join(ROOT, "assets", "audio", "music")
SFX = os.path.join(ROOT, "assets", "audio", "sfx")

SR = 44100
TAU = 2.0 * math.pi


# --- Basic building blocks ---------------------------------------------------

def midi(note):
    """Note name like 'A4', 'Bb3' or 'C#5' (or a MIDI number) -> MIDI number."""
    if isinstance(note, (int, float)):
        return note
    names = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    n = names[note[0]]
    rest = note[1:]
    while rest and rest[0] in "#b":
        n += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    return n + 12 * (int(rest) + 1)


def hz(note):
    return 440.0 * 2.0 ** ((midi(note) - 69) / 12.0)


def tvec(dur):
    return np.arange(int(dur * SR)) / SR


def env(n, attack=0.005, decay=0.2, sustain=0.0, release=0.05, hold=None):
    """Smooth envelope over n samples: linear attack, exponential decay toward
    sustain, then a release ramp at the end."""
    t = np.arange(n) / SR
    e = np.where(t < attack, t / max(attack, 1e-6), 1.0)
    d = np.clip(t - attack, 0.0, None)
    e = e * (sustain + (1.0 - sustain) * np.exp(-d / max(decay, 1e-6)))
    if release > 0:
        r = int(release * SR)
        if r > 0 and r < n:
            e[-r:] *= np.linspace(1.0, 0.0, r) ** 2
    return e


def osc(freq, n, shape="sine", phase=0.0):
    """Oscillator; freq may be a scalar or a per-sample array (for sweeps)."""
    f = np.broadcast_to(np.asarray(freq, dtype=float), (n,))
    ph = np.cumsum(f) / SR + phase
    if shape == "sine":
        return np.sin(TAU * ph)
    if shape == "tri":
        return 2.0 * np.abs(2.0 * (ph % 1.0) - 1.0) - 1.0
    if shape == "saw":
        return 2.0 * (ph % 1.0) - 1.0
    if shape == "square":
        return np.sign(np.sin(TAU * ph))
    raise ValueError(shape)


def sweep(f0, f1, n, curve="exp"):
    t = np.linspace(0.0, 1.0, n)
    if curve == "exp":
        return f0 * (f1 / f0) ** t
    return f0 + (f1 - f0) * t


def spectral(x, gain_fn):
    """Filters x in the frequency domain with a smooth gain curve gain_fn(freqs)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    return np.fft.irfft(X * gain_fn(f), len(x))


def lowpass(x, fc, order=2):
    return spectral(x, lambda f: 1.0 / np.sqrt(1.0 + (f / fc) ** (2 * order)))


def highpass(x, fc, order=2):
    return spectral(x, lambda f: 1.0 / np.sqrt(1.0 + (fc / np.maximum(f, 1e-3)) ** (2 * order)))


def bandpass(x, fc, q=2.0):
    bw = fc / q
    return spectral(x, lambda f: np.exp(-0.5 * ((f - fc) / bw) ** 2))


def sweep_filter(x, f0, f1, width=0.6):
    """Time-varying band-pass by overlap-adding short filtered grains."""
    n = len(x)
    out = np.zeros(n)
    grain = 1024
    hop = grain // 4
    win = np.hanning(grain)
    for start in range(0, n, hop):
        seg = x[start:start + grain]
        if len(seg) < grain:
            seg = np.pad(seg, (0, grain - len(seg)))
        fc = f0 * (f1 / f0) ** (start / max(n - 1, 1))
        y = bandpass(seg * win, fc, 1.0 / width) * 0.5
        end = min(start + grain, n)
        out[start:end] += y[: end - start]
    return out


def noise(n, rng):
    return rng.uniform(-1.0, 1.0, n)


def normalize(x, peak=0.9):
    m = np.max(np.abs(x))
    return x * (peak / m) if m > 0 else x


def fade(x, fin=0.002, fout=0.01):
    x = x.copy()
    a, b = int(fin * SR), int(fout * SR)
    if a:
        x[:a] *= np.linspace(0.0, 1.0, a)
    if b:
        x[-b:] *= np.linspace(1.0, 0.0, b)
    return x


def mixdown(n, *parts):
    """Sums (offset_seconds, signal) pairs into one buffer of n samples."""
    out = np.zeros(n)
    for offset, sig in parts:
        s = int(offset * SR)
        e = min(n, s + len(sig))
        if e > s:
            out[s:e] += sig[: e - s]
    return out


def write_wav(path, data, channels=1):
    data = np.clip(data, -1.0, 1.0)
    pcm = (data * 32767.0).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# --- Instruments ---------------------------------------------------------------

def marimba(note, dur=0.9, bright=1.0):
    f = hz(note)
    n = int(dur * SR)
    t = np.arange(n) / SR
    body = np.sin(TAU * f * t) * np.exp(-t / 0.42)
    # tuned bars have a strong partial near 4x (and a faint one near 10x)
    over = 0.35 * bright * np.sin(TAU * f * 3.93 * t) * np.exp(-t / 0.07)
    over2 = 0.08 * bright * np.sin(TAU * f * 9.8 * t) * np.exp(-t / 0.02)
    mallet = np.exp(-t / 0.0015) * np.sin(TAU * 2400 * t) * 0.15
    return fade((body + over + over2 + mallet) * env(n, 0.002, 10, 1, 0.05), 0.001, 0.05)


def kalimba(note, dur=1.2):
    f = hz(note)
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sin(TAU * f * t) * np.exp(-t / 0.6)
    s += 0.25 * np.sin(TAU * f * 5.4 * t) * np.exp(-t / 0.05)
    s += 0.1 * np.sin(TAU * f * 2.0 * t) * np.exp(-t / 0.25)
    return fade(s, 0.001, 0.08)


def flute(note, dur, rng, vib=True):
    """Breathy pan flute: soft attack, scooped pitch, delayed vibrato, air noise."""
    f0 = hz(note)
    n = int((dur + 0.15) * SR)
    t = np.arange(n) / SR
    scoop = 1.0 - 0.025 * np.exp(-t / 0.04)
    depth = np.clip((t - 0.18) / 0.3, 0.0, 1.0) * (0.006 if vib else 0.0)
    f = f0 * scoop * (1.0 + depth * np.sin(TAU * 5.2 * t))
    tone = osc(f, n) + 0.12 * osc(f * 2, n) + 0.04 * osc(f * 3, n)
    air = bandpass(noise(n, rng), f0 * 1.6, 1.5) * 0.9
    breath = bandpass(noise(n, rng), 1800, 0.8) * np.exp(-t / 0.05) * 0.5
    e = env(n, 0.06, 0.6, 0.75, 0.16)
    return fade((tone * 0.9 + air * 0.25) * e + breath * 0.3, 0.003, 0.05)


def pluck_bass(note, dur):
    f = hz(note)
    n = int((dur + 0.2) * SR)
    t = np.arange(n) / SR
    s = np.sin(TAU * f * t) + 0.35 * np.sin(TAU * 2 * f * t) * np.exp(-t / 0.15)
    s += 0.12 * np.sin(TAU * 3 * f * t) * np.exp(-t / 0.05)
    s = np.tanh(1.6 * s) / np.tanh(1.6)
    return fade(s * env(n, 0.004, 0.55, 0.25, 0.12), 0.002, 0.04)


def pad_chord(notes, dur, rng):
    """Warm string-like pad: detuned band-limited saws with a soft roll-off."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for note in notes:
        f0 = hz(note)
        for det in (-0.004, 0.0, 0.005):
            f = f0 * (1.0 + det)
            ph = rng.uniform(0, 1)
            lfo = 1.0 + 0.002 * np.sin(TAU * (0.3 + rng.uniform(0, 0.2)) * t + rng.uniform(0, TAU))
            for k in range(1, 9):
                if f * k > 5000:
                    break
                out += np.sin(TAU * (f * k * lfo * t + ph * k)) / (k ** 1.6)
    swell = 0.85 + 0.15 * np.sin(TAU * t / dur - math.pi / 2)
    return out * env(n, 0.6, 10, 1, 0.6) * swell / (len(notes) * 3)


def conga(freq, rng, slap=False, dur=0.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = freq * (1.0 + 0.5 * np.exp(-t / 0.012))
    body = osc(f, n) * np.exp(-t / (0.06 if slap else 0.16))
    skin = lowpass(highpass(noise(n, rng), 1800), 8000) * np.exp(-t / (0.02 if slap else 0.006))
    return fade(body + skin * (0.9 if slap else 0.35), 0.0005, 0.02)


def shaker(rng, accent=1.0):
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    e = (t / 0.012) * np.exp(1 - t / 0.012)
    return lowpass(highpass(noise(n, rng), 5500, 3), 11000) * e * accent


def claves(rng):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    return (np.sin(TAU * 2350 * t) + 0.3 * np.sin(TAU * 3800 * t)) * np.exp(-t / 0.025)


def boom(rng):
    """Deep frame-drum hit."""
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    f = 52.0 * (1.0 + 1.2 * np.exp(-t / 0.03))
    s = osc(f, n) * np.exp(-t / 0.28)
    s += lowpass(noise(n, rng), 300) * np.exp(-t / 0.02) * 0.6
    return fade(s, 0.0005, 0.05)


def bird_call(rng):
    """A short tropical bird phrase: a few fast warbling chirps."""
    parts = []
    t0 = 0.0
    base = rng.uniform(2200, 3800)
    for _ in range(rng.integers(2, 6)):
        d = rng.uniform(0.05, 0.12)
        n = int(d * SR)
        up = rng.random() < 0.5
        f = sweep(base * (0.8 if up else 1.25), base * (1.25 if up else 0.8), n)
        f = f * (1.0 + 0.04 * np.sin(TAU * rng.uniform(25, 45) * np.arange(n) / SR))
        parts.append((t0, osc(f, n) * np.sin(np.linspace(0, math.pi, n)) ** 2))
        t0 += d + rng.uniform(0.02, 0.08)
    return mixdown(int((t0 + 0.05) * SR), *parts)


def hoot(rng):
    """A distant two-note jungle hoot (owl/toucan-ish)."""
    f = rng.uniform(380, 520)
    n = int(0.28 * SR)
    t = np.arange(n) / SR
    a = osc(f * (1 + 0.04 * np.sin(math.pi * t / 0.28)), n) * np.sin(np.linspace(0, math.pi, n)) ** 1.5
    b = osc(f * 0.8 * (1 - 0.03 * t / 0.28), n) * np.sin(np.linspace(0, math.pi, n)) ** 1.5
    return mixdown(int(0.7 * SR), (0.0, a), (0.33, b))


# --- Music -----------------------------------------------------------------------

BPM = 104
BEAT = 60.0 / BPM
BAR = 4 * BEAT
BARS = 32
LOOP = BARS * BAR

# One chord per bar, cycling every four bars: Dm - C - Bb - Am (D aeolian).
CHORDS = [
    ("D2", ["D4", "F4", "A4", "D5"], ["D3", "A3", "F4"]),
    ("C2", ["C4", "E4", "G4", "C5"], ["C3", "G3", "E4"]),
    ("Bb1", ["Bb3", "D4", "F4", "Bb4"], ["Bb2", "F3", "D4"]),
    ("A1", ["A3", "C4", "E4", "A4"], ["A2", "E3", "C4"]),
]

# Pan flute melodies: one string per bar, "note:beats", "r" is a rest.
MELODY_1 = [
    "D5:1.5 C5:.5 A4:1 F4:1",
    "G4:1.5 A4:.5 G4:.5 E4:.5 C4:1",
    "D4:.5 F4:.5 Bb4:1.5 A4:.5 G4:1",
    "A4:3 r:1",
    "D5:1.5 C5:.5 A4:1 C5:1",
    "E5:1.5 D5:.5 C5:.5 G4:.5 E4:1",
    "F4:.5 G4:.5 Bb4:1 A4:1 G4:1",
    "A4:2.5 r:1.5",
]
MELODY_2 = [
    "A5:1 F5:.5 E5:.5 D5:1 A4:1",
    "C5:.5 D5:.5 E5:1 G5:1 E5:1",
    "F5:1.5 E5:.5 D5:1 Bb4:1",
    "C5:1 A4:1 E5:2",
    "D5:1.5 C5:.5 A4:1 C5:1",
    "E5:1.5 D5:.5 C5:.5 G4:.5 E4:1",
    "F4:.5 G4:.5 Bb4:1 A4:1 G4:1",
    "A4:1.5 C5:.5 D5:2",
]


def parse_bar(text):
    out, beat = [], 0.0
    for tok in text.split():
        name, _, length = tok.partition(":")
        length = float(length) if length else 1.0
        if name != "r":
            out.append((beat, length, name))
        beat += length
    return out


class Track:
    """Stereo loop buffer with a reverb send. Notes past the end wrap to the
    start, so the loop point is seamless."""

    def __init__(self, seconds):
        self.n = int(round(seconds * SR))
        self.dry = np.zeros((2, self.n))
        self.wet = np.zeros((2, self.n))

    def add(self, time, sig, gain=1.0, pan=0.0, send=0.2):
        s = int(round(time * SR)) % self.n
        idx = (np.arange(len(sig)) + s) % self.n
        lg = gain * math.cos((pan + 1) * math.pi / 4)
        rg = gain * math.sin((pan + 1) * math.pi / 4)
        for ch, g in ((0, lg), (1, rg)):
            np.add.at(self.dry[ch], idx, sig * g)
            if send:
                np.add.at(self.wet[ch], idx, sig * g * send)

    def render(self, rng, room=2.2):
        """Circular convolution reverb (the tail wraps around the loop)."""
        out = self.dry.copy()
        ir_n = int(room * SR)
        t = np.arange(ir_n) / SR
        for ch in range(2):
            ir = noise(ir_n, rng) * np.exp(-t / (room / 6.5))
            ir = lowpass(ir, 5000)
            ir[: int(0.025 * SR)] = 0.0  # pre-delay
            ir /= np.sqrt(np.sum(ir ** 2))
            padded = np.zeros(self.n)
            padded[:ir_n] = ir
            out[ch] += np.fft.irfft(np.fft.rfft(self.wet[ch]) * np.fft.rfft(padded), self.n) * 1.2
        return out


def compose_music():
    rng = np.random.default_rng(1994)
    tr = Track(LOOP)

    def section(bar):
        return bar // 8  # 0 intro, 1 theme, 2 breakdown, 3 theme reprise

    for bar in range(BARS):
        sec = section(bar)
        t0 = bar * BAR
        root, arp, pad = CHORDS[bar % 4]
        last = bar % 8 == 7

        # pad and bass underneath everything
        tr.add(t0, pad_chord(pad, BAR + 0.7, rng), 0.24, 0.0, 0.5)
        bass_pat = [(0, 1.5), (1.5, 0.5), (2.5, 1.0), (3.5, 0.5)] if sec else [(0, 2.5), (2.5, 1.5)]
        for i, (b, d) in enumerate(bass_pat):
            note = midi(root) + (12 if (sec and i == 3) else 0)
            if sec and i == 2:
                note += 7  # fifth
            tr.add(t0 + b * BEAT, pluck_bass(note, d * BEAT), 0.34, 0.0, 0.05)

        # marimba: eighth-note arpeggio; sixteenth-note counter-line in the breakdown
        if sec != 2:
            order = [0, 2, 1, 3, 2, 1, 3, 2]
            for i, k in enumerate(order):
                if i in (3, 7) and sec == 0 and bar % 2 == 0:
                    continue
                vel = 0.32 if i % 2 == 0 else 0.22
                tr.add(t0 + i * BEAT / 2, marimba(arp[k], 0.8, 0.9), vel, -0.35 + 0.1 * (i % 3), 0.25)
        else:
            line = [0, 1, 2, 3, 2, 1, 2, 3, 3, 2, 1, 2, 1, 0, 1, 2]
            for i, k in enumerate(line):
                if i % 4 == 3 and rng.random() < 0.5:
                    continue
                note = midi(arp[k]) + 12
                vel = 0.26 if i % 4 == 0 else 0.16
                tr.add(t0 + i * BEAT / 4, marimba(note, 0.6, 1.1), vel, 0.4 * math.sin(i), 0.3)
            # kalimba sparkles answering on the off-beats
            for b in (1.5, 3.5):
                tr.add(t0 + b * BEAT, kalimba(midi(arp[3]) + 12), 0.15, 0.5, 0.5)

        # pan flute carries the tune in the two theme sections
        if sec in (1, 3):
            mel = (MELODY_1 if sec == 1 else MELODY_2)[bar % 8]
            for b, d, name in parse_bar(mel):
                tr.add(t0 + b * BEAT, flute(name, d * BEAT * 0.95, rng), 0.42, 0.15, 0.45)
                # soft echo, one beat later, on the other side
                tr.add(t0 + (b + 0.75) * BEAT, flute(name, d * BEAT * 0.9, rng), 0.12, -0.5, 0.6)

        # hand percussion, 16 steps per bar
        for step in range(16):
            t = t0 + step * BEAT / 4
            swing = BEAT / 4 * 0.12 if step % 2 else 0.0
            t += swing
            full = sec in (1, 3)
            acc = 1.0 if step % 4 == 2 else 0.6
            tr.add(t, shaker(rng, acc), 0.10 if sec else 0.07, 0.45, 0.1)
            if step in (0, 7, 10):
                tr.add(t, conga(105, rng), 0.55, -0.2, 0.15)
            if step in (4, 12):
                tr.add(t, conga(185, rng), 0.42, 0.25, 0.15)
            if step in (6, 14) and sec:
                tr.add(t, conga(230, rng, slap=True), 0.32, 0.3, 0.2)
            if step in (2, 9, 13):
                tr.add(t, conga(160, rng, dur=0.15), 0.12, -0.1, 0.1)
            if full and step in (0, 3, 6, 10, 12):
                tr.add(t, claves(rng), 0.12, -0.55, 0.25)
            if sec != 0 and step in (0, 8) and not (sec == 2 and step == 8):
                tr.add(t, boom(rng), 0.3, 0.0, 0.1)
        if last:
            # tom fill into the next section
            for i, f in enumerate((240, 210, 180, 150, 125, 105)):
                tr.add(t0 + (2.5 + i * 0.25) * BEAT, conga(f, rng), 0.38, -0.4 + i * 0.16, 0.2)

    # jungle ambience: insects and scattered birds and hoots
    n = tr.n
    t = np.arange(n) / SR
    for pan, fc, rate in ((-0.7, 4800, 37.0), (0.7, 5600, 43.0)):
        buzz = bandpass(noise(n, rng), fc, 6.0)
        # rates are snapped to whole cycles per loop so the drone loops cleanly
        r = round(rate * LOOP) / LOOP
        slow = round(0.11 * LOOP) / LOOP
        am = (0.5 + 0.5 * np.sin(TAU * r * t)) ** 2 * (0.6 + 0.4 * np.sin(TAU * slow * t + pan))
        tr.add(0.0, normalize(buzz * am, 1.0), 0.018, pan, 0.0)
    for _ in range(26):
        tr.add(rng.uniform(0, LOOP), bird_call(rng), rng.uniform(0.03, 0.06), rng.uniform(-0.9, 0.9), 0.7)
    for _ in range(6):
        tr.add(rng.uniform(0, LOOP), hoot(rng), 0.05, rng.uniform(-0.8, 0.8), 0.8)

    mix = tr.render(rng)
    mix = np.stack([highpass(ch, 35) for ch in mix])
    mix = np.tanh(1.2 * mix / np.max(np.abs(mix))) / np.tanh(1.2) * 0.89
    return mix


def save_music():
    os.makedirs(MUSIC, exist_ok=True)
    mix = compose_music()
    tmp = os.path.join(MUSIC, "jungle_theme.tmp.wav")
    write_wav(tmp, mix.T.reshape(-1), channels=2)
    out = os.path.join(MUSIC, "jungle_theme.ogg")
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is needed to encode the music to Ogg Vorbis")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-c:a", "libvorbis", "-q:a", "5", out], check=True)
    os.remove(tmp)
    print("music:", os.path.relpath(out, ROOT), "%.1fs" % LOOP)


# --- Sound effects ---------------------------------------------------------------

def voice(f0_start, f0_end, dur, formants, rng, breath=0.15):
    """A short vocal grunt: a glottal buzz shaped by vowel formants."""
    n = int(dur * SR)
    f0 = sweep(f0_start, f0_end, n)
    f0 = f0 * (1.0 + 0.02 * np.sin(TAU * 18 * np.arange(n) / SR))
    ph = np.cumsum(f0) / SR
    out = np.zeros(n)
    for k in range(1, 40):
        fk = f0 * k
        amp = sum(a * np.exp(-0.5 * ((fk - fc) / bw) ** 2) for fc, bw, a in formants)
        amp = amp * (fk < SR / 2.2) / k ** 0.3
        out += amp * np.sin(TAU * k * ph)
    out += bandpass(noise(n, rng), formants[0][0] * 2, 1.2) * breath
    return out


def sfx_jump(rng):
    n = int(0.2 * SR)
    t = np.arange(n) / SR
    tone = osc(sweep(260, 620, n), n, "tri") * np.exp(-t / 0.07) * 0.5
    whoosh = sweep_filter(noise(n, rng), 600, 2500) * env(n, 0.02, 0.06, 0, 0.05) * 1.4
    return normalize(fade(tone + whoosh), 0.75)


def sfx_land(rng):
    n = int(0.18 * SR)
    t = np.arange(n) / SR
    thud = osc(sweep(120, 55, n), n) * np.exp(-t / 0.05)
    dust = lowpass(noise(n, rng), 1400) * np.exp(-t / 0.03) * 0.8
    return normalize(fade(thud + dust), 0.6)


def sfx_hurt(rng):
    grunt = voice(260, 170, 0.26, [(650, 120, 1.0), (1080, 150, 0.6), (2600, 300, 0.2)], rng)
    grunt *= env(len(grunt), 0.01, 0.12, 0.3, 0.08)
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    hit = osc(sweep(180, 70, n), n) * np.exp(-t / 0.04) + lowpass(noise(n, rng), 2500) * np.exp(-t / 0.012)
    return normalize(fade(mixdown(int(0.32 * SR), (0.0, hit * 0.8), (0.01, grunt))), 0.85)


def sfx_die(rng):
    cry = voice(330, 140, 0.7, [(700, 130, 1.0), (1150, 160, 0.6), (2500, 300, 0.2)], rng)
    cry *= env(len(cry), 0.02, 0.4, 0.4, 0.25)
    notes = [("A4", 0.0), ("F4", 0.22), ("D4", 0.44), ("A3", 0.66)]
    jingle = [(0.3 + o, marimba(nm, 0.9) * 0.55) for nm, o in notes]
    return normalize(fade(mixdown(int(1.9 * SR), (0.0, cry), *jingle)), 0.85)


def sfx_whip(rng):
    n = int(0.22 * SR)
    whoosh = sweep_filter(noise(n, rng), 400, 3200, 0.5) * env(n, 0.09, 0.03, 0, 0.02) * 3.0
    m = int(0.05 * SR)
    t = np.arange(m) / SR
    crack = highpass(noise(m, rng), 2500) * np.exp(-t / 0.004) * 2.2
    crack += osc(sweep(3000, 900, m), m) * np.exp(-t / 0.006) * 0.4
    return normalize(fade(mixdown(int(0.3 * SR), (0.0, whoosh), (0.1, crack))), 0.8)


def sfx_throw(rng):
    n = int(0.2 * SR)
    whoosh = sweep_filter(noise(n, rng), 1800, 500, 0.6) * env(n, 0.03, 0.05, 0, 0.05)
    m = int(0.04 * SR)
    t = np.arange(m) / SR
    snap = osc(900, m) * np.exp(-t / 0.008) * 0.5
    return normalize(fade(mixdown(n, (0.0, snap), (0.01, whoosh * 1.5))), 0.6)


def sfx_hit(rng):
    n = int(0.15 * SR)
    t = np.arange(n) / SR
    knock = osc(sweep(320, 140, n), n) * np.exp(-t / 0.04)
    smack = bandpass(noise(n, rng), 1600, 1.0) * np.exp(-t / 0.012) * 1.5
    return normalize(fade(knock + smack), 0.75)


def sfx_enemy_die(rng):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    squeak = osc(sweep(900, 250, n), n, "tri") * np.exp(-t / 0.12) * 0.5
    poof = lowpass(noise(n, rng), 1800) * env(n, 0.03, 0.12, 0, 0.1)
    return normalize(fade(squeak + poof * 0.9), 0.7)


def bell(note, dur=1.0, partials=((1, 1.0, 1.0), (2.76, 0.4, 0.4), (5.4, 0.2, 0.2))):
    f = hz(note)
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = sum(a * np.sin(TAU * f * r * t) * np.exp(-t / (0.5 * d)) for r, a, d in partials)
    return fade(s, 0.001, 0.05)


def sfx_gold(rng):
    return normalize(mixdown(int(0.7 * SR), (0.0, bell("B5", 0.5)), (0.07, bell("E6", 0.6))), 0.7)


def sfx_stones(rng):
    parts = []
    for i in range(7):
        m = int(0.05 * SR)
        t = np.arange(m) / SR
        click = bandpass(noise(m, rng), rng.uniform(2000, 4500), 3.0) * np.exp(-t / 0.006)
        click += osc(rng.uniform(1200, 2400), m) * np.exp(-t / 0.01) * 0.3
        parts.append((i * 0.035 + rng.uniform(0, 0.02), click * rng.uniform(0.5, 1.0)))
    return normalize(fade(mixdown(int(0.35 * SR), *parts)), 0.6)


def sfx_health(rng):
    parts = []
    for i, f in enumerate((300, 420, 560)):
        m = int(0.09 * SR)
        t = np.arange(m) / SR
        parts.append((i * 0.08, osc(sweep(f, f * 1.9, m), m) * np.sin(np.linspace(0, math.pi, m))))
    parts.append((0.26, bell("A5", 0.5) * 0.5))
    parts.append((0.3, bell("D6", 0.6) * 0.5))
    return normalize(fade(mixdown(int(0.9 * SR), *parts)), 0.7)


def sfx_life(rng):
    notes = ["D5", "F#5", "A5", "D6"]
    parts = [(i * 0.09, bell(nm, 0.8) + marimba(nm, 0.8) * 0.5) for i, nm in enumerate(notes)]
    parts.append((0.36, bell("A6", 1.0) * 0.4))
    return normalize(fade(mixdown(int(1.4 * SR), *parts)), 0.75)


def sfx_checkpoint(rng):
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    chord = sum(bell(nm, 1.6) * a for nm, a in (("D5", 1.0), ("A5", 0.7), ("D6", 0.5), ("F#6", 0.3)))
    shimmer = np.zeros(n)
    for i in range(14):
        m = int(0.12 * SR)
        f = hz("D6") * 2 ** (rng.integers(0, 12) / 12)
        tone = osc(f, m) * np.sin(np.linspace(0, math.pi, m)) ** 2
        s = int((0.05 + i * 0.06) * SR)
        shimmer[s:s + m] += tone[: max(0, min(m, n - s))] * (1 - i / 16)
    return normalize(fade(chord * env(n, 0.003, 10, 1, 0.4) + shimmer * 0.25), 0.7)


def sfx_vine(rng):
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    rustle = sweep_filter(noise(n, rng), 3000, 1200, 0.7) * env(n, 0.01, 0.08, 0, 0.05)
    creak = osc(sweep(140, 110, n), n, "saw") * (0.5 + 0.5 * np.sign(np.sin(TAU * 28 * t)))
    creak = bandpass(creak, 800, 1.5) * env(n, 0.03, 0.1, 0, 0.05)
    grab = lowpass(noise(int(0.05 * SR), rng), 900) * np.exp(-np.arange(int(0.05 * SR)) / SR / 0.012)
    return normalize(fade(mixdown(n, (0.0, rustle), (0.0, grab * 1.2), (0.03, creak * 0.8))), 0.6)


def sfx_zipline(rng):
    n = int(0.8 * SR)
    t = np.arange(n) / SR
    f = sweep(500, 900, n) * (1 + 0.01 * np.sin(TAU * 31 * t))
    whirr = bandpass(osc(f, n, "saw"), 1400, 1.0) * (0.7 + 0.3 * np.sin(TAU * 23 * t))
    hiss = highpass(noise(n, rng), 3000) * 0.3
    clank = bell("E6", 0.3, ((1, 1, 0.3), (2.3, 0.6, 0.2), (4.1, 0.4, 0.1)))
    body = (whirr + hiss) * env(n, 0.05, 10, 1, 0.35)
    return normalize(fade(mixdown(n, (0.0, clank * 0.6), (0.0, body))), 0.6)


def sfx_tar(rng):
    parts = []
    for i in range(4):
        m = int(0.12 * SR)
        t = np.arange(m) / SR
        f0 = rng.uniform(90, 160)
        parts.append((i * 0.06 + rng.uniform(0, 0.03), osc(sweep(f0, f0 * 2.4, m), m) * np.exp(-t / 0.04)))
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    squelch = lowpass(noise(n, rng), 600) * np.exp(-t / 0.08)
    return normalize(fade(mixdown(n, (0.0, squelch), *parts)), 0.75)


def sfx_splash(rng):
    n = int(1.0 * SR)
    t = np.arange(n) / SR
    body = sweep_filter(noise(n, rng), 3500, 700, 0.9) * env(n, 0.005, 0.25, 0, 0.3) * 1.6
    plunge = osc(sweep(220, 60, n), n) * np.exp(-t / 0.08) * 0.6
    bubbles = []
    for _ in range(10):
        m = int(0.05 * SR)
        f0 = rng.uniform(500, 1200)
        bubbles.append((rng.uniform(0.15, 0.7), osc(sweep(f0, f0 * 1.6, m), m) * np.hanning(m) * 0.25))
    return normalize(fade(mixdown(n, (0.0, body), (0.0, plunge), *bubbles)), 0.8)


def sfx_plank(rng):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    pulses = (np.sin(TAU * sweep(35, 22, n, "lin") * t) > 0.6).astype(float)
    creak = bandpass(noise(n, rng), 700, 4.0) * pulses * env(n, 0.05, 0.3, 0, 0.1) * 2.0
    m = int(0.08 * SR)
    tm = np.arange(m) / SR
    crack = (bandpass(noise(m, rng), 1500, 0.8) * 1.8 + osc(sweep(400, 150, m), m)) * np.exp(-tm / 0.015)
    return normalize(fade(mixdown(n, (0.0, creak), (0.3, crack))), 0.7)


def sfx_snake(rng):
    n = int(0.55 * SR)
    hiss = highpass(noise(n, rng), 4000) * env(n, 0.05, 0.3, 0.2, 0.15)
    return normalize(fade(hiss * (0.8 + 0.2 * np.sin(TAU * 13 * np.arange(n) / SR))), 0.5)


def sfx_snap(rng):
    def chomp():
        m = int(0.07 * SR)
        t = np.arange(m) / SR
        return (bandpass(noise(m, rng), 1200, 1.0) * 1.4 + osc(sweep(260, 90, m), m)) * np.exp(-t / 0.018)
    return normalize(fade(mixdown(int(0.25 * SR), (0.0, chomp()), (0.09, chomp() * 0.8))), 0.7)


def sfx_level_complete(rng):
    parts = []
    tune = [("D5", 0.0, 0.18), ("F5", 0.18, 0.18), ("A5", 0.36, 0.18), ("C6", 0.54, 0.18), ("D6", 0.72, 1.1)]
    for nm, o, d in tune:
        parts.append((o, flute(nm, d, rng, vib=d > 0.5) * 0.7))
        parts.append((o, marimba(nm, 0.9) * 0.4))
    for nm in ("D4", "A4", "D5", "F5"):
        parts.append((0.72, marimba(nm, 1.2) * 0.35))
        parts.append((0.72, pad_chord([nm], 1.6, rng) * 1.2))
    for i in range(6):
        parts.append((i * 0.12, conga(160 + (i % 2) * 60, rng) * 0.5))
    parts.append((0.72, boom(rng) * 0.8))
    return normalize(fade(mixdown(int(2.4 * SR), *parts), 0.002, 0.3), 0.85)


def sfx_game_over(rng):
    parts = []
    tune = [("A4", 0.0, 0.3), ("G4", 0.3, 0.3), ("F4", 0.6, 0.3), ("E4", 0.9, 0.3), ("D4", 1.2, 1.3)]
    for nm, o, d in tune:
        parts.append((o, flute(nm, d, rng, vib=d > 0.5) * 0.7))
    for nm in ("D3", "A3", "F4"):
        parts.append((1.2, pad_chord([nm], 1.8, rng) * 1.5))
    parts.append((1.2, boom(rng)))
    return normalize(fade(mixdown(int(3.0 * SR), *parts), 0.002, 0.4), 0.8)


def sfx_pause(rng):
    return normalize(mixdown(int(0.3 * SR), (0.0, marimba("A5", 0.3)), (0.06, marimba("E6", 0.25) * 0.6)), 0.5)


SOUNDS = {
    "jump": sfx_jump,
    "land": sfx_land,
    "hurt": sfx_hurt,
    "die": sfx_die,
    "whip": sfx_whip,
    "throw": sfx_throw,
    "hit": sfx_hit,
    "enemy_die": sfx_enemy_die,
    "gold": sfx_gold,
    "stones": sfx_stones,
    "health": sfx_health,
    "life": sfx_life,
    "checkpoint": sfx_checkpoint,
    "vine": sfx_vine,
    "zipline": sfx_zipline,
    "tar": sfx_tar,
    "splash": sfx_splash,
    "plank": sfx_plank,
    "snake": sfx_snake,
    "snap": sfx_snap,
    "level_complete": sfx_level_complete,
    "game_over": sfx_game_over,
    "pause": sfx_pause,
}


def save_sfx():
    os.makedirs(SFX, exist_ok=True)
    for i, (name, fn) in enumerate(SOUNDS.items()):
        rng = np.random.default_rng(100 + i)
        write_wav(os.path.join(SFX, name + ".wav"), fn(rng))
    print("sfx:", len(SOUNDS), "sounds in", os.path.relpath(SFX, ROOT))


if __name__ == "__main__":
    save_sfx()
    save_music()
