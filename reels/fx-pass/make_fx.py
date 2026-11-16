#!/usr/bin/env python3
"""
FX pass for an already-edited action video.

  audio: original synthesized DJ layer locked to the song's own beats
         (suspense intro: heartbeat + drone + riser/snare-roll -> DROP -> full beat
          -> breakdown + riser -> DROP 2 -> outro boom), sub-thuds on punches,
          light sidechain pump on the original mix
  video: on every hit -> shake + zoom punch + RGB split; strong hits -> bright red flash;
         drops -> white+red flash; kick pulses in the beat sections; heartbeat vignette in the intro

usage: python3 make_fx.py <input.mp4> [out.mp4]
       DROP1 / BREAK / DROP2 / OUTRO env vars (seconds) override the section times
"""
import math, os, subprocess, sys, tempfile, wave
import numpy as np
from PIL import Image
from scipy.signal import lfilter, butter

IN = sys.argv[1]; OUT = sys.argv[2] if len(sys.argv) > 2 else "fx_out.mp4"
SR = 48000
DROP1 = float(os.environ.get("DROP1", 40.0))   # suspense -> full beat
BREAK = float(os.environ.get("BREAK", 84.0))   # breakdown before the glass room
DROP2 = float(os.environ.get("DROP2", 96.0))   # second drop
OUTRO = float(os.environ.get("OUTRO", 158.0))  # drums stop
rng = np.random.default_rng(11)
tmp = tempfile.mkdtemp()
def ff(*a): subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *a], check=True)
def read_wav(p):
    w = wave.open(p); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return a.reshape(-1, w.getnchannels())

pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                     "stream=width,height,r_frame_rate", "-of", "csv=p=0", IN], capture_output=True, text=True).stdout.strip().split(",")
W, H = int(pr[0]), int(pr[1]); num, den = map(int, pr[2].split("/")); FPS = num / den

# ------------------------------------------------------------------ analysis
print("1/4 analysing beats and hits")
src_wav = os.path.join(tmp, "src.wav"); ff("-i", IN, "-vn", "-ar", str(SR), "-ac", "2", src_wav)
mixd = read_wav(src_wav); mono = mixd.mean(1); DUR = len(mono) / SR

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
BPM = 60 / np.median(np.diff(beats)); BEAT = 60 / BPM
# downbeat phase: the beat-phase (mod 4) with most low-end energy after the drop
lowE = np.log1p(30 * X[:, (fq > 30) & (fq < 150)]).sum(1)
def le(b): return lowE[np.clip((b * ofps).astype(int), 0, len(lowE) - 1)].mean()
ph = max(range(4), key=lambda p: le(beats[p::4][beats[p::4] > DROP1]))
bar_starts = beats[ph::4]
def snap_bar(t): return float(bar_starts[np.argmin(np.abs(bar_starts - t))])
DROP1, BREAK, DROP2 = snap_bar(DROP1), snap_bar(BREAK), snap_bar(DROP2)
OUTRO = float(beats[np.argmin(np.abs(beats - OUTRO))])
print(f"   {BPM:.1f} BPM | drop1 {DROP1:.2f}s  break {BREAK:.2f}s  drop2 {DROP2:.2f}s  outro {OUTRO:.2f}s")

# hits: broadband transients (punch/impact sounds) + big motion spikes
hop2, n2 = 256, 1024; f2 = SR / hop2
fr2 = np.lib.stride_tricks.sliding_window_view(mono, n2)[::hop2] * np.hanning(n2)
X2 = np.log1p(30 * np.abs(np.fft.rfft(fr2, axis=1))); fq2 = np.fft.rfftfreq(n2, 1 / SR)
hiF = np.maximum(0, np.diff(X2[:, fq2 > 2500], axis=0)).sum(1)
loF = np.maximum(0, np.diff(X2[:, (fq2 > 40) & (fq2 < 200)], axis=0)).sum(1)
z = lambda x: (x - np.median(x)) / (np.percentile(x, 90) - np.median(x) + 1e-9)
sc = z(hiF) + 0.5 * z(loF)
cand = [(i / f2, sc[i]) for i in range(2, len(sc) - 2) if sc[i] == sc[i - 2:i + 3].max() and sc[i] > 4.0]
hits = []
for t, s in sorted(cand, key=lambda x: -x[1]):                      # strongest first, min gap 0.3s
    if all(abs(t - h[0]) > 0.3 for h in hits): hits.append((t, s))
