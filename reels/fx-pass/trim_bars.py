#!/usr/bin/env python3
"""
Shorten the FX video to a target length by removing whole musical bars, so every
join lands on a downbeat and the beat keeps flowing. Bars are chosen by action
(motion + hit count in the ORIGINAL edit); build-ups, drops, title and ending are kept.

usage: python3 trim_bars.py <original_input.mp4> <fx_video.mp4> [out.mp4]
       TARGET (seconds, default 90), DROP1/BREAK/DROP2/OUTRO like make_fx.py
"""
import os, subprocess, sys, tempfile, wave
import numpy as np

ORIG, FXV = sys.argv[1], sys.argv[2]
OUT = sys.argv[3] if len(sys.argv) > 3 else "fx_90s.mp4"
TARGET = float(os.environ.get("TARGET", 90))
DROP1 = float(os.environ.get("DROP1", 40.0)); BREAK = float(os.environ.get("BREAK", 84.0))
DROP2 = float(os.environ.get("DROP2", 96.0)); OUTRO = float(os.environ.get("OUTRO", 158.0))
TITLE_END = float(os.environ.get("TITLE_END", 8.5))     # keep the opening title
SR = 48000; tmp = tempfile.mkdtemp()

# ---- beats / bars (same tracker as make_fx.py, on the original edit) ----
wav = os.path.join(tmp, "a.wav")
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", ORIG, "-vn", "-ac", "1", "-ar", str(SR), wav], check=True)
w = wave.open(wav); mono = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
DUR = len(mono) / SR
hop, nfft = 512, 2048; ofps = SR / hop
fr = np.lib.stride_tricks.sliding_window_view(mono, nfft)[::hop] * np.hanning(nfft)
X = np.abs(np.fft.rfft(fr, axis=1)); fq = np.fft.rfftfreq(nfft, 1 / SR); Sx = np.log1p(30 * X)
env = np.maximum(0, np.diff(Sx, axis=0)).sum(1)
env = np.maximum(0, env - np.convolve(env, np.ones(32) / 32, "same")); env /= env.std() + 1e-9
ac = np.correlate(env, env, "full")[len(env) - 1:]; lags = np.arange(len(ac)) / ofps
ok = (lags > 60 / 90) & (lags < 60 / 64); period = lags[ok][np.argmax(ac[ok])] * ofps
score = env.copy(); back = np.full(len(env), -1)
for i in range(len(env)):
    lo, hi = int(i - 2 * period), int(i - period / 2)
    if hi <= 0: continue
    js = np.arange(max(lo, 0), hi); pen = -100 * np.log((i - js) / period) ** 2
    k = np.argmax(score[js] + pen); score[i] += score[js][k] + pen[k]; back[i] = js[k]
i = int(np.argmax(score[-int(period):])) + len(env) - int(period); bf = []
while i >= 0: bf.append(i); i = back[i]
beats = np.array(bf[::-1]) / ofps + (hop + nfft / 2) / SR
lowE = np.log1p(30 * X[:, (fq > 30) & (fq < 150)]).sum(1)
def le(b): return lowE[np.clip((b * ofps).astype(int), 0, len(lowE) - 1)].mean()
ph = max(range(4), key=lambda p: le(beats[p::4][beats[p::4] > DROP1]))
bars = beats[ph::4]
snap = lambda t: float(bars[np.argmin(np.abs(bars - t))])
DROP1, BREAK, DROP2 = snap(DROP1), snap(BREAK), snap(DROP2)
OUTRO = float(beats[np.argmin(np.abs(beats - OUTRO))])
BAR = float(np.median(np.diff(bars)))

# ---- action score per bar: motion + audio hit density ----
r = subprocess.run(["ffmpeg", "-hide_banner", "-i", ORIG, "-an", "-vf",
                    "fps=10,scale=96:-2,format=gray,tblend=all_mode=difference,signalstats,"
                    "metadata=print:key=lavfi.signalstats.YAVG:file=-", "-f", "null", "-"],
                   capture_output=True, text=True, check=True)
mot = np.array([float(l.split("=")[1]) for l in r.stdout.splitlines() if "YAVG" in l])
hiF = np.maximum(0, np.diff(Sx[:, fq > 2500], axis=0)).sum(1); hz = (hiF - np.median(hiF)) / (np.percentile(hiF, 90) - np.median(hiF) + 1e-9)
def action(a, b):
    m = mot[int(a * 10):int(b * 10)].mean(); h = (hz[int(a * ofps):int(b * ofps)] > 4).sum()
    return m / (mot.mean() + 1e-9) + 0.15 * h

# ---- segments: (start, end, must_keep) ----
first_bar = next(b for b in bars if b >= TITLE_END - 0.01)
units = [(0.0, first_bar, True)]                                   # title
edges = [b for b in bars if first_bar <= b < OUTRO] + [OUTRO]
for a, b in zip(edges[:-1], edges[1:]):
    must = (DROP1 - 2 * BAR - 0.05 <= a < DROP1 + BAR - 0.05) or \
           (DROP2 - 2 * BAR - 0.05 <= a < DROP2 + BAR - 0.05) or (a >= OUTRO - BAR - 0.05)
    units.append((a, b, must))
units.append((OUTRO, DUR, True))                                   # ending boom
need = sum(b - a for a, b, _ in units) - TARGET
optional = sorted([u for u in units if not u[2]], key=lambda u: action(u[0], u[1]))
drop = set()
for u in optional:                                                 # drop the calmest bars first
    if need <= BAR / 2: break
    drop.add(u); need -= u[1] - u[0]
keep = [u for u in units if u not in drop]
segs = []                                                          # merge adjacent kept bars
for a, b, _ in keep:
    if segs and abs(segs[-1][1] - a) < 1e-3: segs[-1][1] = b
    else: segs.append([a, b])
total = sum(b - a for a, b in segs)
print(f"bars {BAR:.2f}s | removed {len(drop)} bars | {len(segs)} segments | new length {total:.1f}s")
for a, b in segs: print(f"   keep {a:7.2f} -> {b:7.2f}")

# ---- render: hard video cuts on the downbeat, 20 ms audio fades at each join ----
fc, inputs = [], []
for k, (a, b) in enumerate(segs):                                  # one seeked input per segment (low memory)
    inputs += ["-ss", f"{a:.4f}", "-t", f"{b - a:.4f}", "-i", FXV]
    fc.append(f"[{k}:v]setpts=PTS-STARTPTS[v{k}]")
    fc.append(f"[{k}:a]asetpts=PTS-STARTPTS,"
              f"afade=t=in:d=0.02,afade=t=out:st={max(b - a - 0.02, 0):.4f}:d=0.02[a{k}]")
fc.append("".join(f"[v{k}][a{k}]" for k in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=1[v][a]")
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(fc),
                "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", OUT], check=True)
print(f"done -> {OUT}")
