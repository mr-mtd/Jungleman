#!/usr/bin/env python3
"""Generates all of Jungleman's art in a smooth, high-resolution style.

Everything is drawn procedurally (no external assets), so the art is original
and can be regenerated or tweaked at any time:

    python3 tools/generate_art.py

Shapes are drawn with soft gradients, rim light and outlines, supersampled for
clean anti-aliased edges, then saved at 4 texture pixels per world pixel
(`S` below). In-game sprites are scaled by 1/S, so gameplay sizes stay the same
while the art stays sharp at 1080p.

Requires Pillow and NumPy (pip install pillow numpy).
"""
import math
import os
import random

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPRITES = os.path.join(ROOT, "assets", "sprites")
TILES = os.path.join(ROOT, "assets", "tiles")
BG = os.path.join(ROOT, "assets", "backgrounds")
FX = os.path.join(ROOT, "assets", "fx")

S = 4  # texture pixels per world pixel
AA = 3  # supersampling factor while drawing


def hexc(s, a=255):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


def mix(c0, c1, t):
    return tuple(int(round(c0[i] + (c1[i] - c0[i]) * t)) for i in range(4))


def shade(c, f):
    """f > 0 lightens toward white, f < 0 darkens toward black."""
    if f >= 0:
        return mix(c, (255, 255, 255, c[3]), f)
    return mix(c, (0, 0, 0, c[3]), -f)


class Lin:
    """Linear gradient between two world-space points."""

    def __init__(self, c0, c1, p0, p1):
        self.c0, self.c1, self.p0, self.p1 = c0, c1, p0, p1


class Rad:
    """Radial gradient from a world-space centre."""

    def __init__(self, c0, c1, center, radius):
        self.c0, self.c1, self.center, self.radius = c0, c1, center, radius


class Canvas:
    """RGBA drawing surface addressed in world units, supersampled."""

    def __init__(self, w, h, aa=AA, scale=S):
        self.w, self.h = w, h
        self.scale = scale
        self.k = scale * aa
        self.size = (int(round(w * self.k)), int(round(h * self.k)))
        self.img = Image.new("RGBA", self.size, (0, 0, 0, 0))

    # -- masks -----------------------------------------------------------
    def _m(self):
        return Image.new("L", self.size, 0)

    def _p(self, pts):
        return [(x * self.k, y * self.k) for x, y in pts]

    def m_ellipse(self, cx, cy, rx, ry):
        m = self._m()
        k = self.k
        ImageDraw.Draw(m).ellipse(((cx - rx) * k, (cy - ry) * k, (cx + rx) * k, (cy + ry) * k), fill=255)
        return m

    def m_poly(self, pts):
        m = self._m()
        ImageDraw.Draw(m).polygon(self._p(pts), fill=255)
        return m

    def m_rrect(self, x0, y0, x1, y1, r):
        m = self._m()
        k = self.k
        ImageDraw.Draw(m).rounded_rectangle((x0 * k, y0 * k, x1 * k, y1 * k), radius=r * k, fill=255)
        return m

    def m_stroke(self, pts, r, r_end=None):
        """Round-capped stroke through points; radius can taper to r_end."""
        m = self._m()
        d = ImageDraw.Draw(m)
        k = self.k
        n = len(pts)
        r_end = r if r_end is None else r_end
        for i in range(n - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            ra = r + (r_end - r) * i / max(n - 1, 1)
            rb = r + (r_end - r) * (i + 1) / max(n - 1, 1)
            dx, dy = x1 - x0, y1 - y0
            ln = math.hypot(dx, dy) or 1e-6
            nx, ny = -dy / ln, dx / ln
            quad = [(x0 + nx * ra, y0 + ny * ra), (x1 + nx * rb, y1 + ny * rb), (x1 - nx * rb, y1 - ny * rb), (x0 - nx * ra, y0 - ny * ra)]
            d.polygon(self._p(quad), fill=255)
        for i, (x, y) in enumerate(pts):
            rr = (r + (r_end - r) * i / max(n - 1, 1)) * k
            d.ellipse((x * k - rr, y * k - rr, x * k + rr, y * k + rr), fill=255)
        return m

    # -- painting --------------------------------------------------------
    def _paint_img(self, paint, bbox):
        w, h = self.size
        if isinstance(paint, tuple):
            return Image.new("RGBA", self.size, paint)
        x0, y0, x1, y1 = bbox
        xs = (np.arange(x0, x1) + 0.5) / self.k
        ys = (np.arange(y0, y1) + 0.5) / self.k
        X, Y = np.meshgrid(xs, ys)
        if isinstance(paint, Lin):
            (ax, ay), (bx, by) = paint.p0, paint.p1
            dx, dy = bx - ax, by - ay
            t = ((X - ax) * dx + (Y - ay) * dy) / max(dx * dx + dy * dy, 1e-6)
        else:
            cx, cy = paint.center
            t = np.hypot(X - cx, Y - cy) / max(paint.radius, 1e-6)
        t = np.clip(t, 0.0, 1.0)[..., None]
        c0 = np.array(paint.c0, dtype=np.float32)
        c1 = np.array(paint.c1, dtype=np.float32)
        arr = np.zeros((h, w, 4), dtype=np.uint8)
        arr[y0:y1, x0:x1] = (c0 + (c1 - c0) * t).astype(np.uint8)
        return Image.fromarray(arr, "RGBA")

    def fill(self, mask, paint, alpha=1.0):
        bbox = mask.getbbox()
        if not bbox:
            return
        src = self._paint_img(paint, bbox)
        a = ImageChops.multiply(src.getchannel("A"), mask)
        if alpha < 1.0:
            a = a.point(lambda v: int(v * alpha))
        src.putalpha(a)
        self.img.alpha_composite(src)

    def ellipse(self, cx, cy, rx, ry, paint, alpha=1.0):
        self.fill(self.m_ellipse(cx, cy, rx, ry), paint, alpha)

    def poly(self, pts, paint, alpha=1.0):
        self.fill(self.m_poly(pts), paint, alpha)

    def rrect(self, x0, y0, x1, y1, r, paint, alpha=1.0):
        self.fill(self.m_rrect(x0, y0, x1, y1, r), paint, alpha)

    def stroke(self, pts, r, paint, r_end=None, alpha=1.0):
        self.fill(self.m_stroke(pts, r, r_end), paint, alpha)

    def blur_layer(self, draw_fn, radius):
        """Draw onto a temporary canvas, blur it and composite (glows, shadows)."""
        tmp = Canvas(self.w, self.h, aa=self.k // self.scale, scale=self.scale)
        draw_fn(tmp)
        blurred = tmp.img.convert("RGBa").filter(ImageFilter.GaussianBlur(radius * self.k)).convert("RGBA")
        self.img.alpha_composite(blurred)

    def outline(self, color, width):
        """Adds an outline behind everything drawn so far."""
        r = max(1, int(round(width * self.k)))
        a = self.img.getchannel("A").point(lambda v: 255 if v > 40 else 0)
        grown = a.filter(ImageFilter.MaxFilter(2 * r + 1)).filter(ImageFilter.GaussianBlur(self.k * 0.25))
        under = Image.new("RGBA", self.size, color)
        under.putalpha(grown)
        under.alpha_composite(self.img)
        self.img = under

    def paste(self, other):
        self.img.alpha_composite(other.img)

    def final(self):
        img = self.img
        if getattr(self, "under", None) is not None:
            img = self.under.img.copy()
            img.alpha_composite(self.img)
        out = img.convert("RGBa").resize((int(round(self.w * self.scale)), int(round(self.h * self.scale))), Image.LANCZOS)
        return out.convert("RGBA")


def rad(d):
    return math.radians(d)


def limb_end(start, ang, length):
    """ang in degrees from straight down; positive swings toward +x (forward)."""
    return (start[0] + math.sin(rad(ang)) * length, start[1] + math.cos(rad(ang)) * length)


def catmull(points, steps=8):
    out = []
    pts = [points[0]] + list(points) + [points[-1]]
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(2)))
    out.append(points[-1])
    return out


