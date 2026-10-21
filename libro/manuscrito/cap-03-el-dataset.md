# Capítulo 3 — El dataset

> Borrador. Fuente: scripts/01_build_chess_dataset.py, scripts/01b_audit_chess_dataset.py y
> dataset/processed/train_chess_elite.jsonl. Las cifras se recalcularon sobre el archivo final.

Un modelo aprende lo que le enseñas, no lo que crees que le enseñas. Por eso el dataset
merece un capítulo propio.

## La receta: 5.000 posiciones de tres fuentes

El archivo final, `train_chess_elite.jsonl`, tiene **5.000 posiciones**, cada una con su
mejor jugada. Salen de tres conjuntos públicos en Hugging Face:

| Fuente | Posiciones | Qué aporta |
|---|---|---|
| `Lichess/chess-position-evaluations` | 2.000 (40 %) | Posiciones evaluadas por motor, con ventaja clara |
| `Lichess/chess-puzzles` | 2.000 (40 %) | Golpes tácticos y mates directos |
| `agi-noobs/chess-sft-20k` | 1.000 (20 %) | Posiciones curadas para *fine-tuning* |

Los datasets se leen **en streaming**: el script va recorriendo filas sin descargar los
archivos completos, que en el caso de Lichess ocupan muchísimo más de lo que cabe en un
portátil.

### Evaluaciones de Lichess

De cada posición evaluada por el motor nos quedamos con la primera jugada de su línea
principal, pero solo si la posición es **decisiva**: o hay un mate a la vista, o la ventaja
es de al menos 150 centipeones (un peón y medio). Además se descartan posiciones con menos
de 7 piezas (finales casi resueltos) y las de más allá de la jugada 40.

### Problemas de Lichess

Los *puzzles* de Lichess tienen una trampa de formato que conviene conocer: la posición
guardada es **anterior** al error del rival. La primera jugada de la solución es la del
rival que se equivoca, y la segunda es la que lo castiga. Así que el script aplica primero
la jugada del rival y luego toma la siguiente como respuesta correcta.

Se reservó una cuota del 25 % (500 posiciones) para **mates directos**, es decir, jugadas
cuyo SAN termina en `#`. El resto son golpes tácticos de problemas con rating de 1.900 o más.
La idea era darles a los modelos "instinto de mate". Veremos en el capítulo 11 que no
alcanzó.

### Sin duplicados

Antes de añadir una posición, el script comprueba que su FEN no esté ya en el conjunto. Una
posición repetida es un examen que el modelo ya vio; repetirla solo infla los aciertos.

## El formato de cada ejemplo

Cada línea del archivo es una conversación de tres mensajes, lista para entrenar un modelo
de chat:

```json
{"role": "system", "content": "You are an elite chess grandmaster engine created by Vertex Coders. ..."},
{"role": "user", "content": "Position FEN: ...\nLegal moves (SAN): ...\nSelect the best move."},
{"role": "assistant", "content": "Best move: Rexe7+ (UCI: e1e7)"}
```

Antes de escribirla, `python-chess` comprueba que la posición es válida y que la jugada es
legal en ella. Si no, la fila se descarta.

## La auditoría

Un segundo script, `01b_audit_chess_dataset.py`, relee el archivo y verifica las cuotas
(40/40/20), la legalidad de cada jugada, que la respuesta tenga el formato exacto, y el
reparto por fases de la partida y por bando. Sobre el archivo final:

- **2.588** posiciones con turno de blancas y **2.412** de negras.
- **1.457** jugadas correctas dan jaque o mate; **570** son mate directo.
- **1.546** son capturas.

## El detalle que pasó desapercibido

Al preparar este capítulo recalculé una cosa que la auditoría no miraba. El script que
construye el prompt corta la lista de jugadas legales a las **primeras 45**:

```python
legal_str = ", ".join(legal_sans[:45])
```

La intención era razonable: no hacer el prompt demasiado largo. Pero en el medio juego hay
posiciones con más de 45 jugadas legales. Resultado medido sobre el archivo:

- **498 posiciones** (casi el 10 %) llevan la lista recortada.
- En **9 de ellas**, la jugada correcta **no aparece en la lista** que ve el modelo.

Nueve de cinco mil no cambian el resultado del experimento. Pero la lección vale oro: en
esos nueve ejemplos le estamos enseñando al modelo a contestar una jugada que no está entre
las opciones que le dimos. Y cuando más adelante la arena le mande la lista **completa**,
el modelo verá prompts un poco distintos de los que vio al entrenar. Ninguna auditoría
detecta lo que no se le pide comprobar.

## Lo que te llevas de aquí

- Lee los datos en streaming si la fuente es enorme; no necesitas descargarla entera.
- Conoce el formato de cada fuente. En los puzzles de Lichess, la primera jugada es del
  rival.
- Elimina duplicados por la clave que importa (aquí, el FEN), no por la línea completa.
- Valida cada ejemplo con un programa antes de guardarlo.
- Audita también lo que **no** se te ocurrió auditar: cualquier recorte, filtro o
  truncamiento silencioso.

**Lo que viene:** en el capítulo 4, la odisea de afinar a Gemma en 6 GB.
