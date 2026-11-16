#!/usr/bin/env python3
"""
60s lofi Reel: Thanos x "Kabhi Kabhie" (lofi version)

  - song: slowed (pitch kept), warm low-pass, room reverb, vinyl crackle,
          + a synthesized lofi drum beat placed on the song's own detected beats
  - edits and zoom pulses land on the beat
  - kinetic-typography intro (letters zoom/focus into centre, then fly apart)
  - lofi look: warm grade, grain, vignette, light leak, slow camera drift
  - Thor's chop: tape-stop on the music + RGB-split hit, then original audio
  - animated outro tagline

usage: python3 make_lofi_reel.py <thanos.mp4> <song.mp3> [out.mp4]
"""
import math, os, subprocess, sys, tempfile, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SCENE, SONG = sys.argv[1], sys.argv[2]
OUT = sys.argv[3] if len(sys.argv) > 3 else "thanos_lofi_reel.mp4"
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_TITLE = os.path.join(HERE, "fonts/Anton-Regular.ttf")
FONT_SUB = os.path.join(HERE, "fonts/Poppins-SemiBold.ttf")

W, H, FPS, SR = 1080, 1920, 30, 44100
SONG_IN = 12.6          # music start in the mp3
TEMPO = 0.95            # slow-down (pitch preserved)
TARGET_CHOP = 41.0      # where (output time) the song should die
CHOP_SRC = 243.9        # Thor's swing in thanos.mp4
POST_END_SRC = 263.0    # end after "What did you do?" exchange
TITLE = "THANOS"
SUBTITLE = "after wiping out half the universe"
OUTRO = "villain bhi insaan hota hai".split()

# (source start, latest usable source end) in thanos.mp4; durations come from the beat grid
SHOTS = [
    (78.5, 87.6),    # garden vista (under the intro title)
    (88.0, 91.8),    # armour scarecrow
    (92.0, 103.5),   # walking through the flowers
    (124.5, 132.7),  # cooking, calm close-up
    (133.0, 137.5),  # Carol's blast
    (151.0, 153.9),  # chokehold
    (169.8, 172.8),  # empty gauntlet
    (235.9, 238.9),  # Thanos face
    (None, CHOP_SRC) # last shot ends on the chop
]
WANT = [7.0, 3.5, 7.0, 7.0, 3.5, 2.6, 2.6, 2.6, 2.6]  # rough shot lengths, snapped to beats

tmp = tempfile.mkdtemp()
def run(cmd): subprocess.run(cmd, check=True)
def ff(*a): run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *a])
def read_wav(p):
    w = wave.open(p); ch = w.getnchannels()
    a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return a.reshape(-1, ch)
def write_wav(p, a):
    a = np.clip(a, -1, 1); w = wave.open(p, "wb"); w.setnchannels(a.shape[1]); w.setsampwidth(2)
    w.setframerate(SR); w.writeframes((a * 32767).astype(np.int16).tobytes()); w.close()

# ------------------------------------------------------------------ audio: lofi song
print("1/5 lofi-processing the song")
song_wav = os.path.join(tmp, "song.wav")
ff("-ss", str(SONG_IN), "-t", "48", "-i", SONG, "-af",
   f"atempo={TEMPO},highpass=f=70,lowpass=f=4200,"
   "equalizer=f=250:t=q:w=1:g=3,"                       # warm low-mids
   "aecho=0.85:0.5:70|140:0.22|0.12,"                   # small room reverb
   "acompressor=threshold=-18dB:ratio=3:attack=20:release=200",
   "-ar", str(SR), "-ac", "2", song_wav)
song = read_wav(song_wav)