# ---------------------------------------------------------------------------
# Player: a jungle explorer in a pith helmet, built from a posable skeleton.
# ---------------------------------------------------------------------------
INK = hexc("2a1a10")
PAL = {
    "skin": hexc("f2b68a"),
    "skin_d": hexc("c9825a"),
    "hair": hexc("5a3218"),
    "hat": hexc("efd9a2"),
    "hat_d": hexc("b8975a"),
    "band": hexc("7a4a24"),
    "shirt": hexc("e4c47c"),
    "shirt_d": hexc("a8823e"),
    "pants": hexc("6f7f45"),
    "pants_d": hexc("44522a"),
    "boot": hexc("6a3f1f"),
    "boot_d": hexc("3a2210"),
    "strap": hexc("7a4a24"),
    "whip": hexc("7a4422"),
}
LIGHT = (-0.55, -1.0)  # light comes from the upper left


def lit(c_light, c_dark, center, size):
    lx, ly = LIGHT
    ln = math.hypot(lx, ly)
    lx, ly = lx / ln, ly / ln
    p0 = (center[0] + lx * size, center[1] + ly * size)
    p1 = (center[0] - lx * size, center[1] - ly * size)
    return Lin(c_light, c_dark, p0, p1)


def draw_player(p):
    c = Canvas(32, 32)
    dy = p.get("dy", 0)
    hip = (16 + p.get("dx", 0), 20 + dy)
    lean = p.get("lean", 0)
    neck = limb_end(hip, 180 + lean, 7.5)
    shoulder = limb_end(neck, 180 + lean, -0.8)

    def leg(cv, th, bend, back):
        knee = limb_end(hip, th, 5.2)
        foot = limb_end(knee, th - bend, 5.4)
        pants = PAL["pants_d"] if back else PAL["pants"]
        dark = shade(pants, -0.35)
        cv.stroke([hip, knee], 1.75, lit(shade(pants, 0.15), dark, knee, 3))
        cv.stroke([knee, foot], 1.55, lit(shade(pants, 0.1), dark, foot, 3))
        bc = PAL["boot_d"] if back else PAL["boot"]
        cv.rrect(foot[0] - 1.6, foot[1] - 1.6, foot[0] + 2.6, foot[1] + 0.6, 1.0, lit(shade(bc, 0.25), shade(bc, -0.3), foot, 2))

    def arm(cv, sh, el, back):
        elbow = limb_end(shoulder, sh, 3.2)
        hand = limb_end(elbow, sh + el, 4.4)
        sleeve = PAL["shirt_d"] if back else PAL["shirt"]
        skin = PAL["skin_d"] if back else PAL["skin"]
        cv.stroke([elbow, hand], 1.05, lit(shade(skin, 0.1), shade(skin, -0.25), hand, 3))
        cv.ellipse(hand[0], hand[1], 1.2, 1.2, lit(shade(skin, 0.15), shade(skin, -0.25), hand, 1.5))
        cv.stroke([shoulder, elbow], 1.35, lit(shade(sleeve, 0.15), shade(sleeve, -0.3), elbow, 3))
        return hand

    # back limbs
    arm(c, p.get("bsh", -10), p.get("bel", 20), True)
    leg(c, p.get("bth", -5), p.get("bkn", 5), True)
    # torso
    mid = ((hip[0] + neck[0]) / 2, (hip[1] + neck[1]) / 2)
    c.stroke([hip, neck], 2.7, lit(shade(PAL["shirt"], 0.2), PAL["shirt_d"], mid, 5))
    # satchel strap and belt
    c.stroke([limb_end(neck, 90 + lean, 1.6), limb_end(hip, 90 + lean, -2.0)], 0.45, PAL["strap"])
    c.stroke([limb_end(hip, 90 + lean, -2.6), limb_end(hip, 90 + lean, 2.6)], 0.6, hexc("4a2a14"))
    leg(c, p.get("fth", 5), p.get("fkn", 5), False)

    # head
    head = limb_end(neck, 180 + lean, 3.6)
    hx, hy = head
    c.ellipse(hx + 0.2, hy + 0.3, 2.9, 3.0, lit(shade(PAL["skin"], 0.15), PAL["skin_d"], head, 3))
    c.ellipse(hx - 1.6, hy + 0.2, 1.5, 1.9, PAL["hair"])
    c.ellipse(hx - 0.6, hy + 0.6, 0.6, 0.8, shade(PAL["skin_d"], -0.05))  # ear
    c.ellipse(hx + 1.5, hy + 0.1, 0.45, 0.6, hexc("2a1a10"))  # eye
    c.ellipse(hx + 1.65, hy - 0.1, 0.16, 0.16, hexc("ffffff"))
    c.stroke([(hx + 0.9, hy - 0.9), (hx + 2.1, hy - 0.8)], 0.22, PAL["hair"])  # brow
    c.stroke([(hx + 1.6, hy + 1.8), (hx + 2.4, hy + 1.6)], 0.18, shade(PAL["skin_d"], -0.2))  # mouth
    c.ellipse(hx + 2.9, hy + 0.5, 0.55, 0.45, PAL["skin_d"])  # nose
    # pith helmet
    c.fill(c.m_ellipse(hx, hy - 2.7, 3.3, 2.7), lit(shade(PAL["hat"], 0.3), PAL["hat_d"], (hx, hy - 3.5), 3))
    c.ellipse(hx + 0.3, hy - 1.9, 4.9, 0.85, lit(shade(PAL["hat"], 0.2), PAL["hat_d"], (hx, hy - 2), 4))
    c.stroke([(hx - 3.1, hy - 2.6), (hx + 3.1, hy - 2.6)], 0.42, PAL["band"])
    c.ellipse(hx - 1.0, hy - 4.3, 1.2, 0.6, hexc("ffffff"), alpha=0.45)  # specular

    c.outline(INK, 0.45)

    # front arm on its own layer so it reads clearly over the body
    a = Canvas(32, 32)
    hand = arm(a, p.get("fsh", 10), p.get("fel", 20), False)
    if p.get("whip_handle"):
        tip = limb_end(hand, p.get("fsh", 0) + p.get("fel", 0), 3.0)
        a.stroke([hand, tip], 0.5, PAL["whip"])
    if p.get("stone"):
        a.ellipse(hand[0] + 0.3, hand[1] - 0.6, 1.0, 1.0, Rad(hexc("d8d8d0"), hexc("6a6a64"), (hand[0], hand[1] - 1), 1.3))
    a.outline(shade(INK, 0.15), 0.35)
    c.paste(a)
    return c.final()