hits.sort()
# keep only the stronger half; strength = rank (0..1)
hits = sorted(hits, key=lambda h: -h[1])[: max(1, int(len(hits) * 0.55))]
order = {h: r for r, h in enumerate(hits)}
hits = sorted((t, 1 - order[(t, s)] / len(hits)) for t, s in hits)
# red flashes: top hits only, at least 1.5s apart, only once the action has started
red_hits = []
for t, s in sorted(hits, key=lambda h: -h[1]):
    if t > DROP1 - 0.5 and len(red_hits) < 36 and all(abs(t - r) > 1.5 for r in red_hits): red_hits.append(t)
red_hits = set(red_hits)
print(f"   {len(hits)} hits kept, {len(red_hits)} red flashes")

# ------------------------------------------------------------------ audio layer
print("2/4 building the DJ layer")
N = len(mono)
def ex(n, tau): return np.exp(-np.arange(n) / (tau * SR))
def kick(dec=0.32, f1=58):
    n = int(0.6 * SR); t = np.arange(n) / SR; f = f1 + 110 * np.exp(-t / 0.035)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * ex(n, dec)
    click = rng.standard_normal(n) * ex(n, 0.003) * 0.4
    return np.tanh(2.5 * (body + click)) * 0.9
def clap():
    n = int(0.35 * SR); x = np.zeros(n)
    for d in (0, 0.011, 0.022):                                        # 3 quick bursts = clap
        i = int(d * SR); m = n - i; x[i:] += rng.standard_normal(m) * ex(m, 0.012 if d < 0.02 else 0.12)
    b, a = butter(2, [900 / (SR / 2), 7000 / (SR / 2)], "band"); return lfilter(b, a, x) * 0.55
def hat(open_=False):
    n = int((0.25 if open_ else 0.05) * SR); x = rng.standard_normal(n)
    b, a = butter(2, 7000 / (SR / 2), "high"); return lfilter(b, a, x) * ex(n, 0.08 if open_ else 0.012) * 0.25
def snare():
    n = int(0.25 * SR); x = rng.standard_normal(n) * ex(n, 0.07)
    tone = np.sin(2 * np.pi * 190 * np.arange(n) / SR) * ex(n, 0.04)
    b, a = butter(2, 1200 / (SR / 2), "high"); return (lfilter(b, a, x) * 0.6 + tone * 0.4) * 0.6
def boom(len_s=2.5):                                                  # drop impact: sub drop + noise burst
    n = int(len_s * SR); t = np.arange(n) / SR; f = 32 + 60 * np.exp(-t / 0.25)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * ex(n, 0.9)
    nz = rng.standard_normal(n) * ex(n, 0.25); b, a = butter(2, 2500 / (SR / 2)); nz = lfilter(b, a, nz)
    return np.tanh(1.8 * (sub + 0.5 * nz)) * 0.95
def thud():                                                          # punch sweetener
    n = int(0.3 * SR); t = np.arange(n) / SR; f = 50 + 90 * np.exp(-t / 0.02)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * ex(n, 0.09)
    nz = rng.standard_normal(n) * ex(n, 0.015); b, a = butter(2, 3000 / (SR / 2)); nz = lfilter(b, a, nz)
    return np.tanh(2 * (s + 0.6 * nz)) * 0.8
def riser(len_s):                                                    # noise sweep + rising tone
    n = int(len_s * SR); t = np.arange(n) / SR; p = t / len_s
    nz = rng.standard_normal(n); out = np.zeros(n); blk = 2048
    for i in range(0, n, blk):                                        # sweeping band-pass
        fc = 300 + 9000 * (i / n) ** 2; b, a = butter(2, [max(fc * 0.6, 50) / (SR / 2), min(fc * 1.4, SR / 2.2) / (SR / 2)], "band")
        out[i:i + blk] = lfilter(b, a, nz[i:i + blk])
    tone = np.sin(2 * np.pi * np.cumsum(110 * 2 ** (3 * p)) / SR) * 0.25
    return (out * 0.8 + tone) * p ** 2 * 0.7

KICK, KICK_SOFT, CLAP, HAT, OHAT, SN, BOOM, THUD = kick(), kick(0.5, 45), clap(), hat(), hat(True), snare(), boom(), thud()
drums = np.zeros(N + SR * 3); fx = np.zeros(N + SR * 3)
def put(buf, s, t, g=1.0):
    i = int(t * SR)
    if 0 <= i < len(buf): m = min(len(s), len(buf) - i); buf[i:i + m] += g * s[:m]

