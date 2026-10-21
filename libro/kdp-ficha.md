# Ficha de KDP — Jaque al modelo

Todo lo que hay que pegar en el formulario de Amazon. Copiar tal cual.

**Este archivo NO va al repositorio.** Añadir `libro/kdp-ficha.md` al `.gitignore`.

---

## 1. Título, subtítulo y autor

**Título**
```
Jaque al modelo
```

**Subtítulo**
```
Afiné dos IAs para jugar ajedrez y descubrí que el árbitro jugaba por ellas
```

**Autor**
```
Denis Sánchez Leyva
```

**Edición:** 1 · **Idioma:** Español · **Editorial:** Vertex Coders LLC (o en blanco: "Publicado de forma independiente")

> El subtítulo lleva el gancho y la palabra que más se busca ("IA"). El resto de términos
> (QLoRA, Qwen, Gemma, Ollama) van en las palabras clave.

---

## 2. Descripción del producto

KDP acepta HTML básico: `<b>`, `<i>`, `<br>`, `<p>`, `<h4>`, `<ul>`, `<li>`. Máximo 4000 caracteres.

```html
<h4>Afiné dos modelos de IA con los mismos datos y los puse a jugar ajedrez. Ganaba siempre el que menos había entrenado.</h4>

<p>Qwen 2.5 contra Gemma 2. Mismo dataset de 5.000 posiciones, misma técnica, la misma GPU de 6 GB. Y Qwen ganaba partida tras partida, aunque había entrenado una fracción de lo que entrenó Gemma. La primera explicación fue elegante: "Qwen procesa mejor el FEN". Era falsa.</p>

<p>Este libro cuenta la auditoría que encontró la verdad: <b>cuando un modelo fallaba, el árbitro jugaba por él</b>. Y el torneo final que lo demostró: un modelo que eligió una sola jugada de 193 quedó empatado con los que entrenaron durante horas.</p>

<h4>Qué vas a construir</h4>

<p>Dos modelos afinados con <b>QLoRA</b> en una <b>GTX 1660 Ti de 6 GB</b>, exportados a GGUF y servidos con <b>Ollama</b>. Un árbitro de ajedrez en Python con búsqueda alfa-beta. Y una <b>arena de torneos</b> en Angular con relojes Bronstein, emparejamientos Berger, desempate Sonneborn-Berger y PGN con tiempos. El libro incluye <b>todo el código del proyecto</b>, comentado, y los dos modelos están publicados en Hugging Face.</p>

<h4>Por qué este libro es distinto</h4>

<p><b>Es una bitácora, no un tutorial.</b> Se escribió mientras se hacía, con los errores incluidos: un adaptador equivocado que nadie detectó, un parser que convertía fallos en aciertos, un reloj que subía en vez de bajar.</p>

<p><b>Cada cifra está medida.</b> Formato, aciertos, jugadas de respaldo, partidas y torneos: todo sale de los registros del proyecto.</p>

<p><b>La lección vale para cualquier modelo.</b> Casi siempre que medimos un modelo, medimos un sistema. Si tu proyecto tiene un filtro, un respaldo o un parser, este libro te enseña a separar lo que hace el modelo de lo que hace todo lo demás.</p>

<h4>Lo que aprenderás</h4>

<ul>
<li>Construir y auditar un dataset de ajedrez con Lichess y python-chess</li>
<li>QLoRA en 6 GB: enmascarar el prompt, entrenar una época completa y comparar recetas iguales</li>
<li>Exportar a GGUF y escribir un Modelfile de Ollama que no rompa el formato</li>
<li>Auditar un sistema de evaluación: respaldos, parsers, prompts y código muerto</li>
<li>Medir con y sin ayuda, y usar un jugador al azar como línea base</li>
<li>Construir una app de torneos con Angular, FastAPI y relojes de verdad</li>
<li>Publicar modelos en Hugging Face con licencias y fichas honestas</li>
<li>Leer el código completo del proyecto: más de 3.000 líneas, con una guía de lectura para cada archivo</li>
</ul>

<h4>Para quién es</h4>

<p>Para quien afina modelos de lenguaje, o quiere hacerlo, y necesita saber si de verdad aprendieron. No hace falta saber jugar bien al ajedrez: el libro explica lo justo. Sí ayuda saber Python y no tenerle miedo a la línea de comandos.</p>
```