def run_pose(i, n=8):
    ph = 2 * math.pi * i / n
    s, co = math.sin(ph), math.cos(ph)
    return {
        "lean": 9,
        "dy": 0.8 * abs(s) - 0.4,
        "fth": 38 * s,
        "fkn": 15 + 60 * max(0.0, co),
        "bth": -38 * s,
        "bkn": 15 + 60 * max(0.0, -co),
        "fsh": -48 * s,
        "fel": 75,
        "bsh": 48 * s,
        "bel": 75,
    }


def rotate_frame(img, deg, pivot, shift=(0, 0)):
    return img.rotate(deg, resample=Image.BICUBIC, center=(pivot[0] * S, pivot[1] * S), translate=(shift[0] * S, shift[1] * S))


def player_animations():
    hang = {"fsh": 160, "fel": 4, "bsh": 200, "bel": -4, "lean": 0}
    anims = []
    anims.append(("idle", 4, True, [
        draw_player({"fsh": 8, "bsh": -8, "fel": 10, "bel": 10, "fth": 4, "bth": -4}),
        draw_player({"dy": 0.4, "fsh": 9, "bsh": -9, "fel": 12, "bel": 12, "fth": 5, "fkn": 9, "bth": -5, "bkn": 9}),
        draw_player({"dy": 0.7, "fsh": 10, "bsh": -10, "fel": 14, "bel": 14, "fth": 6, "fkn": 12, "bth": -6, "bkn": 12}),
        draw_player({"dy": 0.4, "fsh": 9, "bsh": -9, "fel": 12, "bel": 12, "fth": 5, "fkn": 9, "bth": -5, "bkn": 9}),
    ]))
    anims.append(("run", 14, True, [draw_player(run_pose(i)) for i in range(8)]))
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
    green, green_d, belly = hexc("5fb84a"), hexc("2d6e2a"), hexc("e8e08a")
    frames = []
    for strike in (False, True):
        c = Canvas(24, 16)
        body = lit(shade(green, 0.2), green_d, (12, 11), 6)
        c.ellipse(11, 13.2, 8.0, 2.6, body)
        c.ellipse(11, 10.6, 5.6, 2.3, lit(shade(green, 0.25), green_d, (11, 10), 5))
        c.stroke([(4, 14.2), (17, 14.2)], 0.6, belly, alpha=0.8)
        if strike:
            neck = catmull([(12, 10), (14.5, 7.5), (17.5, 5.6), (19.5, 5.2)])
            head = (20.3, 5.0)
        else:
            neck = catmull([(12, 10), (13, 7.5), (14.2, 5.2), (15.5, 4.2)])
            head = (16.4, 4.0)
        c.stroke(neck, 1.6, lit(shade(green, 0.25), green_d, (14, 7), 4), r_end=1.3)
        c.ellipse(head[0], head[1], 2.6, 1.8, lit(shade(green, 0.3), green_d, head, 3))
        for i in range(5):  # diamond markings
            x = 5.5 + i * 2.8
            c.poly([(x, 12.3), (x + 0.9, 11.4), (x + 1.8, 12.3), (x + 0.9, 13.2)], shade(green_d, -0.2), alpha=0.8)
        c.ellipse(head[0] + 0.7, head[1] - 0.5, 0.65, 0.65, hexc("ffe14a"))
        c.ellipse(head[0] + 0.75, head[1] - 0.5, 0.18, 0.5, hexc("101010"))
        if strike:
            c.stroke([(head[0] + 2.3, head[1] + 0.5), (head[0] + 3.4, head[1] + 0.6)], 0.18, hexc("e0303a"))
            c.stroke([(head[0] + 3.4, head[1] + 0.6), (head[0] + 3.8, head[1] + 0.2)], 0.15, hexc("e0303a"))
            c.stroke([(head[0] + 3.4, head[1] + 0.6), (head[0] + 3.8, head[1] + 1.0)], 0.15, hexc("e0303a"))
        c.outline(hexc("17301a"), 0.4)
        frames.append(c.final())
    return frames


def scorpion_frames():
    body, body_d, sting = hexc("d0603a"), hexc("7a2a16"), hexc("ffd84a")
    frames = []
    for f in range(2):
        c = Canvas(20, 14)
        for i, x in enumerate((7.0, 9.5, 12.0)):
            off = 0.8 if (i + f) % 2 == 0 else -0.8
            c.stroke([(x, 10.0), (x + 0.8 + off, 11.6), (x + off, 13.2)], 0.35, body_d)
        tail = catmull([(6.5, 9.3), (3.6, 8.6), (2.4, 5.6), (3.4, 2.6), (6.0, 1.6), (8.0, 2.5)])
        c.stroke(tail, 1.4, lit(shade(body, 0.25), body_d, (4, 5), 4), r_end=0.7)
        c.poly([(8.0, 2.0), (9.6, 3.3 + f * 0.4), (8.1, 3.4)], sting)
        c.ellipse(10.5, 9.0, 5.4, 2.4, lit(shade(body, 0.3), body_d, (10, 9), 5))
        for x in (7.5, 9.5, 11.5):
            c.stroke([(x, 7.2), (x, 10.6)], 0.15, body_d, alpha=0.7)
        c.stroke([(15.0, 9.0), (16.8, 8.2)], 0.5, body)
        c.ellipse(17.6, 7.8, 1.7, 1.2, lit(shade(body, 0.3), body_d, (17.6, 7.8), 2))
        c.poly([(18.4, 7.0), (19.8, 6.6 + f * 0.3), (18.8, 7.6)], body_d)
        c.ellipse(14.6, 8.1, 0.38, 0.38, hexc("101010"))
        c.ellipse(9.5, 7.6, 2.2, 0.5, hexc("ffffff"), alpha=0.35)
        c.outline(hexc("2a0e06"), 0.35)
        frames.append(c.final())
    return frames


