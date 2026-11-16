#!/usr/bin/env python3
"""
John Wick x "Tujhe Yaad Na Meri Aayi" (karaoke) — beat-synced action reel, 9:16.

  cold open (dialogue, no music) -> song drops with a flash -> montage cut on the
  song's beats (movie SFX kept under the music) -> dialogue break with music ducked
  -> climax (glass room) -> "Be seeing you" ending with the music fading out.

usage: python3 make_jw_reel.py <johnwick.mp4> <song.mp3> [out.mp4]
"""
import math, os, subprocess, sys, tempfile, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

VIDEO, SONG = sys.argv[1], sys.argv[2]
OUT = sys.argv[3] if len(sys.argv) > 3 else "johnwick_reel.mp4"
HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "thanos-kabhi-kabhi", "fonts")
FONT_BIG = os.path.join(FONTS, "Anton-Regular.ttf")
FONT_SM = os.path.join(FONTS, "Poppins-SemiBold.ttf")
W, H, FPS, SR = 1080, 1920, 30, 44100
SONG_DROP = 59.5            # where (in the mp3) the full band kicks in; snapped to a beat

# ---- edit decision list -------------------------------------------------------
# kind: "open"  = dialogue, no music          (start, end) in seconds
#       "beat"  = montage shot, length in beats  (start, beats)
#       "talk"  = dialogue over ducked music  (start, beats)
#       "end"   = ending, original audio + fading music (start, end)
EDL = [
    ("open", 112.9, 120.45, None),
    # --- Chapter 1: home invasion, Red Circle, docks
    ("beat", 17.2, 2, "CHAPTER 1"), ("beat", 26.0, 1, None), ("beat", 35.0, 2, None), ("beat", 40.2, 1, None),
    ("beat", 204.5, 1, None), ("beat", 228.6, 1, None), ("beat", 250.0, 2, None), ("beat", 262.6, 1, None),
    ("beat", 269.0, 1, None), ("beat", 277.0, 1, None), ("beat", 280.0, 2, None),
    ("beat", 337.6, 2, None), ("beat", 362.2, 2, None), ("beat", 378.0, 1, None), ("beat", 404.0, 2, None),
    ("talk", 483.15, 3, None),                                  # "he came back for love, not for you"
    # --- Chapter 2: mirrors
    ("beat", 655.0, 1, "CHAPTER 2"), ("beat", 665.6, 1, None), ("beat", 673.0, 1, None), ("beat", 686.0, 1, None),
    ("beat", 705.4, 2, None), ("beat", 745.0, 1, None), ("beat", 751.0, 1, None), ("beat", 765.2, 1, None),
    # --- Chapter 3: weapons room + glass room climax
    ("beat", 816.0, 1, "CHAPTER 3"), ("beat", 830.0, 1, None), ("beat", 840.2, 1, None), ("beat", 856.0, 1, None),
    ("beat", 865.0, 1, None), ("beat", 910.0, 1, None), ("beat", 930.0, 1, None),
    ("beat", 1000.0, 2, None), ("beat", 1052.0, 1, None), ("beat", 1062.0, 1, None), ("beat", 1088.0, 1, None),
    ("beat", 1110.0, 1, None), ("beat", 1116.0, 1, None), ("beat", 1122.0, 1, None),
    ("beat", 1129.0, 6, None),                                   # glass smash
    ("end", 1147.4, 1161.6, None),                               # "Be seeing you"
]
HOOK = ["Jab koi John Wick ka", "kutta maar de..."]
OUTRO = "Tujhe Yaad Na Meri Aayi"

tmp = tempfile.mkdtemp()
def ff(*a): subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *a], check=True)
def read_wav(p):
    w = wave.open(p); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return a.reshape(-1, w.getnchannels())