---

## 3. Palabras clave (las 7 casillas)

1. `fine-tuning LLM QLoRA en español`
2. `Qwen Gemma comparación modelos`
3. `Ollama GGUF modelo local`
4. `evaluar modelos de lenguaje`
5. `ajedrez e inteligencia artificial`
6. `python-chess motor de ajedrez`
7. `Hugging Face GPU 6 GB`

---

## 4. Categorías

- Computers & Technology › Computer Science › AI & Machine Learning › **Machine Learning**
- Computers & Technology › Computer Science › AI & Machine Learning › **Natural Language Processing**
- Humor & Entertainment › Puzzles & Games › **Chess** (o Computers & Technology › Programming › Languages & Tools › Python)

---

## 5. Ficha técnica del paperback

| Campo | Valor |
|---|---|
| Archivo interior | `libro\Jaque-al-modelo-interior-6x9.pdf` |
| Tamaño de corte (trim) | 6 × 9 in (15,24 × 22,86 cm) |
| Páginas | **146** |
| Interior | Blanco y negro, papel blanco |
| Sangrado (bleed) | **Sin sangrado** |
| Acabado de portada | Mate |
| Ancho del lomo | 146 × 0,002252 in ≈ **0,329 in (8,4 mm)** |
| Portada completa (con sangrado) | **12,579 × 9,25 in** |

> Con 146 páginas el lomo lleva texto (KDP lo permite desde 79). Si cambia el número de
> páginas, hay que regenerar la portada con el número nuevo (`build_cover.py <páginas>`).

---

## 6. Precio (sugerencia; la decisión es tuya)

- **eBook:** 9,99 USD (franja del 70 %: 2,99–9,99).
- **Paperback:** 19,99 USD, como el resto de tus técnicos cortos. KDP muestra la regalía exacta al
  poner el precio.

---

## 7. Enlaces del lanzamiento

- **GitHub:** github.com/Denisijcu/vertex-chess-arena
- **Hugging Face:** huggingface.co/Denisijcu/vertexqwen · huggingface.co/Denisijcu/vertexgemma
- **Video:** youtu.be/2_t0ijTg1_M
- **Amazon:** añadir el enlace al README del repo, a las dos fichas de Hugging Face y a la descripción del video en cuanto esté publicado

---

## 8. Frases del libro para redes

Todas son textuales del manuscrito:

- "Cuando tu modelo gane, pregunta quién más estaba jugando."
- "El que más fallaba era el que más ayuda recibía."
- "Un filtro de candidatos es un jugador."
- "Saber decir una jugada legal no es saber jugar."
- "Lo que no cuentas, no existe."
- "Un jugador al azar dentro de tu arena es la mejor línea base que existe."

---

## 9. Checklist antes de publicar

- [ ] Interior subido: `Jaque-al-modelo-interior-6x9.pdf`, 6×9, sin sangrado
- [ ] Revisar en el **visor de KDP** que no salgan avisos de margen ni de fuentes
- [ ] Portada envolvente `Jaque-al-modelo-portada-paperback.pdf`, 12,579 × 9,25 in, lomo 0,329 in
- [ ] eBook: `Jaque-al-modelo.epub` + portada `Jaque-al-modelo-portada-ebook.jpg` (1600×2560)
- [ ] Título y subtítulo idénticos en portada, interior y formulario
- [ ] ISBN gratuito de KDP
- [ ] KDP Select: decidir
- [ ] Contenido generado con IA: KDP lo pregunta. Responde según cómo se escribió el libro
- [ ] Edición en inglés: planificar como edición separada