def bat_frames():
    body, wing, wing_l = hexc("6a5a86"), hexc("3a2e52"), hexc("8070a8")
    frames = []
    for up in (True, False):
        c = Canvas(20, 12)
        if up:
            lw = [(9.2, 6.0), (6.0, 2.0), (1.0, 0.6), (2.6, 3.2), (0.6, 4.6), (3.6, 5.2), (2.8, 7.0)]
        else:
            lw = [(9.2, 5.6), (6.0, 8.6), (1.0, 10.8), (2.8, 8.4), (0.6, 7.6), (3.6, 6.8), (3.2, 5.4)]
        rw = [(20 - x, y) for x, y in lw]
        c.poly(lw, lit(wing_l, wing, (5, 5), 5))
        c.poly(rw, lit(wing_l, wing, (15, 5), 5))
        for pts in (lw, rw):
            for j in (2, 4):
                c.stroke([pts[0], pts[j]], 0.15, shade(wing, -0.3), alpha=0.8)
        c.poly([(8.4, 3.2), (8.8, 1.6), (9.5, 3.0)], body)
        c.poly([(11.6, 3.2), (11.2, 1.6), (10.5, 3.0)], body)
        c.ellipse(10, 6.0, 2.5, 3.0, lit(shade(body, 0.3), shade(body, -0.3), (10, 6), 3))
        c.blur_layer(lambda t: (t.ellipse(9.0, 5.0, 0.9, 0.9, hexc("ff4040")), t.ellipse(11.0, 5.0, 0.9, 0.9, hexc("ff4040"))), 0.4)
        c.ellipse(9.0, 5.0, 0.4, 0.4, hexc("ffd0d0"))
        c.ellipse(11.0, 5.0, 0.4, 0.4, hexc("ffd0d0"))
        c.outline(hexc("1a1428"), 0.35)
        frames.append(c.final())
    return frames


def croc_frames():
    green, green_d, belly = hexc("6a9a3a"), hexc("2e5418"), hexc("d4cf8a")
    frames = []
    for open_ in (False, True):
        c = Canvas(48, 20)
        c.ellipse(31, 14.0, 16.5, 5.4, lit(shade(green, 0.2), green_d, (31, 12), 9))
        for i, x in enumerate(range(19, 45, 3)):  # scutes
            c.ellipse(x + 0.5, 9.3 + 0.15 * (i % 2), 1.2, 0.9, lit(shade(green, 0.3), green_d, (x, 9), 1.5))
        c.stroke([(19, 17.4), (44, 17.4)], 0.6, belly, alpha=0.7)
        c.rrect(1.0, 13.0, 21.0, 17.0, 1.8, lit(shade(green, 0.15), green_d, (10, 15), 6))  # lower jaw
        if open_:
            c.poly([(20.5, 13.2), (4.0, 13.4), (4.0, 15.2), (20.5, 15.4)], hexc("c0505a"))
            for x in range(5, 19, 2):
                c.poly([(x, 13.3), (x + 0.6, 12.0), (x + 1.2, 13.3)], hexc("fbfbf0"))
            upper = [(21.0, 13.2), (3.0, 3.8), (0.6, 6.0), (1.2, 7.4), (19.0, 15.0)]
            c.poly(upper, lit(shade(green, 0.25), green_d, (10, 8), 7))
            for i in range(6):
                x = 4.5 + i * 2.6
                y = 5.6 + i * 1.35
                c.poly([(x, y), (x + 0.6, y + 1.3), (x + 1.2, y + 0.4)], hexc("fbfbf0"))
            c.ellipse(1.8, 5.2, 0.4, 0.3, hexc("1a2a10"))
        else:
            c.rrect(0.0, 10.6, 21.5, 14.4, 1.9, lit(shade(green, 0.25), green_d, (10, 12), 6))
            for x in range(3, 19, 2):
                c.poly([(x, 14.2), (x + 0.5, 15.2), (x + 1.0, 14.2)], hexc("fbfbf0"))
            c.ellipse(1.4, 11.4, 0.45, 0.32, hexc("1a2a10"))
        c.ellipse(20.0, 9.2, 3.1, 2.6, lit(shade(green, 0.3), green_d, (20, 9), 3))  # eye bump
        c.ellipse(20.6, 8.6, 1.3, 1.0, hexc("ffd23a"))
        c.ellipse(20.7, 8.6, 0.25, 0.85, hexc("101010"))
        c.ellipse(26, 11.0, 6.0, 0.8, hexc("ffffff"), alpha=0.18)
        c.outline(hexc("142a0c"), 0.4)
        frames.append(c.final())
    return frames


def log_frames():
    frames = []
    for f in range(4):
        c = Canvas(16, 16)
        c.ellipse(8, 8, 7.0, 7.0, lit(hexc("8a5a30"), hexc("4a2c14"), (8, 8), 7))
        c.ellipse(8, 8, 5.6, 5.6, Rad(hexc("f0c890"), hexc("b4824e"), (8, 8), 5.6))
        for r in (4.2, 2.8, 1.4):
            c.fill(ImageChops.subtract(c.m_ellipse(8, 8, r, r), c.m_ellipse(8, 8, r - 0.3, r - 0.3)), hexc("9a6a3a"), alpha=0.7)
        a = -f * math.pi / 2
        for d in (0.0, 0.35, -0.35):
            c.ellipse(8 + math.cos(a + d) * 6.3, 8 + math.sin(a + d) * 6.3, 0.7, 0.7, hexc("3a2210"))
        c.stroke([(8 + math.cos(a + 1.6) * 1.5, 8 + math.sin(a + 1.6) * 1.5), (8 + math.cos(a + 1.6) * 4.5, 8 + math.sin(a + 1.6) * 4.5)], 0.2, hexc("8a5a30"))
        c.outline(hexc("2a1608"), 0.4)
        frames.append(c.final())
    return frames


# ---------------------------------------------------------------------------
# Items (16x16 world each, one row). ITEM ORDER must match scripts/entities/
# pickup.gd and checkpoint.gd
# ---------------------------------------------------------------------------
GOLD, GOLD_L, GOLD_D = hexc("f6c33a"), hexc("fff2a8"), hexc("a8700e")


