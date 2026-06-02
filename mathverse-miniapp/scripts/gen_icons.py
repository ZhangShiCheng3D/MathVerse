"""Generate branded app icons for 数界 MathVerse (indigo bg + white 数).

Run from mathverse-miniapp/:  python scripts/gen_icons.py
Regenerates Android launcher icons + adaptive foreground + a 1024 source icon.
"""
import os
from PIL import Image, ImageDraw, ImageFont

INDIGO = (79, 70, 229, 255)   # #4F46E5
WHITE = (255, 255, 255, 255)
FONT = "C:/Windows/Fonts/msyhbd.ttc"  # Microsoft YaHei Bold (has 数)
GLYPH = "数"

RES = os.path.join(os.path.dirname(__file__), "..", "android", "app", "src", "main", "res")
# legacy square/round launcher icon px (48dp base)
LEGACY = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
# adaptive foreground px (108dp canvas)
FOREGROUND = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}


def _draw_glyph(img, frac):
    """Centered white 数 sized to `frac` of the image height."""
    d = ImageDraw.Draw(img)
    size = int(img.height * frac)
    font = ImageFont.truetype(FONT, size, index=0)
    l, t, r, b = d.textbbox((0, 0), GLYPH, font=font)
    x = (img.width - (r - l)) // 2 - l
    y = (img.height - (b - t)) // 2 - t
    d.text((x, y), GLYPH, font=font, fill=WHITE)


def _rounded(size, radius_frac=0.22):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(size * radius_frac)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=INDIGO)
    return img


def _circle(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, size - 1, size - 1], fill=INDIGO)
    return img


def gen_splashes():
    """Rebrand every splash.png at its existing size: indigo bg + 数 + app name."""
    import glob
    for p in glob.glob(os.path.join(RES, "**", "splash.png"), recursive=True):
        w, h = Image.open(p).size
        img = Image.new("RGBA", (w, h), INDIGO)
        d = ImageDraw.Draw(img)
        base = min(w, h)
        # 数 mark
        f1 = ImageFont.truetype(FONT, int(base * 0.26), index=0)
        l, t, r, b = d.textbbox((0, 0), GLYPH, font=f1)
        gx = (w - (r - l)) // 2 - l
        gy = int(h / 2 - (b - t) * 0.85) - t
        d.text((gx, gy), GLYPH, font=f1, fill=WHITE)
        # app name
        name = "数界 MathVerse"
        f2 = ImageFont.truetype(FONT, int(base * 0.075), index=0)
        l2, t2, r2, b2 = d.textbbox((0, 0), name, font=f2)
        nx = (w - (r2 - l2)) // 2 - l2
        ny = int(h / 2 + base * 0.10) - t2
        d.text((nx, ny), name, font=f2, fill=WHITE)
        img.save(p)


def main():
    for dpi, px in LEGACY.items():
        sq = _rounded(px)
        _draw_glyph(sq, 0.62)
        sq.save(os.path.join(RES, f"mipmap-{dpi}", "ic_launcher.png"))

        rd = _circle(px)
        _draw_glyph(rd, 0.58)
        rd.save(os.path.join(RES, f"mipmap-{dpi}", "ic_launcher_round.png"))

    # Adaptive foreground: transparent bg, glyph in the 66dp safe zone (~0.42 of 108).
    for dpi, px in FOREGROUND.items():
        fg = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        _draw_glyph(fg, 0.42)
        fg.save(os.path.join(RES, f"mipmap-{dpi}", "ic_launcher_foreground.png"))

    # 1024 source (store listing / future tooling).
    src = _rounded(1024, radius_frac=0.20)
    _draw_glyph(src, 0.62)
    out = os.path.join(os.path.dirname(__file__), "..", "resources")
    os.makedirs(out, exist_ok=True)
    src.save(os.path.join(out, "icon.png"))
    gen_splashes()
    print("icons + splashes generated")


if __name__ == "__main__":
    main()
