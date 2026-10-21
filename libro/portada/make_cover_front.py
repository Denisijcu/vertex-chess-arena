"""
Portada frontal estilo cartel de gran pelea: dos reyes frente a frente (Qwen y Gemma) y, detrás,
la sombra gigante del árbitro. Genera frente.png a 300 ppp: 6.125 x 9.25 in (con sangrado).
"""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

HERE = Path(__file__).parent
FONTS = HERE.parent / "fonts"
W, H = 1838, 2775
BLEED = 37
SAFE = BLEED + 120

CYAN = (34, 211, 238); VIOLET = (167, 139, 250); AMBER = (255, 196, 92); WHITE = (242, 245, 248)

def font(name, size): return ImageFont.truetype(str(FONTS / name), size)

def radial(cx, cy, r, color, alpha):
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
    a = np.clip(1 - d, 0, 1) ** 2 * alpha
    layer = np.zeros((H, W, 4), np.uint8); layer[..., :3] = color; layer[..., 3] = a.astype(np.uint8)
    return Image.fromarray(layer, "RGBA")

# ---------- fondo ----------
yy = np.linspace(0, 1, H)[:, None, None]
bg = (np.array([6, 9, 16]) * (1 - yy) + np.array([10, 16, 28]) * yy).repeat(W, axis=1)
img = Image.fromarray(bg.astype(np.uint8), "RGB").convert("RGBA")
img = Image.alpha_composite(img, radial(W * 0.5, H * 0.38, W * 0.75, (30, 50, 80), 150))

# focos: conos de luz desde arriba
def beam(x_top, x_bot_l, x_bot_r, color, alpha):
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.polygon([(x_top - 30, -10), (x_top + 30, -10), (x_bot_r, H * 0.62), (x_bot_l, H * 0.62)], fill=color + (alpha,))
    return L.filter(ImageFilter.GaussianBlur(60))
img = Image.alpha_composite(img, beam(W * 0.10, W * 0.05, W * 0.55, CYAN, 55))
img = Image.alpha_composite(img, beam(W * 0.90, W * 0.45, W * 0.95, VIOLET, 55))

# luces del público (bokeh)
rng = np.random.default_rng(7)
bok = Image.new("RGBA", (W, H), (0, 0, 0, 0)); bd = ImageDraw.Draw(bok)
for _ in range(260):
    x = rng.uniform(0, W); y = rng.uniform(H * 0.30, H * 0.45); r = rng.uniform(3, 11)
    c = [WHITE, AMBER, CYAN, VIOLET][rng.integers(0, 4)]
    bd.ellipse([x - r, y - r, x + r, y + r], fill=c + (int(rng.uniform(40, 140)),))
img = Image.alpha_composite(img, bok.filter(ImageFilter.GaussianBlur(2.5)))

# ---------- silueta de rey ----------
BODY = [(0.50,0.00),(0.50,0.04),(0.46,0.055),(0.44,0.075),(0.37,0.095),(0.31,0.125),(0.26,0.19),
        (0.215,0.30),(0.18,0.43),(0.17,0.50),(0.18,0.52),(0.25,0.535),(0.255,0.555),(0.20,0.57),
        (0.175,0.585),(0.19,0.61),(0.24,0.65),(0.285,0.70),(0.305,0.74),(0.29,0.76),(0.20,0.77),(0.10,0.775)]
def catmull(pts, n=14):
    out = []; P = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = map(np.array, P[i - 1:i + 3])
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(tuple(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                                    + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)))
    return out + [pts[-1]]
PROF = catmull(BODY) + [(0.07,0.80),(0.045,0.80),(0.045,0.845),(0.115,0.845),(0.115,0.875),
        (0.045,0.875),(0.045,0.935),(0.0,0.935)]
def king_poly(cx, base, h):
    w = 0.95 * h
    return [(cx + x * w, base - y * h) for x, y in PROF] + [(cx - x * w, base - y * h) for x, y in reversed(PROF)]

def mask_of(poly):
    m = Image.new("L", (W, H), 0); ImageDraw.Draw(m).polygon(poly, fill=255); return m

