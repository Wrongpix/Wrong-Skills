#!/usr/bin/env python3
"""Draw a 4-view orthographic pixel sheet of a wooden treasure chest (our asset)."""
from pathlib import Path
from PIL import Image

OUT = Path(__file__).resolve().parent

# palette
K = (20, 14, 12)
WOOD_D = (86, 48, 26)
WOOD_M = (138, 82, 38)
WOOD_L = (180, 122, 62)
LID_L = (200, 146, 78)
LID_M = (158, 98, 48)
IRON = (46, 46, 52)
IRON_L = (108, 108, 118)
IRON_D = (30, 30, 34)
GOLD = (216, 168, 52)
GOLD_L = (244, 216, 120)
GOLD_D = (156, 106, 28)
FOOT = (38, 28, 24)

W, L, H = 28, 36, 24  # width, length, height including 1px outline


def new(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def px(im, x, y, c):
    if 0 <= x < im.width and 0 <= y < im.height:
        im.putpixel((x, y), c if len(c) == 4 else (*c, 255))


def rect(im, x0, y0, x1, y1, c):
    for y in range(min(y0, y1), max(y0, y1) + 1):
        for x in range(min(x0, x1), max(x0, x1) + 1):
            px(im, x, y, c)


def hline(im, x0, x1, y, c):
    for x in range(min(x0, x1), max(x0, x1) + 1):
        px(im, x, y, c)


def vline(im, x, y0, y1, c):
    for y in range(min(y0, y1), max(y0, y1) + 1):
        px(im, x, y, c)


def outline_opaque(im, color=K):
    src = im.copy()
    out = im.copy()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            if src.getpixel((x, y))[3] == 0:
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and src.getpixel((nx, ny))[3] > 0:
                        out.putpixel((x, y), (*color, 255))
                        break
    return out


def draw_top():
    # 28 x 36, front pointing DOWN (high y)
    im = new(W, L)
    # lid top surface fills the plan
    rect(im, 3, 3, 24, 32, LID_M)
    # slightly narrower ends (rounded plan)
    rect(im, 4, 2, 23, 3, LID_M)
    rect(im, 4, 32, 23, 33, LID_M)
    # warm highlight toward the "light" (upper-left of lid)
    rect(im, 5, 4, 14, 18, LID_L)
    # wood plank seams (lengthwise, front-back)
    for x in (9, 14, 18):
        vline(im, x, 4, 31, WOOD_D)
    # iron bands wrapping across the width
    for y0, y1 in ((8, 10), (24, 26)):
        rect(im, 3, y0, 24, y1, IRON)
        hline(im, 4, 23, y0, IRON_L)
        # rivets
        for x in (5, 13, 22):
            px(im, x, y0 + 1, IRON_L)
    # lock plate at the front edge
    rect(im, 11, 30, 16, 33, IRON)
    rect(im, 12, 31, 15, 32, GOLD)
    px(im, 13, 32, GOLD_L)
    px(im, 14, 32, GOLD_D)
    # hinge knuckles at the back edge
    for x in (6, 7, 20, 21):
        rect(im, x, 2, x, 4, IRON_L)
    return outline_opaque(im)


def draw_side():
    # 36 x 24, front pointing LEFT (low x)
    im = new(L, H)
    # feet
    rect(im, 4, 20, 7, 22, FOOT)
    rect(im, 28, 20, 31, 22, FOOT)
    # body (z from ~10 to 20)
    rect(im, 3, 10, 32, 19, WOOD_M)
    rect(im, 3, 16, 32, 19, WOOD_D)
    # plank lines
    hline(im, 4, 31, 13, WOOD_D)
    hline(im, 4, 31, 16, WOOD_D)
    # iron bands around the body (vertical in side? no — they wrap circumference,
    # so on the long side they are vertical straps at two stations)
    for x0, x1 in ((8, 10), (25, 27)):
        rect(im, x0, 10, x1, 19, IRON)
        vline(im, x0, 10, 19, IRON_L)
        px(im, x0 + 1, 12, IRON_L)
        px(im, x0 + 1, 17, IRON_L)
    # lid body (z 3..10), slight arch: higher in the middle
    rect(im, 3, 5, 32, 10, LID_M)
    # arch
    rect(im, 5, 4, 30, 5, LID_M)
    rect(im, 8, 3, 27, 4, LID_L)
    rect(im, 12, 2, 23, 3, LID_L)
    # lid highlight
    rect(im, 4, 6, 16, 8, LID_L)
    # lid straps continue the body straps
    for x0, x1 in ((8, 10), (25, 27)):
        rect(im, x0, 3, x1, 10, IRON)
        vline(im, x0, 3, 10, IRON_L)
    # front lock (left)
    rect(im, 3, 9, 6, 13, IRON)
    rect(im, 3, 10, 5, 12, GOLD)
    px(im, 4, 11, GOLD_L)
    # hinges at the back (right), on the seam
    rect(im, 30, 8, 32, 11, IRON_L)
    rect(im, 31, 9, 32, 10, IRON)
    return outline_opaque(im)


def draw_front():
    im = new(W, H)
    # feet
    rect(im, 4, 20, 7, 22, FOOT)
    rect(im, 20, 20, 23, 22, FOOT)
    # body
    rect(im, 3, 10, 24, 19, WOOD_M)
    rect(im, 3, 16, 24, 19, WOOD_D)
    hline(im, 4, 23, 13, WOOD_D)
    hline(im, 4, 23, 16, WOOD_D)
    # bands at the left and right of the front (they sit on the short sides
    # in plan — actually the wrap bands are on the length stations, so on
    # FRONT we see them only as a thin edge at the far left/right if at all.
    # Add a horizontal iron strap across the front for a classic chest read.)
    rect(im, 3, 14, 24, 16, IRON)
    hline(im, 4, 23, 14, IRON_L)
    for x in (6, 14, 21):
        px(im, x, 15, IRON_L)
    # lid
    rect(im, 3, 5, 24, 10, LID_M)
    rect(im, 5, 4, 22, 5, LID_M)
    rect(im, 8, 3, 19, 4, LID_L)
    rect(im, 11, 2, 16, 3, LID_L)
    rect(im, 4, 6, 14, 8, LID_L)
    # lid horizontal strap (continuation)
    rect(im, 3, 6, 24, 8, IRON)
    hline(im, 4, 23, 6, IRON_L)
    # big lock on the seam
    rect(im, 11, 8, 16, 15, IRON)
    rect(im, 12, 9, 15, 14, IRON_D)
    rect(im, 12, 10, 15, 13, GOLD)
    px(im, 13, 11, GOLD_L)
    px(im, 14, 12, GOLD_D)
    # hasp bar
    hline(im, 12, 15, 8, IRON_L)
    return outline_opaque(im)


def draw_back():
    im = new(W, H)
    rect(im, 4, 20, 7, 22, FOOT)
    rect(im, 20, 20, 23, 22, FOOT)
    rect(im, 3, 10, 24, 19, WOOD_M)
    rect(im, 3, 16, 24, 19, WOOD_D)
    hline(im, 4, 23, 13, WOOD_D)
    hline(im, 4, 23, 16, WOOD_D)
    rect(im, 3, 14, 24, 16, IRON)
    hline(im, 4, 23, 14, IRON_L)
    # lid
    rect(im, 3, 5, 24, 10, LID_M)
    rect(im, 5, 4, 22, 5, LID_M)
    rect(im, 8, 3, 19, 4, LID_L)
    rect(im, 11, 2, 16, 3, LID_L)
    rect(im, 3, 6, 24, 8, IRON)
    hline(im, 4, 23, 6, IRON_L)
    # two hinge knuckles on the seam
    for x0, x1 in ((5, 8), (19, 22)):
        rect(im, x0, 8, x1, 12, IRON)
        rect(im, x0 + 1, 9, x1 - 1, 11, IRON_L)
        px(im, x0 + 1, 10, IRON_D)
    return outline_opaque(im)


def sheet():
    views = [draw_top(), draw_side(), draw_front(), draw_back()]
    names = ["top", "side", "front", "back"]
    gap, pad = 48, 40
    widths = [v.width for v in views]
    height = max(v.height for v in views)
    total_w = pad * 2 + sum(widths) + gap * 3
    total_h = pad * 2 + height
    canvas = Image.new("RGBA", (total_w, total_h), (255, 255, 255, 255))
    x = pad
    for v, n in zip(views, names):
        v.resize((v.width * 8, v.height * 8), Image.Resampling.NEAREST).save(OUT / f"view-{n}@8x.png")
        y = pad + (height - v.height) // 2
        canvas.paste(v, (x, y), v)
        x += v.width + gap
    path = OUT / "views.png"
    canvas.convert("RGB").save(path)
    canvas.resize((canvas.width * 4, canvas.height * 4), Image.Resampling.NEAREST).save(OUT / "views@4x.png")
    print("wrote", path, canvas.size)
    return path


if __name__ == "__main__":
    sheet()
