"""Beat-synced vector lyric video for "Om Namah Shivaya" (Shiv Panchakshar Stotram, Sanskrit + English rap).

Draws Mahadev in meditation on Kailash with skia (vector, anti-aliased), syncs glow, damru,
third eye and flashes to the song's beats, and overlays timed lyrics. Frames are piped to ffmpeg.

usage: python render_video.py AUDIO.mp3 TAKE OUT.mp4 [--w 1920 --h 1080 --fps 30 --start 0 --dur 0]
"""
import argparse
import math
import os
import random
import subprocess
import sys

import numpy as np
import skia
import librosa
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lyrics_timeline import SECTIONS, TIMINGS  # noqa: E402

FONT_DIR = os.environ.get("FONT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts"))

# ----------------------------------------------------------------------------- colours
PALETTES = {  # sky top, sky bottom, accent (rim/halo), particle colour
    "intro":  ((5, 6, 18), (18, 24, 58), (120, 170, 255), (220, 230, 255)),
    "verse":  ((6, 10, 36), (27, 42, 107), (110, 190, 255), (200, 225, 255)),
    "rap":    ((26, 5, 5), (110, 30, 10), (255, 140, 50), (255, 170, 80)),
    "bridge": ((2, 2, 6), (11, 15, 37), (150, 120, 255), (190, 180, 255)),
    "drop":   ((12, 10, 50), (70, 25, 100), (255, 200, 90), (255, 220, 140)),
    "outro":  ((5, 6, 15), (16, 26, 51), (130, 170, 230), (210, 220, 240)),
}


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_c(c1, c2, t):
    return tuple(int(round(lerp(x, y, t))) for x, y in zip(c1, c2))


def argb(c, a=255):
    return skia.ColorSetARGB(int(max(0, min(255, a))), *c)


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ----------------------------------------------------------------------------- timeline
def build_timeline(take, song_len):
    cfg = TIMINGS[take]
    names = [s[0] for s in SECTIONS]
    sections, lines = [], []
    for i, (name, pal, ls) in enumerate(SECTIONS):
        s0 = cfg[name]
        s1 = cfg[names[i + 1]] if i + 1 < len(names) else song_len
        drop = cfg.get("drop")
        if drop is not None and s0 < drop < s1:  # split off an instrumental drop section
            sections.append({"name": name, "pal": pal, "start": s0, "end": drop})
            sections.append({"name": "drop", "pal": "drop", "start": drop, "end": s1})
        else:
            sections.append({"name": name, "pal": pal, "start": s0, "end": s1})
        fixed = cfg.get("line_times", {}).get(name)
        n = len(ls)
        pad = 0.4
        span = (s1 - s0 - 2 * pad) / n
        for j, (text, script, meaning) in enumerate(ls):
            a, b = fixed[j] if fixed else (s0 + pad + j * span, s0 + pad + (j + 1) * span)
            lines.append({"text": text, "script": script, "meaning": meaning,
                          "start": a, "end": b, "section": name})
    return sections, lines


def palette_at(t, sections, fade=1.2):
    for i, s in enumerate(sections):
        if s["start"] <= t < s["end"] or i == len(sections) - 1:
            cur = PALETTES[s["pal"]]
            if i > 0 and t - s["start"] < fade:
                prev = PALETTES[sections[i - 1]["pal"]]
                k = smooth((t - s["start"]) / fade)
                return tuple(lerp_c(p, c, k) for p, c in zip(prev, cur)), s
            return cur, s
    return PALETTES["intro"], sections[0]


