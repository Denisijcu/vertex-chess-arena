"""
build_pdf.py — Interior KDP 6x9 de "Jaque al modelo" con pandoc + XeLaTeX.
Adaptado de F:\\vertex-lab\\docs\\build_pdf.py (Vertex-Core).
Uso: python build_pdf.py <carpeta manuscrito> <carpeta fonts>
"""
import re, subprocess, sys
from pathlib import Path
import pyphen

MAN = Path(sys.argv[1] if len(sys.argv) > 1 else "manuscrito")
FONTS = Path(sys.argv[2] if len(sys.argv) > 2 else "fonts")
OUT = Path("build"); OUT.mkdir(exist_ok=True)

FRONT = ["front-01-dedicatoria.md", "front-02-prefacio.md", "front-03-para-quien-es.md", "front-04-como-leer.md"]
BODY = ["cap-01-la-idea.md", "cap-02-el-laboratorio.md", "cap-03-el-dataset.md", "cap-04-gemma.md",
        "cap-05-qwen.md", "cap-06-ollama.md", "cap-07-el-arbitro.md", "cap-08-qwen-siempre-gana.md",
        "cap-09-un-duelo-justo.md", "cap-10-la-arena-profesional.md", "cap-11-la-verdad-del-tablero.md",
        "cap-12-lecciones.md", "cap-13-publicarlo.md"]
BACK = ["back-01-conclusion.md", "apendice-a-comandos.md", "apendice-b-hiperparametros.md",
        "apendice-c-partidas.md",
        "apendice-d-datos.md", "apendice-e-entrenamiento.md", "apendice-f-exportacion.md", "apendice-g-arbitro.md",
        "apendice-h-arena.md", "apendice-i-api.md", "apendice-j-reloj-torneos.md", "back-02-sobre-el-autor.md"]

FIXES = [(" → ", " a ")]  # la fuente de texto (subconjunto latino) no tiene la flecha

_HY = pyphen.Pyphen(lang="es", left=3, right=3)
_WORD = re.compile(r"[A-Za-zÁÉÍÓÚÑÜáéíóúñü]{7,}")


def tex_escape(s):
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
                 ("_", r"\_"), ("{", r"\{"), ("}", r"\}")]:
        s = s.replace(a, b)
    return s


def hyphenate(line):
    parts = re.split(r"(`[^`]*`|https?://\S+|\S+\.(?:com|org|io|md|py|json|yaml|txt|be|co)\S*|\]\([^)]*\))", line)
    for i in range(0, len(parts), 2):
        parts[i] = _WORD.sub(lambda m: _HY.inserted(m.group(0), hyphen="\u00ad"), parts[i])
    return "".join(parts)


def preprocess(fn, txt):
    for a, b in FIXES:
        txt = txt.replace(a, b)
    if fn == "front-01-dedicatoria.md":
        cuerpo = [p.strip().replace("\n", " ") for p in txt.split("# Dedicatoria", 1)[1].strip().split("\n\n")]
        return ("```{=latex}\n\\clearpage\\thispagestyle{empty}"
                "\\vspace*{1.8in}\\begin{center}\\itshape\n```\n\n" + "\n\n".join(cuerpo) +
                "\n\n```{=latex}\n\\end{center}\n```\n")
    for firma in ("front-02-prefacio.md", "back-01-conclusion.md"):
        if fn == firma:
            txt = txt.replace("— Denis Sánchez Leyva\nMiami, 2026",
                              "```{=latex}\n\\par\\vspace{8pt}\\begin{flushright}\\itshape — Denis Sánchez Leyva\\\\ Miami, 2026\\end{flushright}\n```")
    lines = txt.splitlines()
    if fn.startswith("cap-"):  # quitar la nota "> Borrador. Fuente: ..."
        i = next(k for k, l in enumerate(lines) if l.startswith("# "))
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and lines[j].lstrip().startswith(">"):
            while j < len(lines) and lines[j].lstrip().startswith(">"):
                j += 1
            lines = lines[:i + 1] + lines[j:]
    if fn.startswith("apendice-"):  # la nota de fuente del apéndice también fuera
        i = next(k for k, l in enumerate(lines) if l.startswith("# "))
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and lines[j].lstrip().startswith("> Fuente") or (j < len(lines) and "Fuente:" in lines[j]):
            while j < len(lines) and lines[j].lstrip().startswith(">"):
                j += 1
            lines = lines[:i + 1] + lines[j:]
    out, in_code = [], False
    for l in lines:
        if l.startswith("```"):
            in_code = not in_code
        if not in_code and l.startswith("# "):
            title = l[2:].strip()
            label, name = title.split(" — ", 1) if " — " in title else ("", title)
            name = re.sub(r'"([^"]*)"', "“\\1”", name)
            out += ["", "```{=latex}", r"\vcchapter{%s}{%s}" % (tex_escape(label), tex_escape(name)), "```", ""]
            continue
        if not in_code and l.strip() == "---":
            out += ["", "```{=latex}", r"\vcbreak", "```", ""]
            continue
        if not in_code and not l.startswith(("#", "|")) and not l.startswith("    "):
            l = hyphenate(l)
        out.append(l)
    return "\n".join(out)