def glow(c, cx, cy, r, color, strength=0.6):
    """Soft halo kept on a layer underneath, so outlines don't trace it."""
    if getattr(c, "under", None) is None:
        c.under = Canvas(c.w, c.h, aa=c.k // c.scale, scale=c.scale)
    c.under.blur_layer(lambda t: t.ellipse(cx, cy, r, r, color, alpha=strength), r * 0.5)


def items_sheet():
    cells = []

    c = Canvas(16, 16)  # 0 gold bar
    glow(c, 8, 9, 4, GOLD, 0.35)
    c.poly([(2, 12.5), (14, 12.5), (11.8, 6.5), (4.2, 6.5)], Lin(GOLD_L, GOLD_D, (5, 6), (11, 13)))
    c.poly([(4.2, 6.5), (11.8, 6.5), (11, 5.2), (5, 5.2)], GOLD_L)
    c.poly([(5.6, 7.3), (7.2, 7.3), (5.4, 11.8), (3.8, 11.8)], hexc("ffffff"), alpha=0.5)
    c.outline(hexc("5a3a06"), 0.4)
    cells.append(c)

    c = Canvas(16, 16)  # 1 sling stones pouch
    c.ellipse(8, 10, 5, 4.3, lit(hexc("b88a52"), hexc("6a4422"), (8, 10), 5))
    c.poly([(5.5, 6.8), (10.5, 6.8), (9.2, 4.0), (6.8, 4.0)], lit(hexc("b88a52"), hexc("6a4422"), (8, 5), 3))
    c.stroke([(5.6, 6.6), (10.4, 6.6)], 0.5, hexc("4a2a12"))
    for x, y, r in ((6.4, 9.6, 1.5), (9.4, 10.6, 1.6), (8.0, 8.4, 1.2)):
        c.ellipse(x, y, r, r, Rad(hexc("e8e8e0"), hexc("707068"), (x - 0.5, y - 0.5), r * 1.4))
    c.outline(hexc("2e1a0a"), 0.4)
    cells.append(c)

    c = Canvas(16, 16)  # 2 canteen
    c.stroke([(2.5, 7.5), (5.5, 1.5)], 0.45, hexc("7a4a24"))
    c.stroke([(13.5, 7.5), (10.5, 1.5)], 0.45, hexc("7a4a24"))
    c.ellipse(8, 9.6, 5.6, 5.6, lit(hexc("8ec0c8"), hexc("3a6a78"), (8, 9.6), 6))
    c.ellipse(8, 9.6, 4.0, 4.0, Rad(hexc("a8d8e0"), hexc("5a8a96"), (7, 8.5), 5))
    c.rrect(6.4, 2.6, 9.6, 5.0, 0.8, lit(hexc("c09060"), hexc("6a4422"), (8, 3.8), 2))
    c.rrect(7.3, 7.0, 8.7, 12.2, 0.4, hexc("e8443a"))
    c.rrect(5.4, 8.9, 10.6, 10.3, 0.4, hexc("e8443a"))
    c.ellipse(5.8, 7.0, 1.2, 0.8, hexc("ffffff"), alpha=0.6)
    c.outline(hexc("1a2a30"), 0.4)
    cells.append(c)

    c = Canvas(16, 16)  # 3 extra life: golden explorer statuette
    glow(c, 8, 8.5, 4.2, GOLD, 0.35)
    c.rrect(4.2, 13, 11.8, 14.8, 0.6, Lin(GOLD, GOLD_D, (8, 13), (8, 15)))
    c.stroke([(8, 7.4), (8, 12.5)], 2.0, Lin(GOLD_L, GOLD_D, (6, 8), (10, 12)))
    c.ellipse(8, 5.6, 2.3, 2.3, Lin(GOLD_L, GOLD_D, (6.5, 4), (9.5, 7.5)))
    c.ellipse(8, 3.9, 2.6, 2.1, Lin(GOLD_L, GOLD, (7, 2), (9, 5)))
    c.ellipse(8, 4.6, 4.0, 0.8, Lin(GOLD_L, GOLD_D, (6, 4), (10, 5)))
    c.ellipse(7.0, 3.2, 0.9, 0.5, hexc("ffffff"), alpha=0.7)
    c.outline(hexc("5a3a06"), 0.4)
    cells.append(c)

    for active in (False, True):  # 4 dormant checkpoint idol, 5 awakened
        c = Canvas(16, 16)
        if active:
            glow(c, 8, 8.5, 5, hexc("8affc0"), 0.35)
        base_l, base_d = (GOLD_L, GOLD_D) if active else (hexc("c4c0b0"), hexc("6a665a"))
        c.rrect(2.0, 2.0, 14.0, 15.6, 2.0, lit(base_l, base_d, (8, 8), 8))
        c.rrect(0.6, 4.4, 2.6, 9.6, 0.8, lit(base_l, base_d, (1.5, 7), 3))
        c.rrect(13.4, 4.4, 15.4, 9.6, 0.8, lit(base_l, base_d, (14.5, 7), 3))
        c.rrect(2.0, 2.0, 14.0, 4.0, 1.0, shade(base_d, 0.1), alpha=0.8)
        eye = hexc("50ffa0") if active else shade(base_d, -0.3)
        if active:
            c.blur_layer(lambda t: (t.ellipse(5.4, 7.0, 1.6, 1.1, eye), t.ellipse(10.6, 7.0, 1.6, 1.1, eye)), 0.6)
        c.ellipse(5.4, 7.0, 1.4, 0.9, eye)
        c.ellipse(10.6, 7.0, 1.4, 0.9, eye)
        c.rrect(7.2, 8.0, 8.8, 10.6, 0.5, shade(base_d, -0.1), alpha=0.8)
        c.rrect(4.4, 12.0, 11.6, 13.0, 0.4, shade(base_d, -0.2), alpha=0.9)
        for x in (5.0, 7.0, 9.0, 11.0):
            c.rrect(x - 0.4, 13.0, x + 0.4, 14.0, 0.2, shade(base_d, -0.2), alpha=0.9)
        c.ellipse(5.0, 3.4, 2.0, 0.6, hexc("ffffff"), alpha=0.35)
        c.outline(hexc("3a3426") if not active else hexc("5a3a06"), 0.4)
        cells.append(c)

    c = Canvas(16, 16)  # 6 sling stone projectile
    c.ellipse(8, 8, 1.8, 1.8, Rad(hexc("f0f0e8"), hexc("6a6a62"), (7.3, 7.3), 2.5))
    c.outline(hexc("2a2a26"), 0.3)
    cells.append(c)

    sheet = Image.new("RGBA", (16 * S * len(cells), 16 * S), (0, 0, 0, 0))
    for i, cv in enumerate(cells):
        sheet.paste(cv.final(), (i * 16 * S, 0))
    return sheet


# ---------------------------------------------------------------------------
# Terrain textures used by scripts/ground_art.gd and props
# ---------------------------------------------------------------------------
def wrap_draw(c, period_w, period_h, fn):
    for ox in (-period_w, 0, period_w):
        for oy in ((-period_h, 0, period_h) if period_h else (0,)):
            fn(ox, oy)


def soil_texture():
    """Seamless 64x64-world soil."""
    rng = random.Random(7)
    c = Canvas(64, 64, aa=2)
    c.rrect(0, 0, 64, 64, 0, hexc("7a4a2a"))
    blobs = [(rng.uniform(0, 64), rng.uniform(0, 64), rng.uniform(3, 9), rng.uniform(2, 5), rng.choice([0.08, -0.1, 0.05, -0.15])) for _ in range(60)]
    for x, y, rx, ry, f in blobs:
        wrap_draw(c, 64, 64, lambda ox, oy: c.ellipse(x + ox, y + oy, rx, ry, shade(hexc("7a4a2a"), f), alpha=0.6))
    for _ in range(26):  # pebbles
        x, y, r = rng.uniform(0, 64), rng.uniform(0, 64), rng.uniform(0.6, 1.8)
        tone = rng.choice([hexc("a89a88"), hexc("8a7a6a"), hexc("b8a890")])
        wrap_draw(c, 64, 64, lambda ox, oy: (c.ellipse(x + ox + 0.3, y + oy + 0.4, r, r * 0.8, hexc("3a2210"), alpha=0.5),
                                             c.ellipse(x + ox, y + oy, r, r * 0.8, Rad(shade(tone, 0.3), shade(tone, -0.2), (x + ox - r * 0.3, y + oy - r * 0.3), r * 1.4))))
    for _ in range(14):  # roots
        x, y = rng.uniform(0, 64), rng.uniform(0, 64)
        pts = [(x, y)]
        for _ in range(4):
            x += rng.uniform(1.5, 4)
            y += rng.uniform(-1.5, 1.5)
            pts.append((x, y))
        wrap_draw(c, 64, 64, lambda ox, oy: c.stroke([(px + ox, py + oy) for px, py in pts], 0.35, hexc("4e2e16"), r_end=0.15, alpha=0.7))
    return c.final()


def grass_texture():
    """Seamless 64x10-world grass edge; the ground surface sits at y=4."""
    rng = random.Random(3)
    c = Canvas(64, 10)
    base = Lin(hexc("8ad84a"), hexc("2f7a2a"), (0, 3), (0, 9))
    edge = [(0, 4)] + [(x, 4 + rng.uniform(-0.2, 0.2)) for x in range(2, 64, 2)] + [(64, 4)]
    bottom = [(x, 7.5 + 1.2 * math.sin(x * 0.7) + rng.uniform(-0.3, 0.3)) for x in range(64, -1, -2)]
    c.poly(edge + bottom, base)
    for x in range(0, 64, 4):  # drip shadows into soil
        c.ellipse(x + 2, 8.2 + 0.8 * math.sin(x), 1.6, 1.0, hexc("2a5a1e"), alpha=0.6)
    blades = []
    for _ in range(90):
        x = rng.uniform(0, 64)
        h = rng.uniform(1.6, 4.0)
        lean = rng.uniform(-1.2, 1.2)
        col = rng.choice([hexc("9ae45a"), hexc("6cc040"), hexc("4fa034")])
        blades.append((x, h, lean, col))
    for x, h, lean, col in blades:
        wrap_draw(c, 64, 0, lambda ox, oy: c.poly([(x + ox - 0.45, 4.6), (x + ox + lean, 4.6 - h), (x + ox + 0.45, 4.6)], Lin(shade(col, 0.25), shade(col, -0.25), (0, 4.6 - h), (0, 4.6))))
    c.stroke([(0, 4.4), (64, 4.4)], 0.25, hexc("c8f28a"), alpha=0.6)
    return c.final()


def stone_block(mossy):
    c = Canvas(16, 16)
    base = hexc("a8a290")
    c.rrect(0, 0, 16, 16, 0, hexc("5e584a"))
    c.rrect(0.35, 0.35, 15.65, 15.65, 1.2, lit(shade(base, 0.2), shade(base, -0.25), (8, 8), 9))
    c.rrect(1.2, 1.2, 14.8, 14.8, 1.0, lit(shade(base, 0.05), shade(base, -0.12), (8, 8), 8))
    c.stroke([(3.5, 4.0), (5.5, 6.5), (5.0, 8.5)], 0.18, shade(base, -0.4), alpha=0.7)
    c.stroke([(11.0, 10.0), (12.5, 12.6)], 0.18, shade(base, -0.4), alpha=0.7)
    c.ellipse(4.0, 2.2, 3.0, 0.5, hexc("ffffff"), alpha=0.25)
    if mossy:
        rng = random.Random(5)
        pts = [(0, 0), (16, 0)] + [(x, 2.0 + 1.6 * math.sin(x * 0.9) + rng.uniform(0, 0.8)) for x in range(16, -1, -1)]
        c.poly(pts, Lin(hexc("8ad04e"), hexc("3a7a2a"), (0, 0), (0, 4)))
        for x in (2.5, 7.0, 12.5):
            c.ellipse(x, 3.6 + rng.uniform(0, 1), 1.0, 0.7, hexc("4a8a32"))
    return c.final()


def wood_plank(w, h, rope):
    c = Canvas(w, h)
    c.rrect(0.3, 0.2, w - 0.3, h - 0.4, 1.0, lit(hexc("d8a466"), hexc("7a4a22"), (w / 2, h / 2), h))
    for y in (h * 0.35, h * 0.62):
        c.stroke([(1.2, y), (w - 1.2, y + 0.2)], 0.12, hexc("6a3a18"), alpha=0.6)
    c.ellipse(w * 0.66, h * 0.45, 0.7, 0.4, hexc("6a3a18"), alpha=0.7)
    c.stroke([(1.0, 0.8), (w - 1.0, 0.8)], 0.25, hexc("fff0c8"), alpha=0.5)
    if rope:
        for x in (1.6, w - 1.6):
            c.rrect(x - 0.7, -0.2, x + 0.7, h, 0.3, Lin(hexc("e8d8a8"), hexc("9a8458"), (x - 0.7, 0), (x + 0.7, 0)))
    c.outline(hexc("3a2210"), 0.3)
    return c.final()


def ledge_texture():
    c = Canvas(16, 10)
    c.rrect(0, 0.2, 16, 4.6, 1.2, lit(hexc("d8a466"), hexc("7a4a22"), (8, 2), 5))
    c.stroke([(0.5, 2.3), (15.5, 2.5)], 0.12, hexc("6a3a18"), alpha=0.6)
    c.stroke([(0.5, 0.9), (15.5, 0.9)], 0.25, hexc("fff0c8"), alpha=0.5)
    for x in (3.0, 13.0):
        c.stroke([(x, 4.4), (x - 1.5, 9.6)], 0.55, lit(hexc("b88450"), hexc("5a3418"), (x, 6), 3))
    c.outline(hexc("3a2210"), 0.3)
    return c.final()


def vine_texture():
    """Seamless vertical vine segment, 16x16 world."""
    c = Canvas(16, 16)
    for phase, col in ((0.0, hexc("4f9a32")), (math.pi, hexc("3a7a26"))):
        def strand(ox, oy, phase=phase, col=col):
            pts = [(8 + 1.0 * math.sin(y / 16 * 2 * math.pi + phase), y + oy) for y in np.linspace(-1, 17, 19)]
            c.stroke(pts, 0.7, lit(shade(col, 0.3), shade(col, -0.3), (8, 8), 2))
        wrap_draw(c, 0, 16, strand)
    for y, side in ((3.0, 1), (11.0, -1)):
        def leaf(ox, oy, y=y, side=side):
            cx = 8 + side * 3.0
            c.poly([(8, y + oy), (cx, y + oy - 1.6), (8 + side * 5.2, y + oy + 0.4), (cx, y + oy + 1.4)], Lin(hexc("9ae060"), hexc("2f7a2a"), (8, y + oy - 1), (8 + side * 5, y + oy + 1)))
            c.stroke([(8, y + oy), (8 + side * 4.6, y + oy + 0.3)], 0.12, hexc("2a6020"), alpha=0.6)
        wrap_draw(c, 0, 16, leaf)
    return c.final()


def temple_facade():
    """Mayan step-temple for the level exit (112x96 world)."""
    w, h = 112, 96
    c = Canvas(w, h, aa=2)
    stone_l, stone_d = hexc("c8bea2"), hexc("7a7058")
    steps = 5
    for i in range(steps):
        x0, x1 = 4 + i * 10, w - 4 - i * 10
        y1 = h - i * 14
        y0 = y1 - 14
        c.rrect(x0, y0, x1, y1, 1.0, lit(stone_l, stone_d, ((x0 + x1) / 2, (y0 + y1) / 2), 30))
        c.rrect(x0, y0, x1, y0 + 1.2, 0.6, hexc("ffffff"), alpha=0.25)
        c.rrect(x0, y1 - 1.5, x1, y1, 0.6, hexc("2a2418"), alpha=0.25)
        for x in range(x0 + 4, x1 - 4, 9):
            c.rrect(x, y0 + 4, x + 5, y0 + 9, 1.0, Lin(hexc("6a6250"), hexc("9a907a"), (x, y0 + 4), (x + 5, y0 + 9)), alpha=0.9)
        rng = random.Random(i)
        for _ in range(6):
            mx = rng.uniform(x0 + 2, x1 - 2)
            c.ellipse(mx, y0 + 0.8, rng.uniform(1.5, 3.5), 1.0, hexc("5a9a3a"), alpha=0.9)
    c.rrect(42, 10, 70, 27, 1.0, lit(stone_l, stone_d, (56, 18), 14))
    c.rrect(48, 14, 64, 27, 2.0, Lin(hexc("1a120c"), hexc("3a2a1c"), (56, 14), (56, 27)))
    c.poly([(40, 10), (72, 10), (66, 5), (46, 5)], lit(stone_l, stone_d, (56, 7), 10))
    # doorway (the player walks into this)
    c.rrect(42, 52, 70, 96, 1.5, lit(stone_l, stone_d, (56, 70), 20))
    c.fill(c.m_rrect(44.5, 56, 67.5, 96, 6.0), Lin(hexc("05030a"), hexc("2a1c12"), (56, 60), (56, 96)))
    # glowing glyph eyes above the door
    for x in (49.5, 62.5):
        c.blur_layer(lambda t, x=x: t.ellipse(x, 47.5, 3.0, 2.2, hexc("ffd040")), 1.0)
        c.ellipse(x, 47.5, 1.8, 1.3, hexc("fff2b0"))
    # hanging vines
    rng = random.Random(11)
    for x in (12, 30, 84, 100):
        ln = rng.uniform(12, 26)
        y0 = h - 14 * (2 if x in (30, 84) else 1) + 0.5
        pts = [(x + 0.8 * math.sin(t * 0.5), y0 + t) for t in np.linspace(0, ln, 8)]
        c.stroke(pts, 0.6, hexc("4a8a2e"))
        for t in range(2, int(ln), 4):
            c.ellipse(x + 1.2 * (-1) ** t, y0 + t, 1.2, 0.7, hexc("6ab84a"))
    c.outline(hexc("2a2418"), 0.35)
    return c.final()


def leaf_particle():
    c = Canvas(8, 8)
    c.poly([(1, 4), (4, 1.4), (7, 4), (4, 6.6)], Lin(hexc("b8e070"), hexc("4a8a2a"), (2, 2), (6, 6)))
    c.stroke([(1.2, 4), (6.8, 4)], 0.15, hexc("3a6a20"), alpha=0.7)
    return c.final()


def glow_particle():
    c = Canvas(8, 8)
    c.blur_layer(lambda t: t.ellipse(4, 4, 2.0, 2.0, hexc("fff6b0")), 1.0)
    c.ellipse(4, 4, 0.8, 0.8, hexc("ffffff"))
    return c.final()


# ---------------------------------------------------------------------------
# Parallax backgrounds (480x270 world, the scrolling ones tile horizontally)
# ---------------------------------------------------------------------------
BW, BH = 480, 270


def bg_sky():
    c = Canvas(BW, BH, aa=1)
    c.rrect(0, 0, BW, BH, 0, Lin(hexc("16566e"), hexc("f6dda0"), (0, 0), (0, 215)))
    c.blur_layer(lambda t: t.ellipse(330, 150, 90, 70, hexc("fff0b8"), alpha=0.7), 30)
    c.ellipse(330, 150, 18, 18, Rad(hexc("fffbe8"), hexc("ffe8a0"), (330, 150), 18), alpha=0.9)
    rng = random.Random(2)
    def clouds(t):
        for _ in range(9):
            x, y = rng.uniform(0, BW), rng.uniform(30, 120)
            for j in range(4):
                t.ellipse(x + j * 14 - 20, y + rng.uniform(-4, 4), rng.uniform(14, 26), rng.uniform(6, 10), hexc("ffffff"), alpha=0.35)
    c.blur_layer(clouds, 5)
    return c.final()


def periodic(x, seed, amps):
    return sum(a * math.sin(2 * math.pi * f * x / BW + seed * (i + 1)) for i, (a, f) in enumerate(amps))


def bg_far():
    c = Canvas(BW, BH, aa=1)
    for depth, (top, col, amps) in enumerate((
        (150, hexc("8fb8a8"), [(18, 2), (9, 5), (4, 11)]),
        (172, hexc("6f9e88"), [(14, 3), (7, 7), (3, 13)]),
    )):
        pts = [(x, top + periodic(x, depth + 1, amps)) for x in range(0, BW + 1, 4)]
        c.poly(pts + [(BW, BH), (0, BH)], Lin(shade(col, 0.1), shade(col, -0.1), (0, top - 20), (0, BH)))
    # hazy pyramid
    col = hexc("7aa596")
    for i in range(6):
        c.rrect(300 + i * 7, 196 - (i + 1) * 13, 380 - i * 7, 197 - i * 13, 0.5, lit(shade(col, 0.12), shade(col, -0.08), (340, 160), 40))
    c.rrect(333, 108, 347, 119, 0.5, col)
    c.rrect(0, 150, BW, BH, 0, Lin(hexc("e8e0b0", 0), hexc("dfe6c0", 160), (0, 150), (0, 230)))
    return c.final()


def tree_canopy(c, x, y, r, base, rng, ox=0):
    for _ in range(7):
        bx = x + rng.uniform(-r, r) + ox
        by = y + rng.uniform(-r * 0.5, r * 0.4)
        br = r * rng.uniform(0.45, 0.75)
        c.ellipse(bx, by, br, br * 0.85, lit(shade(base, 0.22), shade(base, -0.25), (bx, by), br))


def bg_mid():
    c = Canvas(BW, BH, aa=1)
    rng = random.Random(4)
    trunk = hexc("4a6a52")
    trees = [(x, rng.uniform(8, 14)) for x in range(30, BW, 80)]
    for x, tw in trees:
        wrap_draw(c, BW, 0, lambda ox, oy: c.rrect(x + ox, 70, x + ox + tw, BH, 2, Lin(shade(trunk, 0.1), shade(trunk, -0.2), (x + ox, 0), (x + ox + tw, 0))))
    canopies = [(x, rng.uniform(40, 80), rng.uniform(28, 40)) for x in range(0, BW, 40)]
    for x, y, r in canopies:
        state = rng.getstate()
        for ox in (-BW, 0, BW):
            rng.setstate(state)
            tree_canopy(c, x, y, r, hexc("3f7a5a"), rng, ox)
    bush = [(x, rng.uniform(220, 232), rng.uniform(16, 26)) for x in range(0, BW, 22)]
    for x, y, r in bush:
        wrap_draw(c, BW, 0, lambda ox, oy: c.ellipse(x + ox, y, r, r * 0.7, lit(hexc("3f7a5a"), hexc("24503a"), (x + ox, y), r)))
    c.rrect(0, 232, BW, BH, 0, hexc("24503a"))
    c.rrect(0, 0, BW, BH, 0, Lin(hexc("cfe3c8", 70), hexc("cfe3c8", 0), (0, 120), (0, 260)))
    return c.final()


def bg_near():
    c = Canvas(BW, BH, aa=1)
    rng = random.Random(9)
    trunk = hexc("5a4a32")
    for x in (40, 200, 330, 430):
        tw = rng.uniform(16, 24)
        def draw_trunk(ox, oy, x=x, tw=tw):
            c.poly([(x + ox - 3, BH), (x + ox + 2, 0), (x + ox + tw - 2, 0), (x + ox + tw + 4, BH)], Lin(shade(trunk, 0.2), shade(trunk, -0.35), (x + ox, 0), (x + ox + tw, 0)))
            for yy in range(20, BH, 26):
                c.stroke([(x + ox + 3, yy), (x + ox + tw * 0.6, yy + 6)], 0.6, shade(trunk, -0.4), alpha=0.5)
        wrap_draw(c, BW, 0, draw_trunk)
    def rays(t):
        for x in (80, 180, 300, 420):
            t.poly([(x, 0), (x + 26, 0), (x - 60, BH), (x - 110, BH)], hexc("fff4c0"), alpha=0.18)
    c.blur_layer(rays, 6)
    for x in range(0, BW, 34):
        state = rng.getstate()
        for ox in (-BW, 0, BW):
            rng.setstate(state)
            tree_canopy(c, x, rng.uniform(4, 26), rng.uniform(22, 32), hexc("2f6a2a"), rng, ox)
    for x in range(25, BW, 60):  # hanging vines
        ln = rng.uniform(40, 120)
        def hanging(ox, oy, x=x, ln=ln):
            pts = [(x + ox + 2 * math.sin(t * 0.08), 20 + t) for t in np.linspace(0, ln, 12)]
            c.stroke(pts, 0.9, hexc("3d7a2a"))
            for t in range(8, int(ln), 10):
                side = 1 if t % 20 else -1
                c.ellipse(x + ox + side * 2.2 + 2 * math.sin(t * 0.08), 20 + t, 2.4, 1.2, hexc("5aa040"))
        wrap_draw(c, BW, 0, hanging)
    return c.final()


# ---------------------------------------------------------------------------
# Sheet + SpriteFrames writers
# ---------------------------------------------------------------------------
def write_sheet(name, anims, fw, fh):
    """anims: list of (name, fps, loop, [frames]). One animation per row.
    fw/fh are in world units; the sheet is stored at S pixels per unit."""
    pw, ph = fw * S, fh * S
    cols = max(len(a[3]) for a in anims)
    sheet = Image.new("RGBA", (cols * pw, len(anims) * ph), (0, 0, 0, 0))
    for r, (_, _, _, frames) in enumerate(anims):
        for c, f in enumerate(frames):
            sheet.paste(f, (c * pw, r * ph))
    sheet.save(os.path.join(SPRITES, name + ".png"), optimize=True)

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
                f"region = Rect2({c * pw}, {r * ph}, {pw}, {ph})\n"
            )
            frame_refs.append('{\n"duration": 1.0,\n"texture": SubResource("AtlasTexture_%d")\n}' % sid)
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


