"""Generate tab-bar icons for 数界 MathVerse.

Run from mathverse-miniapp/:  python scripts/gen_tab_icons.py
4 tabs (home / solve / learn / me) x 2 states (normal gray, active indigo).
Output: src/assets/tab/<name>.png and <name>-on.png  (81x81)
"""
import os
from PIL import Image, ImageDraw

S = 81
NORMAL = (139, 143, 166, 255)   # #8b8fa6
ACTIVE = (79, 70, 229, 255)      # #4F46E5
OUT = os.path.join(os.path.dirname(__file__), "..", "src", "assets", "tab")


def _canvas():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def home(c):
    img, d = _canvas()
    d.polygon([(40, 16), (66, 38), (14, 38)], fill=c)          # roof
    d.rectangle([22, 36, 58, 64], fill=c)                       # body
    d.rectangle([35, 48, 45, 64], fill=(0, 0, 0, 0))           # door (punch out)
    return img


def solve(c):
    img, d = _canvas()
    d.ellipse([18, 16, 50, 48], outline=c, width=7)            # lens
    d.line([46, 44, 64, 62], fill=c, width=8)                  # handle
    return img


def learn(c):
    img, d = _canvas()
    d.rectangle([18, 20, 63, 60], outline=c, width=6)          # cover
    d.line([40, 22, 40, 58], fill=c, width=6)                  # spine
    return img


def me(c):
    img, d = _canvas()
    d.ellipse([30, 16, 51, 37], fill=c)                        # head
    d.pieslice([20, 40, 61, 78], 180, 360, fill=c)             # shoulders
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("home", home), ("solve", solve), ("learn", learn), ("me", me)):
        fn(NORMAL).save(os.path.join(OUT, f"{name}.png"))
        fn(ACTIVE).save(os.path.join(OUT, f"{name}-on.png"))
    print("tab icons generated ->", OUT)


if __name__ == "__main__":
    main()