# ------------------------------------------------------------------ beat tracking (DP, Ellis 2007)
print("2/5 tracking beats")
mono = song.mean(1); hop = 512; nfft = 2048; ofps = SR / hop
frames = np.lib.stride_tricks.sliding_window_view(mono, nfft)[::hop] * np.hanning(nfft)
spec = np.log1p(20 * np.abs(np.fft.rfft(frames, axis=1)))
env = np.maximum(0, np.diff(spec, axis=0)).sum(1)
env = np.maximum(0, env - np.convolve(env, np.ones(32) / 32, "same")); env /= env.std() + 1e-9
ac = np.correlate(env, env, "full")[len(env) - 1:]
lags = np.arange(len(ac)) / ofps
ok = (lags > 60 / 118) & (lags < 60 / 88)             # song pulse ~100 BPM after slow-down
period = lags[ok][np.argmax(ac[ok])] * ofps
score = env.copy(); back = np.full(len(env), -1)
for i in range(len(env)):
    lo, hi = int(i - 2 * period), int(i - period / 2)
    if hi <= 0: continue
    js = np.arange(max(lo, 0), hi)
    pen = -100 * np.log((i - js) / period) ** 2
    k = np.argmax(score[js] + pen); score[i] += score[js][k] + pen[k]; back[i] = js[k]
i = int(np.argmax(score[-int(period):])) + len(env) - int(period); beats = []
while i >= 0: beats.append(i); i = back[i]
beat_frames = np.array(beats[::-1])
beats = beat_frames / ofps + (hop + nfft / 2) / SR
bpm = 60 / np.median(np.diff(beats))
print(f"   {bpm:.1f} BPM, {len(beats)} beats")
bi = beat_frames
print(f"   onset strength on beats {env[bi].mean():.2f} vs average {env.mean():.2f}")

# kick/snare phase: kick on the beat set with more low-end energy
low = np.abs(np.fft.rfft(frames, axis=1))[:, 1:12].sum(1)
def lowE(b): return low[np.clip((b * ofps).astype(int), 0, len(low) - 1)].mean()
kick_phase = 0 if lowE(beats[0::2]) >= lowE(beats[1::2]) else 1

# chop on a kick beat near TARGET_CHOP
cands = [b for k, b in enumerate(beats) if (k - kick_phase) % 2 == 0]
CHOP = float(min(cands, key=lambda b: abs(b - TARGET_CHOP)))
print(f"   chop at {CHOP:.2f}s")

# ------------------------------------------------------------------ audio: drums + crackle + tape stop
print("3/5 building the beat")
rng = np.random.default_rng(7)
def env_exp(n, tau): return np.exp(-np.arange(n) / (tau * SR))
def kick():
    n = int(0.45 * SR); t = np.arange(n) / SR
    f = 45 + 75 * np.exp(-t / 0.05); ph = 2 * np.pi * np.cumsum(f) / SR
    return np.tanh(2.2 * np.sin(ph) * env_exp(n, 0.16)) * 0.9
def snare():
    n = int(0.3 * SR); noise = rng.standard_normal(n)
    noise = np.convolve(noise, np.ones(6) / 6, "same")               # soften
    tone = np.sin(2 * np.pi * 185 * np.arange(n) / SR) * env_exp(n, 0.05)
    return (0.55 * noise * env_exp(n, 0.09) + 0.5 * tone) * 0.6
def hat():
    n = int(0.06 * SR); x = rng.standard_normal(n); x = np.diff(x, prepend=0)
    return x * env_exp(n, 0.012) * 0.12
K, S_, HH = kick(), snare(), hat()
drums = np.zeros(len(song) + SR)
def place(sample, t, g=1.0):
    i = int(t * SR)
    if 0 <= i < len(drums):
        seg = sample[: len(drums) - i]; drums[i:i + len(seg)] += g * seg
for k, b in enumerate(beats):
    if b > CHOP: break
    is_kick = (k - kick_phase) % 2 == 0
    nxt = beats[k + 1] if k + 1 < len(beats) else b + 60 / bpm
    if is_kick: place(K, b)
    else: place(S_, b, 0.9)
    place(HH, b, 0.8); place(HH, b + 0.58 * (nxt - b), 0.55)          # swung 8ths
    if not is_kick and k % 4 == 3: place(K, b + 0.58 * (nxt - b), 0.55)  # ghost kick