def save(img, *parts):
    img.save(os.path.join(ROOT, *parts), optimize=True)


def main():
    for d in (SPRITES, TILES, BG, FX):
        os.makedirs(d, exist_ok=True)
    write_sheet("player", player_animations(), 32, 32)
    s = snake_frames()
    write_sheet("snake", [("idle", 3, True, [s[0]]), ("strike", 1, False, [s[1]])], 24, 16)
    write_sheet("scorpion", [("walk", 6, True, scorpion_frames())], 20, 14)
    write_sheet("bat", [("fly", 8, True, bat_frames())], 20, 12)
    cr = croc_frames()
    write_sheet("croc", [("closed", 1, False, [cr[0]]), ("open", 1, False, [cr[1]])], 48, 20)
    write_sheet("log", [("roll", 10, True, log_frames())], 16, 16)
    save(items_sheet(), "assets", "sprites", "items.png")
    save(temple_facade(), "assets", "sprites", "temple.png")
    save(soil_texture(), "assets", "tiles", "soil.png")
    save(grass_texture(), "assets", "tiles", "grass.png")
    save(stone_block(False), "assets", "tiles", "stone.png")
    save(stone_block(True), "assets", "tiles", "stone_moss.png")
    save(ledge_texture(), "assets", "tiles", "ledge.png")
    save(wood_plank(16, 6, True), "assets", "tiles", "bridge_plank.png")
    save(vine_texture(), "assets", "tiles", "vine.png")
    save(leaf_particle(), "assets", "fx", "leaf.png")
    save(glow_particle(), "assets", "fx", "glow.png")
    save(bg_sky(), "assets", "backgrounds", "sky.png")
    save(bg_far(), "assets", "backgrounds", "far.png")
    save(bg_mid(), "assets", "backgrounds", "mid.png")
    save(bg_near(), "assets", "backgrounds", "near.png")
    print("art generated")


if __name__ == "__main__":
    main()
