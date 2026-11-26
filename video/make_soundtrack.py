"""Synthesize the ambient soundtrack for video/story.html (76 s, 48 kHz stereo WAV).

Everything is generated from code (no samples, no licensing questions): a warm pad that
follows the story's scenes, soft pulses, typing ticks, node "pings", transition whooshes
and a finale impact. Event times mirror the timeline constants in story.html; if you
retime a scene there, retime it here.

Usage: python3 video/make_soundtrack.py out.wav
"""
import sys
import wave

import numpy as np
from scipy import signal

SR = 48000
DUR = 76.0
N = int(SR * DUR)
rng = np.random.default_rng(1710)
t_all = np.arange(N) / SR


def note(name):
    names = {'C': -9, 'C#': -8, 'D': -7, 'D#': -6, 'E': -5, 'F': -4, 'F#': -3, 'G': -2, 'G#': -1, 'A': 0, 'A#': 1, 'B': 2}
    n, octv = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[n] + (octv - 4) * 12) / 12)


def adsr_window(n, a, r):
    w = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    if na: w[:na] = np.linspace(0, 1, na) ** 2
    if nr: w[-nr:] *= np.linspace(1, 0, nr) ** 2
    return w


def place(buf, start, sig, gain=1.0):
    i = int(start * SR)
    if i >= len(buf): return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


def pad_voice(freq, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for det in (-0.07, 0.0, 0.06):            # three detuned voices, in semitones
        f = freq * 2 ** (det / 12)
        ph = rng.uniform(0, 2 * np.pi)
        for h in range(1, 7):                  # soft saw: harmonics at 1/h^1.4
            out += np.sin(2 * np.pi * f * h * t + ph * h) / h ** 1.4
    lfo = 0.85 + 0.15 * np.sin(2 * np.pi * 0.11 * t + rng.uniform(0, 6))
    return out * lfo


# --- pad chords: (start, end, notes) -------------------------------------------------------
CHORDS = [
    (0.0, 8.6, ['A2', 'E3', 'B3', 'C4']),        # S1 origin: Am(add9), low and dark
    (7.6, 13.6, ['F2', 'C3', 'A3', 'E4']),       # S2 lesson: Fmaj7
    (12.8, 17.6, ['C3', 'G3', 'E4', 'D4']),      # S3 journey: C - G - Am - F
    (16.8, 21.8, ['G2', 'D3', 'B3', 'A4']),
    (21.0, 26.0, ['A2', 'E3', 'C4', 'B4']),
    (25.2, 30.6, ['F2', 'C3', 'A3', 'G4']),
    (29.8, 35.6, ['D3', 'A3', 'F4', 'E4']),      # S4 turn: Dm - E (tension)
    (34.8, 40.6, ['E2', 'B2', 'G#3', 'D4']),
    (39.8, 46.6, ['F2', 'C3', 'A3', 'E4']),      # S5 practice: F - C
    (45.8, 52.6, ['C3', 'G3', 'E4', 'B4']),
    (51.8, 58.6, ['A2', 'E3', 'C4', 'B4']),      # S6 architecture: Am - G
    (57.8, 64.4, ['G2', 'D3', 'B3', 'A4']),
    (65.4, 76.0, ['C2', 'G2', 'E3', 'D4', 'G4']),  # S7 finale: Cadd9, open and resolved
]
pad = np.zeros(N)
for s, e, notes in CHORDS:
    dur = e - s
    v = sum(pad_voice(note(nm), dur) for nm in notes) / len(notes)
    v *= adsr_window(len(v), 1.4 if s > 0 else 2.5, 1.6)
    place(pad, s, v, 0.42)
# warm it: lowpass with a slowly opening cutoff, brighter at the finale
sos_dark = signal.butter(2, 1200, 'low', fs=SR, output='sos')
sos_bright = signal.butter(2, 3200, 'low', fs=SR, output='sos')
pad_d, pad_b = signal.sosfilt(sos_dark, pad), signal.sosfilt(sos_bright, pad)
mix_b = np.clip((t_all - 64.5) / 2.0, 0, 1)
pad = pad_d * (1 - mix_b) + pad_b * mix_b

# --- sub pulse (a soft heartbeat in the journey and architecture scenes) ---------------------
def thump(f0=52, dur=0.55):
    t = np.arange(int(dur * SR)) / SR
    f = f0 * (1 + 1.2 * np.exp(-t * 30))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)

perc = np.zeros(N)
for start, end in ((14.0, 29.0), (53.0, 63.0)):
    for k in np.arange(start, end, 1.0):
        place(perc, k, thump(), 0.55)