# drum bus: low-pass + saturation (lofi)
from scipy.signal import lfilter
a = np.exp(-2 * np.pi * 5500 / SR); y = lfilter([1 - a], [1, -a], drums)
drums = np.tanh(1.4 * y)[: len(song)]
# sidechain-ish pump on the song from kicks
pump = np.ones(len(song))
for k, b in enumerate(beats):
    if (k - kick_phase) % 2 == 0 and b < CHOP:
        i = int(b * SR); n = min(int(0.35 * SR), len(pump) - i)
        if n > 0: pump[i:i + n] = np.minimum(pump[i:i + n], 1 - 0.25 * np.exp(-np.arange(n) / (0.12 * SR)))
mix = song * pump[:, None] * 0.8 + drums[:, None] * 0.55

# vinyl crackle + hiss (whole reel)
def crackle(n):
    c = np.zeros(n); idx = rng.integers(0, n, int(n / SR * 12))
    c[idx] = rng.standard_normal(len(idx)) * 0.25
    c = np.convolve(c, np.exp(-np.arange(40) / 6), "same")
    return c + rng.standard_normal(n) * 0.004

# tape stop over the last 0.9s before the chop
L = int(CHOP * SR); ts = int(0.9 * SR)
rate = np.ones(L); rate[L - ts:] = np.linspace(1, 0, ts) ** 1.6
pos = np.concatenate([[0], np.cumsum(rate)[:-1]])
tape = np.stack([np.interp(pos, np.arange(len(mix)), mix[:, c]) for c in range(2)], 1)
fade = np.ones(L); fade[-int(0.05 * SR):] = np.linspace(1, 0, int(0.05 * SR))
song_part = tape * fade[:, None]

# post-chop original movie audio
post_wav = os.path.join(tmp, "post.wav")
ff("-ss", str(CHOP_SRC), "-to", str(POST_END_SRC), "-i", SCENE, "-vn", "-af",
   "volume=14dB,alimiter=limit=0.9", "-ar", str(SR), "-ac", "2", post_wav)
post = read_wav(post_wav)
gap = np.zeros((int(0.12 * SR), 2))                                   # tiny silence = impact
audio = np.concatenate([song_part, gap, post])
audio += crackle(len(audio))[:, None] * 0.6
n_out = len(audio); fo = int(1.5 * SR); audio[-fo:] *= np.linspace(1, 0, fo)[:, None]
mix_wav = os.path.join(tmp, "mix.wav"); write_wav(mix_wav, audio * 0.9)
TOTAL = n_out / SR
POST_START = CHOP + 0.12
print(f"   total {TOTAL:.2f}s")
if os.environ.get("AUDIO_ONLY"):
    import shutil; shutil.copy(mix_wav, OUT); sys.exit(0)

# ------------------------------------------------------------------ edit decision list on the beat grid
def snap(t): return float(beats[np.argmin(np.abs(beats - t))])
bounds, acc_t = [0.0], 0.0
for w in WANT[:-1]:
    acc_t += w; b = snap(acc_t)
    if b <= bounds[-1] + 0.5: b = bounds[-1] + 60 / bpm
    bounds.append(b)
bounds.append(CHOP)
edl = []
for (s, e), t0, t1 in zip(SHOTS, bounds[:-1], bounds[1:]):
    d = t1 - t0
    if s is None or s + d > e: s = e - d
    edl.append((s, d))
edl.append((CHOP_SRC, POST_END_SRC - CHOP_SRC + 0.12))                 # include the 0.12s gap
for (s, d), t0 in zip(edl, bounds):
    print(f"   {t0:6.2f}s  src {s:7.2f} for {d:5.2f}s")

# ------------------------------------------------------------------ text assets
def ease_out_expo(x): return 1 if x >= 1 else 1 - 2 ** (-10 * max(x, 0))
def ease_in_cubic(x): x = min(max(x, 0), 1); return x ** 3
def ease_out_back(x):
    x = min(max(x, 0), 1); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2

