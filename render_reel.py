"""Honey Hua — metinden B-roll reel render'ı.

Onaylanan eşleştirme tablosuna göre klipleri 1080x1920 dikey kırpar,
sıcak altın/kehribar tonuna çeker, cümleleri altyazı olarak basar,
müziği ekler ve output/honey_reel_<tarih>.mp4 olarak kaydeder.
"""
import datetime
import pathlib
import subprocess
import tempfile
import textwrap

ROOT = pathlib.Path(__file__).resolve().parent
INPUT = ROOT / "input"
OUTPUT = ROOT / "output"
MUSIC = ROOT / "music" / "crossing_the_rubicon.mp3"
MUSIC_START = 1.0  # parçanın başındaki ~1.2 sn sessizliği atla
FONT = "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"

W, H, FPS = 1080, 1920, 24

# (cümle, klip, başlangıç, kaynak süresi, kırpma merkezi 0–1, hız)
# hız < 1 → yavaşlatma; ekrandaki süre = kaynak süresi / hız
SEGMENTS = [
    ("Hi, I'm Honey Hua.", "video.mp4", 2.0, 2.0, 0.50, 1.0),
    ("A little curious, a little unpredictable, and always chasing something beautiful.",
     "video (4).mp4", 0.0, 4.8, 0.54, 1.0),
    ("I collect moments, not things.", "video (3).mp4", 0.0, 2.6, 0.51, 1.0),
    ("I find stories in places, colors in cultures, and inspiration in the most unexpected corners of the world.",
     "mp_ (1).mp4", 0.5, 6.6, 0.45, 1.0),
    ("Sometimes I'm behind the camera.", "video.mp4", 0.0, 2.2, 0.50, 1.0),
    ("Sometimes I'm the story.", "video (2).mp4", 0.0, 2.2, 0.50, 1.0),
    ("I believe life is too beautiful to be lived in just one way.",
     "videomp_.mp4", 4.4, 3.6, 0.48, 0.82),
    ("So, I'm here to explore, create, experiment, and maybe inspire you along the way.",
     "video (1).mp4", 0.0, 5.6, 0.50, 1.0),
    ("This is my world.", "videok.mp4", 0.0, 2.2, 0.50, 1.0),
    ("And we're just getting started.", "videomp_.mp4", 0.5, 2.2, 0.49, 1.0),
    ("I'm Honey Hua.", "video.mp4", 4.0, 2.0, 0.50, 1.0),
    ("Nice to meet you.", "video.mp4", 6.0, 2.0, 0.50, 1.0),
]

# Tüm kliplere aynı hafif sıcak ton: renk sıçraması olmasın diye tek bir grade.
GRADE = ("colorbalance=rs=0.03:bs=-0.04:rm=0.02:bm=-0.03:rh=0.02:bh=-0.02,"
         "eq=contrast=1.03:saturation=1.04")


def run(cmd):
    subprocess.run(cmd, check=True)


def make_gradient(tmp):
    """Alt kısımda yumuşak karartma: açık zeminlerde altyazı okunsun diye."""
    g = tmp / "grad.png"
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"color=black:s={W}x{H},format=rgba",
         "-vf", (f"geq=r=0:g=0:b=0:"
                 f"a='if(lt(Y,{H}*0.58),0,140*pow((Y-{H}*0.58)/({H}*0.42),1.4))'"),
         "-frames:v", "1", str(g)])
    return g


def render_segment(i, seg, tmp, grad):
    text, clip, start, src_dur, cx, speed = seg
    out_dur = src_dur / speed
    txt = tmp / f"t{i}.txt"
    txt.write_text("\n".join(textwrap.wrap(text, 26)))

    # 16:9 karenin içinden 9:16 dilim; merkez kliple birlikte ayarlanır.
    crop = f"crop=ih*9/16:ih:(iw-ih*9/16)*{cx}:0"
    chain = [crop, f"scale={W}:{H}:flags=lanczos", "unsharp=5:5:0.4", GRADE]
    if speed != 1.0:
        chain.insert(0, f"setpts=PTS/{speed},minterpolate=fps={FPS}:mi_mode=mci")
    chain += [
        f"fps={FPS}",
        "format=rgba[base];[base][1:v]overlay=0:0",
        "format=yuv420p",
        (f"drawtext=fontfile={FONT}:textfile={txt}:text_align=C:"
         f"fontsize=58:line_spacing=14:fontcolor=0xFFF3DC:"
         f"shadowcolor=0x000000@0.55:shadowx=2:shadowy=2:"
         f"x=(w-text_w)/2:y=h*0.79:"
         f"alpha='min(1,t/0.25)*min(1,({out_dur}-t)/0.2)'"),
    ]
    out = tmp / f"s{i:02d}.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-t", str(src_dur),
         "-i", str(INPUT / clip), "-loop", "1", "-i", str(grad), "-an",
         "-filter_complex", ",".join(chain),
         "-t", f"{out_dur:.3f}", "-c:v", "libx264", "-crf", "16",
         "-preset", "slow", str(out)])
    return out, out_dur


def main():
    OUTPUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        grad = make_gradient(tmp)
        parts = [render_segment(i, s, tmp, grad) for i, s in enumerate(SEGMENTS)]
        total = sum(p[1] for p in parts)
        (tmp / "list.txt").write_text(
            "".join(f"file '{p[0]}'\n" for p in parts))
        out = OUTPUT / f"honey_reel_{datetime.date.today().isoformat()}.mp4"
        run(["ffmpeg", "-v", "error", "-y",
             "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
             "-ss", str(MUSIC_START), "-i", str(MUSIC),
             "-filter_complex",
             (f"[0:v]fade=t=in:st=0:d=0.4,fade=t=out:st={total - 0.8:.3f}:d=0.8[v];"
              f"[1:a]atrim=0:{total:.3f},afade=t=in:st=0:d=1,"
              f"afade=t=out:st={total - 2.5:.3f}:d=2.5,loudnorm=I=-16:TP=-1.5[a]"),
             "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-crf", "17", "-preset", "slow",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", "-t", f"{total:.3f}", str(out)])
        print(out, f"{total:.1f}s")


if __name__ == "__main__":
    main()
