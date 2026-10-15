"""Buat logo Privacy Browser: privacy_browser/icon.ico + privacy_browser/logo.png.

Konsep: perisai putih berisi pola sidik jari (identitas yang dilindungi) di atas
latar squircle bergradasi indigo -> violet, dengan titik "pindai" cyan.
Jalankan: python tools/make_icon.py
"""
import math
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "privacy_browser"
S = 1024  # kanvas kerja (digambar besar lalu diperkecil supaya halus)


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def gradient(size, stops, angle=45):
    """Gradasi linear multi-warna pada sudut tertentu."""
    g = Image.new("RGB", (size, size))
    px = g.load()
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    span = size * (abs(ca) + abs(sa))
    for y in range(size):
        for x in range(size):
            t = ((x - size / 2) * ca + (y - size / 2) * sa) / span + 0.5
            t = min(max(t, 0.0), 1.0)
            for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
                if t <= p1:
                    px[x, y] = lerp(c0, c1, (t - p0) / (p1 - p0 or 1))
                    break
    return g


def bezier(p0, p1, p2, p3, n=60):
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        yield (u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
               u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1])


def shield_points(cx, top, w, h):
    """Siluet perisai: puncak sedikit melengkung, bahu lebar, ujung bawah meruncing."""
    l, r, b = cx - w / 2, cx + w / 2, top + h
    pts = []
    pts += bezier((cx, top), (cx + w * .18, top + h * .07), (r - w * .08, top + h * .09), (r, top + h * .12))
    pts += bezier((r, top + h * .12), (r + w * .01, top + h * .55), (cx + w * .30, b - h * .14), (cx, b))
    pts += bezier((cx, b), (cx - w * .30, b - h * .14), (l - w * .01, top + h * .55), (l, top + h * .12))
    pts += bezier((l, top + h * .12), (l + w * .08, top + h * .09), (cx - w * .18, top + h * .07), (cx, top))
    return pts


def mask_from(draw_fn, size=S):
    m = Image.new("L", (size, size), 0)
    draw_fn(ImageDraw.Draw(m))
    return m


def render(detail=True):
    pad = 36
    radius = 236
    bg_mask = mask_from(lambda d: d.rounded_rectangle((pad, pad, S - pad, S - pad), radius, fill=255))

    # Latar: indigo cerah -> violet -> indigo gelap
    bg = gradient(S, [(0, (99, 102, 241)), (.5, (79, 70, 229)), (1, (46, 16, 101))], angle=60)
    # kilau lembut di kiri atas
    glow = mask_from(lambda d: d.ellipse((-260, -320, 700, 560), fill=110)).filter(ImageFilter.GaussianBlur(120))
    bg = Image.composite(Image.new("RGB", (S, S), (167, 139, 250)), bg, glow)

    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    canvas.paste(bg, (0, 0), bg_mask)

    # Garis tepi tipis (cahaya) di sepanjang squircle
    rim = mask_from(lambda d: d.rounded_rectangle((pad, pad, S - pad, S - pad), radius, outline=255, width=6))
    fade = Image.linear_gradient("L").rotate(180).point(lambda v: v * 100 // 255).resize((S, S))
    rim = ImageChops.multiply(rim, fade)
    canvas.paste((255, 255, 255, 255), (0, 0), rim)

    cx, top, w, h = S / 2, 178, 560, 690
    outer = shield_points(cx, top, w, h)

    # Bayangan perisai
    shadow = mask_from(lambda d: d.polygon([(x, y + 26) for x, y in outer], fill=150)).filter(ImageFilter.GaussianBlur(34))
    shadow = ImageChops.multiply(shadow, bg_mask)
    canvas.paste((20, 8, 60, 255), (0, 0), shadow)

    # Perisai putih
    shield_mask = mask_from(lambda d: d.polygon(outer, fill=255))
    canvas.paste((255, 255, 255, 255), (0, 0), shield_mask)

    # Area dalam perisai (untuk memotong sidik jari)
    inner = shield_points(cx, top + 62, w - 124, h - 120)
    inner_mask = mask_from(lambda d: d.polygon(inner, fill=255))

    # Pola sidik jari: busur konsentris berlubang, bergradasi indigo -> violet
    fx, fy = cx, top + h * .50
    ring_w = 30 if detail else 52
    step = 64 if detail else 104
    rings = ((0, 300), (210, 140), (250, 120), (200, 170), (230, 130)) if detail else ((0, 300), (220, 140), (230, 130))
    fp = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(fp)
    for i, (start, sweep) in enumerate(rings):
        r = 40 + i * step
        box = (fx - r, fy - r, fx + r, fy + r)
        if i == 0:
            d.ellipse((fx - ring_w * .9, fy - ring_w * .9, fx + ring_w * .9, fy + ring_w * .9), fill=255)
            continue
        # dua segmen per cincin dengan celah supaya terlihat organik
        d.arc(box, start, start + sweep, fill=255, width=ring_w)
        d.arc(box, start + sweep + 34, start + 360 - 34, fill=255, width=ring_w)
    fp = ImageChops.multiply(fp, inner_mask)
    fp_color = gradient(S, [(0, (99, 102, 241)), (1, (124, 58, 237))], angle=90)
    canvas.paste(fp_color, (0, 0), fp)

    # Titik pindai cyan di inti sidik jari
    dot = 34 if detail else 54
    core = mask_from(lambda d: d.ellipse((fx - dot, fy - dot, fx + dot, fy + dot), fill=255))
    halo = mask_from(lambda d: d.ellipse((fx - dot * 2.2, fy - dot * 2.2, fx + dot * 2.2, fy + dot * 2.2), fill=255))
    canvas.paste((255, 255, 255, 255), (0, 0), halo)
    canvas.paste((34, 211, 238, 255), (0, 0), core)

    # Garis pindai horizontal cyan melintasi perisai
    if detail:
        scan = mask_from(lambda d: d.rounded_rectangle((cx - 170, fy - 7, cx - dot * 2.2 - 14, fy + 7), 7, fill=255))
        scan2 = mask_from(lambda d: d.rounded_rectangle((cx + dot * 2.2 + 14, fy - 7, cx + 170, fy + 7), 7, fill=255))
        canvas.paste((34, 211, 238, 255), (0, 0), ImageChops.multiply(ImageChops.lighter(scan, scan2), inner_mask))
    return canvas


def main():
    big = render(detail=True)
    small = render(detail=False)
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    frames = [(small if s <= 32 else big).resize((s, s), Image.LANCZOS) for s in sizes]
    frames[-1].save(OUT / "icon.ico", sizes=[(s, s) for s in sizes], append_images=frames[:-1])
    big.resize((512, 512), Image.LANCZOS).save(OUT / "logo.png")
    for s in (36, 45, 54, 63, 72):  # logo sidebar untuk skala layar 100%..200%
        big.resize((s, s), Image.LANCZOS).save(OUT / f"logo_{s}.png")
    print("icon ->", OUT / "icon.ico")
    print("logo ->", OUT / "logo.png")


if __name__ == "__main__":
    main()