def write_wav(p, a):
    a = np.clip(a, -1, 1); w = wave.open(p, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((a * 32767).astype(np.int16).tobytes()); w.close()
def frames(t): return round(t * FPS)

# ---- song beats ---------------------------------------------------------------------
print("1/4 tracking song beats")
song_wav = os.path.join(tmp, "song.wav"); ff("-i", SONG, "-ar", str(SR), "-ac", "2", song_wav)
song = read_wav(song_wav); mono = song.mean(1)
hop, nfft = 512, 2048; ofps = SR / hop
fr = np.lib.stride_tricks.sliding_window_view(mono, nfft)[::hop] * np.hanning(nfft)
spec = np.log1p(20 * np.abs(np.fft.rfft(fr, axis=1)))
env = np.maximum(0, np.diff(spec, axis=0)).sum(1)
env = np.maximum(0, env - np.convolve(env, np.ones(32) / 32, "same")); env /= env.std() + 1e-9
ac = np.correlate(env, env, "full")[len(env) - 1:]; lags = np.arange(len(ac)) / ofps
ok = (lags > 60 / 90) & (lags < 60 / 66); period = lags[ok][np.argmax(ac[ok])] * ofps
score = env.copy(); back = np.full(len(env), -1)
for i in range(len(env)):
    lo, hi = int(i - 2 * period), int(i - period / 2)
    if hi <= 0: continue
    js = np.arange(max(lo, 0), hi); pen = -100 * np.log((i - js) / period) ** 2
    k = np.argmax(score[js] + pen); score[i] += score[js][k] + pen[k]; back[i] = js[k]
i = int(np.argmax(score[-int(period):])) + len(env) - int(period); bf = []
while i >= 0: bf.append(i); i = back[i]
beats = np.array(bf[::-1]) / ofps + (hop + nfft / 2) / SR
print(f"   {60 / np.median(np.diff(beats)):.1f} BPM")
b0 = int(np.argmin(np.abs(beats - SONG_DROP))); S0 = beats[b0]
print(f"   music drops from song {S0:.2f}s")

# ---- timeline: each shot gets (src_start, n_frames, kind, label, out_start) ----------
print("2/4 building the timeline")
shots, t_out, bi = [], 0.0, b0
music_start = None
for kind, s, x, label in EDL:
    if kind in ("open", "end"):
        n = frames(x - s)
    else:
        if music_start is None: music_start = frames(t_out) / FPS
        # length = song time between beat bi and bi+x, in frames, measured from the drop
        n = frames(beats[bi + x] - S0 + music_start) - frames(t_out); bi += x
    shots.append(dict(src=s, n=n, kind=kind, label=label, t0=frames(t_out) / FPS))
    t_out = (frames(t_out) + n) / FPS
TOTAL = t_out
for sh in shots: print(f"   {sh['t0']:6.2f}s {sh['kind']:4s} src {sh['src']:7.2f} {sh['n'] / FPS:5.2f}s {sh['label'] or ''}")
print(f"   total {TOTAL:.2f}s")

# ---- audio ---------------------------------------------------------------------------
print("3/4 mixing audio")
N = int(round(TOTAL * SR)) + SR
orig = np.zeros((N, 2), np.float32); mus_gain = np.zeros(N, np.float32)
GAIN = {"open": (2.0, 0.0), "beat": (0.6, 0.85), "talk": (2.8, 0.2), "end": (3.4, 0.45)}
for k, sh in enumerate(shots):
    d = sh["n"] / FPS; p = os.path.join(tmp, f"o{k}.wav")
    ff("-ss", f"{sh['src']:.3f}", "-t", f"{d:.3f}", "-i", VIDEO, "-vn", "-ar", str(SR), "-ac", "2", p)
    a = read_wav(p); i0 = int(round(sh["t0"] * SR)); n = min(len(a), int(round(d * SR)))
    a = a[:n].copy(); r = min(220, n // 2)
    a[:r] *= np.linspace(0, 1, r)[:, None]; a[n - r:] *= np.linspace(1, 0, r)[:, None]
    og, mg = GAIN[sh["kind"]]
    orig[i0:i0 + n] += a * og; mus_gain[i0:i0 + n] = mg
mus_gain = np.convolve(mus_gain, np.ones(int(0.15 * SR)) / int(0.15 * SR), "same")   # smooth ducking
ms = int(round(music_start * SR))
mus_gain[:ms] = 0
last = shots[-1]; e0 = int(round(last["t0"] * SR)); mus_gain[e0:] *= np.linspace(1, 0, N - e0) ** 0.8
music = np.zeros((N, 2), np.float32); seg = song[int(round(S0 * SR)): int(round(S0 * SR)) + N - ms]
music[ms:ms + len(seg)] = seg
mix = np.tanh((orig + music * mus_gain[:, None]) * 1.1) / 1.1
n_out = int(round(TOTAL * SR)); mix = mix[:n_out]; fo = int(0.8 * SR); mix[-fo:] *= np.linspace(1, 0, fo)[:, None]
mix_wav = os.path.join(tmp, "mix.wav"); write_wav(mix_wav, mix)

# ---- text --------------------------------------------------------------------------
def eo(x): x = min(max(x, 0), 1); return 1 - (1 - x) ** 4
def ei(x): x = min(max(x, 0), 1); return x ** 3
def eback(x):
    x = min(max(x, 0), 1); c1 = 1.70158; c3 = c1 + 1; return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2
def text_img(s, font, fill=(255, 255, 255), glow=(255, 60, 40), stroke=0):
    ref = font.getbbox("Ahgjpy"); box = font.getbbox(s); pad = 40
    w = box[2] - box[0] + 2 * pad; h = ref[3] - ref[1] + 2 * pad
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.text((pad - box[0], pad - ref[1]), s, font=font, fill=fill + (255,), stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    g = Image.new("RGBA", im.size, glow + (0,)); g.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.8)))
    return Image.alpha_composite(g, im)
