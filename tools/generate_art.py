#!/usr/bin/env python3
"""Generates all of Jungleman's placeholder pixel art.

Everything here is drawn procedurally (no external assets), so the art is
original and can be regenerated or tweaked at any time:

    python3 tools/generate_art.py

Outputs PNG sprite sheets under assets/ and matching Godot SpriteFrames
(.tres) resources so the animations show up in the editor's SpriteFrames panel.
Requires Pillow (pip install pillow).
"""
import math
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPRITES = os.path.join(ROOT, "assets", "sprites")
TILES = os.path.join(ROOT, "assets", "tiles")
BG = os.path.join(ROOT, "assets", "backgrounds")


def hexc(s, a=255):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


OUTLINE = hexc("1a1008")


def new(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def plot(img, x, y, c):
    x = int(math.floor(x + 0.5))
    y = int(math.floor(y + 0.5))
    if 0 <= x < img.width and 0 <= y < img.height:
        img.putpixel((x, y), c)


def line(img, p0, p1, w, c):
    """Thick pixel line made of stamped squares."""
    x0, y0 = p0
    x1, y1 = p1
    n = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
    for i in range(n + 1):
        t = i / n
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        for dx in range(w):
            for dy in range(w):
                plot(img, x - (w - 1) / 2 + dx, y - (w - 1) / 2 + dy, c)


def rect(img, x0, y0, x1, y1, c):
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            plot(img, x, y, c)


def outline(img, c=OUTLINE):
    """Adds a 1px outline around every opaque pixel."""
    src = img.copy()
    px = src.load()
    w, h = src.size
    for x in range(w):
        for y in range(h):
            if px[x, y][3] != 0:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and px[nx, ny][3] != 0:
                    img.putpixel((x, y), c)
                    break
    return img


def rad(d):
    return math.radians(d)


def limb_end(start, ang, length):
    """ang in degrees from straight down; positive swings toward +x (forward)."""
    return (start[0] + math.sin(rad(ang)) * length, start[1] + math.cos(rad(ang)) * length)


# ---------------------------------------------------------------------------
# Player: a pith-helmeted jungle explorer drawn from a simple skeleton.
# ---------------------------------------------------------------------------
PAL = {
    "skin": hexc("e0a070"),
    "skin_dark": hexc("b07850"),
    "hair": hexc("4a2a14"),
    "hat": hexc("d8b878"),
    "hat_band": hexc("7a4a24"),
    "shirt": hexc("c8a860"),
    "shirt_dark": hexc("98783c"),
    "pants": hexc("5a6a3a"),
    "pants_dark": hexc("3e4a28"),
    "boot": hexc("4a2c14"),
    "belt": hexc("3a2410"),
    "eye": hexc("1a1008"),
    "whip": hexc("6a3c1c"),
}


def draw_player(p):
    img = new(32, 32)
    dy = p.get("dy", 0)
    hip = (16 + p.get("dx", 0), 20 + dy)
    lean = p.get("lean", 0)
    neck = limb_end(hip, 180 + lean, 8)
    shoulder = limb_end(neck, 180 + lean, -1)

    def leg(th, bend, pants, back):
        knee = limb_end(hip, th, 5)
        foot = limb_end(knee, th - bend, 6)
        line(img, hip, knee, 3, pants)
        line(img, knee, foot, 3, pants)
        fx, fy = int(math.floor(foot[0] + 0.5)), int(math.floor(foot[1] + 0.5))
        rect(img, fx - 1, fy - 1, fx + 2, fy, PAL["boot"] if not back else hexc("33200e"))

    def arm(sh, el, skin, sleeve, layer=None):
        dst = layer if layer is not None else img
        elbow = limb_end(shoulder, sh, 3)
        hand = limb_end(elbow, sh + el, 5)
        line(dst, shoulder, elbow, 2, sleeve)
        line(dst, elbow, hand, 2, skin)
        plot(dst, hand[0], hand[1], skin)
        return hand

    # back limbs first (darker), then torso, front leg, head, front arm
    back_hand = arm(p.get("bsh", -10), p.get("bel", 20), PAL["skin_dark"], PAL["shirt_dark"])
    leg(p.get("bth", -5), p.get("bkn", 5), PAL["pants_dark"], True)
    line(img, hip, neck, 5, PAL["shirt"])
    # belt
    line(img, limb_end(hip, 90 + lean, -2), limb_end(hip, 90 + lean, 2), 1, PAL["belt"])
    leg(p.get("fth", 5), p.get("fkn", 5), PAL["pants"], False)

    head = limb_end(neck, 180 + lean, 4)
    hx, hy = int(math.floor(head[0] + 0.5)), int(math.floor(head[1] + 0.5))
    rect(img, hx - 2, hy - 2, hx + 2, hy + 2, PAL["skin"])
    rect(img, hx - 2, hy - 2, hx - 1, hy + 1, PAL["hair"])
    plot(img, hx + 1, hy - 1, PAL["eye"])
    plot(img, hx + 2, hy + 1, PAL["skin_dark"])
    # pith helmet: dome + wide brim
    rect(img, hx - 2, hy - 5, hx + 2, hy - 3, PAL["hat"])
    rect(img, hx - 1, hy - 6, hx + 1, hy - 6, PAL["hat"])
    rect(img, hx - 4, hy - 2, hx + 4, hy - 2, PAL["hat"])
    rect(img, hx - 2, hy - 3, hx + 2, hy - 3, PAL["hat_band"])

    # the front arm gets its own outline so it reads clearly over the body
    layer = new(32, 32)
    front_hand = arm(p.get("fsh", 10), p.get("fel", 20), PAL["skin"], PAL["shirt_dark"], layer)
    if p.get("whip_handle"):
        d = limb_end(front_hand, p.get("fsh", 0) + p.get("fel", 0), 3)
        line(layer, front_hand, d, 1, PAL["whip"])
    if p.get("stone"):
        rect(layer, int(front_hand[0]), int(front_hand[1]) - 1, int(front_hand[0]) + 1, int(front_hand[1]), hexc("8a8a8a"))
    _ = back_hand
    img = outline(img)
    img.alpha_composite(outline(layer, PAL["skin_dark"]))
    return img


def run_pose(i, n=6):
    ph = 2 * math.pi * i / n
    s, c = math.sin(ph), math.cos(ph)
    return {
        "lean": 10,
        "dy": 1 if abs(s) > 0.8 else 0,
        "fth": 38 * s,
        "fkn": 15 + 55 * max(0.0, c),
        "bth": -38 * s,
        "bkn": 15 + 55 * max(0.0, -c),
        "fsh": -45 * s,
        "fel": 70,
        "bsh": 45 * s,
        "bel": 70,
    }


def rotate_frame(img, deg, pivot, shift=(0, 0)):
    out = img.rotate(deg, resample=Image.NEAREST, center=pivot, translate=shift)
    return out


def player_animations():
    hang = {"fsh": 158, "fel": 4, "bsh": 202, "bel": -4, "lean": 0}
    anims = []
    anims.append(("idle", 3, True, [
        draw_player({"fsh": 8, "bsh": -8, "fel": 10, "bel": 10, "fth": 4, "bth": -4}),
        draw_player({"dy": 1, "fsh": 10, "bsh": -10, "fel": 14, "bel": 14, "fth": 6, "fkn": 12, "bth": -6, "bkn": 12}),
    ]))
    anims.append(("run", 12, True, [draw_player(run_pose(i)) for i in range(6)]))
    anims.append(("jump", 8, False, [
        draw_player({"lean": 5, "dy": -3, "fth": 60, "fkn": 85, "bth": 15, "bkn": 70, "fsh": 150, "fel": 10, "bsh": -60, "bel": 40}),
    ]))
    anims.append(("fall", 8, True, [
        draw_player({"lean": 0, "fth": 25, "fkn": 25, "bth": -15, "bkn": 30, "fsh": 130, "fel": 20, "bsh": -130, "bel": -20}),
        draw_player({"lean": 0, "fth": 30, "fkn": 30, "bth": -20, "bkn": 25, "fsh": 140, "fel": 10, "bsh": -140, "bel": -10}),
    ]))
    anims.append(("crouch", 1, False, [
        draw_player({"lean": 20, "dy": 5, "fth": 60, "fkn": 120, "bth": 20, "bkn": 100, "fsh": 40, "fel": 40, "bsh": 10, "bel": 40}),
    ]))
    anims.append(("whip", 14, False, [
        draw_player({"lean": -5, "fth": 20, "fkn": 20, "bth": -15, "bkn": 10, "fsh": -150, "fel": -20, "bsh": -30, "bel": 20, "whip_handle": True}),
        draw_player({"lean": 5, "fth": 20, "fkn": 20, "bth": -15, "bkn": 10, "fsh": 160, "fel": -10, "bsh": -30, "bel": 20, "whip_handle": True}),
        draw_player({"lean": 10, "fth": 22, "fkn": 20, "bth": -15, "bkn": 10, "fsh": 95, "fel": 0, "bsh": -30, "bel": 20, "whip_handle": True}),
    ]))
    anims.append(("throw", 12, False, [
        draw_player({"lean": -5, "fth": 20, "fkn": 20, "bth": -15, "bkn": 10, "fsh": -110, "fel": -40, "bsh": 30, "bel": 20, "stone": True}),
        draw_player({"lean": 10, "fth": 25, "fkn": 20, "bth": -15, "bkn": 10, "fsh": 110, "fel": 0, "bsh": -30, "bel": 20}),
    ]))
    anims.append(("swing", 6, True, [
        draw_player(dict(hang, fth=18, fkn=25, bth=10, bkn=30)),
        draw_player(dict(hang, fth=5, fkn=10, bth=-2, bkn=15)),
        draw_player(dict(hang, fth=-10, fkn=5, bth=-16, bkn=10)),
        draw_player(dict(hang, fth=5, fkn=10, bth=-2, bkn=15)),
    ]))
    anims.append(("climb", 8, True, [
        draw_player({"lean": 0, "fsh": 160, "fel": 0, "bsh": 205, "bel": -25, "fth": 30, "fkn": 50, "bth": 0, "bkn": 5}),
        draw_player({"lean": 0, "fsh": 150, "fel": 25, "bsh": 200, "bel": 0, "fth": 0, "fkn": 5, "bth": 30, "bkn": 50}),
    ]))
    anims.append(("zip", 6, True, [
        draw_player(dict(hang, fth=45, fkn=40, bth=35, bkn=45)),
        draw_player(dict(hang, fth=50, fkn=35, bth=40, bkn=40)),
    ]))
    anims.append(("struggle", 6, True, [
        draw_player({"lean": 0, "fsh": 150, "fel": 30, "bsh": 200, "bel": -10, "fth": 10, "bth": -10}),
        draw_player({"lean": 0, "fsh": 200, "fel": -10, "bsh": 150, "bel": 30, "fth": -10, "bth": 10}),
    ]))
    hurt = draw_player({"lean": -18, "fth": 25, "fkn": 20, "bth": -10, "bkn": 10, "fsh": 120, "fel": 20, "bsh": -120, "bel": -20})
    anims.append(("hurt", 1, False, [hurt]))
    anims.append(("die", 6, False, [
        hurt,
        rotate_frame(hurt, 45, (16, 31), (6, 0)),
        rotate_frame(hurt, 90, (16, 31), (13, -3)),
    ]))
    return anims


# ---------------------------------------------------------------------------
# Enemies
# ---------------------------------------------------------------------------
def snake_frames():
    green, dark, belly, red = hexc("3c8c3c"), hexc("24602a"), hexc("c8c040"), hexc("d02020")
    frames = []
    for strike in (False, True):
        img = new(24, 16)
        d = ImageDraw.Draw(img)
        d.ellipse((3, 10, 19, 15), fill=green)
        d.ellipse((6, 7, 16, 12), fill=green)
        for x in (5, 9, 13, 17):
            plot(img, x, 12, dark)
        if not strike:
            line(img, (12, 8), (14, 4), 3, green)
            d.ellipse((13, 2, 19, 6), fill=green)
            plot(img, 17, 3, hexc("ffe040"))
            plot(img, 20, 5, red)
        else:
            line(img, (12, 8), (17, 5), 3, green)
            d.ellipse((17, 3, 23, 7), fill=green)
            plot(img, 21, 4, hexc("ffe040"))
            line(img, (23, 6), (23, 7), 1, red)
        line(img, (7, 14), (17, 14), 1, belly)
        frames.append(outline(img))
    return frames


def scorpion_frames():
    body, dark, sting = hexc("9c3c1c"), hexc("6a2410"), hexc("f0d040")
    frames = []
    for f in range(2):
        img = new(20, 14)
        d = ImageDraw.Draw(img)
        # legs
        for i, x in enumerate((7, 10, 13)):
            off = 1 if (i + f) % 2 == 0 else -1
            line(img, (x, 10), (x + off, 13), 1, dark)
        d.ellipse((5, 7, 15, 11), fill=body)
        # claws
        line(img, (14, 9), (17, 8), 1, body)
        d.ellipse((16, 6, 19, 9), fill=body)
        # tail curling over the back
        pts = [(6, 9), (3, 8), (2, 5), (3, 2), (6, 1), (8, 2)]
        for a, b in zip(pts, pts[1:]):
            line(img, a, b, 2, body)
        plot(img, 9, 3 + f, sting)
        plot(img, 16, 8, hexc("101010"))
        frames.append(outline(img))
    return frames


def bat_frames():
    body, wing, eye = hexc("5a4a6a"), hexc("3a2e4a"), hexc("ff3030")
    frames = []
    for up in (True, False):
        img = new(20, 12)
        d = ImageDraw.Draw(img)
        if up:
            d.polygon([(9, 6), (1, 0), (3, 4), (0, 5)], fill=wing)
            d.polygon([(10, 6), (18, 0), (16, 4), (19, 5)], fill=wing)
        else:
            d.polygon([(9, 5), (1, 10), (4, 8), (0, 7)], fill=wing)
            d.polygon([(10, 5), (18, 10), (15, 8), (19, 7)], fill=wing)
        d.ellipse((7, 3, 12, 9), fill=body)
        plot(img, 8, 5, eye)
        plot(img, 11, 5, eye)
        plot(img, 8, 2, body)
        plot(img, 11, 2, body)
        frames.append(outline(img))
    return frames


def croc_frames():
    green, dark, belly, eye = hexc("4a7a2a"), hexc("2e5418"), hexc("a8b060"), hexc("f0e040")
    teeth, mouth = hexc("f8f8f0"), hexc("a02828")
    frames = []
    for open_ in (False, True):
        img = new(48, 20)
        d = ImageDraw.Draw(img)
        d.ellipse((12, 9, 47, 19), fill=green)  # back
        for x in range(16, 44, 4):  # ridges
            plot(img, x, 9, dark)
            plot(img, x + 1, 8, dark)
        d.rectangle((2, 14, 20, 17), fill=green)  # lower jaw
        if open_:
            d.polygon([(20, 13), (6, 13), (6, 15), (20, 15)], fill=mouth)
            d.polygon([(20, 13), (2, 3), (0, 6), (18, 15)], fill=green)  # upper jaw raised
            for x in range(4, 18, 3):
                plot(img, x, 13, teeth)
                plot(img, x + 1, 7 + (x - 4) // 3, teeth)
        else:
            d.rectangle((0, 11, 20, 14), fill=green)  # upper jaw closed
            for x in range(3, 18, 3):
                plot(img, x, 14, teeth)
            plot(img, 1, 11, dark)
        d.ellipse((17, 6, 23, 11), fill=green)  # eye bump
        plot(img, 19, 8, eye)
        plot(img, 20, 8, hexc("101010"))
        line(img, (22, 17), (44, 17), 1, belly)
        frames.append(outline(img))
    return frames


def log_frames():
    bark, ring, light = hexc("6a4020"), hexc("a07040"), hexc("c89860")
    frames = []
    for f in range(4):
        img = new(16, 16)
        d = ImageDraw.Draw(img)
        d.ellipse((1, 1, 14, 14), fill=bark)
        d.ellipse((4, 4, 11, 11), fill=ring)
        d.ellipse((6, 6, 9, 9), fill=light)
        a = -f * math.pi / 2
        plot(img, 7.5 + math.cos(a) * 5, 7.5 + math.sin(a) * 5, hexc("3a2410"))
        plot(img, 7.5 + math.cos(a + 0.4) * 5, 7.5 + math.sin(a + 0.4) * 5, hexc("3a2410"))
        frames.append(outline(img))
    return frames


# ---------------------------------------------------------------------------
# Items (16x16 each, laid out in a single row)
# ITEM ORDER must match scripts/pickup.gd and scripts/checkpoint.gd
# ---------------------------------------------------------------------------
def items_sheet():
    gold, gold_l, gold_d = hexc("f0c030"), hexc("fff090"), hexc("b08010")
    stone, stone_d, stone_l = hexc("8a8a80"), hexc("5a5a52"), hexc("b0b0a8")
    tiles = []

    img = new(16, 16)  # 0 gold bar
    d = ImageDraw.Draw(img)
    d.polygon([(2, 12), (13, 12), (11, 6), (4, 6)], fill=gold)
    line(img, (5, 7), (9, 7), 1, gold_l)
    line(img, (2, 12), (13, 12), 1, gold_d)
    tiles.append(outline(img))

    img = new(16, 16)  # 1 sling stones bag
    d = ImageDraw.Draw(img)
    d.ellipse((3, 5, 12, 14), fill=hexc("8a6a3a"))
    rect(img, 6, 3, 9, 5, hexc("8a6a3a"))
    line(img, (5, 5), (10, 5), 1, hexc("4a3010"))
    d.ellipse((5, 8, 8, 11), fill=stone)
    d.ellipse((8, 9, 11, 12), fill=stone_l)
    tiles.append(outline(img))

    img = new(16, 16)  # 2 canteen (health)
    d = ImageDraw.Draw(img)
    d.ellipse((2, 4, 13, 15), fill=hexc("5a7a6a"))
    d.ellipse((4, 6, 11, 13), fill=hexc("7a9a8a"))
    rect(img, 6, 1, 9, 4, hexc("8a6a3a"))
    line(img, (1, 6), (5, 1), 1, hexc("4a3010"))
    line(img, (14, 6), (10, 1), 1, hexc("4a3010"))
    line(img, (7, 8), (7, 11), 1, hexc("e04040"))
    line(img, (6, 9), (8, 9), 1, hexc("e04040"))
    tiles.append(outline(img))

    img = new(16, 16)  # 3 extra life: golden explorer statuette
    d = ImageDraw.Draw(img)
    rect(img, 4, 13, 11, 14, gold_d)
    rect(img, 6, 6, 9, 12, gold)
    d.ellipse((5, 2, 10, 7), fill=gold)
    rect(img, 3, 3, 12, 3, gold_l)
    rect(img, 5, 1, 10, 2, gold_l)
    plot(img, 8, 4, gold_d)
    tiles.append(outline(img))

    for active in (False, True):  # 4 idle checkpoint idol, 5 active
        img = new(16, 16)
        body = gold if active else stone
        dk = gold_d if active else stone_d
        rect(img, 2, 2, 13, 15, body)
        rect(img, 2, 2, 13, 3, dk)
        rect(img, 4, 6, 6, 7, hexc("30e070") if active else dk)
        rect(img, 9, 6, 11, 7, hexc("30e070") if active else dk)
        rect(img, 7, 8, 8, 10, dk)
        rect(img, 4, 12, 11, 12, dk)
        for x in (4, 6, 8, 10):
            plot(img, x, 13, dk)
        rect(img, 0, 4, 1, 9, dk)
        rect(img, 14, 4, 15, 9, dk)
        tiles.append(outline(img))

    img = new(16, 16)  # 6 sling stone projectile
    d = ImageDraw.Draw(img)
    d.ellipse((6, 6, 9, 9), fill=stone)
    plot(img, 7, 7, stone_l)
    tiles.append(outline(img))

    sheet = new(16 * len(tiles), 16)
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * 16, 0))
    return sheet