# ----------------------------------------------------------------------------- audio analysis
def analyse(audio, fps, n_frames):
    y, sr = librosa.load(audio, sr=22050, mono=True)
    hop = 512
    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    _, beats = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=hop, units="time")
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    S = np.abs(librosa.stft(y, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr)
    bass = S[freqs < 150].mean(axis=0)
    times = librosa.times_like(rms, sr=sr, hop_length=hop)
    ft = np.arange(n_frames) / fps
    loud = np.interp(ft, times, rms / (rms.max() + 1e-9))
    bass_f = np.interp(ft, times, bass / (np.percentile(bass, 99) + 1e-9))
    return np.asarray(beats), np.clip(loud, 0, 1), np.clip(bass_f, 0, 1.5)


def beat_pulse(t, beats, decay=0.16):
    i = np.searchsorted(beats, t) - 1
    if i < 0:
        return 0.0, 0
    dt = t - beats[i]
    return math.exp(-dt / decay), i


# ----------------------------------------------------------------------------- static scenery
class Scenery:
    def __init__(self, W, H, seed=7):
        rnd = random.Random(seed)
        self.W, self.H = W, H
        self.stars = [(rnd.random() * W, rnd.random() * H * 0.7, rnd.uniform(0.6, 2.2) * H / 1080,
                       rnd.uniform(0, 6.28), rnd.uniform(0.5, 2.0)) for _ in range(260)]
        self.particles = [(rnd.random(), rnd.random(), rnd.uniform(0.02, 0.07), rnd.uniform(1, 3.2) * H / 1080,
                           rnd.uniform(0, 6.28)) for _ in range(140)]
        self.mountains = [self._ridge(rnd, base, amp, n) for base, amp, n in
                          ((0.62, 0.20, 9), (0.70, 0.14, 13), (0.80, 0.09, 17))]

    def _ridge(self, rnd, base, amp, n):
        W, H = self.W, self.H
        pts = []
        for i in range(n + 1):
            x = W * i / n
            centre = 1 - abs(i / n - 0.5) * 2  # taller towards the middle (Kailash)
            yv = H * (base - amp * (0.35 + 0.65 * centre) * rnd.uniform(0.55, 1.0))
            pts.append((x, yv))
        return pts


def ridge_path(pts, W, H, dx=0.0):
    p = skia.Path()
    p.moveTo(-50 + dx, H + 10)
    p.lineTo(pts[0][0] - 50 + dx, pts[0][1])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        mx = (x0 + x1) / 2
        p.quadTo(x0 + dx, y0, mx + dx, (y0 + y1) / 2)
    p.lineTo(pts[-1][0] + 50 + dx, pts[-1][1])
    p.lineTo(W + 50 + dx, H + 10)
    p.close()
    return p


# ----------------------------------------------------------------------------- Mahadev figure (local units, origin = seat centre, y down)
def figure_paths():
    def union(a, b):
        return skia.Op(a, b, skia.PathOp.kUnion_PathOp)

    def oval(l, t, r, b):
        o = skia.Path(); o.addOval(skia.Rect.MakeLTRB(l, t, r, b)); return o

    # crossed legs / lap
    body = oval(-285, -120, 285, 25)
    # torso: broad shoulders, tapering waist, widening into the arms resting on the knees
    t = skia.Path()
    t.moveTo(-150, -338)
    t.quadTo(0, -362, 150, -338)                 # shoulders
    t.quadTo(195, -300, 208, -170)               # right upper arm (outer)
    t.quadTo(222, -110, 232, -62)                # right forearm to knee
    t.lineTo(150, -70)
    t.quadTo(0, -95, -150, -70)
    t.lineTo(-232, -62)
    t.quadTo(-222, -110, -208, -170)             # left forearm / upper arm
    t.quadTo(-195, -300, -150, -338)
    t.close()
    body = union(body, t)
    # neck, head, ears
    neck = skia.Path(); neck.addRect(skia.Rect.MakeLTRB(-28, -385, 28, -325))
    body = union(body, neck)
    body = union(body, oval(-58, -505, 58, -362))
    # jata (matted-hair bun), smaller and set on top of the head
    for l, tp, r, b in ((-50, -572, 50, -488), (-34, -622, 34, -558), (-19, -652, 19, -612)):
        body = union(body, oval(l, tp, r, b))
    # hair falling onto the shoulders
    for sgn in (-1, 1):
        h = skia.Path()
        h.moveTo(sgn * 50, -480)
        h.cubicTo(sgn * 92, -440, sgn * 112, -390, sgn * 150, -318)
        h.lineTo(sgn * 122, -318)
        h.cubicTo(sgn * 92, -380, sgn * 72, -410, sgn * 48, -440)
        h.close()
        body = union(body, h)
    return body


def figure_details():
    """Lines drawn on top of the body: arm contours, closed eyes, brows, lips."""
    p = skia.Path()
    for sgn in (-1, 1):
        p.moveTo(sgn * 128, -285); p.quadTo(sgn * 170, -200, sgn * 178, -95)        # inner arm line
        p.moveTo(sgn * 150, -80); p.quadTo(sgn * 90, -40, sgn * 20, -45)            # crossed-leg fold
        p.moveTo(sgn * 12, -428); p.quadTo(sgn * 26, -420, sgn * 40, -428)          # closed eyes
        p.moveTo(sgn * 10, -441); p.quadTo(sgn * 26, -449, sgn * 44, -441)          # brows
    p.moveTo(-12, -385); p.quadTo(0, -380, 12, -385)                                # lips
    p.moveTo(0, -420); p.lineTo(-4, -400); p.lineTo(4, -400)                        # nose
    return p


def crescent_path():
    a = skia.Path(); a.addCircle(48, -585, 30)
    b = skia.Path(); b.addCircle(62, -597, 26)
    return skia.Op(a, b, skia.PathOp.kDifference_PathOp)


def trishul_path():
    p = skia.Path()
    p.moveTo(0, 40); p.lineTo(0, -620)                       # shaft
    p.moveTo(0, -620); p.lineTo(0, -790)                     # centre spear
    p.moveTo(-11, -770); p.lineTo(0, -805); p.lineTo(11, -770)
    p.moveTo(-60, -625); p.quadTo(0, -600, 60, -625)         # cross-guard
    for sgn in (-1, 1):                                      # side prongs
        p.moveTo(sgn * 10, -628)
        p.cubicTo(sgn * 85, -640, sgn * 85, -700, sgn * 62, -760)
        p.moveTo(sgn * 52, -745); p.lineTo(sgn * 62, -775); p.lineTo(sgn * 72, -745)
    return p


def damru_path():
    p = skia.Path()
    p.moveTo(-26, -34); p.lineTo(26, -34); p.lineTo(3, 0); p.lineTo(26, 34); p.lineTo(-26, 34); p.lineTo(-3, 0); p.close()
    return p


# ----------------------------------------------------------------------------- text cache
class TextCache:
    def __init__(self, H, W):
        self.H = H
        self.cache = {}
        k = H / 1080 if H <= W * 1.2 else W / 1080 * 1.25
        self.f_dev = self._font("NotoSansDevanagari.ttf", int(58 * k), b"SemiBold")
        self.f_dev_big = self._font("NotoSansDevanagari.ttf", int(120 * k), b"Bold")
        self.f_en = self._font("Montserrat.ttf", int(50 * k), b"ExtraBold")
        self.f_mean = self._font("Montserrat.ttf", int(28 * k), b"Medium")
        self.f_title = self._font("Cinzel.ttf", int(44 * k), b"Bold")

    def _font(self, name, size, var):
        f = ImageFont.truetype(os.path.join(FONT_DIR, name), size)
        f._var = var
        try:
            f.set_variation_by_name(var)
        except Exception:
            pass
        return f

    def _resize(self, font, size):
        f = font.font_variant(size=size)
        try:
            f.set_variation_by_name(font._var)
        except Exception:
            pass
        f._var = font._var
        return f

    def get(self, text, font, colour, max_w=None, glow=None):
        key = (text, id(font), colour, max_w, glow)
        if key in self.cache:
            return self.cache[key]
        rows = [text]
        if max_w and font.getlength(text) > max_w and " " in text:  # wrap onto two lines
            words = text.split(" ")
            best = min(range(1, len(words)),
                       key=lambda i: abs(font.getlength(" ".join(words[:i])) - font.getlength(" ".join(words[i:]))))
            rows = [" ".join(words[:best]), " ".join(words[best:])]
        if max_w:  # shrink only if a row still does not fit
            size = font.size
            while max(font.getlength(r) for r in rows) > max_w and size > 12:
                size -= 2
                font = self._resize(font, size)
        asc, desc = font.getmetrics()
        line_h = int((asc + desc) * 1.08)
        widths = [font.getlength(r) for r in rows]
        pad = int(self.H * 0.03)
        w, h = int(max(widths) + 2 * pad), int(line_h * len(rows) + 2 * pad)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for i, r in enumerate(rows):  # dark outline for legibility, each row centred
            d.text(((w - widths[i]) / 2, pad + i * line_h), r, font=font, fill=colour + (255,),
                   stroke_width=max(2, int(self.H / 360)), stroke_fill=(0, 0, 0, 200))
        img = skia.Image.fromarray(np.array(im), colorType=skia.ColorType.kRGBA_8888_ColorType,
                                   alphaType=skia.AlphaType.kUnpremul_AlphaType)
        self.cache[key] = (img, w, h)
        return self.cache[key]


# ----------------------------------------------------------------------------- frame renderer
class Renderer:
    def __init__(self, W, H, fps, sections, lines, beats, loud, bass):
        self.W, self.H, self.fps = W, H, fps
        self.sections, self.lines = sections, lines
        self.beats, self.loud, self.bass = beats, loud, bass
        self.scn = Scenery(W, H)
        self.text = TextCache(H, W)
        self.surface = skia.Surface(W, H)
        self.body = figure_paths()
        self.details = figure_details()
        self.crescent = crescent_path()
        self.trishul = trishul_path()
        self.damru = damru_path()
        self.portrait = H > W
        k = min(W / 1920, H / 1080) if not self.portrait else W / 1080
        self.fig_scale = (0.78 if not self.portrait else 0.95) * (H / 1080 if not self.portrait else k)
        self.fig_x = W * 0.5
        self.fig_y = H * (0.80 if not self.portrait else 0.66)
        self.drop_t = next(s["start"] for s in sections if s["pal"] == "drop")
        self.drop_end = max(s["end"] for s in sections if s["pal"] == "drop")
        self.rap_starts = [s["start"] for s in sections if s["pal"] == "rap"]

    # -- helpers
    def paint(self, c, a=255, **kw):
        return skia.Paint(AntiAlias=True, Color=argb(c, a), **kw)

    def glow_paint(self, c, a, sigma, **kw):
        p = self.paint(c, a, **kw)
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, sigma))
        return p

    # -- layers
    def sky(self, cv, pal, t, energy):
        top, bot = pal[0], pal[1]
        sh = skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(0, self.H)], [argb(top), argb(bot)])
        cv.drawPaint(skia.Paint(Shader=sh))
        for x, y, r, ph, sp in self.scn.stars:
            a = 120 + 120 * math.sin(t * sp + ph)
            cv.drawCircle(x, y, r, self.paint((235, 240, 255), a * (0.6 + 0.4 * energy)))

    def halo(self, cv, pal, t, pulse, energy, drop_amt):
        cx, cy = self.fig_x, self.fig_y - 430 * self.fig_scale
        R = 300 * self.fig_scale * (1 + 0.04 * pulse)
        acc = pal[2]
        sh = skia.GradientShader.MakeRadial(skia.Point(cx, cy), R * 1.9,
                                            [argb(acc, 150 + 80 * pulse + 60 * drop_amt), argb(acc, 40), argb(acc, 0)],
                                            [0.0, 0.45, 1.0])
        cv.drawCircle(cx, cy, R * 1.9, skia.Paint(AntiAlias=True, Shader=sh))
        # moon disc
        cv.drawCircle(cx, cy, R * 0.92, self.paint(lerp_c(acc, (255, 255, 255), 0.65), 70 + 40 * energy))
        # rotating mandala rings
        cv.save(); cv.translate(cx, cy)
        ring = self.paint(lerp_c(acc, (255, 255, 255), 0.4), 110 + 120 * pulse,
                          Style=skia.Paint.kStroke_Style, StrokeWidth=2.2 * self.fig_scale)
        cv.save(); cv.rotate(t * 6)
        for i in range(24):
            cv.rotate(15)
            p = skia.Path()
            p.moveTo(0, -R * 1.02); p.quadTo(R * 0.09, -R * 1.18, 0, -R * 1.30); p.quadTo(-R * 0.09, -R * 1.18, 0, -R * 1.02)
            cv.drawPath(p, ring)
        cv.restore()
        cv.save(); cv.rotate(-t * 9)
        for i in range(12):
            cv.rotate(30)
            p = skia.Path()
            p.moveTo(0, -R * 1.38); p.lineTo(0, -R * 1.52)
            p.moveTo(-R * 0.04, -R * 1.47); p.lineTo(0, -R * 1.55); p.lineTo(R * 0.04, -R * 1.47)
            cv.drawPath(p, ring)
        cv.restore()
        cv.drawCircle(0, 0, R * 1.34, ring)
        cv.restore()

    def mountains(self, cv, pal, t):
        cols = [lerp_c(pal[1], (0, 0, 0), k) for k in (0.35, 0.55, 0.75)]
        for i, (pts, col) in enumerate(zip(self.scn.mountains, cols)):
            dx = math.sin(t * 0.05 + i) * self.W * 0.004 * (i + 1)
            path = ridge_path(pts, self.W, self.H, dx)
            cv.drawPath(path, self.paint(col))
            if i == 0:  # snowy rim light on the far range
                cv.drawPath(path, self.paint((220, 230, 255), 70, Style=skia.Paint.kStroke_Style, StrokeWidth=2))

    def ganga(self, cv, t, pal):
        s = self.fig_scale
        cv.save(); cv.translate(self.fig_x, self.fig_y); cv.scale(s, s)
        for i in range(7):
            p = skia.Path()
            off = i * 7
            p.moveTo(-5, -680)
            p.cubicTo(-120 - off, -820 - off, -330 - off, -760, -420 - off, -560 + off)
            p.cubicTo(-470 - off, -420, -500, -250, -520 - off, 40)
            if i == 0:  # soft glow under the water
                cv.drawPath(p, self.glow_paint((140, 210, 255), 70, 14, Style=skia.Paint.kStroke_Style, StrokeWidth=40))
            dash = skia.DashPathEffect.Make([60 + i * 9, 30 + i * 5], -(t * 160 + i * 37) % (90 + i * 14))
            paint = self.paint((190, 235, 255), 150 - i * 15, Style=skia.Paint.kStroke_Style,
                               StrokeWidth=max(1.5, 4.5 - i * 0.5), StrokeCap=skia.Paint.kRound_Cap, PathEffect=dash)
            cv.drawPath(p, paint)
        cv.restore()

    def figure(self, cv, pal, t, pulse, drop_amt, beat_idx):
        s = self.fig_scale
        acc = pal[2]
        breath = 1 + 0.006 * math.sin(t * 0.9)
        cv.save(); cv.translate(self.fig_x, self.fig_y); cv.scale(s, s * breath)
        # rim glow
        cv.drawPath(self.body, self.glow_paint(acc, 170 + 70 * pulse, 18, Style=skia.Paint.kStroke_Style, StrokeWidth=14))
        # Shiva's blue body
        sh = skia.GradientShader.MakeLinear([skia.Point(0, -680), skia.Point(0, 30)],
                                            [argb((48, 92, 160)), argb((16, 32, 72))])
        cv.drawPath(self.body, skia.Paint(AntiAlias=True, Shader=sh))
        cv.drawPath(self.body, self.paint(lerp_c(acc, (255, 255, 255), 0.5), 160,
                                          Style=skia.Paint.kStroke_Style, StrokeWidth=3))
        # face, arm and leg contours
        cv.drawPath(self.details, self.paint((10, 22, 50), 230, Style=skia.Paint.kStroke_Style, StrokeWidth=3.5,
                                             StrokeCap=skia.Paint.kRound_Cap))
        for sgn in (-1, 1):  # earrings and hands in chin mudra on the knees
            cv.drawCircle(sgn * 60, -400, 8, self.paint((255, 205, 110)))
            cv.drawCircle(sgn * 226, -66, 16, self.paint((70, 120, 190)))
            cv.drawCircle(sgn * 226, -66, 7, self.paint((230, 235, 250), 200, Style=skia.Paint.kStroke_Style, StrokeWidth=2.5))
        # ash tilak (three lines) + third eye
        tl = self.paint((235, 235, 240), 220, Style=skia.Paint.kStroke_Style, StrokeWidth=4, StrokeCap=skia.Paint.kRound_Cap)
        for dy in (-482, -473, -464):
            cv.drawLine(-32, dy, 32, dy, tl)
        eye_open = 0.25 + 0.75 * drop_amt
        eye = skia.Path(); eye.addOval(skia.Rect.MakeLTRB(-5 - 3 * eye_open, -456 - 11, 5 + 3 * eye_open, -456 + 11))
        cv.drawPath(eye, self.glow_paint((255, 120, 40), 120 + 135 * max(pulse, drop_amt), 8 + 14 * drop_amt))
        cv.drawPath(eye, self.paint((255, 200, 120), 230))
        if drop_amt > 0.05:  # rays from the third eye at the drop
            cv.save(); cv.translate(0, -456); cv.rotate(t * 20)
            ray = self.glow_paint((255, 190, 90), 90 * drop_amt, 6, Style=skia.Paint.kStroke_Style, StrokeWidth=5)
            for i in range(12):
                cv.rotate(30)
                cv.drawLine(0, -40, 0, -40 - 160 * drop_amt * (0.7 + 0.3 * pulse), ray)
            cv.restore()
        # crescent moon
        cv.drawPath(self.crescent, self.glow_paint((255, 250, 220), 200, 10))
        cv.drawPath(self.crescent, self.paint((255, 252, 235)))
        # rudraksha mala
        for i in range(19):
            a = math.pi * (0.15 + 0.7 * i / 18)
            cv.drawCircle(math.cos(a) * 92, -345 + math.sin(a) * 120, 6.5, self.paint((120, 60, 30)))
        # serpent around the neck, hood rising over the right shoulder
        snake = skia.Path()
        snake.moveTo(-78, -340); snake.cubicTo(-55, -298, 55, -298, 80, -338)
        snake.cubicTo(100, -365, 92, -410, 108, -445)
        sp = self.paint((40, 150, 110), 255, Style=skia.Paint.kStroke_Style, StrokeWidth=17, StrokeCap=skia.Paint.kRound_Cap)
        cv.drawPath(snake, self.glow_paint((90, 255, 190), 120, 6, Style=skia.Paint.kStroke_Style, StrokeWidth=20))
        cv.drawPath(snake, sp)
        cv.drawPath(snake, self.paint((150, 230, 170), 160, Style=skia.Paint.kStroke_Style, StrokeWidth=3,
                                      PathEffect=skia.DashPathEffect.Make([6, 10], 0)))
        hood = skia.Path(); hood.addOval(skia.Rect.MakeLTRB(84, -488, 134, -432))
        cv.drawPath(hood, self.paint((40, 150, 110)))
        cv.drawPath(hood, self.paint((150, 230, 170), 200, Style=skia.Paint.kStroke_Style, StrokeWidth=2.5))
        for ex in (100, 118):
            cv.drawCircle(ex, -462, 3.2, self.paint((255, 230, 120)))
        cv.restore()
        # trishul with damru (to the figure's right)
        cv.save(); cv.translate(self.fig_x + 340 * s, self.fig_y); cv.scale(s, s)
        gold = (255, 205, 110)
        cv.drawPath(self.trishul, self.glow_paint(gold, 120 + 120 * pulse, 10, Style=skia.Paint.kStroke_Style, StrokeWidth=12))
        cv.drawPath(self.trishul, self.paint(gold, 255, Style=skia.Paint.kStroke_Style, StrokeWidth=7,
                                             StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join))
        shake = math.sin(t * 38) * 14 * pulse * (1 if beat_idx % 2 else -1)
        cv.save(); cv.translate(0, -560); cv.rotate(shake)
        cv.drawPath(self.damru, self.paint((150, 70, 40)))
        cv.drawPath(self.damru, self.paint((255, 220, 160), 230, Style=skia.Paint.kStroke_Style, StrokeWidth=3))
        for sgn in (-1, 1):  # beaters on strings
            bx = sgn * (30 + 10 * pulse)
            cv.drawLine(sgn * 3, 0, bx, 12 + 8 * pulse, self.paint((240, 230, 210), 220, StrokeWidth=2))
            cv.drawCircle(bx, 12 + 8 * pulse, 5, self.paint((240, 230, 210)))
        cv.restore()
        cv.restore()

    def rock(self, cv, pal):
        s = self.fig_scale
        p = skia.Path()
        x, y = self.fig_x, self.fig_y
        p.moveTo(x - 700 * s, self.H + 5)
        p.cubicTo(x - 560 * s, y + 70 * s, x - 420 * s, y + 5 * s, x - 300 * s, y + 12 * s)
        p.lineTo(x + 320 * s, y + 12 * s)
        p.cubicTo(x + 450 * s, y + 8 * s, x + 600 * s, y + 80 * s, x + 760 * s, self.H + 5)
        p.close()
        sh = skia.GradientShader.MakeLinear([skia.Point(0, y), skia.Point(0, self.H)],
                                            [argb(lerp_c(pal[1], (0, 0, 0), 0.7)), argb((0, 0, 0))])
        cv.drawPath(p, skia.Paint(AntiAlias=True, Shader=sh))

    def particles(self, cv, pal, t, energy):
        for x0, y0, sp, r, ph in self.scn.particles:
            y = (y0 - t * sp) % 1.0
            x = x0 + 0.015 * math.sin(t * 0.6 + ph)
            a = (90 + 120 * energy) * (0.5 + 0.5 * math.sin(t * 2 + ph))
            cv.drawCircle(x * self.W, y * self.H, r, self.paint(pal[3], a))

    def lyrics(self, cv, t):
        W, H = self.W, self.H
        base_y = H * (0.865 if not self.portrait else 0.83)
        for ln in self.lines:
            if not (ln["start"] <= t <= ln["end"]):
                continue
            a_in = smooth((t - ln["start"]) / 0.25)
            a_out = smooth((ln["end"] - t) / 0.2)
            alpha = min(a_in, a_out)
            rise = (1 - a_in) * H * 0.02
            if ln["script"] == "dev":
                img, w, h = self.text.get(ln["text"], self.text.f_dev, (255, 226, 160), max_w=W * 0.9)
            else:
                img, w, h = self.text.get(ln["text"], self.text.f_en, (255, 255, 255), max_w=W * 0.9)
            p = skia.Paint(Alphaf=alpha)
            cv.drawImage(img, (W - w) / 2, base_y - h / 2 + rise, skia.SamplingOptions(), p)
            if ln["meaning"]:
                mi, mw, mh = self.text.get(ln["meaning"], self.text.f_mean, (200, 215, 240), max_w=W * 0.9)
                cv.drawImage(mi, (W - mw) / 2, base_y + h * 0.42 + rise, skia.SamplingOptions(), skia.Paint(Alphaf=alpha * 0.9))

    def titles(self, cv, t, song_len):
        W, H = self.W, self.H
        a = smooth(1 - (t - 4.5) / 1.5) if t > 4.5 else smooth(t / 1.2)
        if a > 0.01:
            img, w, h = self.text.get("ॐ नमः शिवाय", self.text.f_dev_big, (255, 230, 170))
            cv.drawImage(img, (W - w) / 2, H * 0.03, skia.SamplingOptions(), skia.Paint(Alphaf=a))
            sub, sw, sh = self.text.get("SHIV PANCHAKSHAR STOTRAM  ·  DEVOTIONAL RAP", self.text.f_title, (230, 235, 255))
            cv.drawImage(sub, (W - sw) / 2, H * 0.03 + h * 0.95, skia.SamplingOptions(), skia.Paint(Alphaf=a * 0.9))
        a2 = smooth((t - (song_len - 7)) / 2.0)
        if a2 > 0.01:
            img, w, h = self.text.get("हर हर महादेव", self.text.f_dev_big, (255, 230, 170))
            cv.drawImage(img, (W - w) / 2, H * 0.12, skia.SamplingOptions(), skia.Paint(Alphaf=a2))

    def flashes(self, cv, t, pal):
        W, H = self.W, self.H
        a = 0.0
        for st in [self.drop_t] + self.rap_starts:
            if st <= t < st + 0.9:
                a = max(a, (1 - (t - st) / 0.9) ** 2 * (0.85 if st == self.drop_t else 0.45))
        if a > 0:
            cv.drawPaint(self.paint((255, 245, 225), 255 * a))
        if self.drop_t <= t < self.drop_t + 1.6:  # shockwave ring from the third eye
            k = (t - self.drop_t) / 1.6
            cx, cy = self.fig_x, self.fig_y - 456 * self.fig_scale
            cv.drawCircle(cx, cy, k * max(W, H) * 0.9,
                          self.glow_paint((255, 210, 140), 200 * (1 - k), 12, Style=skia.Paint.kStroke_Style,
                                          StrokeWidth=10 * (1 - k) + 2))

    def vignette(self, cv):
        W, H = self.W, self.H
        sh = skia.GradientShader.MakeRadial(skia.Point(W / 2, H / 2), max(W, H) * 0.75,
                                            [argb((0, 0, 0), 0), argb((0, 0, 0), 0), argb((0, 0, 0), 190)],
                                            [0.0, 0.55, 1.0])
        cv.drawPaint(skia.Paint(Shader=sh))

    def frame(self, fi, song_len):
        t = fi / self.fps
        pal, sec = palette_at(t, self.sections)
        pulse, bi = beat_pulse(t, self.beats)
        if bi % 4 == 0:
            pulse *= 1.25
        pulse = min(1.0, pulse * (0.4 + 0.8 * self.bass[fi]))
        energy = float(self.loud[fi])
        drop_amt = 0.0
        if sec["pal"] == "drop":
            drop_amt = smooth((t - self.drop_t) / 1.0) * smooth((self.drop_end - t) / 2.0)
        cv = self.surface.getCanvas()
        cv.save()
        zoom = 1 + 0.012 * pulse + 0.03 * drop_amt
        cv.translate(self.W / 2, self.H / 2); cv.scale(zoom, zoom); cv.translate(-self.W / 2, -self.H / 2)
        self.sky(cv, pal, t, energy)
        self.halo(cv, pal, t, pulse, energy, drop_amt)
        self.mountains(cv, pal, t)
        self.ganga(cv, t, pal)
        self.rock(cv, pal)
        self.figure(cv, pal, t, pulse, drop_amt, bi)
        self.particles(cv, pal, t, energy)
        cv.restore()
        self.vignette(cv)
        self.flashes(cv, t, pal)
        self.lyrics(cv, t)
        self.titles(cv, t, song_len)
        fade = min(smooth(t / 1.0), smooth((song_len - t) / 2.0))
        if fade < 1:
            cv.drawPaint(self.paint((0, 0, 0), 255 * (1 - fade)))
        return self.surface.makeImageSnapshot().toarray(colorType=skia.ColorType.kRGBA_8888_ColorType)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio"); ap.add_argument("take"); ap.add_argument("out")
    ap.add_argument("--w", type=int, default=1920); ap.add_argument("--h", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--start", type=float, default=0.0); ap.add_argument("--dur", type=float, default=0.0)
    ap.add_argument("--still", type=float, default=None, help="render a single PNG at this time")
    a = ap.parse_args()

    song_len = librosa.get_duration(path=a.audio)
    n_frames = int(song_len * a.fps)
    sections, lines = build_timeline(a.take, song_len)
    beats, loud, bass = analyse(a.audio, a.fps, n_frames)
    r = Renderer(a.w, a.h, a.fps, sections, lines, beats, loud, bass)

    if a.still is not None:
        Image.fromarray(r.frame(int(a.still * a.fps), song_len)).convert("RGB").save(a.out)
        print("saved", a.out)
        return

    f0 = int(a.start * a.fps)
    f1 = n_frames if a.dur <= 0 else min(n_frames, f0 + int(a.dur * a.fps))
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{a.w}x{a.h}", "-r", str(a.fps), "-i", "-",
           "-ss", f"{f0 / a.fps:.3f}", "-t", f"{(f1 - f0) / a.fps:.3f}", "-i", a.audio,
           "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", a.out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fi in range(f0, f1):
        ff.stdin.write(r.frame(fi, song_len).tobytes())
        if (fi - f0) % (a.fps * 10) == 0:
            print(f"frame {fi - f0}/{f1 - f0}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("done", a.out, "rc", ff.returncode)


if __name__ == "__main__":
    main()