def glyph(ch, font, color=(255, 244, 230), glow=(155, 92, 255)):
    pad = 60; box = list(font.getbbox(ch)); ref = font.getbbox("Ahgjpy")   # shared baseline
    box[1], box[3] = ref[1], ref[3]; w = box[2] - box[0] + 2 * pad; h = box[3] - box[1] + 2 * pad
    img = Image.new("RGBA", (max(w, 1), max(h, 1)), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.text((pad - box[0], pad - box[1]), ch, font=font, fill=color + (255,))
    g = Image.new("RGBA", img.size, glow + (0,)); g.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(18)))
    out = Image.alpha_composite(g, img); out = Image.alpha_composite(g, out)
    return out

ft = ImageFont.truetype(FONT_TITLE, 250); fs = ImageFont.truetype(FONT_SUB, 50); fo_ = ImageFont.truetype(FONT_SUB, 84)
title_glyphs = [glyph(c, ft) for c in TITLE]
spacing = 14
adv = [ft.getlength(c) for c in TITLE]; tw = sum(adv) + spacing * (len(TITLE) - 1)
cx0 = W / 2 - tw / 2; title_pos = []
for c, a_ in zip(TITLE, adv):
    title_pos.append((cx0 + a_ / 2, H / 2 - 60)); cx0 += a_ + spacing
lr = np.random.default_rng(3)
title_rand = [(lr.uniform(-350, 350), lr.uniform(-500, 500), lr.uniform(-30, 30)) for _ in TITLE]
sub_glyphs = [glyph(c, fs, glow=(255, 150, 60)) if c != " " else None for c in SUBTITLE]
sub_adv = [fs.getlength(c) for c in SUBTITLE]
outro_glyphs = [glyph(wd, fo_, glow=(255, 140, 70)) for wd in OUTRO]
outro_adv = [fo_.getlength(wd) for wd in OUTRO]

T_IN0 = 0.15
T_OUT = snap(2.6)                                     # letters fly apart on a beat
print(f"   title flies out at {T_OUT:.2f}s")

def paste(frame, g, cx, cy, scale=1.0, alpha=1.0, blur=0.0, rot=0.0):
    if alpha <= 0.01 or scale <= 0.01: return
    im = g
    if abs(scale - 1) > 1e-3:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if abs(rot) > 0.3: im = im.rotate(rot, Image.BILINEAR, expand=True)
    if blur > 0.4: im = im.filter(ImageFilter.GaussianBlur(blur))
    if alpha < 0.999:
        a_ = im.getchannel("A").point(lambda v: int(v * alpha)); im = im.copy(); im.putalpha(a_)
    frame.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2))) if (
        0 <= int(cx - im.width / 2) and 0 <= int(cy - im.height / 2) and
        int(cx + im.width / 2) < W and int(cy + im.height / 2) < H) else _safe_paste(frame, im, cx, cy)

def _safe_paste(frame, im, cx, cy):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); layer.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)
    frame.alpha_composite(layer)

def beat_pulse(t, beats_, amp, tau=0.14):
    i = np.searchsorted(beats_, t) - 1
    return amp * math.exp(-(t - beats_[i]) / tau) if i >= 0 else 0.0

