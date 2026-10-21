"""
build_cover.py — Portada envolvente KDP (paperback 6x9, papel blanco) + portada eBook de "Jaque al modelo".
Adaptado de F:\\vertex-lab\\docs\\portada\\build_cover.py. Uso: python build_cover.py <páginas del interior>
"""
import sys, subprocess
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import ParagraphStyle
from PIL import Image

HERE = Path(__file__).parent
FONTS = HERE.parent / "fonts"
ART = HERE / "frente.png"   # cartel completo (arte + textos), generado por make_cover_front.py

PAGES = int(sys.argv[1]) if len(sys.argv) > 1 else 58
SPINE = PAGES * 0.002252            # papel blanco, B/N
BLEED = 0.125
TRIM_W, TRIM_H = 6.0, 9.0
W = BLEED + TRIM_W + SPINE + TRIM_W + BLEED
H = BLEED + TRIM_H + BLEED

for name, f in [("Serif", "source-serif-4-latin-400-normal.ttf"), ("SerifIt", "source-serif-4-latin-400-italic.ttf"),
                ("SerifSB", "source-serif-4-latin-600-normal.ttf"), ("Sans", "source-sans-3-latin-400-normal.ttf"),
                ("SansSB", "source-sans-3-latin-600-normal.ttf"), ("SansB", "source-sans-3-latin-700-normal.ttf")]:
    pdfmetrics.registerFont(TTFont(name, str(FONTS / f)))
pdfmetrics.registerFontFamily("Serif", normal="Serif", bold="SerifSB", italic="SerifIt", boldItalic="SerifSB")

BG = HexColor("#0C1522")
WHITE = HexColor("#F2F5F8")
SOFT = HexColor("#B9C6D3")
ACCENT = HexColor("#FFC45C")      # ámbar de las casillas candidatas


def cover_image(c, x, y, w, h):
    im = Image.open(ART)
    iw, ih = im.size
    s = max(w / iw, h / ih)
    dw, dh = iw * s, ih * s
    c.saveState()
    p = c.beginPath(); p.rect(x, y, w, h); c.clipPath(p, stroke=0, fill=0)
    c.drawImage(ImageReader(im), x + (w - dw) / 2, y + (h - dh) / 2, dw, dh)
    c.restoreState()


def front_text(c, x0, y0, w, h, top_safe, bottom_safe, left_safe):
    return  # v2: los textos de la portada ya van dentro de frente.png (estilo cartel de pelea)
    lx = x0 + left_safe
    top = y0 + h - top_safe
    c.setFillColor(WHITE)
    c.setFont("SansB", 50)
    c.drawString(lx, top - 48, "Jaque al modelo")
    c.setFillColor(ACCENT)
    c.rect(lx + 2, top - 66, 1.25 * inch, 2.4, stroke=0, fill=1)
    c.setFillColor(WHITE)
    c.setFont("Sans", 18.5)
    for i, t in enumerate(["Afiné dos IAs para jugar ajedrez", "y descubrí que el árbitro", "jugaba por ellas"]):
        c.drawString(lx + 1, top - 96 - i * 23, t)
    c.setFillColor(SOFT)
    c.setFont("SerifIt", 11.5)
    c.drawString(lx + 1, top - 176, "Bitácora real de un duelo entre Qwen y Gemma en una GPU de 6 GB")
    c.setFillColor(WHITE)
    c.setFont("SansSB", 17)
    c.drawString(lx + 1, y0 + bottom_safe + 16, "Denis Sánchez Leyva")
    c.setFillColor(SOFT)
    c.setFont("Sans", 9.5)
    c.drawString(lx + 1, y0 + bottom_safe, "VERTEX CODERS LLC")


