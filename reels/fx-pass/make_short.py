#!/usr/bin/env python3
"""
60-second 9:16 cut of the FX video with slow motion and smooth transitions.

  - keeps whole musical bars so the beat never stutters
  - fixed: title, build-up bars, both drops, the bar before the ending, ending boom
  - fills the rest with the highest-action bars
  - 3 slow-motion bars (0.5x, motion-interpolated) on the biggest hits; their audio goes
    muffled + echoey ("underwater" slow-mo sound)
  - transitions centred on the downbeat: zoom into slow-mo, blur out of it,
    white flash into drops, smooth slides elsewhere

usage: python3 make_short.py <original_input.mp4> <fx_video.mp4> [out.mp4]
       TARGET seconds (default 60); DROP1/BREAK/DROP2/OUTRO like make_fx.py
"""
import os, subprocess, sys, tempfile, wave
import numpy as np
from scipy.signal import butter, lfilter

ORIG, FXV = sys.argv[1], sys.argv[2]
OUT = sys.argv[3] if len(sys.argv) > 3 else "short_60s.mp4"
TARGET = float(os.environ.get("TARGET", 60))
DROP1 = float(os.environ.get("DROP1", 40.0)); BREAK = float(os.environ.get("BREAK", 84.0))
DROP2 = float(os.environ.get("DROP2", 96.0)); OUTRO = float(os.environ.get("OUTRO", 158.0))
TITLE_END = 5.0
SR, FPS, XD = 48000, 30, 0.3                       # audio rate, fps, transition length
tmp = tempfile.mkdtemp(dir=os.environ.get("TMPDIR"))
def run(*a): subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *a], check=True)
def q(t): return round(t * FPS) / FPS            # snap to frame grid

# ---------------- beats / bars / hits (from the original edit) ----------------
print("1/4 analysing")
wav = os.path.join(tmp, "o.wav"); run("-i", ORIG, "-vn", "-ac", "1", "-ar", str(SR), wav)
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
DROP1, BREAK, DROP2, OUTRO = snap(DROP1), snap(BREAK), snap(DROP2), snap(OUTRO)
BAR = float(np.median(np.diff(bars)))
bar_list = [(float(a), float(b)) for a, b in zip(bars[:-1], bars[1:])]
def bar_at(t): return next(((a, b) for a, b in bar_list if a <= t < b), None)

r = subprocess.run(["ffmpeg", "-hide_banner", "-i", ORIG, "-an", "-vf",
                    "fps=10,scale=96:-2,format=gray,tblend=all_mode=difference,signalstats,"
                    "metadata=print:key=lavfi.signalstats.YAVG:file=-", "-f", "null", "-"],
                   capture_output=True, text=True, check=True)
mot = np.array([float(l.split("=")[1]) for l in r.stdout.splitlines() if "YAVG" in l])
hiF = np.maximum(0, np.diff(Sx[:, fq > 2500], axis=0)).sum(1)
hz = (hiF - np.median(hiF)) / (np.percentile(hiF, 90) - np.median(hiF) + 1e-9)
def action(a, b): return mot[int(a * 10):int(b * 10)].mean() / (mot.mean() + 1e-9) + 0.15 * (hz[int(a * ofps):int(b * ofps)] > 4).sum()
def best_hit(a, b):
    i0, i1 = int(a * ofps), int(b * ofps); k = int(np.argmax(hz[i0:i1])); return (i0 + k) / ofps