# ---------- el árbitro: sombra gigante ámbar al fondo ----------
arb = king_poly(W * 0.5, H * 0.47, H * 0.42)
am = mask_of(arb)
ghost = Image.new("RGBA", (W, H), AMBER + (0,)); ghost.putalpha(am.point(lambda v: v * 0.16))
img = Image.alpha_composite(img, ghost.filter(ImageFilter.GaussianBlur(6)))
edge = am.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(3))
eg = Image.new("RGBA", (W, H), AMBER + (0,)); eg.putalpha(edge.point(lambda v: min(255, v * 0.8)))
img = Image.alpha_composite(img, eg)

# ---------- tablero (la arena) ----------
hy, by = int(H * 0.44), int(H * 0.74)
def pt(u, v):
    z = 3.6 + (1.0 - 3.6) * v; k = 1.0 / z
    y = hy + (by - hy) * (k - 1 / 3.6) / (1 - 1 / 3.6)
    w = W * 2.2 * k
    return (W / 2 - w / 2 + u * w, y)
board = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(board)
cand = {(3, 4), (4, 4), (3, 5), (4, 5)}
for r in range(8):
    for c in range(8):
        q = [pt(c / 8, r / 8), pt((c + 1) / 8, r / 8), pt((c + 1) / 8, (r + 1) / 8), pt(c / 8, (r + 1) / 8)]
        a = int(60 + 150 * r / 8)
        d.polygon(q, fill=((31, 95, 139, a) if (r + c) % 2 else (185, 198, 211, int(a * .5))))
        if (c, r) in cand:
            d.polygon(q, fill=AMBER + (110,)); d.line(q + [q[0]], fill=AMBER + (255,), width=4)
# el tablero se funde hacia abajo para dejar sitio al título
fade = np.linspace(1, 0, H)[:, None]; fade = np.clip((fade - 0.27) / 0.10, 0, 1)
ba = np.array(board); ba[..., 3] = (ba[..., 3] * fade).astype(np.uint8)
img = Image.alpha_composite(img, Image.fromarray(ba, "RGBA"))

# ---------- los dos contendientes ----------
def fighter(img, cx, base, h, fill, rim, shade_side):
    poly = king_poly(cx, base, h); m = mask_of(poly)
    # sombra en el suelo
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([cx - 0.55 * h, base - 0.05 * h, cx + 0.55 * h, base + 0.06 * h], fill=(0, 0, 0, 190))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(22)))
    # halo de color
    g = Image.new("RGBA", (W, H), rim + (0,)); g.putalpha(m.filter(ImageFilter.MaxFilter(21)).filter(ImageFilter.GaussianBlur(40)).point(lambda v: v * 0.85))
    img = Image.alpha_composite(img, g)
    # cuerpo con degradado lateral (luz del lado del foco)
    xs = np.linspace(0, 1, W)[None, :, None]
    lo, hi = np.array(fill[0]), np.array(fill[1])
    t = np.clip((xs - (cx - 0.35 * h) / W) / (0.7 * h / W), 0, 1)
    if shade_side == "right": t = 1 - t
    col = (hi * (1 - t) + lo * t).repeat(H, axis=0)
    body = Image.fromarray(np.dstack([col, np.full((H, W, 1), 255)]).astype(np.uint8), "RGBA"); body.putalpha(m)
    img = Image.alpha_composite(img, body)
    # filo de luz (rim light)
    e = m.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.5))
    rl = Image.new("RGBA", (W, H), rim + (0,)); rl.putalpha(e); img = Image.alpha_composite(img, rl)
    return img

kh = H * 0.27; base = H * 0.60
img = fighter(img, W * 0.265, base, kh, ((120, 135, 150), WHITE), CYAN, "right")      # Qwen: rey blanco
img = fighter(img, W * 0.735, base, kh, ((8, 10, 16), (70, 60, 105)), VIOLET, "left")  # Gemma: rey negro

