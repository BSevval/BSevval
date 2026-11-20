"""Honey Hua — efektli reel (v2).

v1'in eşleştirme tablosu aynen kullanılır; üstüne kare kare işlenen bir katman eklenir:
kinetik tipografi (kelime kelime beliren, altın vurgulu yazılar), yavaş push-in,
sıcak ışık sızıntıları (light leak), halation/bloom, film greni, vinyet,
altın flaş geçişler ve sahneye özel anlar:
  - "unpredictable" kelimesinde kısa bir RGB glitch
  - "I collect moments" → kare donar, deklanşör flaşı, polaroid'e dönüşür
  - "behind the camera" → kamera vizörü (REC, timecode, köşe çizgileri)
  - "I'm the story" → sinematik siyah bantlar kayarak girer
  - kapanış → siyah üzerinde "honey." imzası

Çıktı: output/honey_reel_<tarih>_v2.mp4
"""
import datetime
import math
import multiprocessing as mp
import pathlib
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent
INPUT, OUTPUT, FONTS = ROOT / "input", ROOT / "output", ROOT / "fonts"
MUSIC = ROOT / "music" / "crossing_the_rubicon.mp3"
MUSIC_START = 1.0
W, H, FPS = 1080, 1920, 24

GRADE = ("colorbalance=rs=0.03:bs=-0.04:rm=0.02:bm=-0.03:rh=0.02:bh=-0.02,"
         "eq=contrast=1.04:saturation=1.03")

CREAM = (255, 241, 214)
GOLD_TOP, GOLD_BOT = (247, 221, 150), (201, 146, 62)

FONT_FILES = {
    "serif": "cormorant-garamond-latin-500-italic.woff",
    "serif_up": "cormorant-garamond-latin-500-normal.woff",
    "script": "great-vibes-latin-400-normal.woff",
    "sans": "montserrat-latin-300-normal.woff",
    "sans_b": "montserrat-latin-500-normal.woff",
}

# Yazı stilleri: (font, boyut, dolgu, parıltı)
STYLES = {
    "body": ("serif", 74, "cream", False),
    "small": ("serif", 60, "cream", False),
    "emph": ("serif", 118, "gold", True),
    "huge": ("serif", 150, "gold", True),
    "script": ("script", 190, "gold", True),
    "script_m": ("script", 150, "gold", True),
    "ui": ("sans_b", 56, "cream", False),
    "big": ("serif", 128, "gold", True),
}