def paperback():
    out = HERE / "Jaque-al-modelo-portada-paperback.pdf"
    c = canvas.Canvas(str(out), pagesize=(W * inch, H * inch), initialFontName="Sans")
    c.setTitle("Jaque al modelo — portada paperback"); c.setAuthor("Denis Sánchez Leyva")
    c.setFillColor(BG); c.rect(0, 0, W * inch, H * inch, stroke=0, fill=1)
    # portada (derecha)
    fx = (BLEED + TRIM_W + SPINE) * inch
    cover_image(c, fx, 0, (TRIM_W + BLEED) * inch, H * inch)
    front_text(c, fx, 0, (TRIM_W + BLEED) * inch, H * inch,
               top_safe=(BLEED + 0.55) * inch, bottom_safe=(BLEED + 0.5) * inch, left_safe=0.45 * inch)
    # lomo: KDP no admite texto con menos de 79 páginas
    sx = (BLEED + TRIM_W) * inch
    c.setFillColor(HexColor("#0A121D")); c.rect(sx, 0, SPINE * inch, H * inch, stroke=0, fill=1)
    if PAGES >= 79:
        c.saveState(); c.translate(sx + SPINE * inch / 2, H * inch / 2); c.rotate(-90)
        fs = min(10.0, SPINE * 72 * 0.42); c.setFont("SansSB", fs); c.setFillColor(WHITE)
        t = "JAQUE AL MODELO   ·   DENIS SÁNCHEZ LEYVA"
        c.drawString(-pdfmetrics.stringWidth(t, "SansSB", fs) / 2, -fs * 0.35, t); c.restoreState()
    # contraportada (izquierda)
    m = (BLEED + 0.5) * inch
    bx, bw = m, (TRIM_W - 1.0) * inch
    top = H * inch - (BLEED + 0.6) * inch
    hook = ParagraphStyle("hook", fontName="SansSB", fontSize=17.5, leading=23, textColor=WHITE)
    body = ParagraphStyle("body", fontName="Serif", fontSize=11.3, leading=16, textColor=SOFT, spaceAfter=10)
    bul = ParagraphStyle("bul", parent=body, leftIndent=12, bulletIndent=0, spaceAfter=5, bulletColor=ACCENT,
                         bulletFontName="SansB")
    quote = ParagraphStyle("q", fontName="SerifIt", fontSize=13.5, leading=18, textColor=WHITE, leftIndent=12,
                           spaceBefore=12, spaceAfter=14)
    small = ParagraphStyle("s", fontName="Serif", fontSize=9.8, leading=13.5, textColor=SOFT)
    story = [
        Paragraph("Afiné dos modelos de IA con los mismos datos y los puse a jugar ajedrez. "
                  "Ganaba siempre el que menos había entrenado.", hook),
        Paragraph("&nbsp;", ParagraphStyle("sp", fontName="Serif", fontSize=8, leading=12)),
        Paragraph("Este libro es la bitácora real de un duelo entre <b>Qwen 2.5</b> y <b>Gemma 2</b>, afinados "
                  "con QLoRA en una tarjeta de seis gigas. Y de la auditoría que destapó la verdad: cuando un "
                  "modelo fallaba, el árbitro jugaba por él. En el torneo final, un modelo que eligió una sola "
                  "jugada de 193 quedó empatado con los que entrenaron durante horas.", body),
        Paragraph("Lo que aprenderás:", ParagraphStyle("h", parent=body, textColor=WHITE, fontName="SerifSB",
                                                     spaceAfter=6, spaceBefore=4)),
    ]
    for b in ["Construir y auditar un dataset de 5.000 posiciones de Lichess",
              "QLoRA en 6 GB: enmascarar el prompt y comparar recetas iguales",
              "Exportar a GGUF y servir con Ollama sin perder el formato",
              "Medir al modelo y no al sistema: respaldos, parsers y filtros",
              "Una arena de torneos con relojes, Berger y Sonneborn-Berger",
              "Todo el código del proyecto, completo y comentado"]:
        story.append(Paragraph(b, bul, bulletText="•"))
    story.append(Paragraph("«Cuando tu modelo gane, pregunta quién más estaba jugando.»", quote))
    story.append(Paragraph("<b>Denis Sánchez Leyva</b> es fundador de Vertex Coders LLC (Miami) y autor de "
                           "una docena de libros sobre inteligencia artificial, agentes y MCP.", small))
    fr = Frame(bx, 1.9 * inch, bw, top - 1.9 * inch, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    fr.addFromList(story, c)
    assert not story, "la contraportada no cabe"
    c.setFillColor(ACCENT); c.setFont("SansSB", 9.5)
    c.drawString(bx, m + 0.42 * inch, "VERTEX CODERS LLC")
    c.setFillColor(SOFT); c.setFont("Sans", 8.5)
    c.drawString(bx, m + 0.24 * inch, "github.com/Denisijcu/vertex-chess-arena")
    c.drawString(bx, m + 0.08 * inch, "huggingface.co/Denisijcu")
    c.showPage(); c.save()
    return out


def ebook():
    out = HERE / "ebook_tmp.pdf"
    ew, eh = 6.0 * inch, 9.6 * inch
    c = canvas.Canvas(str(out), pagesize=(ew, eh), initialFontName="Sans")
    c.setFillColor(BG); c.rect(0, 0, ew, eh, stroke=0, fill=1)
    cover_image(c, 0, 0, ew, eh)
    front_text(c, 0, 0, ew, eh, top_safe=0.55 * inch, bottom_safe=0.5 * inch, left_safe=0.45 * inch)
    c.showPage(); c.save()
    return out


if __name__ == "__main__":
    p = paperback()
    e = ebook()
    subprocess.run(["pdftoppm", "-r", str(1600 / 6), "-jpeg", "-jpegopt", "quality=95", "-singlefile", str(e),
                    str(HERE / "eb")], check=True)
    im = Image.open(HERE / "eb.jpg").convert("RGB").resize((1600, 2560), Image.LANCZOS)
    im.save(HERE / "Jaque-al-modelo-portada-ebook.jpg", quality=95, dpi=(300, 300))
    (HERE / "eb.jpg").unlink(); e.unlink()
    print(f"OK  paperback {W:.3f} x {H:.3f} in (lomo {SPINE:.3f} in, {PAGES} pág.) -> {p.name}")
    print("OK  ebook 1600x2560 -> Jaque-al-modelo-portada-ebook.jpg")