# --- typing ticks during the terminal lines --------------------------------------------------
ticks = np.zeros(N)
sos_tick = signal.butter(2, [2500, 7000], 'band', fs=SR, output='sos')
for i in range(4):
    a = 2.4 + i * 1.15
    k = a
    while k < a + 0.95:
        click = signal.sosfilt(sos_tick, rng.standard_normal(int(0.012 * SR))) * np.exp(-np.arange(int(0.012 * SR)) / SR * 400)
        place(ticks, k, click, 0.35 * rng.uniform(0.6, 1.0))
        k += rng.uniform(0.035, 0.07)

# --- pings: journey nodes, pillars, layers, finale name --------------------------------------
def bell(freq, dur=1.8):
    t = np.arange(int(dur * SR)) / SR
    return (np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 2.76 * t) * np.exp(-t * 3)) * np.exp(-t * 2.6)

pings = np.zeros(N)
penta = ['E5', 'G5', 'A5', 'C6', 'D6']
for i in range(5):                               # journey nodes light (JT0 + i * JSTEP)
    place(pings, 15.2 + i * 2.55, bell(note(penta[i])), 0.16)
for i in range(3):                               # pillars arrive
    place(pings, 42.4 + i * 1.1, bell(note(['A4', 'C5', 'E5'][i]), 2.2), 0.16)
for i in range(6):                               # layers stack bottom-up
    place(pings, 53.2 + (5 - i) * 0.32, bell(note(['C5', 'D5', 'E5', 'G5', 'A5', 'C6'][5 - i]), 1.2), 0.08)
for i in range(5):                               # control-plane items
    place(pings, 56.6 + i * 0.55, bell(note('E6'), 0.6), 0.05)
place(pings, 67.6, bell(note('G5'), 3.0), 0.14)
place(pings, 69.0, bell(note('C6'), 3.0), 0.12)

# --- whooshes on scene changes ----------------------------------------------------------------
def whoosh(dur=1.6, f0=300, f1=4000):
    n = int(dur * SR)
    noise = rng.standard_normal(n)
    out = np.zeros(n)
    seg = 512
    for s in range(0, n, seg):
        x = s / n
        fc = f0 * (f1 / f0) ** np.sin(np.pi * x * 0.5)
        sos = signal.butter(2, [fc * 0.7, min(fc * 1.4, SR / 2 - 100)], 'band', fs=SR, output='sos')
        out[s:s + seg] = signal.sosfilt(sos, noise[s:s + seg])
    env = np.sin(np.pi * np.linspace(0, 1, n)) ** 2
    return out * env

fx = np.zeros(N)
for tt in (8.0, 13.0, 30.0, 40.0, 52.0):
    w = whoosh()
    place(fx, tt - 0.9, w, 0.22)

# --- finale: rising swell into an impact ------------------------------------------------------
swell_n = int(1.6 * SR)
swell = signal.sosfilt(signal.butter(2, 900, 'low', fs=SR, output='sos'), rng.standard_normal(swell_n))
swell *= np.linspace(0, 1, swell_n) ** 3
place(fx, 64.0, swell, 0.5)
imp_t = np.arange(int(3.5 * SR)) / SR
impact = np.sin(2 * np.pi * np.cumsum(42 * (1 + 2.5 * np.exp(-imp_t * 12))) / SR) * np.exp(-imp_t * 1.6)
impact += signal.sosfilt(signal.butter(2, 400, 'low', fs=SR, output='sos'), rng.standard_normal(len(imp_t))) * np.exp(-imp_t * 5) * 0.6
place(fx, 65.6, impact, 0.75)

# --- mix, reverb, master ----------------------------------------------------------------------
dry = pad * 0.9 + perc * 0.7 + ticks + pings + fx

def reverb_ir(seed, secs=2.8):
    r = np.random.default_rng(seed)
    n = int(secs * SR)
    ir = r.standard_normal(n) * np.exp(-np.arange(n) / SR * 2.4)
    ir = signal.sosfilt(signal.butter(1, 5000, 'low', fs=SR, output='sos'), ir)
    return ir / np.sqrt(np.sum(ir ** 2))

L = dry + signal.fftconvolve(dry, reverb_ir(1), mode='full')[:N] * 0.35
R = dry + signal.fftconvolve(dry, reverb_ir(2), mode='full')[:N] * 0.35
st = np.stack([L, R], axis=1)
st = signal.sosfilt(signal.butter(2, 28, 'high', fs=SR, output='sos'), st, axis=0)  # remove rumble/DC
fade = np.minimum(np.clip(t_all / 1.5, 0, 1), np.clip((DUR - t_all) / 2.0, 0, 1))
st *= fade[:, None]
st = np.tanh(st / (np.max(np.abs(st)) + 1e-9) * 1.6) / np.tanh(1.6) * 0.6    # soft limiter, peaks ~-4.5 dBFS (ambient level)

out = sys.argv[1] if len(sys.argv) > 1 else 'soundtrack.wav'
with wave.open(out, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((st * 32767).astype('<i2').tobytes())
print('wrote', out, f'{DUR:.0f}s')