# Satır: (görünme zamanı sn, [(metin, stil), ...]) — metin Şevval'in metninin aynısı,
# sadece satırlara bölünüp stillendirildi.
SEGMENTS = [
    dict(clip="video.mp4", start=2.0, dur=2.0, cx=0.50, zoom=(1.10, 1.02),
         leak=0.5, y=0.70,
         lines=[(0.15, [("Hi, I'm", "body")]),
                (0.45, [("Honey Hua.", "script")])]),
    dict(clip="video (4).mp4", start=0.0, dur=4.8, cx=0.54, zoom=(1.0, 1.08),
         flash_in=True, y=0.74, glitch="unpredictable,",
         lines=[(0.2, [("A little curious,", "body")]),
                (1.0, [("a little", "body"), ("unpredictable,", "emph")]),
                (2.2, [("and always chasing", "body")]),
                (3.0, [("something", "body"), ("beautiful.", "emph")])]),
    dict(clip="video (3).mp4", start=0.0, dur=1.5, cx=0.51, zoom=(1.0, 1.05),
         freeze=1.9, y=0.84,
         lines=[(0.2, [("I collect", "body"), ("moments,", "emph")]),
                (1.9, [("not things.", "body")])]),
    dict(clip="mp_ (1).mp4", start=0.5, dur=6.6, cx=0.45, zoom=(1.0, 1.06),
         y=0.70,
         lines=[(0.15, [("I find stories in", "body"), ("places,", "emph")]),
                (1.2, [("colors", "emph"), ("in cultures,", "body")]),
                (3.6, [("and", "small"), ("inspiration", "emph"), ("in the most", "small")]),
                (4.6, [("unexpected corners of the world.", "small")])]),
    dict(clip="video.mp4", start=0.0, dur=2.3, cx=0.50, zoom=(1.0, 1.04),
         viewfinder=True, flash_in=True, y=0.78,
         lines=[(0.2, [("Sometimes I'm", "ui")]),
                (0.6, [("behind the camera.", "ui")])]),
    dict(clip="video (2).mp4", start=0.0, dur=2.6, cx=0.50, zoom=(1.08, 1.0),
         letterbox=True, flash_in=True, y=0.86,
         lines=[(0.3, [("Sometimes I'm", "small")]),
                (0.7, [("the story.", "script_m")])]),
    dict(clip="videomp_.mp4", start=4.4, dur=3.6, cx=0.48, speed=0.82,
         zoom=(1.0, 1.06), leak=1.0, y=0.72,
         lines=[(0.2, [("I believe life is too", "body")]),
                (1.1, [("beautiful", "huge")]),
                (2.2, [("to be lived in just one way.", "small")])]),
    dict(clip="video (1).mp4", start=0.0, dur=5.6, cx=0.50, zoom=(1.0, 1.07),
         y=0.68,
         lines=[(0.15, [("So, I'm here to", "body")]),
                (0.9, [("explore,", "emph")]),
                (1.5, [("create,", "emph")]),
                (2.1, [("experiment,", "emph")]),
                (3.2, [("and maybe inspire you along the way.", "small")])]),
    dict(clip="videok.mp4", start=0.0, dur=2.4, cx=0.50, zoom=(1.12, 1.0),
         flash_in=True, track=True, y=0.80,
         lines=[(0.25, [("This is my world.", "big")])]),
    dict(clip="videomp_.mp4", start=0.5, dur=2.2, cx=0.49, zoom=(1.0, 1.08),
         leak=1.0, y=0.78,
         lines=[(0.15, [("And we're just", "body")]),
                (0.7, [("getting started.", "emph")])]),
    dict(clip="video.mp4", start=4.0, dur=2.0, cx=0.50, zoom=(1.0, 1.05),
         flash_in=True, leak=0.6, y=0.74,
         lines=[(0.15, [("I'm", "body")]),
                (0.35, [("Honey Hua.", "script")])]),
    dict(clip="video.mp4", start=6.0, dur=2.0, cx=0.50, zoom=(1.05, 1.09),
         leak=0.4, y=0.80, fade_out=0.6,
         lines=[(0.2, [("Nice to meet you.", "body")])]),
    dict(endcard=True, dur=2.0),
]