def to_latex(files):
    md = "\n\n".join(preprocess(f, (MAN / f).read_text(encoding="utf-8")) for f in files)
    r = subprocess.run(["pandoc", "-f", "markdown-auto_identifiers+smart+lists_without_preceding_blankline", "-t", "latex",
                        "--highlight-style=tango", "--wrap=preserve"], input=md, capture_output=True, text=True, check=True)
    tex = r.stdout.replace("\u00ad", "\\-")
    tex = re.sub(r"\\texttt\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}",
                 lambda m: r"\texttt{" + m.group(1).replace("/", r"/\allowbreak{}").replace(r"\_", r"\_\allowbreak{}")
                 .replace(r"\textbackslash{}", r"\textbackslash{}\allowbreak{}").replace(",", r",\allowbreak{}")
                 .replace("-", r"-\allowbreak{}") + "}", tex)
    return tex


front, body, back = to_latex(FRONT), to_latex(BODY), to_latex(BACK)

hl = subprocess.run(["pandoc", "-s", "-f", "markdown", "-t", "latex", "--highlight-style=tango"],
                    input="```python\nx=1\n```", capture_output=True, text=True, check=True).stdout
hl = hl[hl.index(r"\usepackage{color}"):]
hl = hl[:hl.index(r"\usepackage{longtable") if r"\usepackage{longtable" in hl else hl.index(r"\setlength{\emergencystretch")]
hl = re.sub(r"\\DefineVerbatimEnvironment\{Highlighting\}\{Verbatim\}\{commandchars=\\\\\\{\\}\}\n?", "", hl)

