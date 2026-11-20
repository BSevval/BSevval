"""Honey Hua — "Evime hoş geldim" reel'i (v3).

Drive videoları kullanılmaz; görüntü tamamen üretilir: karanlıktan Bangkok sabahına
yükselen bir ışık yolculuğu. Metin Şevval'in yazdığı haliyle, kelime eklenmeden.

Her kart bir nefes gibi gelir ve gider: yazı bulanıktan netleşerek "nefes alır",
bulanıklaşıp yukarı süzülerek "nefes verir"; geçişlerde gerçek bir nefes sesi duyulur.
Sahneye özel:
  - "Bazen kaybolmak..."      → harfler tek tek dağılıp bulanıklaşır, sis çöker
  - "Sonra yeniden bulmak..." → dağınık harfler bir araya gelir, ışık geri döner
  - "Bangkok sabahı..."       → güneş aşağıdan yükselir, ışığın doruğu
  - "‘Kahvemi aldım, acelem yok’" → sıcak ışıkta yavaşça yükselen buhar
  - "Kameranın arkasında da..."   → silik kamera vizörü köşeleri
  - "Evime hoş geldim."       → tam siyah, beyaz harfler, neredeyse sessizlik
  - imza                      → "Honey Hua — Home in Bangkok 2027."

Çıktı: output/honey_reel_<tarih>_evime_hos_geldim.mp4
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
OUTPUT, FONTS, MUSIC = ROOT / "output", ROOT / "fonts", ROOT / "music"
W, H, FPS = 1080, 1920, 24
LW, LH = 270, 480  # arka plan bu çözünürlükte üretilip büyütülür

CREAM = (255, 244, 228)
WHITE = (255, 255, 255)

# (metin satırları, süre, ışık seviyesi, sahne etiketi, nefes sesi)
CARDS = [
    (None, 0.8, 0.00, "black", None),
    (["Bir yolculuk..."], 3.6, 0.03, "", "v2"),
    (["Önce öğrenmek..."], 2.8, 0.12, "", "v3"),
    (["Sonra üretmek..."], 2.8, 0.22, "", "v4"),
    (["Bazen kaybolmak..."], 3.4, 0.07, "lost", "s2"),
    (["Sonra yeniden bulmak..."], 3.4, 0.36, "found", "v1"),
    (["Bangkok sabahı..."], 3.8, 1.00, "sunrise", "v2"),
    (["‘Kahvemi aldım,", "acelem yok’"], 3.9, 0.72, "coffee", "s3"),
    (["Emeğimle buradayım..."], 3.2, 0.45, "", "v3"),
    (["Kameranın arkasında da,", "önünde de ben varım..."], 4.4, 0.30, "camera", "v4"),
    (None, 1.1, 0.00, "black", None),
    (["Evime hoş geldim."], 4.3, 0.00, "home", "s2"),
    (["Honey Hua — Home in Bangkok 2027."], 3.8, 0.00, "signature", None),
    (None, 1.0, 0.00, "black", None),
]

# nefes sesinin kaynak dosyadaki parçaları (silencedetect ile bulundu)
BREATHS = {
    "v1": ("breath_varied.wav", 0.00, 0.66), "v2": ("breath_varied.wav", 0.91, 0.71),
    "v3": ("breath_varied.wav", 2.29, 0.45), "v4": ("breath_varied.wav", 3.10, 0.46),
    "s2": ("breath_sigh.wav", 0.85, 0.62), "s3": ("breath_sigh.wav", 2.03, 1.25),
}

STARTS = np.cumsum([0] + [c[1] for c in CARDS])
TOTAL = float(STARTS[-1])
NFRAMES = int(round(TOTAL * FPS))


def ease(p):
    p = min(1.0, max(0.0, p))
    return p * p * (3 - 2 * p)


def card_at(t):
    i = int(np.searchsorted(STARTS, t, side="right") - 1)
    i = min(max(i, 0), len(CARDS) - 1)
    return i, t - STARTS[i]


def light_at(t):
    """Kartların ışık seviyeleri arasında yumuşak geçiş (kart ortalarından interpolasyon)."""
    mids = [STARTS[i] + c[1] / 2 for i, c in enumerate(CARDS)]
    lv = [c[2] for c in CARDS]
    if t <= mids[0]:
        return lv[0]
    for j in range(len(mids) - 1):
        if mids[j] <= t <= mids[j + 1]:
            p = ease((t - mids[j]) / (mids[j + 1] - mids[j]))
            return lv[j] + (lv[j + 1] - lv[j]) * p
    return lv[-1]


def scene_weight(t, tag, ramp=0.9):
    """Sahne etiketinin o anki ağırlığı (kenarlarda yumuşak)."""
    i, lt = card_at(t)
    w = 0.0
    for j, c in enumerate(CARDS):
        if c[3] != tag:
            continue
        s, e = STARTS[j], STARTS[j] + c[1]
        w = max(w, ease((t - s + ramp * 0.3) / ramp) * ease((e - t + ramp * 0.3) / ramp))
    return w


# ---------------------------------------------------------------- arka plan
LY, LX = np.mgrid[0:LH, 0:LW].astype(np.float32)
LXn, LYn = LX / LW, LY / LH
VIG = (1 - 0.55 * (((LXn - 0.5) / 0.7) ** 2 + ((LYn - 0.5) / 0.6) ** 2).clip(0, 1) ** 1.3)
_rng = np.random.default_rng(11)


def smooth_noise(seed, scale):
    r = np.random.default_rng(seed)
    small = r.random((max(2, LH // scale), max(2, LW // scale))).astype(np.float32)
    img = Image.fromarray((small * 255).astype(np.uint8)).resize((LW, LH * 2), Image.BICUBIC)
    return np.asarray(img, np.float32) / 255


FOG = [smooth_noise(s, 40) for s in (1, 2)]
def steam_noise(seed):
    """Dikey uzamış, ince buhar lifleri."""
    r = np.random.default_rng(seed)
    small = r.random((LH // 24, LW // 5)).astype(np.float32)
    img = Image.fromarray((small * 255).astype(np.uint8)).resize((LW, LH * 2), Image.BICUBIC)
    img = img.filter(ImageFilter.GaussianBlur(2))
    return np.asarray(img, np.float32) / 255


STEAM = steam_noise(5)


def background(t):
    L = light_at(t)
    breath = 1 + 0.07 * math.sin(2 * math.pi * t / 4.4)
    base = np.array([9, 6, 4], np.float32)
    img = np.broadcast_to(base, (LH, LW, 3)).copy()

    sun = scene_weight(t, "sunrise", 1.6)
    # ışık kaynağı: aşağıdan yükselen sıcak küre
    sy = 1.25 - 0.18 * L - 0.32 * sun
    r = 0.42 + 0.25 * L + 0.15 * sun
    d = np.sqrt(((LXn - 0.5) * 0.56) ** 2 + (LYn - sy) ** 2)
    glow = np.exp(-(d / r) ** 2 * 2.2)
    core = np.exp(-(d / (0.12 + 0.05 * sun)) ** 2) * sun
    warm = np.array([255, 150, 70], np.float32)
    gold = np.array([255, 205, 130], np.float32)
    img += glow[..., None] * warm * (0.55 * L) * breath
    img += core[..., None] * gold * 0.9
    # alt pus
    haze = (LYn ** 2.2)[..., None] * np.array([200, 110, 55], np.float32) * 0.35 * L
    img += haze

    lost = scene_weight(t, "lost", 1.2)
    if lost > 0.01:
        f = FOG[0][int(t * 6) % LH:int(t * 6) % LH + LH] * 0.6 + \
            FOG[1][int(t * 10) % LH:int(t * 10) % LH + LH] * 0.4
        img = img * (1 - 0.35 * lost) + (f[..., None] * np.array([70, 55, 45], np.float32)) * lost

    cof = scene_weight(t, "coffee", 1.2)
    if cof > 0.01:
        off = int(t * 22) % LH
        n = STEAM[LH - off: 2 * LH - off] if off else STEAM[LH:2 * LH]
        sway = 0.04 * np.sin(LYn * 9 - t * 1.4) + 0.02 * np.sin(LYn * 17 + t * 0.8)
        col = np.exp(-(((LXn - 0.5 - sway) / (0.05 + 0.12 * (1 - LYn))) ** 2))
        fade = (LYn.clip(0.45, 1) - 0.45) / 0.55
        mask = col * np.sin(np.pi * fade) * (n ** 3.0)
        img += mask[..., None] * np.array([255, 238, 220], np.float32) * 0.45 * cof

    img *= VIG[..., None]
    return img


class Dust:
    """Işıkta süzülen toz zerrecikleri (yarım çözünürlükte çizilir)."""

    def __init__(self, n=80):
        r = np.random.default_rng(3)
        self.x = r.random(n)
        self.y = r.random(n)
        self.s = r.uniform(1.0, 3.6, n)
        self.v = r.uniform(0.006, 0.02, n)
        self.ph = r.random(n) * 6.28
        self.sprites = {}

    def sprite(self, s):
        k = round(s, 1)
        if k not in self.sprites:
            R = int(s * 3) + 2
            yy, xx = np.mgrid[-R:R + 1, -R:R + 1]
            self.sprites[k] = np.exp(-(xx ** 2 + yy ** 2) / (2 * s * s)).astype(np.float32)
        return self.sprites[k]

    def draw(self, t, strength):
        hw, hh = W // 2, H // 2
        out = np.zeros((hh, hw), np.float32)
        if strength < 0.01:
            return out
        for x, y, s, v, ph in zip(self.x, self.y, self.s, self.v, self.ph):
            px = (x + 0.02 * math.sin(t * 0.5 + ph)) % 1 * hw
            py = (y - v * t) % 1 * hh
            sp = self.sprite(s)
            R = sp.shape[0] // 2
            x0, y0 = int(px) - R, int(py) - R
            if x0 < 0 or y0 < 0 or x0 + sp.shape[1] > hw or y0 + sp.shape[0] > hh:
                continue
            tw = 0.5 + 0.5 * math.sin(t * 1.3 + ph * 3)
            out[y0:y0 + sp.shape[0], x0:x0 + sp.shape[1]] += sp * (0.4 + 0.6 * tw)
        return out * strength


DUST = Dust()
GR = np.random.default_rng(9)
GRAIN = [np.asarray(Image.fromarray(GR.normal(128, 20, (H // 2, W // 2)).clip(0, 255)
                                    .astype(np.uint8)).resize((W, H), Image.BILINEAR),
                    np.float32)[..., None] - 128 for _ in range(6)]


# ------------------------------------------------------------------- yazı
_fonts = {}


def font(name, size):
    if (name, size) not in _fonts:
        _fonts[(name, size)] = ImageFont.truetype(str(FONTS / name), size)
    return _fonts[(name, size)]


def style_for(tag):
    if tag == "home":
        return "cormorant-tr-500-normal.ttf", 98, WHITE, 0
    if tag == "signature":
        return "montserrat-tr-300-normal.ttf", 38, (240, 234, 222), 5
    return "cormorant-tr-400-italic.ttf", 92, CREAM, 0


def char_layout(lines, tag):
    """Her harf için (karakter, x, y) — satırlar ekranın ortasında."""
    fname, size, _, track = style_for(tag)
    f = font(fname, size)
    asc, desc = f.getmetrics()
    lh = (asc + desc) * 1.08
    total_h = lh * len(lines)
    y = H * 0.47 - total_h / 2
    out = []
    for line in lines:
        widths = [f.getlength(c) + track for c in line]
        x = (W - (sum(widths) - track)) / 2
        for c, cw in zip(line, widths):
            out.append((c, x, y))
            x += cw
        y += lh
    return out


def text_layer(lines, tag, lt, dur):
    """Kartın yazısını nefes animasyonuyla RGBA olarak çiz. Dönüş: (rgba ndarray, x0, y0)."""
    fname, size, color, _ = style_for(tag)
    f = font(fname, size)
    chars = char_layout(lines, tag)
    pad = 160
    xs = [c[1] for c in chars]
    ys = [c[2] for c in chars]
    x0, y0 = int(min(xs)) - pad, int(min(ys)) - pad
    x1 = int(max(xs)) + size + pad
    y1 = int(max(ys)) + int(size * 1.4) + pad
    layer = Image.new("L", (x1 - x0, y1 - y0), 0)
    d = ImageDraw.Draw(layer)

    t_in, t_out = (1.4, 1.1) if tag in ("home", "signature") else (1.05, 0.9)
    pin = ease(lt / t_in)
    pout = ease((lt - (dur - t_out)) / t_out)
    alpha = pin * (1 - pout)
    blur = 9 * (1 - pin) + 8 * pout
    dy = 12 * (1 - pin) - 16 * pout

    rng = np.random.default_rng(len(lines[0]))
    n = len(chars)
    dirs = rng.normal(0, 1, (n, 2))
    order = rng.permutation(n) / max(n - 1, 1)
    for k, (c, x, y) in enumerate(chars):
        a, ox, oy = alpha, 0.0, dy
        if tag == "lost":
            # son 1.6 sn'de harfler sırayla dağılır
            p = ease((lt - (dur - 1.7) - order[k] * 0.6) / 1.0)
            a = pin * (1 - p)
            ox, oy = dirs[k, 0] * 90 * p, dirs[k, 1] * 60 * p - 30 * p
        elif tag == "found":
            # dağınık harfler sırayla yerine oturur
            p = ease((lt - 0.1 - order[k] * 0.7) / 0.9)
            a = p * (1 - pout)
            ox, oy = dirs[k, 0] * 110 * (1 - p), dirs[k, 1] * 80 * (1 - p) + dy * pout
        if a <= 0.003:
            continue
        d.text((x - x0 + ox, y - y0 + oy), c, font=f, fill=int(255 * a))
    if tag == "lost":
        blur = 9 * (1 - pin) + 7 * ease((lt - (dur - 1.7)) / 1.6)
    elif tag == "found":
        blur = 8 * (1 - ease(lt / 1.3)) + 8 * pout
    if blur > 0.3:
        layer = layer.filter(ImageFilter.GaussianBlur(float(blur)))
    m = np.asarray(layer, np.float32) / 255
    rgba = np.zeros(m.shape + (4,), np.float32)
    rgba[..., :3] = color
    rgba[..., 3] = m
    return rgba, x0, y0


def viewfinder(strength):
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    m, L = 90, 120
    for (x, y, dx, dy) in [(m, m + 120, 1, 1), (W - m, m + 120, -1, 1),
                           (m, H - m - 120, 1, -1), (W - m, H - m - 120, -1, -1)]:
        d.line([(x, y), (x + dx * L, y)], fill=255, width=3)
        d.line([(x, y), (x, y + dy * L)], fill=255, width=3)
    return (np.asarray(img, np.float32) / 255 * strength)[..., None]


VF = None


# ------------------------------------------------------------------ kare
def frame(t, idx):
    global VF
    bg = Image.fromarray(background(t).clip(0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
    f = np.asarray(bg, np.float32).copy()

    L = light_at(t)
    i, lt = card_at(t)
    dark = CARDS[i][3] in ("home", "signature", "black") and L < 0.02
    dust = DUST.draw(t, 0 if dark else 0.08 + 0.9 * L)
    if dust.any():
        dimg = np.asarray(Image.fromarray((dust * 255).clip(0, 255).astype(np.uint8))
                          .resize((W, H), Image.BILINEAR), np.float32)[..., None] / 255
        f += dimg * np.array([255, 215, 160], np.float32) * 0.8

    cam = scene_weight(t, "camera", 1.0)
    if cam > 0.01:
        if VF is None:
            VF = viewfinder(1.0)
        f = f * (1 - VF * 0.3 * cam) + VF * 0.3 * cam * 240

    i, lt = card_at(t)
    lines, dur, _, tag, _ = CARDS[i]
    if lines:
        rgba, x0, y0 = text_layer(lines, tag, lt, dur)
        h, w = rgba.shape[:2]
        xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
        sub = rgba[ya - y0:yb - y0, xa - x0:xb - x0]
        a = sub[..., 3:4]
        # yazının arkasında çok hafif sıcak parıltı
        f[ya:yb, xa:xb] = f[ya:yb, xa:xb] * (1 - a) + sub[..., :3] * a

    f += GRAIN[idx % 6] * (0.55 if tag not in ("home", "signature", "black") else 0.35)
    return f.clip(0, 255).astype(np.uint8)


def render_chunk(args):
    a, b, path = args
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "15",
         "-preset", "medium", "-tune", "grain", "-pix_fmt", "yuv420p", str(path)],
        stdin=subprocess.PIPE)
    for k in range(a, b):
        enc.stdin.write(frame(k / FPS, k).tobytes())
    enc.stdin.close()
    enc.wait()


# ------------------------------------------------------------------- ses
def audio_filter():
    """Piyano yatağı + her kart başında hafif yankılı bir nefes."""
    inputs = ["-ss", "0", "-i", str(MUSIC / "paus.mp3")]
    chains, labels = [], []
    home_s = STARTS[[c[3] for c in CARDS].index("home")]
    chains.append(
        f"[0:a]atrim=0:{TOTAL:.3f},asetpts=PTS-STARTPTS,"
        f"volume='if(lt(t,{home_s - 1.2:.2f}),0.55,0.55-0.33*min(1,(t-{home_s - 1.2:.2f})/1.5))':eval=frame,"
        f"afade=t=in:st=0:d=2.5,afade=t=out:st={TOTAL - 4:.2f}:d=4[m]")
    n_in = 1
    for i, c in enumerate(CARDS):
        if not c[4]:
            continue
        fn, s, d = BREATHS[c[4]]
        inputs += ["-i", str(MUSIC / fn)]
        at = max(0.0, STARTS[i] - 0.15) * 1000
        vol = 0.9 if c[4].startswith("s") else 0.75
        chains.append(
            f"[{n_in}:a]atrim={s}:{s + d},asetpts=PTS-STARTPTS,"
            f"afade=t=in:d=0.05,afade=t=out:st={d - 0.12:.2f}:d=0.12,"
            f"aformat=sample_rates=44100:channel_layouts=stereo,"
            f"aecho=0.8:0.6:70|140:0.22|0.12,volume={vol},adelay={int(at)}|{int(at)}[b{n_in}]")
        labels.append(f"[b{n_in}]")
        n_in += 1
    chains.append(
        f"[m]aformat=sample_rates=44100:channel_layouts=stereo[m2];"
        f"[m2]{''.join(labels)}amix=inputs={len(labels) + 1}:normalize=0,"
        f"atrim=0:{TOTAL:.3f},loudnorm=I=-18:TP=-2[a]")
    return inputs, ";".join(chains)


def main():
    OUTPUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        n = 4
        bounds = [round(NFRAMES * k / n) for k in range(n + 1)]
        jobs = [(bounds[k], bounds[k + 1], tmp / f"c{k}.mp4") for k in range(n)]
        with mp.Pool(n) as pool:
            pool.map(render_chunk, jobs)
        (tmp / "list.txt").write_text("".join(f"file '{j[2]}'\n" for j in jobs))
        ain, afc = audio_filter()
        out = OUTPUT / f"honey_reel_{datetime.date.today().isoformat()}_evime_hos_geldim.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", str(tmp / "list.txt")] + ain +
            ["-filter_complex", _shift_inputs(afc),
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", "-t", f"{TOTAL:.3f}", str(out)], check=True)
        print(out, f"{TOTAL:.1f}s")


def _shift_inputs(fc):
    """Video 0. girdi olduğu için ses girdilerinin indeksini bir kaydır."""
    import re
    return re.sub(r"\[(\d+):a\]", lambda m: f"[{int(m.group(1)) + 1}:a]", fc)


if __name__ == "__main__":
    main()
