# Capítulo 8 — "Qwen siempre gana"

> Borrador. Fuente: diagnostics/duel_both_colors.py y duel_results.txt,
> diagnostics/probe_bias.py y probe_results.jsonl, y la revisión de código del 20-10-2026.

La primera versión de la bitácora tenía una conclusión elegante: *"Qwen demuestra mayor
competencia nativa en el procesamiento de cadenas FEN densas"*. Suena a paper. Era falso.
Este capítulo cuenta cómo se desmonta una conclusión bonita: leyendo el código y midiendo.

## El duelo con lupa

Primero, un duelo de dos partidas con colores cambiados y un contador por jugada. Para cada
jugada se anotó si salió **limpia** (el modelo nombró una opción válida), si fue **respaldo**
(el árbitro tuvo que elegir) y si coincidió con la **primera** jugada de la lista del motor
(la "top-1").

| | Limpias | Respaldo | Top-1 del motor |
|---|---|---|---|
| Partida 1, Qwen (blancas) | 31 | **14** | 25 de 45 |
| Partida 1, Gemma (negras) | 44 | **0** | 11 de 44 |
| Partida 2, Gemma (blancas) | 77 | 1 | 19 de 78 |
| Partida 2, Qwen (negras) | 62 | **16** | 25 de 78 |

Qwen ganó las dos. Y la tabla dice por qué: en la partida 1, **Gemma nunca falló y Qwen
falló 14 veces**. Cada fallo de Qwen era una jugada del motor. Qwen jugó la top-1 del motor
en más de la mitad de sus jugadas; Gemma, en una de cada cuatro.

**El que más fallaba era el que más ayuda recibía.**

## Los siete problemas

La revisión de código encontró siete cosas. Ninguna era grave sola. Juntas fabricaban el
resultado.

1. **El respaldo premiaba fallar.** `candidate_moves[0]` era la mejor jugada del motor
   (capítulo 7).
2. **El Qwen de la arena era el de 80 pasos.** El exportador leía otra carpeta (capítulo 5).
   En 40 posiciones del propio dataset, ese modelo dio **0 de 40** respuestas en formato.
3. **El parser era indulgente.** Si no encontraba `Best move:`, recorría la prosa buscando
   *cualquier cosa* con forma de jugada y la aceptaba si estaba entre las opciones. Una
   frase como *"the bishop could go to f7"* podía convertirse en una jugada "limpia". Y usaba
   `board.parse_san()`, que acepta `Bxf7` aunque en f7 no haya nada que capturar. Por eso el
   legacy, que nunca escribía el formato, tenía 31 jugadas "limpias".
4. **El prompt de la arena no era el del entrenamiento.** Otro mensaje de sistema, una
   línea extra `Side to move:` y, en lugar de las jugadas legales, los cuatro candidatos del
   árbitro con la etiqueta `Legal moves`.
5. **Código muerto.** `_evaluate_move`, con toda la lógica de rematar finales (la caja de
   la dama, el mate en 2), estaba escrita pero **no se llamaba desde ningún sitio**.
6. **Colores fijos.** El script de partidas ponía siempre al mismo modelo con blancas.
7. **Repeticiones sin reclamar** y temperatura de 0,05: las partidas tendían a repetirse
   jugada por jugada.

## Por qué nadie lo vio

Porque cada pieza tenía una buena razón. El respaldo con la mejor jugada "evita que la
partida se rompa". El parser indulgente "rescata respuestas casi correctas". El filtro de
candidatos "evita que el modelo regale piezas". La temperatura baja "da respuestas
estables". Cada decisión, sola, mejoraba la experiencia de ver partidas. Juntas convirtieron
el experimento en una medición del árbitro.

Y había una pista que lo gritaba desde el principio: **el modelo que menos había entrenado
ganaba**. En vez de sospechar, la bitácora inventó una teoría para explicarlo.

## Lo que te llevas de aquí

- Cuando el resultado contradice el esfuerzo de entrenamiento, **sospecha de la arena antes
  que de los modelos**.
- Cuenta por separado las jugadas del modelo y las del sistema. Si no las cuentas, no
  existen.
- Un parser indulgente convierte fallos en aciertos. Acepta solo el formato exacto.
- El prompt de evaluación debe ser **idéntico** al de entrenamiento.
- Busca código muerto: una función que nadie llama es una promesa que no se cumple.
- Desconfía de tus propias conclusiones elegantes. Escríbelas, y luego intenta romperlas.

**Lo que viene:** en el capítulo 9 rehacemos el duelo para que sea justo.