kick_times = []
for k in range(len(beats) - 1):
    b, nb = beats[k], beats[k + 1]; step = (nb - b) / 4
    pos = (k - ph) % 4; bar_i = (k - ph) // 4
    full = (DROP1 <= b < BREAK) or (DROP2 <= b < OUTRO)
    if b < DROP1 and b > 2.0:                                         # suspense: heartbeat on bar starts
        if pos == 0:
            put(drums, KICK_SOFT, b, 0.55); put(drums, KICK_SOFT, b + step * 1.2, 0.4); kick_times.append(b)
        if b >= DROP1 - 2 * 4 * BEAT and pos in (0, 2): put(drums, HAT, b, 0.5)
    elif BREAK <= b < DROP2:                                          # breakdown: sparse filtered kick
        if pos == 0: put(drums, KICK_SOFT, b, 0.6); kick_times.append(b)
        put(drums, HAT, b + 2 * step, 0.35)
    elif full:
        hard = b >= DROP2
        if pos == 0: put(drums, KICK, b); kick_times.append(b)
        if pos == 1: put(drums, KICK, b + 2 * step, 0.7)             # syncopated kick
        if pos == 2 and bar_i % 2 == 1: put(drums, KICK, b + 3 * step, 0.6)
        if pos in (1, 3): put(drums, CLAP, b)
        for s_ in range(4):
            if s_ % 2 == 0 or hard: put(drums, HAT, b + s_ * step, 0.8 if s_ == 0 else 0.5)
        if pos == 3 and bar_i % 4 == 3:                               # hat roll every 4th bar
            for s_ in range(8): put(drums, HAT, b + s_ * step / 2, 0.45)
        if pos == 2 and bar_i % 2 == 0: put(drums, OHAT, b + 2 * step, 0.6)

# builds into each drop: riser over 2 bars + snare roll over the last bar
for drop, start in ((DROP1, DROP1 - 8 * BEAT), (DROP2, DROP2 - 8 * BEAT)):
    put(fx, riser(drop - start), start, 0.9)
    n_roll = 16; r0 = drop - 4 * BEAT
    for j in range(n_roll):
        tj = r0 + (drop - r0) * (1 - (1 - j / n_roll) ** 1.6)          # accelerating
        put(drums, SN, tj, 0.25 + 0.6 * j / n_roll)
    put(fx, BOOM, drop, 1.0)
put(fx, BOOM, OUTRO, 0.9)
# tension drone under the suspense intro (pulsing low fifth)
d0, d1 = int(3.0 * SR), int(DROP1 * SR); t = np.arange(d1 - d0) / SR
drone = (np.sin(2 * np.pi * 55 * t) + 0.5 * np.sin(2 * np.pi * 82.4 * t)) * (0.55 + 0.45 * np.sin(2 * np.pi * t / (2 * BEAT)))
drone *= np.minimum(1, t / 4) * np.minimum(1, (d1 - d0 - np.arange(d1 - d0)) / (0.05 * SR)) * 0.12
fx[d0:d1] += drone
# punch sweeteners
for t_, s in hits:
    if s > 0.5: put(fx, THUD, t_ - 0.005, 0.3 + 0.6 * s)

drums, fx = drums[:N], fx[:N]
b, a = butter(2, 9000 / (SR / 2)); drums = lfilter(b, a, drums)
lay = np.tanh(1.3 * (drums * 0.75 + fx * 0.8))
# sidechain pump on the original mix
pump = np.ones(N)
for kt in kick_times:
    i = int(kt * SR); n = min(int(0.3 * SR), N - i)
    if n > 0: pump[i:i + n] = np.minimum(pump[i:i + n], 1 - 0.3 * np.exp(-np.arange(n) / (0.1 * SR)))
