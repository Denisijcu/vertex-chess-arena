# Capítulo 9 — Un duelo justo

> Borrador. Fuente: scripts/02_train_qwen_chess.py (V3), models/qwen_chess_adapter_v3/train_log.json,
> arena/engine_arbiter.py (V3), diagnostics/probe_v3_stdout.txt, tourney_pure_v3.txt y
> tourney_arbiter_v3.txt.

Sabiendo lo que estaba mal, el plan era sencillo de decir: que los dos modelos lleguen a la
arena en igualdad de condiciones, y que la arena no juegue por ninguno.

## Paso 1: el entrenamiento espejo

Qwen V3 se entrenó con **la misma receta que Gemma**, línea por línea (capítulo 4):
QLoRA `r=8`, `alpha=16`, `lr 5e-5` con calentamiento de 15 pasos y coseno, lote efectivo 8,
384 tokens, `fp16`, atención `eager`, **625 pasos = una época**, y la pérdida solo sobre la
respuesta.

Para enmascarar el prompt en Qwen hubo que pelear con un detalle de la librería: con
`tokenize=True`, `apply_chat_template` devolvía un objeto `BatchEncoding` en lugar de una
lista de ids. La solución robusta es pedir el texto y codificarlo aparte:

```python
prompt_text = tokenizer.apply_chat_template(
    messages[:-1], tokenize=False, add_generation_prompt=True)
prompt_ids = tokenizer.encode(prompt_text, add_special_tokens=False)
answer_ids = tokenizer.encode(answer + "<|im_end|>", add_special_tokens=False)
labels = [-100] * len(prompt_ids) + answer_ids
```

Fíjate en el `<|im_end|>` al final de la respuesta: el modelo también aprende a **cerrar su
turno**, que es lo que luego detiene la generación en Ollama.

**Cifras del entrenamiento** (de `train_log.json`):

- 625 pasos en **13 h 42 min**: unos 79 s por paso. Subió a unos 145 s por paso en los ratos
  en que se jugaban partidas con Ollama en la misma GPU.
- Pérdida: de **4,23** en el paso 1 a **0,23** en el paso 625. Media de todo el
  entrenamiento, 0,36; media de los últimos 50 pasos, 0,20.
- Los pasos 1, 2 y 4 dieron gradiente `NaN` y se saltaron. Es normal en `fp16`: el escalador
  de pérdida empieza alto y lo va bajando hasta encontrar un valor que no desborde.

## Paso 2: un árbitro honesto

El árbitro V3 cambia cinco cosas:

1. **Respaldo aleatorio.** Si el modelo falla, la jugada se elige **al azar** entre sus
   opciones. Fallar ya no se premia.
2. **Parser estricto.** Solo cuenta `Best move: <SAN exacto>`, `UCI: <uci exacto>` o una
   respuesta que sea exactamente una jugada. Nada de rescatar prosa.
3. **El prompt del dataset**, carácter por carácter.
4. **Dos modos**, y el modo forma parte del resultado:
   - **`pure`**: el modelo ve **todas** las jugadas legales. El árbitro solo hace de notario.
   - **`arbiter`**: el modelo elige entre los candidatos filtrados, como antes.
5. **Código vivo y anti-bucles.** `_evaluate_move` por fin ordena los candidatos en finales
   ganados, y se descartan las jugadas que repiten una posición reciente.

Además, las partidas alternan colores y reclaman la triple repetición.

## Paso 3: medir al modelo sin tablero

Antes de jugar, un sondeo: las mismas 40 posiciones del dataset para los tres modelos.

| Modelo | Formato `Best move:` | Acierta la jugada del dataset |
|---|---|---|
| Qwen legacy | 0 / 40 | 0 / 40 |
| **Qwen V3** | **39 / 40** | 4 / 40 |
| **Gemma** | **40 / 40** | **9 / 40** |

El reentrenamiento funcionó: Qwen pasó de no saber contestar a contestar casi siempre. Pero
Gemma acierta más del doble. Con datos de entrenamiento, ojo: estas posiciones ya las vieron.

Un detalle curioso del sondeo: a veces Qwen V3 da bien el SAN y mal el UCI, como en
`Best move: Bb7 (UCI: d8b7)`, que no corresponde a la posición. El parser V3 lee primero el
SAN, así que no le afecta. Pero es otra prueba de que el modelo aprendió la **forma** de la
respuesta mejor que su contenido.

## Paso 4: jugar

**Modo puro, 10 partidas:** Gemma 5,5 – Qwen V3 4,5. Jugadas válidas: Gemma 99,2 %, Qwen
95,5 %. Solo una partida decisiva; las otras nueve, tablas por triple repetición (capítulo
11).

**Modo árbitro, 4 partidas:** Qwen V3 2,5 – Gemma 1,5. Jugadas válidas: Qwen 94,1 %, Gemma
99,6 %. Y un dato que lo dice todo: en las tres partidas decisivas **ganaron las blancas**.
Con el árbitro, lo que más pesa es quién mueve primero, no qué modelo hay detrás.

Sin árbitro gana Gemma, el que mejor contesta. Con árbitro, el resultado es una moneda al
aire. La diferencia entre los modelos solo se ve cuando quitas la ayuda.

## Lo que te llevas de aquí

- Para comparar dos modelos, **la misma receta** de entrenamiento. Si no, comparas recetas.
- Con prompts largos y respuestas cortas, enmascara el prompt y entrena también el token de
  fin de turno.
- El respaldo de un sistema debe ser **neutral**. El azar es neutral; el motor no.
- Mide con y sin ayuda, y publica las dos cifras.
- Un sondeo fuera del tablero (formato y acierto por posición) separa "sabe contestar" de
  "sabe jugar".

**Lo que viene:** en el capítulo 10, la arena profesional: relojes, torneos y todo lo que
hace falta para que otros puedan jugar.