# ---------------------------------------------------------------------------
# Tiles (16x16, laid out in a single row)
# TILE ORDER must match scripts/level.gd
# ---------------------------------------------------------------------------
def tiles_sheet():
    dirt, dirt_d, dirt_l = hexc("7a4a28"), hexc("5a341a"), hexc("94603a")
    grass, grass_d, grass_l = hexc("3a8a2a"), hexc("246018"), hexc("6ab84a")
    brick, brick_d, brick_l = hexc("8a8470"), hexc("5e584a"), hexc("aaa490")
    moss = hexc("4a7a3a")
    wood, wood_d, wood_l = hexc("9a6a34"), hexc("6a4420"), hexc("c0905a")
    tar, tar_l = hexc("1a1420"), hexc("3a3048")
    water, water_l, water_d = hexc("2a6a8a"), hexc("6ab0c8"), hexc("1a4a6a")
    out = []
    rng = [3, 7, 11, 2, 13, 5, 9, 1, 14, 6, 10, 4, 12, 8, 0, 15]

    def dirt_tile(rocks):
        img = Image.new("RGBA", (16, 16), dirt)
        for i in range(16):
            plot(img, rng[i], rng[(i * 5) % 16], dirt_d if i % 2 else dirt_l)
        if rocks:
            ImageDraw.Draw(img).ellipse((3, 8, 8, 12), fill=hexc("8a8a80"))
            ImageDraw.Draw(img).ellipse((10, 2, 13, 5), fill=hexc("6a6a62"))
        return img

    img = dirt_tile(False)  # 0 grass top
    rect(img, 0, 0, 15, 3, grass)
    for x in range(0, 16, 2):
        plot(img, x, 4 + (x // 2) % 2, grass_d)
        plot(img, x + 1, 0, grass_l)
    out.append(img)
    out.append(dirt_tile(False))  # 1 dirt
    out.append(dirt_tile(True))  # 2 dirt with rocks

    def brick_tile(mossy):
        img = Image.new("RGBA", (16, 16), brick)
        rect(img, 0, 7, 15, 7, brick_d)
        rect(img, 0, 15, 15, 15, brick_d)
        rect(img, 7, 0, 7, 7, brick_d)
        rect(img, 3, 8, 3, 15, brick_d)
        rect(img, 12, 8, 12, 15, brick_d)
        rect(img, 0, 0, 6, 0, brick_l)
        rect(img, 8, 0, 15, 0, brick_l)
        rect(img, 4, 8, 11, 8, brick_l)
        if mossy:
            for x in range(16):
                for y in range(0, 2 + (x * 7) % 4):
                    plot(img, x, y, moss)
        return img

    out.append(brick_tile(False))  # 3 temple brick
    out.append(brick_tile(True))  # 4 mossy temple brick

    img = new(16, 16)  # 5 wooden ledge (one-way)
    rect(img, 0, 0, 15, 4, wood)
    rect(img, 0, 0, 15, 0, wood_l)
    rect(img, 0, 4, 15, 4, wood_d)
    rect(img, 2, 5, 3, 9, wood_d)
    rect(img, 12, 5, 13, 9, wood_d)
    plot(img, 7, 2, wood_d)
    out.append(img)

    img = new(16, 16)  # 6 bridge plank
    rect(img, 1, 0, 14, 4, wood)
    rect(img, 1, 0, 14, 0, wood_l)
    rect(img, 1, 4, 14, 4, wood_d)
    rect(img, 0, 1, 0, 2, hexc("c8b080"))
    rect(img, 15, 1, 15, 2, hexc("c8b080"))
    out.append(img)

    img = new(16, 16)  # 7 vine segment
    rect(img, 7, 0, 8, 15, hexc("4a8a2a"))
    rect(img, 7, 0, 7, 15, hexc("2e6018"))
    rect(img, 9, 3, 11, 4, hexc("6ab84a"))
    rect(img, 4, 10, 6, 11, hexc("6ab84a"))
    out.append(img)

    img = Image.new("RGBA", (16, 16), tar)  # 8 tar surface
    rect(img, 0, 0, 15, 1, tar_l)
    ImageDraw.Draw(img).ellipse((4, 1, 7, 4), outline=tar_l)
    plot(img, 12, 2, tar_l)
    out.append(img)
    img = Image.new("RGBA", (16, 16), tar)  # 9 tar body
    plot(img, 3, 6, tar_l)
    plot(img, 11, 11, tar_l)
    out.append(img)

    img = Image.new("RGBA", (16, 16), water)  # 10 water surface
    for x in range(16):
        plot(img, x, 1 + int(math.sin(x / 16 * 2 * math.pi) * 1.5), water_l)
    rect(img, 2, 6, 5, 6, water_l)
    out.append(img)
    img = Image.new("RGBA", (16, 16), water_d)  # 11 water body
    rect(img, 9, 5, 12, 5, water)
    rect(img, 2, 12, 4, 12, water)
    out.append(img)

    sheet = new(16 * len(out), 16)
    for i, t in enumerate(out):
        sheet.paste(t, (i * 16, 0))
    return sheet


def temple_facade():
    """Mayan step-temple used for the level exit (112x96)."""
    w, h = 112, 96
    img = new(w, h)
    stone, dark, light, moss = hexc("9a9078"), hexc("6a6250"), hexc("bab098"), hexc("4a7a3a")
    steps = 5
    for i in range(steps):
        x0 = 4 + i * 10
        x1 = w - 5 - i * 10
        y1 = h - 1 - i * 14
        y0 = y1 - 13
        rect(img, x0, y0, x1, y1, stone)
        rect(img, x0, y0, x1, y0, light)
        rect(img, x0, y1, x1, y1, dark)
        for x in range(x0 + 3, x1, 8):
            rect(img, x, y0 + 4, x + 3, y0 + 7, dark)
        for x in range(x0, x1, 5):
            plot(img, x, y0 + 1, moss)
    # roof shrine
    rect(img, 44, 12, 67, 26, stone)
    rect(img, 44, 12, 67, 12, light)
    rect(img, 50, 16, 61, 26, dark)
    # doorway (player walks into this)
    rect(img, 44, 56, 67, 95, hexc("140c08"))
    rect(img, 42, 54, 69, 55, light)
    rect(img, 42, 54, 43, 95, dark)
    rect(img, 68, 54, 69, 95, dark)
    # glyph eyes above door
    rect(img, 48, 46, 51, 49, hexc("f0c030"))
    rect(img, 60, 46, 63, 49, hexc("f0c030"))
    return outline(img)


# ---------------------------------------------------------------------------
# Parallax backgrounds (480x270, tile horizontally)
# ---------------------------------------------------------------------------
def bg_far():
    w, h = 480, 270
    img = new(w, h)
    top, bottom = hexc("1e5a6a"), hexc("c8d890")
    for y in range(h):
        t = y / (h - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,)
        for x in range(w):
            img.putpixel((x, y), c)
    d = ImageDraw.Draw(img)
    hill = hexc("6a9a6a")
    pts = [(0, h)]
    for x in range(0, w + 1, 8):
        pts.append((x, 170 + 18 * math.sin(x / w * 2 * math.pi * 2) + 8 * math.sin(x / 23.0)))
    pts.append((w, h))
    d.polygon(pts, fill=hill)
    # distant pyramid silhouette
    pyr = hexc("4e7a5a")
    for i in range(6):
        d.rectangle((300 + i * 7, 200 - (i + 1) * 14, 380 - i * 7, 200 - i * 14), fill=pyr)
    d.rectangle((332, 104, 348, 116), fill=pyr)
    return img


def bg_mid():
    w, h = 480, 270
    img = new(w, h)
    d = ImageDraw.Draw(img)
    trunk, trunk_d = hexc("3a4a2a"), hexc("2a3a1e")
    leaf, leaf_d = hexc("2e6a2a"), hexc("1e4a1e")
    for i, x in enumerate(range(20, w, 70)):
        tw = 10 + (i * 7) % 8
        d.rectangle((x, 60, x + tw, h), fill=trunk)
        d.rectangle((x, 60, x + 2, h), fill=trunk_d)
    for x in range(-20, w + 20, 34):
        r = 24 + (x * 13) % 14
        cy = 40 + (x * 7) % 30
        d.ellipse((x - r, cy - r, x + r, cy + r), fill=leaf_d)
        d.ellipse((x - r + 6, cy - r + 4, x + r - 6, cy + r - 8), fill=leaf)
    d.rectangle((0, 0, w, 20), fill=leaf_d)
    # undergrowth
    for x in range(0, w, 12):
        r = 10 + (x * 5) % 8
        d.ellipse((x - r, 236 - r, x + r, 236 + r), fill=leaf_d)
    d.rectangle((0, 236, w, h), fill=leaf_d)
    # hanging vines (decorative)
    for x in range(45, w, 95):
        ln = 50 + (x * 3) % 60
        d.line((x, 20, x, 20 + ln), fill=hexc("3a7a2a"), width=2)
    return img


# ---------------------------------------------------------------------------
# Sheet + SpriteFrames writers
# ---------------------------------------------------------------------------
def write_sheet(name, anims, fw, fh):
    """anims: list of (name, fps, loop, [frames]). One animation per row."""
    cols = max(len(a[3]) for a in anims)
    sheet = new(cols * fw, len(anims) * fh)
    for r, (_, _, _, frames) in enumerate(anims):
        for c, f in enumerate(frames):
            sheet.paste(f, (c * fw, r * fh))
    png = os.path.join(SPRITES, name + ".png")
    sheet.save(png)

    subs = []
    anim_entries = []
    sid = 0
    for r, (aname, fps, loop, frames) in enumerate(anims):
        frame_refs = []
        for c in range(len(frames)):
            sid += 1
            subs.append(
                f'[sub_resource type="AtlasTexture" id="AtlasTexture_{sid}"]\n'
                f'atlas = ExtResource("1_sheet")\n'
                f"region = Rect2({c * fw}, {r * fh}, {fw}, {fh})\n"
            )
            frame_refs.append(
                '{\n"duration": 1.0,\n"texture": SubResource("AtlasTexture_%d")\n}' % sid
            )
        anim_entries.append(
            '{\n"frames": [%s],\n"loop": %s,\n"name": &"%s",\n"speed": %.1f\n}'
            % (", ".join(frame_refs), "true" if loop else "false", aname, fps)
        )
    tres = (
        f'[gd_resource type="SpriteFrames" load_steps={sid + 2} format=3]\n\n'
        f'[ext_resource type="Texture2D" path="res://assets/sprites/{name}.png" id="1_sheet"]\n\n'
        + "\n".join(subs)
        + "\n[resource]\nanimations = ["
        + ", ".join(anim_entries)
        + "]\n"
    )
    with open(os.path.join(SPRITES, name + "_frames.tres"), "w", newline="\n") as fh_:
        fh_.write(tres)


def main():
    for d in (SPRITES, TILES, BG):
        os.makedirs(d, exist_ok=True)
    write_sheet("player", player_animations(), 32, 32)
    s = snake_frames()
    write_sheet("snake", [("idle", 3, True, [s[0]]), ("strike", 1, False, [s[1]])], 24, 16)
    write_sheet("scorpion", [("walk", 6, True, scorpion_frames())], 20, 14)
    write_sheet("bat", [("fly", 8, True, bat_frames())], 20, 12)
    c = croc_frames()
    write_sheet("croc", [("closed", 1, False, [c[0]]), ("open", 1, False, [c[1]])], 48, 20)
    write_sheet("log", [("roll", 10, True, log_frames())], 16, 16)
    items_sheet().save(os.path.join(SPRITES, "items.png"))
    temple_facade().save(os.path.join(SPRITES, "temple.png"))
    tiles_sheet().save(os.path.join(TILES, "jungle_tiles.png"))
    bg_far().save(os.path.join(BG, "bg_far.png"))
    bg_mid().save(os.path.join(BG, "bg_mid.png"))
    print("art generated")


if __name__ == "__main__":
    main()