# ---------- textos ----------
d = ImageDraw.Draw(img)
def center(text, y, f, fill, spacing=0, stroke=0, stroke_fill=None, x=None):
    if spacing:
        widths = [d.textlength(ch, font=f) for ch in text]; total = sum(widths) + spacing * (len(text) - 1)
        x0 = (W - total) / 2 if x is None else x - total / 2
        for ch, w in zip(text, widths):
            d.text((x0, y), ch, font=f, fill=fill); x0 += w + spacing
        return
    w = d.textlength(text, font=f); d.text(((W - w) / 2 if x is None else x - w / 2, y), text, font=f, fill=fill,
                                          stroke_width=stroke, stroke_fill=stroke_fill)

center("VERTEX CHESS ARENA PRESENTA", SAFE - 20, font("oswald-latin-500-normal.ttf", 44), WHITE + (220,), spacing=9)
center("UN DUELO DE INTELIGENCIA ARTIFICIAL", SAFE + 50, font("oswald-latin-400-normal.ttf", 34), AMBER + (230,), spacing=6)

# nombres de los rivales
NY = int(H * 0.615)
fn = font("anton-latin-400-normal.ttf", 104)
center("QWEN 2.5", NY, fn, CYAN, x=W * 0.255, stroke=4, stroke_fill=(5, 8, 14))
center("GEMMA 2", NY, fn, VIOLET, x=W * 0.745, stroke=4, stroke_fill=(5, 8, 14))
center("VS", NY - 12, font("anton-latin-400-normal.ttf", 140), AMBER, stroke=5, stroke_fill=(5, 8, 14))

# título con degradado dorado
def gold_text(text, y, size):
    f = font("anton-latin-400-normal.ttf", size)
    tw = d.textlength(text, font=f); x = (W - tw) / 2
    m = Image.new("L", (W, H), 0); md = ImageDraw.Draw(m); md.text((x, y), text, font=f, fill=255)
    bbox = m.getbbox()
    t = np.clip((np.arange(H)[:, None] - bbox[1]) / max(1, bbox[3] - bbox[1]), 0, 1)[..., None]
    top, mid, bot = np.array([255, 236, 160]), np.array([255, 196, 92]), np.array([196, 120, 30])
    g = np.where(t < 0.5, top + (mid - top) * (t * 2), mid + (bot - mid) * ((t - .5) * 2)).repeat(W, axis=1)
    gi = Image.fromarray(g.astype(np.uint8), "RGB").convert("RGBA"); gi.putalpha(m)
    o = Image.new("RGBA", (W, H), (5, 8, 14, 0)); o.putalpha(m.filter(ImageFilter.MaxFilter(13)))
    glow = Image.new("RGBA", (W, H), AMBER + (0,)); glow.putalpha(m.filter(ImageFilter.GaussianBlur(28)).point(lambda v: v * 0.6))
    return [glow, o, gi], bbox
TS = 250
layers1, b1 = gold_text("JAQUE AL", int(H * 0.665), TS)
layers2, b2 = gold_text("MODELO", b1[3] + 25 - (b1[1] - int(H * 0.665)), TS)
for L in layers1 + layers2: img = Image.alpha_composite(img, L)
d = ImageDraw.Draw(img)

# franja del subtítulo
fy = b2[3] + 55
band = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(band).rectangle([0, fy - 16, W, fy + 122], fill=(5, 8, 14, 215))
img = Image.alpha_composite(img, band); d = ImageDraw.Draw(img)
fs = font("oswald-latin-500-normal.ttf", 44)
center("AFINÉ DOS IAs PARA JUGAR AJEDREZ Y DESCUBRÍ", fy, fs, WHITE)
center("QUE EL ÁRBITRO JUGABA POR ELLAS", fy + 54, fs, AMBER)

# autor
center("DENIS SÁNCHEZ LEYVA", max(fy + 165, H - BLEED - 140), font("oswald-latin-700-normal.ttf", 48), WHITE, spacing=6)
print("bboxes", b1, b2, "fy", fy)

img.convert("RGB").save(HERE / "frente.png", dpi=(300, 300))
print("OK frente.png", img.size)
