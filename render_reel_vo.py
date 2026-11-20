"""Honey Hua — seslendirmeli "Evime hoş geldim" reel'i.

Yalnızca üç katman: siyah zemin üzerinde yazı, Şevval'in seslendirmesi ve alttan piyano.
Yazılar seslendirmeye hizalı (zamanlar faster-whisper + enerji analiziyle çıkarıldı,
Şevval onayladı). "Bir yolculuk..." ve imza seslendirmede yok; sessizce, yalnızca
müzikle görünür.

Çıktı: output/honey_reel_<tarih>_evime_hos_geldim_vo.mp4
"""
import datetime
import pathlib
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent
FONTS, OUTPUT = ROOT / "fonts", ROOT / "output"
VOICE = ROOT / "input" / "voice" / "ses_261121.m4a"
MUSIC = ROOT / "music" / "paus.mp3"
W, H, FPS = 1080, 1920, 24
TOTAL = 30.5

CREAM, WHITE, SIG = (255, 244, 228), (255, 255, 255), (240, 234, 222)
BODY = ("cormorant-tr-400-italic.ttf", 92, CREAM, 0)
HOME = ("cormorant-tr-500-normal.ttf", 98, WHITE, 0)
SIGN = ("montserrat-tr-300-normal.ttf", 38, SIG, 5)

# (kart başlangıcı, kart bitişi, [(satır, satırın geliş zamanı)], stil)
CARDS = [
    (0.4, 2.4, [("Bir yolculuk...", 0.4)], BODY),
    (2.6, 3.9, [("Önce öğrenmek...", 2.6)], BODY),
    (3.95, 5.5, [("Sonra üretmek...", 3.95)], BODY),
    (5.55, 7.5, [("Bazen kaybolmak...", 5.55)], BODY),
    (7.55, 10.6, [("Sonra yeniden bulmak...", 7.55)], BODY),
    (10.7, 12.3, [("Bangkok sabahı...", 10.7)], BODY),
    (12.4, 15.9, [("‘Kahvemi aldım,", 12.4), ("acelem yok’", 14.4)], BODY),
    (16.0, 17.8, [("Emeğimle buradayım...", 16.0)], BODY),
    (17.9, 22.2, [("Kameranın arkasında da,", 17.9), ("önünde de ben varım...", 19.8)], BODY),
    (22.45, 25.8, [("Evime hoş geldim.", 22.45)], HOME),
    (26.3, 29.6, [("Honey Hua — Home in Bangkok 2027.", 26.3)], SIGN),
]

FADE_IN, FADE_OUT = 0.35, 0.35
_fonts = {}


def font(name, size):
    if (name, size) not in _fonts:
        _fonts[(name, size)] = ImageFont.truetype(str(FONTS / name), size)
    return _fonts[(name, size)]


def ease(p):
    p = min(1.0, max(0.0, p))
    return p * p * (3 - 2 * p)


def line_image(text, style):
    """Satırın tam boyutlu maskesi (sonradan bulanıklaştırılıp kaydırılacak)."""
    fname, size, _, track = style
    f = font(fname, size)
    pad = 60
    widths = [f.getlength(c) + track for c in text]
    tw = int(sum(widths) - track)
    asc, desc = f.getmetrics()
    img = Image.new("L", (tw + 2 * pad, asc + desc + 2 * pad), 0)
    d = ImageDraw.Draw(img)
    x = pad
    for c, cw in zip(text, widths):
        d.text((x, pad), c, font=f, fill=255)
        x += cw
    return img, pad, asc + desc


_cache = {}


def cached_line(text, style):
    k = (text, style)
    if k not in _cache:
        _cache[k] = line_image(text, style)
    return _cache[k]


rng = np.random.default_rng(4)
GRAIN = [np.asarray(Image.fromarray(rng.normal(128, 14, (H // 2, W // 2)).clip(0, 255)
                                    .astype(np.uint8)).resize((W, H), Image.BILINEAR),
                    np.int16)[..., None] - 128 for _ in range(6)]
BASE = np.full((H, W, 3), 6, np.int16)  # saf siyah değil, hafif sıcak-nötr koyu


def frame(t, idx):
    canvas = Image.new("L", (W, H), 0)
    color = CREAM
    for start, end, lines, style in CARDS:
        if not (start <= t <= end):
            continue
        color = style[2]
        pout = ease((t - (end - FADE_OUT)) / FADE_OUT)
        imgs = [cached_line(txt, style) for txt, _ in lines]
        lh = max(h for _, _, h in imgs) * 1.08
        y0 = H * 0.47 - lh * len(lines) / 2
        for k, ((txt, t_in), (img, pad, _)) in enumerate(zip(lines, imgs)):
            pin = ease((t - t_in) / FADE_IN)
            a = pin * (1 - pout)
            if a <= 0.003:
                continue
            blur = 6 * (1 - pin) + 5 * pout
            im = img.filter(ImageFilter.GaussianBlur(float(blur))) if blur > 0.3 else img
            dy = 8 * (1 - pin) - 10 * pout
            m = im.point(lambda v, a=a: int(v * a))
            x = (W - img.width) // 2
            y = int(y0 + k * lh - pad + dy)
            canvas.paste(m, (x, y), m)
    mask = np.asarray(canvas, np.int32)[..., None]
    f = BASE + (np.array(color, np.int32) - BASE) * mask // 255
    f = f + GRAIN[idx % 6]
    return f.clip(0, 255).astype(np.uint8)


def main():
    OUTPUT.mkdir(exist_ok=True)
    out = OUTPUT / f"honey_reel_{datetime.date.today().isoformat()}_evime_hos_geldim_vo.mp4"
    # Ses: seslendirme öne; piyano, ses konuşurken sidechain ile alçalır.
    afc = (
        "[1:a]aformat=sample_rates=48000:channel_layouts=stereo,"
        "highpass=f=80,afftdn=nf=-30,"
        "acompressor=threshold=0.08:ratio=3:attack=10:release=200:makeup=2,"
        f"loudnorm=I=-17:TP=-2:LRA=7,apad=whole_dur={TOTAL},asplit=2[vo][sc];"
        f"[2:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:{TOTAL},"
        f"volume=0.75,afade=t=in:st=0:d=1.5,afade=t=out:st={TOTAL - 3.5}:d=3.5[mu];"
        "[mu][sc]sidechaincompress=threshold=0.03:ratio=4:attack=60:release=600[duck];"
        f"[duck][vo]amix=inputs=2:normalize=0:duration=longest,atrim=0:{TOTAL},"
        "alimiter=limit=0.89[a]"
    )
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", str(VOICE), "-i", str(MUSIC),
         "-filter_complex", afc, "-map", "0:v", "-map", "[a]",
         "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-tune", "grain",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", "-t", str(TOTAL), str(out)],
        stdin=subprocess.PIPE)
    for i in range(int(TOTAL * FPS)):
        enc.stdin.write(frame(i / FPS, i).tobytes())
    enc.stdin.close()
    enc.wait()
    print(out)


if __name__ == "__main__":
    main()