def draw_text(frame, t):
    # ---- intro kinetic title
    if t < T_OUT + 0.9:
        for i, (g, (px, py), (rx, ry, rr)) in enumerate(zip(title_glyphs, title_pos, title_rand)):
            ti = T_IN0 + i * 0.07; x = ease_out_expo((t - ti) / 0.55)
            if t < ti: continue
            scale = 3.6 - 2.6 * x; blur = 22 * (1 - x); alpha = min(1, (t - ti) / 0.2)
            cx, cy, rot = px + rx * (1 - x), py + ry * (1 - x), rr * (1 - x)
            if t >= T_IN0 + 0.8: scale *= 1 + beat_pulse(t, beats, 0.06)
            to = T_OUT + abs(i - (len(TITLE) - 1) / 2) * 0.04
            if t > to:
                y = ease_in_cubic((t - to) / 0.5)
                dx = px - W / 2; dirx = dx / (abs(dx) + 1e-6)
                cx += dirx * (300 + abs(dx)) * 2.2 * y; cy += (ry * 0.8) * y
                scale *= 1 + 1.8 * y; blur += 24 * y; alpha *= 1 - y; rot += rr * 1.5 * y
            paste(frame, g, cx, cy, scale, alpha, blur, rot)
        # subtitle: tracking-in, then dissolves
        s_in = ease_out_expo((t - 0.75) / 0.8); track = 6 + 40 * (1 - s_in)
        s_out = ease_in_cubic((t - T_OUT) / 0.4)
        total = sum(sub_adv) + track * (len(SUBTITLE) - 1); x0 = W / 2 - total / 2
        for g, a_ in zip(sub_glyphs, sub_adv):
            if g is not None and t > 0.75:
                paste(frame, g, x0 + a_ / 2, H / 2 + 130 + 40 * s_out, 1.0,
                      min(1, (t - 0.75) / 0.4) * (1 - s_out), 6 * (1 - s_in) + 14 * s_out)
            x0 += a_ + track
        # accent line grows from the centre
        ln = ease_out_expo((t - 1.0) / 0.5) * (1 - ease_in_cubic((t - T_OUT) / 0.3))
        if ln > 0.01:
            d = ImageDraw.Draw(frame); half = 260 * ln
            d.rounded_rectangle((W / 2 - half, H / 2 + 88, W / 2 + half, H / 2 + 94), 3, fill=(155, 92, 255, 230))
    # ---- outro tagline: words drop in, staggered
    t0 = TOTAL - 4.2
    if t > t0:
        total = sum(outro_adv) + 22 * (len(OUTRO) - 1)
        rows = [OUTRO[:2], OUTRO[2:]]                  # 2 lines
        k = 0
        for r, row in enumerate(rows):
            rw = sum(outro_adv[k:k + len(row)]) + 22 * (len(row) - 1); x0 = W / 2 - rw / 2
            for j in range(len(row)):
                g = outro_glyphs[k]; a_ = outro_adv[k]; tw_ = t0 + k * 0.2
                x = (t - tw_) / 0.45
                if x > 0:
                    e = ease_out_back(x); fade_ = 1 - ease_in_cubic((t - (TOTAL - 0.7)) / 0.6)
                    paste(frame, g, x0 + a_ / 2, 1480 + r * 115 + 70 * (1 - e), 1.25 - 0.25 * e,
                          min(1, x * 2) * fade_, 10 * max(0, 1 - x * 1.5))
                x0 += a_ + 22; k += 1

# ------------------------------------------------------------------ video
print("4/5 rendering video (this takes a few minutes)")
fc = []
for i, (s, d) in enumerate(edl):
    fc.append(f"[0:v]trim=start={s:.3f}:duration={d:.3f},setpts=PTS-STARTPTS,fps={FPS}[s{i}]")
fc.append("".join(f"[s{i}]" for i in range(len(edl))) + f"concat=n={len(edl)}:v=1:a=0,"
          "colorbalance=rs=0.07:gs=0.02:bs=-0.06:rh=0.04:bh=-0.04,eq=saturation=0.92:contrast=1.04:gamma=1.04,"
          "curves=all='0/0.06 0.5/0.52 1/0.94',split[a][b]")    # lifted blacks = faded lofi look
fc.append("[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:2,eq=brightness=-0.18[bg]")
fc.append("[b]scale=1080:-2:flags=lanczos[fg]")
fc.append("[bg][fg]overlay=(W-w)/2:(H-h)/2,vignette=PI/4.5,noise=alls=9:allf=t,format=rgb24[v]")
dec = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", SCENE, "-filter_complex", ";".join(fc),
                        "-map", "[v]", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                        "-i", mix_wav, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                        "-c:v", "libx264", "-crf", "19", "-preset", "medium", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", OUT],
                       stdin=subprocess.PIPE)