# ---------------------------------------------------------------- yardımcılar
def ease(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


_font_cache = {}


def font(name, size):
    k = (name, size)
    if k not in _font_cache:
        _font_cache[k] = ImageFont.truetype(str(FONTS / FONT_FILES[name]), size)
    return _font_cache[k]


def gold_gradient(w, h):
    t = np.linspace(0, 1, h)[:, None, None]
    top, bot = np.array(GOLD_TOP), np.array(GOLD_BOT)
    g = top * (1 - t) + bot * t
    return np.broadcast_to(g, (h, w, 3)).astype(np.uint8)


_tok_cache = {}


def token(text, style, tracking=0):
    """Tek kelime/grup için RGBA görsel (gölge + parıltı + altın gradyan dahil)."""
    k = (text, style, tracking)
    if k in _tok_cache:
        return _tok_cache[k]
    fname, size, fill, glow = STYLES[style]
    f = font(fname, size)
    pad = 40
    if tracking:
        widths = [f.getlength(c) + tracking for c in text]
        tw = int(sum(widths))
    else:
        tw = int(f.getlength(text))
    asc, desc = f.getmetrics()
    w, h = tw + 2 * pad, asc + desc + 2 * pad
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    if tracking:
        x = pad
        for c, cw in zip(text, widths):
            d.text((x, pad), c, font=f, fill=255)
            x += cw
    else:
        d.text((pad, pad), text, font=f, fill=255)
    m = np.asarray(mask, dtype=np.float32) / 255
    if fill == "gold":
        rgb = gold_gradient(w, h).astype(np.float32)
    else:
        rgb = np.broadcast_to(np.array(CREAM, np.float32), (h, w, 3))
    # yumuşak gölge
    sh = np.asarray(mask.filter(ImageFilter.GaussianBlur(6)), np.float32) / 255 * 0.55
    sh = np.roll(np.roll(sh, 3, 0), 2, 1)
    out_a = m + sh * (1 - m)
    out_rgb = (rgb * m[..., None]) / np.maximum(out_a[..., None], 1e-4)
    if glow:
        gl = np.asarray(mask.filter(ImageFilter.GaussianBlur(18)), np.float32) / 255 * 0.6
        gl_rgb = np.array((255, 196, 110), np.float32)
        a2 = out_a + gl * (1 - out_a)
        out_rgb = (out_rgb * out_a[..., None] + gl_rgb * (gl * (1 - out_a))[..., None]) \
            / np.maximum(a2[..., None], 1e-4)
        out_a = a2
    arr = np.dstack([np.clip(out_rgb, 0, 255), out_a * 255]).astype(np.uint8)
    res = (arr, pad, asc)
    _tok_cache[k] = res
    return res


def layout(seg):
    """Satırları ortalı bir bloğa yerleştir: her kelime için (x, y, metin, stil, t_in)."""
    tr = 6 if seg.get("track") else 0
    rows = []
    for t0, toks in seg["lines"]:
        words = []
        for text, style in toks:
            for wtxt in text.split(" "):
                words.append((wtxt, style))
        fname_sizes = [STYLES[s] for _, s in words]
        space = max(font(fn, sz).getlength(" ") for fn, sz, _, _ in fname_sizes)
        widths = [token(wt, st, tr)[0].shape[1] - 2 * token(wt, st, tr)[1] for wt, st in words]
        asc = max(token(wt, st)[2] for wt, st in words)
        line_h = max(STYLES[st][1] for _, st in words) * 1.12
        rows.append((t0, words, widths, space, asc, line_h))
    total_h = sum(r[5] for r in rows)
    y = seg.get("y", 0.75) * H - total_h / 2
    placed = []
    for t0, words, widths, space, asc, line_h in rows:
        lw = sum(widths) + space * (len(words) - 1)
        x = (W - lw) / 2
        for i, ((wt, st), ww) in enumerate(zip(words, widths)):
            # taban çizgisini hizala
            base_y = y + asc - token(wt, st)[2]
            placed.append((x, base_y, wt, st, t0 + i * 0.11))
            x += ww + space
        y += line_h
    return placed


def paste(canvas, img, x, y, alpha=1.0):
    """canvas: float32 HxWx3; img: uint8 RGBA."""
    x, y = int(round(x)), int(round(y))
    h, w = img.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x0 >= x1 or y0 >= y1:
        return
    sub = img[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32)
    a = sub[..., 3:4] / 255 * alpha
    canvas[y0:y1, x0:x1] = canvas[y0:y1, x0:x1] * (1 - a) + sub[..., :3] * a


# --------------------------------------------------------------- global efektler
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
VIGNETTE = (1 - 0.38 * (((XX - W / 2) / (W * 0.75)) ** 2 + ((YY - H / 2) / (H * 0.62)) ** 2)
            .clip(0, 1) ** 1.4)[..., None].astype(np.float32)
# altta yumuşak karartma: açık zeminlerde yazı okunsun
VIGNETTE *= (1 - 0.5 * (((YY - H * 0.55) / (H * 0.45)).clip(0, 1) ** 1.5))[..., None]
_rng = np.random.default_rng(7)
GRAIN = [np.asarray(Image.fromarray(
    (_rng.normal(128, 22, (H // 2, W // 2))).clip(0, 255).astype(np.uint8))
    .resize((W, H), Image.BILINEAR), np.float32)[..., None] - 128 for _ in range(6)]
LY, LX = np.mgrid[0:240, 0:135].astype(np.float32)


def light_leak(t, strength, seed):
    """Kehribar renkli, yavaşça süzülen iki ışık lekesi (düşük çözünürlükte üretilir)."""
    out = np.zeros((240, 135, 3), np.float32)
    blobs = [((255, 150, 60), 0.15 + 0.2 * math.sin(t * 0.7 + seed), 0.2 + 0.1 * t, 70),
             ((255, 200, 120), 0.9 - 0.1 * t, 0.75 + 0.1 * math.cos(t + seed), 55)]
    for col, bx, by, r in blobs:
        g = np.exp(-(((LX - bx * 135) ** 2 + (LY - by * 240) ** 2) / (2 * r * r)))
        out += g[..., None] * np.array(col, np.float32)
    img = Image.fromarray(out.clip(0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
    return np.asarray(img, np.float32) * strength


def bloom(frame):
    small = Image.fromarray(frame.clip(0, 255).astype(np.uint8)).resize((W // 4, H // 4))
    s = np.asarray(small, np.float32)
    hi = np.clip(s - 185, 0, None) * 2.2
    b = Image.fromarray(hi.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(10))
    b = np.asarray(b.resize((W, H), Image.BILINEAR), np.float32)
    return b * np.array([1.0, 0.82, 0.6], np.float32) * 0.45


def screen(a, b):
    return 255 - (255 - a) * (255 - b) / 255


# ----------------------------------------------------------------- özel anlar
def viewfinder(canvas, t, gt):
    c = (255, 246, 230)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m, L, lw = 70, 110, 5
    for (x, y, dx, dy) in [(m, m + 60, 1, 1), (W - m, m + 60, -1, 1),
                           (m, H - m - 60, 1, -1), (W - m, H - m - 60, -1, -1)]:
        d.line([(x, y), (x + dx * L, y)], fill=c + (220,), width=lw)
        d.line([(x, y), (x, y + dy * L)], fill=c + (220,), width=lw)
    if int(t * 2.5) % 2 == 0:
        d.ellipse([m + 10, m + 92, m + 44, m + 126], fill=(225, 60, 45, 235))
    f = font("sans_b", 40)
    d.text((m + 62, m + 88), "REC", font=f, fill=c + (230,))
    fr = int(gt * FPS)
    tc = f"00:00:{fr // FPS:02d}:{fr % FPS:02d}"
    d.text((W - m - f.getlength(tc) - 10, m + 88), tc, font=f, fill=c + (230,))
    cx, cy, s = W // 2, H // 2 - 120, 26
    d.line([(cx - s, cy), (cx + s, cy)], fill=c + (160,), width=3)
    d.line([(cx, cy - s), (cx, cy + s)], fill=c + (160,), width=3)
    f2 = font("sans", 34)
    d.text((m + 10, H - m - 140), "4K  24FPS  ISO 400", font=f2, fill=c + (200,))
    paste(canvas, np.asarray(img), 0, 0)


def letterbox(canvas, t):
    bar = int(270 * ease(t / 0.45))
    if bar:
        canvas[:bar] *= 0.0
        canvas[H - bar:] *= 0.0


def polaroid(still, k):
    """Donmuş kareyi polaroid'e çevir; k=0 tam ekran, k=1 küçülmüş ve eğik."""
    bg = Image.fromarray(still.clip(0, 255).astype(np.uint8))
    bgb = np.asarray(bg.resize((W // 8, H // 8)).filter(ImageFilter.GaussianBlur(3))
                     .resize((W, H), Image.BILINEAR), np.float32) * (1 - 0.45 * k)
    s = 1 - 0.27 * k
    pw, ph = int(W * s), int(H * s * 0.86)
    photo = bg.resize((pw, int(H * s))).crop((0, int(H * s * 0.05), pw, int(H * s * 0.05) + ph))
    border, bottom = int(28 * k) + 1, int(120 * k) + 1
    card = Image.new("RGBA", (pw + 2 * border, ph + border + bottom), (250, 244, 232, 255))
    card.paste(photo, (border, border))
    card = card.rotate(-4 * k, resample=Image.BICUBIC, expand=True)
    out = bgb.copy()
    sh = np.asarray(card.split()[3].filter(ImageFilter.GaussianBlur(20)), np.float32) / 255
    cw, ch = card.size
    x, y = (W - cw) // 2, int((H - ch) / 2 - 120 * k)
    shadow = np.zeros((ch, cw, 4), np.uint8)
    shadow[..., 3] = (sh * 150 * k).astype(np.uint8)
    paste(out, shadow, x + 14, y + 22)
    paste(out, np.asarray(card), x, y)
    return out


def glitch_token(img, t):
    rnd = np.random.default_rng(int(t * 1000))
    d = int(rnd.integers(6, 16))
    out = img.copy()
    out[..., 0] = np.roll(img[..., 0], -d, 1)
    out[..., 2] = np.roll(img[..., 2], d, 1)
    out[..., 3] = np.maximum(np.maximum(np.roll(img[..., 3], -d, 1), np.roll(img[..., 3], d, 1)),
                             img[..., 3])
    return out


def slice_shift(frame, t):
    rnd = np.random.default_rng(int(t * 997))
    out = frame.copy()
    for _ in range(5):
        y0 = int(rnd.integers(0, H - 80))
        hh = int(rnd.integers(20, 90))
        out[y0:y0 + hh] = np.roll(frame[y0:y0 + hh], int(rnd.integers(-40, 40)), 1)
    return out


# ------------------------------------------------------------------ segment
def decode(seg):
    speed = seg.get("speed", 1.0)
    crop = f"crop=ih*9/16:ih:(iw-ih*9/16)*{seg['cx']}:0"
    vf = [crop, f"scale={W}:{H}:flags=lanczos", GRADE, f"fps={FPS}", "format=rgb24"]
    if speed != 1.0:
        vf.insert(0, f"setpts=PTS/{speed},minterpolate=fps={FPS}:mi_mode=mci")
    p = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-ss", str(seg["start"]), "-t", str(seg["dur"]),
         "-i", str(INPUT / seg["clip"]), "-an", "-vf", ",".join(vf),
         "-frames:v", str(int(round(seg["dur"] / speed * FPS))),
         "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    n = int(round(seg["dur"] / speed * FPS))
    frames, last = 0, None
    while frames < n:
        buf = p.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        last = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        frames += 1
        yield last
    p.stdout.close()
    p.wait()
    while frames < n:  # kaynak erken biterse son kareyi tut
        frames += 1
        yield last


def zoom(frame, z):
    if abs(z - 1) < 1e-3:
        return frame.astype(np.float32)
    cw, ch = W / z, H / z
    x0, y0 = (W - cw) / 2, (H - ch) / 2
    img = Image.fromarray(frame).resize((W, H), Image.BILINEAR,
                                        box=(x0, y0, x0 + cw, y0 + ch))
    return np.asarray(img, np.float32)


def render_segment(args):
    idx, seg, t_offset, path = args
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
         "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", str(path)],
        stdin=subprocess.PIPE)

    if seg.get("endcard"):
        n = int(seg["dur"] * FPS)
        for i in range(n):
            t = i / FPS
            c = np.zeros((H, W, 3), np.float32)
            a = ease((t - 0.2) / 0.8) * (1 - ease((t - seg["dur"] + 0.5) / 0.5))
            tok, pad, _ = token("honey.", "script_m")
            paste(c, tok, (W - tok.shape[1]) / 2, H * 0.47 - tok.shape[0] / 2, a)
            c = c + GRAIN[i % 6] * 0.5
            enc.stdin.write(c.clip(0, 255).astype(np.uint8).tobytes())
        enc.stdin.close()
        enc.wait()
        return

    speed = seg.get("speed", 1.0)
    live_n = int(round(seg["dur"] / speed * FPS))
    freeze_n = int(seg.get("freeze", 0) * FPS)
    total_n = live_n + freeze_n
    dur = total_n / FPS
    z0, z1 = seg["zoom"]
    placed = layout(seg)
    frames = decode(seg)
    still = None

    for i in range(total_n):
        t = i / FPS
        gt = t_offset + t
        if i < live_n:
            raw = next(frames)
            f = zoom(raw, z0 + (z1 - z0) * (t / dur))
            still = f
        else:
            k = ease((i - live_n) / (0.45 * FPS))
            f = polaroid(still, k)

        f = f + bloom(f)
        if seg.get("leak"):
            f = screen(f, light_leak(t, seg["leak"] * 0.55, idx))
        f = f * VIGNETTE

        if seg.get("letterbox"):
            letterbox(f, t)
        if seg.get("viewfinder"):
            viewfinder(f, t, gt)

        # kinetik tipografi
        fade_all = 1 - ease((t - (dur - 0.22)) / 0.22)
        for x, y, wt, st, t_in in placed:
            p = (t - t_in) / 0.42
            if p <= 0:
                continue
            a = ease(p) * fade_all
            dy = (1 - ease(p)) * 28
            img = token(wt, st, 6 if seg.get("track") else 0)[0]
            if seg.get("glitch") == wt and 0 < t - t_in < 0.45:
                img = glitch_token(img, gt)
            if st in ("emph", "huge", "script", "script_m"):
                sc = 1.08 - 0.08 * ease(p)  # vurgulu kelimeler hafifçe yerine oturur
                if abs(sc - 1) > 1e-3:
                    pi = Image.fromarray(img)
                    nw, nh = int(pi.width * sc), int(pi.height * sc)
                    img = np.asarray(pi.resize((nw, nh), Image.BICUBIC))
                    x2 = x - (nw - pi.width) / 2
                    y2 = y - (nh - pi.height) / 2
                    paste(f, img, x2 - token(wt, st)[1], y2 - token(wt, st)[1] + dy, a)
                    continue
            paste(f, img, x - token(wt, st)[1], y - token(wt, st)[1] + dy, a)

        if seg.get("glitch"):
            gx = [t_in for x, y, wt, st, t_in in placed if wt == seg["glitch"]][0]
            if 0.05 < t - gx < 0.2:
                f = slice_shift(f, gt)

        # deklanşör flaşı (polaroid anı)
        if freeze_n and live_n <= i < live_n + 4:
            f = f + (255 - f) * (1 - (i - live_n) / 4) * 0.9
        # altın flaş geçiş
        if seg.get("flash_in") and t < 0.3:
            k = 1 - t / 0.3
            f = f + (np.array([255, 214, 150], np.float32) - f) * (k ** 2) * 0.85
        if seg.get("fade_out") and t > dur - seg["fade_out"]:
            f = f * (1 - ease((t - dur + seg["fade_out"]) / seg["fade_out"]))

        f = f + GRAIN[(i + idx) % 6] * 0.6
        enc.stdin.write(f.clip(0, 255).astype(np.uint8).tobytes())
    enc.stdin.close()
    enc.wait()


def seg_duration(seg):
    if seg.get("endcard"):
        return int(seg["dur"] * FPS) / FPS
    live = int(round(seg["dur"] / seg.get("speed", 1.0) * FPS))
    return (live + int(seg.get("freeze", 0) * FPS)) / FPS


def main():
    OUTPUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        jobs, t = [], 0.0
        for i, seg in enumerate(SEGMENTS):
            jobs.append((i, seg, t, tmp / f"s{i:02d}.mp4"))
            t += seg_duration(seg)
        total = t
        # uzun segmentler önce: dört çekirdeğe dengeli dağılsın
        order = sorted(jobs, key=lambda j: -seg_duration(j[1]))
        with mp.Pool(4) as pool:
            pool.map(render_segment, order, chunksize=1)
        (tmp / "list.txt").write_text("".join(f"file '{j[3]}'\n" for j in jobs))
        out = OUTPUT / f"honey_reel_{datetime.date.today().isoformat()}_v2.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y",
             "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
             "-ss", str(MUSIC_START), "-i", str(MUSIC),
             "-filter_complex",
             (f"[1:a]atrim=0:{total:.3f},afade=t=in:st=0:d=0.8,"
              f"afade=t=out:st={total - 3:.3f}:d=3,loudnorm=I=-16:TP=-1.5[a]"),
             "-map", "0:v", "-map", "[a]", "-c:v", "copy",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
             "-t", f"{total:.3f}", str(out)], check=True)
        print(out, f"{total:.1f}s")


if __name__ == "__main__":
    main()
