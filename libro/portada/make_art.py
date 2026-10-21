"""Arte de portada: tablero en perspectiva, rey blanco y las 4 casillas candidatas del árbitro."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

S = 2  # supersampling
W, H = 1800 * S, 2700 * S          # 6x9 a 300 ppp
img = Image.new("RGB", (W, H), (9, 16, 26))
# degradado vertical sutil
g = np.linspace(0, 1, H)[:, None]
base = np.array([9, 16, 26]); top = np.array([14, 26, 42])
arr = (base * g + top * (1 - g))[:, None, :].repeat(W, axis=1).astype(np.uint8)
img = Image.fromarray(arr.reshape(H, W, 3))
d = ImageDraw.Draw(img, "RGBA")

# tablero en perspectiva
hy = int(H * 0.40)            # línea del horizonte
by = H + int(H * 0.05)        # borde cercano (fuera de la imagen)
cx = W // 2
far_w, near_w = W * 0.62, W * 1.9
N = 8
def pt(u, v):  # u en [0,1] a lo ancho, v en [0,1] de lejos a cerca; perspectiva real
    z_far, z_near = 4.2, 1.0
    z = z_far + (z_near - z_far) * v
    k = z_near / z                      # 1 en el borde cercano, pequeño lejos
    y = hy + (by - hy) * k
    w = near_w * k
    return (cx - w / 2 + u * w, y)
cand = {(3, 5), (5, 5), (2, 6), (6, 3)}
for r in range(N):
    for c in range(N):
        q = [pt(c / N, r / N), pt((c + 1) / N, r / N), pt((c + 1) / N, (r + 1) / N), pt(c / N, (r + 1) / N)]
        dark = (r + c) % 2
        fade = int(40 + 170 * (r / N))
        col = (31, 95, 139, fade) if dark else (185, 198, 211, int(fade * 0.55))
        d.polygon(q, fill=col)
        if (c, r) in cand:
            d.polygon(q, fill=(240, 170, 60, 120))
            d.line(q + [q[0]], fill=(255, 196, 92, 255), width=5 * S)

img = img.filter(ImageFilter.GaussianBlur(0.6 * S))
d = ImageDraw.Draw(img, "RGBA")
# rey Staunton dibujado a mano (silueta), sobre una casilla candidata, con halo y sombra
BODY = [(0.50,0.00),(0.50,0.04),(0.46,0.055),(0.44,0.075),(0.37,0.095),(0.31,0.125),(0.26,0.19),
        (0.215,0.30),(0.18,0.43),(0.17,0.50),(0.18,0.52),(0.25,0.535),(0.255,0.555),(0.20,0.57),
        (0.175,0.585),(0.19,0.61),(0.24,0.65),(0.285,0.70),(0.305,0.74),(0.29,0.76),(0.20,0.77),(0.10,0.775)]
def catmull(pts, n=14):
    out = []
    P = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = map(np.array, P[i - 1:i + 3])
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(tuple(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                                    + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)))
    return out + [pts[-1]]
PROF = catmull(BODY) + [(0.07,0.80),(0.045,0.80),(0.045,0.845),(0.115,0.845),(0.115,0.875),
        (0.045,0.875),(0.045,0.935),(0.0,0.935)]
kx, ky = pt(4.5 / N, 4.55 / N)
KH = 980 * S; KW = 0.95 * KH
poly = [(kx + x * KW, ky - y * KH) for x, y in PROF] + [(kx - x * KW, ky - y * KH) for x, y in reversed(PROF)]
# sombra
sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
sd.ellipse([kx - 0.55 * KW, ky - 0.05 * KH, kx + 0.75 * KW, ky + 0.06 * KH], fill=(0, 0, 0, 170))
sh = sh.filter(ImageFilter.GaussianBlur(25 * S))
img = Image.alpha_composite(img.convert("RGBA"), sh)
# halo
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
gd.polygon(poly, fill=(255, 196, 92, 150))
glow = glow.filter(ImageFilter.GaussianBlur(45 * S))
img = Image.alpha_composite(img, glow)
# cuerpo con sombreado lateral
body = Image.new("RGBA", (W, H), (0, 0, 0, 0)); bd = ImageDraw.Draw(body)
bd.polygon(poly, fill=(242, 245, 248, 255))
mask = body.split()[3]
shade = Image.new("RGBA", (W, H), (0, 0, 0, 0)); shd = ImageDraw.Draw(shade)
for i in range(200):
    x0 = kx - KW * 0.1 + i * KW * 0.003
    shd.rectangle([x0, 0, x0 + KW * 0.003, H], fill=(31, 60, 90, int(140 * (i / 199) ** 1.6)))
shade.putalpha(Image.fromarray(np.minimum(np.array(shade.split()[3]), np.array(mask))))
body = Image.alpha_composite(body, shade)
img = Image.alpha_composite(img, body)
# oscurecer la parte superior para el título
ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
for y in range(int(H * 0.42)):
    a = int(170 * (1 - y / (H * 0.42)))
    od.line([(0, y), (W, y)], fill=(9, 16, 26, a))
img = Image.alpha_composite(img, ov).convert("RGB").resize((W // S, H // S), Image.LANCZOS)
img.save("arte.jpg", quality=95)
print("OK arte.jpg", img.size)