# light leak (warm, drifting), precomputed
yy, xx = np.mgrid[0:H // 8, 0:W // 8].astype(np.float32)
def leak(t):
    cx = W / 8 * (0.85 + 0.15 * math.sin(t * 0.3)); cy = H / 8 * (0.15 + 0.1 * math.cos(t * 0.23))
    g = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * (W / 8 * 0.45) ** 2))
    im = Image.fromarray((g * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
    return np.asarray(im, np.float32)[..., None] / 255 * np.array([255, 150, 70], np.float32)

kicks = np.array([b for k, b in enumerate(beats) if (k - kick_phase) % 2 == 0 and b < CHOP])
cuts = np.array(bounds[1:-1])
n_frames = int(TOTAL * FPS); fsize = W * H * 3
for n in range(n_frames):
    raw = dec.stdout.read(fsize)
    if len(raw) < fsize: break
    t = n / FPS
    img = Image.frombuffer("RGB", (W, H), raw)
    # camera: slow drift per shot + zoom punch on kicks and cuts
    k = int(np.searchsorted(bounds, t, side="right") - 1); k = min(k, len(bounds) - 1)
    t0 = bounds[k] if k < len(bounds) else POST_START
    t1 = bounds[k + 1] if k + 1 < len(bounds) else TOTAL
    prog = (t - t0) / max(t1 - t0, 1e-3)
    z = 1.02 + (0.05 * prog if k % 2 == 0 else 0.05 * (1 - prog))
    if t < CHOP:
        z += beat_pulse(t, kicks, 0.022, 0.16) + beat_pulse(t, cuts, 0.03, 0.12)
    dx = 12 * math.sin(t * 0.4); dy = 10 * math.cos(t * 0.31)
    if CHOP <= t < CHOP + 0.35:                       # shake on the chop
        dx += 28 * math.sin(t * 90) * (1 - (t - CHOP) / 0.35); z += 0.04
    cw, ch = W / z, H / z; x0 = (W - cw) / 2 + dx; y0 = (H - ch) / 2 + dy
    img = img.transform((W, H), Image.AFFINE, (cw / W, 0, x0, 0, ch / H, y0), Image.BILINEAR)
    arr = np.asarray(img, np.float32)
    lk = 0.10 + 0.06 * math.sin(t * 0.7)
    if t < CHOP: lk += beat_pulse(t, beats, 0.05, 0.25)
    arr = arr + (255 - arr) * leak(t) / 255 * lk           # screen blend
    if CHOP <= t < CHOP + 0.3:                             # RGB split hit
        s_ = int(18 * (1 - (t - CHOP) / 0.3)); arr[..., 0] = np.roll(arr[..., 0], s_, 1); arr[..., 2] = np.roll(arr[..., 2], -s_, 1)
    if 0.0 <= t - CHOP < 0.06: arr = arr * 0.4 + 255 * 0.6  # flash
    if t < T_OUT + 0.6:                                    # intro: blurred/dark bg, reveal as letters fly out
        r = 1 - ease_out_expo((t - T_OUT) / 0.6)
        if r > 0.02:
            im2 = Image.fromarray(arr.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(14 * r))
            arr = np.asarray(im2, np.float32) * (1 - 0.45 * r)
    fin = min(1, t / 0.4, (TOTAL - t) / 0.6)
    arr = arr * max(fin, 0)
    frame = Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert("RGBA")
    draw_text(frame, t)
    enc.stdin.write(frame.convert("RGB").tobytes())
    if n % 150 == 0: print(f"   {t:5.1f}s / {TOTAL:.1f}s", flush=True)
enc.stdin.close(); enc.wait(); dec.terminate()
print(f"5/5 done -> {OUT}")