F = FONTS.resolve().as_posix() + "/"
tex = r"""\documentclass[10.5pt,twoside,openany]{book}
\usepackage[paperwidth=6in,paperheight=9in,inner=0.8in,outer=0.6in,top=0.75in,bottom=0.8in,headsep=0.22in,footskip=0.4in]{geometry}
\usepackage{fontspec}
\usepackage{polyglossia}
\setdefaultlanguage{spanish}
\setmainfont{source-serif-4-latin-400-normal.ttf}[Path=FONTDIR, ItalicFont=source-serif-4-latin-400-italic.ttf,
  BoldFont=source-serif-4-latin-600-normal.ttf, BoldItalicFont=source-serif-4-latin-600-italic.ttf, Ligatures=TeX]
\newfontfamily\headfont{source-sans-3-latin-600-normal.ttf}[Path=FONTDIR, BoldFont=source-sans-3-latin-700-normal.ttf, Ligatures=TeX]
\newfontfamily\headlight{source-sans-3-latin-400-normal.ttf}[Path=FONTDIR, ItalicFont=source-sans-3-latin-400-italic.ttf, Ligatures=TeX]
\setmonofont{DejaVu Sans Mono}[Scale=0.80]
\usepackage{microtype}
\usepackage{xcolor}
\definecolor{vcaccent}{HTML}{1F5F8B}
\definecolor{vcgray}{HTML}{6B6B6B}
\definecolor{vcquote}{HTML}{F2F5F8}
\usepackage{fvextra}
\usepackage{graphicx}
\usepackage{fancyhdr}
\usepackage{titlesec}
\usepackage{enumitem}
\setlist{itemsep=2pt,topsep=4pt,leftmargin=1.3em}
\usepackage{longtable,booktabs,array,calc}
\renewcommand{\arraystretch}{1.15}
\usepackage[hidelinks,pdftitle={Jaque al modelo},pdfauthor={Denis Sánchez Leyva}]{hyperref}
\usepackage{xurl}
\usepackage{bookmark}
\usepackage{etoolbox}
\usepackage[framemethod=default]{mdframed}
\linespread{1.12}
\setlength{\parindent}{1.2em}
\setlength{\parskip}{0pt}
\widowpenalty=10000 \clubpenalty=10000
\emergencystretch=2em
\providecommand{\tightlist}{\setlength{\itemsep}{1pt}\setlength{\parskip}{0pt}}
\setcounter{secnumdepth}{-10}
\setcounter{tocdepth}{0}
\AtBeginEnvironment{longtable}{\small}

HIGHLIGHT
\DefineVerbatimEnvironment{Highlighting}{Verbatim}{commandchars=\\\{\},breaklines,breakanywhere,fontsize=\small,numbersep=6pt}
\renewcommand{\theFancyVerbLine}{\textcolor{vcgray}{\tiny\arabic{FancyVerbLine}}}
\renewenvironment{Shaded}{\begin{mdframed}[backgroundcolor=vcquote,linewidth=0pt,innerleftmargin=6pt,innerrightmargin=6pt,innertopmargin=5pt,innerbottommargin=5pt,skipabove=8pt,skipbelow=8pt]}{\end{mdframed}}
\RecustomVerbatimEnvironment{verbatim}{Verbatim}{breaklines,breakanywhere,fontsize=\small,frame=leftline,framerule=1.2pt,rulecolor=\color{vcaccent},xleftmargin=4pt}
\renewenvironment{quote}{\begin{mdframed}[backgroundcolor=vcquote,linecolor=vcaccent,topline=false,bottomline=false,rightline=false,linewidth=2pt,innerleftmargin=8pt,innerrightmargin=8pt,innertopmargin=6pt,innerbottommargin=6pt,skipabove=8pt,skipbelow=8pt]\small\itshape\setlength{\parindent}{0pt}}{\end{mdframed}}

\titleformat{\section}{\headfont\large\color{vcaccent}}{}{0pt}{}
\titlespacing*{\section}{0pt}{16pt plus 4pt}{6pt}
\titleformat{\subsection}{\headfont\normalsize}{}{0pt}{}
\titlespacing*{\subsection}{0pt}{12pt plus 3pt}{4pt}
\titleformat{\subsubsection}{\headfont\small\itshape}{}{0pt}{}
\titlespacing*{\subsubsection}{0pt}{10pt}{3pt}
\titleformat{\chapter}[display]{}{}{0pt}{}
\titlespacing*{\chapter}{0pt}{0pt}{0pt}

\newcommand{\vcrunning}{}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[LE]{\headlight\footnotesize\color{vcgray}\MakeUppercase{Jaque al modelo}}
\fancyhead[RO]{\headlight\footnotesize\color{vcgray}\vcrunning}
\fancyfoot[LE,RO]{\headlight\small\thepage}
\renewcommand{\headrulewidth}{0pt}
\fancypagestyle{plain}{\fancyhf{}\fancyfoot[LE,RO]{\headlight\small\thepage}}

\newcommand{\vcchapter}[2]{%
  \clearpage
  \phantomsection\addcontentsline{toc}{chapter}{\ifstrempty{#1}{#2}{#1 — #2}}%
  \renewcommand{\vcrunning}{#2}%
  \thispagestyle{plain}%
  \vspace*{0.2in}%
  \ifstrempty{#1}{}{{\headlight\small\color{vcaccent}\MakeUppercase{#1}\par}\vspace{6pt}}%
  {\headfont\fontsize{22}{26}\selectfont\raggedright #2\par}%
  \vspace{6pt}{\color{vcaccent}\rule{0.9in}{1.5pt}}\par
  \vspace{0.25in}\noindent\ignorespaces}
\newcommand{\vcbreak}{\par\vspace{8pt}\begin{center}{\color{vcaccent}\textbullet\quad\textbullet\quad\textbullet}\end{center}\vspace{4pt}}

\begin{document}
\frontmatter
\pagestyle{empty}
\begin{titlepage}
\vspace*{1.5in}
{\headfont\fontsize{38}{42}\selectfont Jaque al modelo\par}
\vspace{10pt}{\color{vcaccent}\rule{1.4in}{2pt}}\par\vspace{14pt}
{\headlight\fontsize{15}{19}\selectfont Afiné dos IAs para jugar ajedrez\\y descubrí que el árbitro\\jugaba por ellas\par}
\vspace{12pt}
{\itshape\color{vcgray} Bitácora real de un duelo entre Qwen y Gemma\\en una GPU de 6\,GB\par}
\vfill
{\headfont\large Denis Sánchez Leyva\par}
\vspace{3pt}{\headlight\small\color{vcgray}Vertex Coders LLC · Miami, FL\par}
\vspace{0.3in}
\end{titlepage}
\newpage
\null\vfill
{\footnotesize\setlength{\parindent}{0pt}\setlength{\parskip}{5pt}
\textit{Jaque al modelo: afiné dos IAs para jugar ajedrez y descubrí que el árbitro jugaba por ellas}

Primera edición, 2026

© 2026 Denis Sánchez Leyva — Vertex Coders LLC. Todos los derechos reservados.

Ninguna parte de esta publicación puede ser reproducida, distribuida o transmitida en cualquier forma o por cualquier medio sin el permiso previo por escrito del autor, salvo en el caso de citas breves para reseñas y ciertos usos no comerciales permitidos por la ley de derechos de autor.

Los modelos descritos en este libro son obras derivadas de Qwen2.5-3B-Instruct (Qwen Team, Alibaba Cloud) y de Gemma 2 2B (Google), y están sujetos a las licencias y términos de uso de sus modelos base. Los datos de entrenamiento proceden de conjuntos públicos de Lichess y de Hugging Face. El código y los ejemplos de este libro se ofrecen con fines educativos, «tal cual», sin garantía de ningún tipo.

El tablero de la aplicación usa cm-chessboard (licencia MIT) y las piezas de ajedrez de Colin M. L. Burnett (licencia CC BY-SA 3.0). Las reglas del juego se validan con python-chess y chess.js.

Las marcas y nombres de productos mencionados pertenecen a sus respectivos dueños.

Publicado de forma independiente.\par}
\pagestyle{fancy}
FRONT
\clearpage
\renewcommand{\vcrunning}{Índice}
\renewcommand{\contentsname}{Índice}
\begingroup
\titleformat{\chapter}[display]{\headfont\fontsize{22}{26}\selectfont}{}{0pt}{}
\titlespacing*{\chapter}{0pt}{0.2in}{0.25in}
\tableofcontents
\endgroup
\mainmatter
BODY
\backmatter
BACK
\end{document}
"""
tex = tex.replace("HIGHLIGHT", hl).replace("FONTDIR", F)
tex = tex.replace("FRONT", front).replace("BODY", body).replace("BACK", back)
tex = tex.replace(r"\begin{document}", r"""\makeatletter
\renewcommand*\l@chapter[2]{\addpenalty{-\@highpenalty}\vskip 0.55em plus 1pt
  \setlength\@tempdima{0pt}\begingroup\parindent\z@\rightskip\@pnumwidth\parfillskip-\@pnumwidth
  \leavevmode\headlight\small #1\nobreak\leaders\hbox{$\m@th\mkern 4mu\hbox{.}\mkern 4mu$}\hfill\nobreak
  \hb@xt@\@pnumwidth{\hss\headlight\small #2}\par\penalty\@highpenalty\endgroup}
\makeatother
\begin{document}""", 1)
(OUT / "jaque-al-modelo.tex").write_text(tex, encoding="utf-8")
for _ in range(3):
    r = subprocess.run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "jaque-al-modelo.tex"], cwd=OUT,
                       capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-3000:]); sys.exit(1)
print("OK", OUT / "jaque-al-modelo.pdf")