def paste(frame, im, cx, cy, scale=1.0, alpha=1.0, blur=0.0):
    if alpha <= 0.01: return
    if abs(scale - 1) > 1e-3: im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if blur > 0.4: im = im.filter(ImageFilter.GaussianBlur(blur))
    if alpha < 0.999: im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0)); layer.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)
    frame.alpha_composite(layer)

f_hook = ImageFont.truetype(FONT_SM, 64); f_chap = ImageFont.truetype(FONT_BIG, 110); f_out = ImageFont.truetype(FONT_BIG, 92)
hook_words = [[text_img(w, f_hook, stroke=3) for w in line.split()] for line in HOOK]
hook_adv = [[f_hook.getlength(w) for w in line.split()] for line in HOOK]
chap = {sh["label"]: (text_img(sh["label"], f_chap, glow=(255, 40, 30)), sh["t0"]) for sh in shots if sh["label"]}
outro_img = text_img(OUTRO, f_out, glow=(255, 120, 40))
FG_TOP, FG_H = (H - 760) // 2, 760

def draw_text(frame, t):
    # hook: words pop in one by one during the cold open, top area
    open_end = shots[1]["t0"]
    if t < open_end + 0.2:
        k = 0
        for r, (line, advs) in enumerate(zip(hook_words, hook_adv)):
            lw = sum(advs) + 18 * (len(advs) - 1); x = W / 2 - lw / 2
            for im, a in zip(line, advs):
                tw = 0.3 + k * 0.22; p = (t - tw) / 0.35
                if p > 0:
                    out = ei((t - (open_end - 0.25)) / 0.25)
                    paste(frame, im, x + a / 2, FG_TOP - 230 + r * 92 - 40 * out, 1.4 - 0.4 * eback(p), min(1, p * 2) * (1 - out), 8 * max(0, 1 - p * 2) + 10 * out)
                x += a + 18; k += 1
    # chapter labels: slam in with blur, hold, slide away
    for im, t0 in chap.values():
        dt = t - t0
        if 0 <= dt < 1.6:
            p = eo(dt / 0.25); out = ei((dt - 1.25) / 0.35)
            paste(frame, im, W / 2 + 500 * out, FG_TOP + FG_H + 150, 1.8 - 0.8 * p, p * (1 - out), 18 * (1 - p) + 12 * out)
    # outro title over the last shot's final 3 s
    t0 = TOTAL - 3.4
    if t > t0:
        p = eo((t - t0) / 0.5); out = ei((t - (TOTAL - 0.6)) / 0.5)
        paste(frame, outro_img, W / 2, FG_TOP + FG_H + 170 + 50 * (1 - p), 1.0, p * (1 - out), 12 * (1 - p))

