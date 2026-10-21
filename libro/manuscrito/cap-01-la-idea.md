# Capítulo 1 — La idea

> Borrador. Fuente: logs/bitacora.md (2026-10-16). Todo lo técnico de este capítulo pasó de
> verdad y está medido.

Hay preguntas que solo se contestan poniendo a dos cosas a pelear. ¿Qué modelo pequeño
aprende mejor una tarea concreta? Puedes leer *benchmarks*, comparar tablas, discutir en
foros. O puedes hacer lo que haría cualquiera en un barrio: ponerlos frente a frente y ver
quién gana.

La tarea que elegí fue el ajedrez.

## Por qué ajedrez

El ajedrez tiene tres propiedades que lo hacen perfecto para medir un modelo de lenguaje:

1. **Las reglas son exactas.** Una jugada es legal o no lo es. No hay "más o menos". Eso
   significa que cada respuesta del modelo se puede comprobar con un programa, sin opiniones.
2. **El resultado es indiscutible.** Una partida termina en victoria, derrota o tablas. No
   hace falta un juez humano que diga si la respuesta "suena bien".
3. **Hay datos de sobra.** Lichess, el servidor de ajedrez libre más grande del mundo,
   publica millones de partidas, posiciones evaluadas por motores y problemas tácticos con
   su solución.

Y una cuarta, que no es técnica pero importa: el ajedrez se entiende. Cualquiera que vea un
tablero sabe si un modelo hizo una tontería. Eso hace que los fallos sean visibles, y los
fallos visibles son los que enseñan.

## Los dos contendientes

Elegí dos modelos abiertos que cupieran en mi tarjeta, una **GTX 1660 Ti de 6 GB**:

- **Qwen 2.5 de 3.000 millones de parámetros (3B)**, versión *Instruct*, de Alibaba.
- **Gemma 2 de 2.000 millones de parámetros (2B)**, versión *it*, de Google.

Los dos son modelos de chat de propósito general. Ninguno fue entrenado para jugar ajedrez.
Saben qué es el ajedrez, como saben qué es la fotosíntesis, pero si les das una posición y
les pides la mejor jugada, contestan con párrafos llenos de confianza y jugadas que a veces
ni existen.

La idea era enseñarles una sola cosa: dada una posición, elegir la mejor jugada y decirla en
un formato fijo. Con el mismo dataset, con la misma técnica (QLoRA), en la misma máquina. Y
luego, a jugar.

## Qué le pedimos a un modelo

Para que la comparación sea limpia, el modelo nunca juega "de memoria". En cada turno recibe
tres cosas:

```
Position FEN: r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3
Legal moves (SAN): Bb5, Bc4, Nc3, d4, ...
Select the best move.
```

- El **FEN**, que es la forma estándar de escribir una posición de ajedrez en una línea de
  texto.
- La lista de **jugadas legales** en notación SAN (la que usan los libros: `Nf3`, `Bxc6`,
  `O-O`).
- La instrucción.

Y debe contestar exactamente así:

```
Best move: Bb5 (UCI: f1b5)
```

La jugada en SAN y, entre paréntesis, en UCI, que es la notación "de máquina": casilla de
origen y casilla de destino.

Darle la lista de jugadas legales es una decisión de diseño importante. Un modelo de 3B no
sabe calcular qué jugadas son legales en una posición; eso lo hace mejor un programa en
microsegundos. Lo que queremos medir es otra cosa: si, entre las jugadas posibles, el
modelo sabe cuál es buena.

## Alrededor de los modelos: la arena

Un modelo que contesta "Best move: Bb5" no es todavía un jugador de ajedrez. Hace falta
alguien que lleve el tablero, que compruebe la jugada, que pase el turno, que decida cuándo
se acaba la partida. A ese alguien lo llamé **el árbitro**: un programa en Python, con la
librería `python-chess`, que habla con los modelos a través de Ollama.

Encima del árbitro puse una página web sencilla para ver las partidas. Más adelante (capítulo
10) esa página se convirtió en una aplicación de torneos con reloj, al estilo de chess.com.

Guarda la palabra *árbitro*. Va a ser la protagonista inesperada de este libro.

## La sorpresa

Entrené a los dos. Los puse a jugar. Qwen ganó. Los volví a poner. Qwen ganó otra vez.
Partida tras partida, Qwen.

Lo raro no era que ganara uno. Lo raro era quién. Según lo que yo creía, Gemma había
entrenado 625 pasos y Qwen solo 80. Era como si el que menos había estudiado sacara
siempre la mejor nota.

Hay dos formas de reaccionar a algo así. La primera es inventarse una explicación bonita:
"Qwen es una arquitectura superior para el razonamiento formal". Lo escribí, de hecho, en la
primera versión de la bitácora. La segunda es sospechar. Este libro cuenta lo que pasó
cuando, por fin, sospeché.

## Lo que te llevas de aquí

- Elige tareas donde la respuesta se pueda **verificar con un programa**. Te ahorrarán
  discusiones y te darán números honestos.
- Separa lo que debe hacer el modelo de lo que puede hacer un programa. Las jugadas legales
  las calcula `python-chess`; el modelo solo elige.
- Un resultado que contradice tus expectativas no es un éxito ni un fracaso: es una pista.

**Lo que viene:** en el capítulo 2 montamos el laboratorio, una GPU de 6 GB con Windows y
todas sus trampas.
