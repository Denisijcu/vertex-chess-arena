"""
Pone el enlace de Amazon del libro en todos los sitios del proyecto, de una vez:
  1. README.md del repo (marca <!-- AMAZON -->)
  2. Fichas de Hugging Face de vertexqwen y vertexgemma (las sube)
  3. libro/descripcion_youtube_libro.txt con la línea para pegar en el video

Uso, desde E:\\vertex-chess-arena:
  venv\\Scripts\\python.exe libro\\publicar_enlace_amazon.py https://www.amazon.com/dp/XXXXXXXXXX
Después: git add, commit y push del README.
"""
import re, sys
from pathlib import Path
from huggingface_hub import upload_folder

if len(sys.argv) != 2 or not sys.argv[1].startswith("https://"):
    sys.exit("Uso: publicar_enlace_amazon.py https://www.amazon.com/dp/XXXXXXXXXX")
URL = sys.argv[1].strip()
ROOT = Path(__file__).resolve().parent.parent
TITLE = "Jaque al modelo: afiné dos IAs para jugar ajedrez y descubrí que el árbitro jugaba por ellas"

# 1. README del repo
readme = ROOT / "README.md"
s = readme.read_text(encoding="utf-8")
s2 = re.sub(r"\*Jaque al modelo:[^\n]*?<!-- AMAZON -->", f"[*{TITLE}*]({URL}) (Amazon) <!-- AMAZON -->", s)
if s2 == s and URL not in s:
    sys.exit("No encontré la marca <!-- AMAZON --> en README.md")
readme.write_text(s2, encoding="utf-8")
print("OK README.md")

# 2. Fichas de Hugging Face
for repo in ("vertexqwen", "vertexgemma"):
    p = ROOT / "hf_upload" / repo / "README.md"
    c = p.read_text(encoding="utf-8")
    c = c.replace("book: *Jaque al modelo* (Spanish, coming soon on Amazon)",
                  f"book: [*Jaque al modelo*]({URL}) (Spanish, Amazon)")
    p.write_text(c, encoding="utf-8")
    info = upload_folder(repo_id=f"Denisijcu/{repo}", folder_path=str(p.parent), allow_patterns=["README.md"],
                         commit_message="Model card: link to the book on Amazon")
    print("OK", repo, info)

# 3. Línea para la descripción del video
txt = ROOT / "libro" / "descripcion_youtube_libro.txt"
txt.write_text(f"📖 El libro \"Jaque al modelo\", ya en Amazon: {URL}\n", encoding="utf-8")
print("OK", txt, "-> cambia en YouTube la línea del libro por esta")