out = mixd * pump[:, None] * 0.85 + lay[:, None] * 0.7
out_wav = os.path.join(tmp, "out.wav")
w = wave.open(out_wav, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((np.clip(out, -1, 1) * 32767).astype(np.int16).tobytes()); w.close()

# ------------------------------------------------------------------ video
print("3/4 rendering video FX")
hit_t = np.array([h[0] for h in hits]); hit_s = np.array([h[1] for h in hits])
kick_arr = np.array(kick_times); bars_full = np.array([b for b in bar_starts if (DROP1 <= b < BREAK) or (DROP2 <= b < OUTRO)])
dec = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", IN, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", f"{W}x{H}", "-r", f"{num}/{den}", "-i", "-", "-i", out_wav,
                        "-af", "loudnorm=I=-14:TP=-1.0:LRA=9", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-shortest",
                        "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
vig = (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2).clip(0, 2)[..., None] / 2   # 0 centre .. 1 corners
def last_event(arr, t):
    i = np.searchsorted(arr, t, side="right") - 1
    return (t - arr[i], i) if i >= 0 else (1e9, -1)
fsize = W * H * 3; n = 0
while True:
    raw = dec.stdout.read(fsize)
    if len(raw) < fsize: break
    t = n / FPS; n += 1
    dt, hi_ = last_event(hit_t, t); s = hit_s[hi_] if hi_ >= 0 else 0
    e_hit = (0.35 + 0.65 * s) * math.exp(-dt / 0.12) if dt < 0.6 else 0.0
    dk, _ = last_event(kick_arr, t); e_kick = math.exp(-dk / 0.12) if dk < 0.5 else 0.0
    drop_dt = min((t - d for d in (DROP1, DROP2, OUTRO) if t >= d), default=1e9)
    e_drop = math.exp(-drop_dt / 0.25) if drop_dt < 1.2 else 0.0
    full = (DROP1 <= t < BREAK) or (DROP2 <= t < OUTRO)
    # --- geometry: shake + zoom punch
    z = 1.0 + 0.07 * e_hit + (0.018 * e_kick if full else 0) + 0.08 * e_drop
    ph_ = dt * 2 * math.pi * 22
    dx = 30 * e_hit * math.sin(ph_ + hi_) + 18 * e_drop * math.sin(t * 140)
    dy = 22 * e_hit * math.cos(ph_ * 1.3 + hi_) + 12 * e_drop * math.cos(t * 120)
    img = Image.frombuffer("RGB", (W, H), raw)
    if z > 1.001 or abs(dx) > 0.3 or abs(dy) > 0.3:
        cw, ch = W / z, H / z
        img = img.transform((W, H), Image.AFFINE, (cw / W, 0, (W - cw) / 2 + dx, 0, ch / H, (H - ch) / 2 + dy), Image.BILINEAR)
    arr = np.asarray(img, np.float32)
    # --- colour: RGB split, red flash on strong hits, drops flash white+red, kick brightness pulse
    split = int(16 * e_hit + 24 * e_drop)
    if split >= 2:
        arr = arr.copy(); arr[..., 0] = np.roll(arr[..., 0], split, 1); arr[..., 2] = np.roll(arr[..., 2], -split, 1)
    is_red = hi_ >= 0 and hit_t[hi_] in red_hits
    red = (0.8 * e_hit / max(s, 1e-6) * min(1, s + 0.3) if is_red else 0.0) + 0.6 * e_drop
    if full and len(bars_full):                                        # red pulse on every 4th bar
        db, bi_ = last_event(bars_full, t)
        if bi_ >= 0 and bi_ % 4 == 0 and db < 0.8: red += 0.35 * math.exp(-db / 0.2)
    if red > 0.01:
        lum = arr.mean(2, keepdims=True)
        tint = np.concatenate([np.minimum(255, lum * 1.6 + 60), lum * 0.25, lum * 0.25], 2)   # bright red grade
        arr = arr * (1 - min(red, 0.85)) + tint * min(red, 0.85)
    if e_drop > 0.3: arr = arr + (255 - arr) * (e_drop - 0.3) * 0.9   # white flash on the drop
    if full: arr = arr * (1 + 0.08 * e_kick)
    if t < DROP1:                                                       # heartbeat vignette in the intro
        hb = math.exp(-dk / 0.18) if dk < 1 else 0
        arr = arr * (1 - vig * (0.55 - 0.25 * hb))
        arr[..., 0] += (vig[..., 0] * 70 * hb)
    else:
        arr = arr * (1 - vig * 0.3)
    enc.stdin.write(arr.clip(0, 255).astype(np.uint8).tobytes())
    if n % 900 == 0: print(f"   {t:6.1f}s / {DUR:.1f}s", flush=True)
enc.stdin.close(); enc.wait(); dec.wait()
print(f"4/4 done -> {OUT}")