# ---------------- plan ----------------
print("2/4 planning")
fixed = {bar_at(DROP1 - 0.01), bar_at(DROP1 + 0.01), bar_at(DROP2 - 0.01), bar_at(DROP2 + 0.01), bar_at(OUTRO - 0.01)}
first = next(a for a, b in bar_list if a >= TITLE_END)
sec1 = [bb for bb in bar_list if DROP1 + BAR - 0.05 <= bb[0] and bb[1] <= BREAK + 0.05 and bb not in fixed]
sec2 = [bb for bb in bar_list if DROP2 + BAR - 0.05 <= bb[0] and bb[1] <= OUTRO + 0.05 and bb not in fixed]
# slow-mo: strongest hit in section 1, in the first half of section 2, and the climax (last 4 bars)
slow = []
for pool in (sec1, sec2[: len(sec2) // 2], sec2[-4:]):
    pool = [bb for bb in pool if bb not in [s[0] for s in slow]]
    bb = max(pool, key=lambda bb: hz[int(bb[0] * ofps):int(bb[1] * ofps)].max()); slow.append((bb, best_hit(*bb)))
slow_bars = {s[0] for s in slow}
base = TITLE_END_T = first
budget = TARGET - (first + len(fixed) * BAR + (DUR - OUTRO) + len(slow) * BAR)
n_extra = max(0, int(round(budget / BAR)))
cands = sorted([bb for bb in sec1 + sec2 if bb not in slow_bars], key=lambda bb: -action(*bb))[:n_extra]
units = [("norm", 0.0, first)]
for bb in sorted(set(cands) | fixed | slow_bars):
    if bb in slow_bars:
        h = dict(slow)[bb]; units.append(("slow", bb[0], bb[1], h))
    else: units.append(("norm", bb[0], bb[1]))
units.append(("norm", OUTRO, DUR))
# merge contiguous normal bars
segs = []
for u in units:
    if segs and u[0] == "norm" and segs[-1][0] == "norm" and abs(segs[-1][2] - u[1]) < 1e-3:
        segs[-1] = ("norm", segs[-1][1], u[2])
    else: segs.append(u)
total = sum(s[2] - s[1] for s in segs)
if total > TARGET + 0.4:                                            # shave the ending tail to fit
    k = len(segs) - 1; segs[k] = ("norm", segs[k][1], segs[k][2] - (total - TARGET)); total = TARGET
# transition before each segment (none for the first)
def trans_into(prev, cur):
    if cur[0] == "slow": return "zoomin"
    if prev[0] == "slow": return "hblur"
    if abs(cur[1] - DROP1) < 0.1 or abs(cur[1] - DROP2) < 0.1: return "fadewhite"
    return "smoothleft"
trans = [None] + [trans_into(segs[i - 1], segs[i]) for i in range(1, len(segs))]
for s, tr in zip(segs, trans):
    print(f"   {s[0]:4s} {s[1]:7.2f}->{s[2]:7.2f}  {'(hit %.2f)' % s[3] if s[0] == 'slow' else ''}  in:{tr}")
print(f"   {len(segs)} segments, length {total:.1f}s")

# ---------------- audio (numpy, equal-power crossfades centred on the cut) ----------------
print("3/4 audio")
aw = os.path.join(tmp, "fx.wav"); run("-i", FXV, "-vn", "-ac", "2", "-ar", str(SR), aw)
w = wave.open(aw); A = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32).reshape(-1, 2) / 32768
def sl(a, b):
    i0, i1 = int(round(a * SR)), int(round(b * SR)); out = np.zeros((i1 - i0, 2), np.float32)
    s0, s1 = max(i0, 0), min(i1, len(A)); out[s0 - i0:s1 - i0] = A[s0:s1]; return out
bl, al = butter(2, 700 / (SR / 2))
def underwater(x):
    y = lfilter(bl, al, x, axis=0); d = int(0.13 * SR); e = y.copy()
    for k in range(1, 4): e[d * k:] += y[:-d * k] * (0.45 ** k)
    return e * 1.3
half = XD / 2; n_half = int(round(half * SR))
pieces = []
for i, s in enumerate(segs):
    pre = half if trans[i] else 0; post = half if i + 1 < len(segs) else 0
    x = sl(s[1] - pre, s[2] + post)
    if s[0] == "slow": x = underwater(x)
    pieces.append(x)
mix = pieces[0]
for x in pieces[1:]:
    n = 2 * n_half; t = np.linspace(0, np.pi / 2, n)[:, None]
    over = mix[-n:] * np.cos(t) + x[:n] * np.sin(t)
    mix = np.concatenate([mix[:-n], over, x[n:]])
fo = int(1.0 * SR); mix[-fo:] *= np.linspace(1, 0, fo)[:, None]
mixw = os.path.join(tmp, "mix.wav"); ww = wave.open(mixw, "wb"); ww.setnchannels(2); ww.setsampwidth(2); ww.setframerate(SR)
ww.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes()); ww.close()

# ---------------- video: one clip per segment (with transition handles), then xfade chain ----------------
print("4/4 video")
clips, durs = [], []
for i, s in enumerate(segs):
    pre = half if trans[i] else 0; post = half if i + 1 < len(segs) else 0
    core = s[2] - s[1]; out_len = q(core + pre + post); p = os.path.join(tmp, f"c{i}.mp4")
    if s[0] == "slow":                                    # 0.5x around the hit, motion-interpolated
        src_len = out_len / 2; st = max(0, s[3] - 0.45 * src_len)
        vf = ("minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
              f"setpts=2*(PTS-STARTPTS),fps={FPS},trim=duration={out_len:.4f},setpts=PTS-STARTPTS")
        run("-ss", f"{st:.4f}", "-t", f"{src_len + 0.2:.4f}", "-i", FXV, "-an", "-vf", vf,
            "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", "-pix_fmt", "yuv420p", p)
    else:
        run("-ss", f"{s[1] - pre:.4f}", "-t", f"{out_len:.4f}", "-i", FXV, "-an",
            "-vf", f"fps={FPS},trim=duration={out_len:.4f},setpts=PTS-STARTPTS",
            "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", "-pix_fmt", "yuv420p", p)
    clips.append(p); durs.append(out_len)
    print(f"   clip {i + 1}/{len(segs)}", flush=True)
inputs = sum((["-i", c] for c in clips), []) + ["-i", mixw]
fc, prev, acc = [], "[0:v]", durs[0]
for i in range(1, len(clips)):
    off = acc - XD
    fc.append(f"{prev}[{i}:v]xfade=transition={trans[i]}:duration={XD}:offset={off:.4f}[x{i}]")
    prev = f"[x{i}]"; acc = acc + durs[i] - XD
# 9:16 layout: drop the baked-in letterbox, blurred background, bigger centred picture
fc.append(f"{prev}crop=1920:840:0:120,split[a][b];"
          "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:2,eq=brightness=-0.25[bg];"
          "[b]crop=1300:840,scale=1080:-2:flags=lanczos[fg];[bg][fg]overlay=0:(H-h)/2,setsar=1,"
          f"fade=t=out:st={acc - 1.0:.3f}:d=1.0[v]")
run(*inputs, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", f"{len(clips)}:a",
    "-af", "loudnorm=I=-14:TP=-1.0:LRA=9", "-c:v", "libx264", "-profile:v", "high", "-crf", "20",
    "-maxrate", "12M", "-bufsize", "24M", "-preset", "medium", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", OUT)
print(f"done -> {OUT} ({acc:.1f}s)")
