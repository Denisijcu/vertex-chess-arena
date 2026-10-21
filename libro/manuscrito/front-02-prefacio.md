# Prefacio

La idea parecía sencilla. Tomo dos modelos de lenguaje abiertos, pequeños, de los que caben
en una tarjeta gráfica de casa. Los afino con el mismo conjunto de posiciones de ajedrez. Los
pongo a jugar uno contra otro. Gana el mejor.

Ganó Qwen. Ganó siempre. Y eso que, según yo, había entrenado bastante menos que Gemma.

Ese "y eso que" es el motivo de este libro. Un resultado que contradice lo que esperas es la
mejor noticia que te puede dar un experimento, porque te obliga a mirar debajo. Y lo que
encontré debajo no fue un modelo prodigioso. Fue un árbitro que, sin que nadie se lo pidiera,
jugaba por los modelos; un adaptador que no era el que yo creía; una función entera que no se
ejecutaba nunca; un parser que aceptaba jugadas que no existían. Cada pieza, por separado,
parecía razonable. Juntas, fabricaban un ganador.

Este no es un libro de ajedrez, aunque haya tableros en casi todas las páginas. Es un libro
sobre **medir**. Sobre la diferencia entre evaluar un modelo y evaluar el sistema que lo
rodea. Sobre por qué una cifra que te gusta merece más sospecha que una que no te gusta. Y
sobre cómo se arregla todo eso cuando lo encuentras: con un entrenamiento espejo, un duelo
justo y una arena con reloj, como la de cualquier torneo.

Todo lo que cuento pasó de verdad, en mi máquina, entre el 16 y el 20 de octubre de 2026, y
está registrado en la bitácora del proyecto. Cuando digo que algo tardó 13 horas y 42
minutos, es porque tardó eso. Cuando digo que un modelo acertó 4 de 40, es porque lo medí con
las mismas 40 posiciones que al otro.

Si estás afinando tu propio modelo, ojalá este libro te ahorre la semana que a mí me costó
descubrir que el árbitro jugaba por ellas.

— Denis Sánchez Leyva
Miami, 2026