# ---- video ---------------------------------------------------------------------------
print("4/4 rendering video")
inputs, fc = [], []
for k, sh in enumerate(shots):
    inputs += ["-ss", f"{sh['src']:.3f}", "-t", f"{sh['n'] / FPS + 0.5:.3f}", "-i", VIDEO]
    fc.append(f"[{k}:v]fps={FPS},trim=end_frame={sh['n']},setpts=PTS-STARTPTS[v{k}]")
fc.append("".join(f"[v{k}]" for k in range(len(shots))) + f"concat=n={len(shots)}:v=1:a=0,"
          "colorbalance=rs=-0.04:bs=0.06:rh=0.06:bh=-0.05,eq=contrast=1.12:saturation=1.08,split[a][b]")
fc.append("[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=28:2,eq=brightness=-0.22[bg]")
fc.append(f"[b]crop=iw*0.75:ih,scale=1080:{FG_H}:flags=lanczos[fg]")
fc.append(f"[bg][fg]overlay=0:{FG_TOP},vignette=PI/5,noise=alls=5:allf=t,format=rgb24[v]")
dec = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc),
                        "-map", "[v]", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", mix_wav, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                        "-c:v", "libx264", "-crf", "19", "-preset", "medium", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", OUT],
                       stdin=subprocess.PIPE)
cut_times = np.array([sh["t0"] for sh in shots[1:]])
big_hits = {round(shots[1]["t0"], 3)} | {round(sh["t0"], 3) for sh in shots if sh["label"]} | {round(shots[-2]["t0"], 3)}
fsize = W * H * 3
for n in range(frames(TOTAL)):
    raw = dec.stdout.read(fsize)
    if len(raw) < fsize: break
    t = n / FPS; img = Image.frombuffer("RGB", (W, H), raw)
    i = np.searchsorted(cut_times, t, side="right") - 1
    z, dx = 1.0, 0.0
    if i >= 0:
        dt = t - cut_times[i]; kind = shots[i + 1]["kind"]
        if kind == "beat": z += 0.07 * math.exp(-dt / 0.13)                    # zoom punch on each cut
        if round(cut_times[i], 3) in big_hits and dt < 0.3: dx = 22 * math.sin(dt * 80) * (1 - dt / 0.3)
    if shots[-1]["t0"] <= t: z += 0.04 * (t - shots[-1]["t0"]) / (TOTAL - shots[-1]["t0"])  # slow push-in at the end
    if z > 1.001 or dx:
        cw, ch = W / z, H / z
        img = img.transform((W, H), Image.AFFINE, (cw / W, 0, (W - cw) / 2 + dx, 0, ch / H, (H - ch) / 2), Image.BILINEAR)
    if i >= 0 and round(cut_times[i], 3) in big_hits and t - cut_times[i] < 2 / FPS:
        img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), 0.75)  # flash
    fade = min(1, t / 0.3, (TOTAL - t) / 0.8)
    if fade < 1: img = Image.blend(Image.new("RGB", (W, H)), img, max(fade, 0))
    frame = img.convert("RGBA"); draw_text(frame, t)
    enc.stdin.write(frame.convert("RGB").tobytes())
    if n % 300 == 0: print(f"   {t:5.1f}s / {TOTAL:.1f}s", flush=True)
enc.stdin.close(); enc.wait(); dec.terminate()
print(f"done -> {OUT}")
