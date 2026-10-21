# Capítulo 4 — Afinando a Gemma 2 (2B)

> Borrador. Fuente: logs/bitacora.md (2026-10-17) y el script de entrenamiento de Gemma.
> Duración del entrenamiento: dato de Denis (no se conservó el log).

Gemma fue el modelo difícil. No porque aprendiera peor, sino porque llegar a entrenarla en
una tarjeta de 6 GB costó varios intentos. Este capítulo cuenta la receta que funcionó y,
sobre todo, por qué cada pieza está ahí.

## QLoRA en una frase

Cargamos el modelo base **comprimido a 4 bits** y lo dejamos congelado. Al lado de algunas de
sus capas añadimos dos matrices pequeñas, `A` y `B`, y **solo entrenamos esas**. El
resultado del entrenamiento no es un modelo nuevo, es un **adaptador** de pocos megas que
se "enchufa" al modelo base.

Dos números controlan el adaptador:

- **`r` (rango):** el tamaño de las matrices. Usamos `r = 8`. Más rango, más capacidad y
  más memoria.
- **`alpha`:** cuánto pesa el adaptador sobre el modelo base. Usamos `alpha = 16`, el doble
  del rango, que es la convención habitual.

## La receta

| Parámetro | Valor | Por qué |
|---|---|---|
| Modelo base | Gemma 2 2B *it*, 4 bits | Cabe en 6 GB con margen |
| LoRA | `r=8`, `alpha=16` | Pequeño y estable |
| Tasa de aprendizaje | `5e-5`, calentamiento de 15 pasos, coseno | Conservadora: no queremos que olvide hablar |
| Lote efectivo | 8 | Lote real pequeño + acumulación de gradientes |
| Longitud máxima | 384 tokens | Posición + jugadas + respuesta |
| Precisión | `fp16` | Turing no tiene `bf16` |
| Atención | `eager` | La recomendada para Gemma 2 |
| Pasos | 625 | 5.000 ejemplos ÷ 8 = **una época** |
| *Gradient checkpointing* | activado | Recalcula activaciones en vez de guardarlas: menos memoria |
| Guardado intermedio | ninguno (`save_strategy="no"`) | Ver "Reanudar sin miedo" |

## Entrenar solo la respuesta

Esta es la decisión más importante del capítulo, y la que más adelante explicará parte de la
diferencia entre los dos modelos.

Cada ejemplo tiene un prompt largo (sistema + FEN + lista de jugadas) y una respuesta
cortísima (`Best move: Nf3 (UCI: g1f3)`). Si calculas la pérdida sobre **todo** el texto,
el modelo pasa la mayor parte del entrenamiento aprendiendo a copiar listas de jugadas
legales, que ya le damos hechas. La señal útil, la jugada, se ahoga.

La solución es **enmascarar** el prompt: a esos tokens se les pone la etiqueta `-100`, que
la función de pérdida ignora. Así el modelo solo recibe nota por la respuesta:

```python
prompt_ids = tokenizer.encode(prompt_text, add_special_tokens=False)
answer_ids = tokenizer.encode(answer_text, add_special_tokens=False)
input_ids = prompt_ids + answer_ids
labels    = [-100] * len(prompt_ids) + answer_ids
```

Gemma se entrenó así desde el principio. El primer Qwen, no. Guarda este dato para el
capítulo 5.

## Once horas

Los 625 pasos tardaron **unas 11 horas** en la GTX 1660 Ti: alrededor de un minuto por paso.
Sin *tensor cores*, en `fp16`, con un lote real de una sola secuencia. Es lento, pero cabe en
una noche. Como referencia, Qwen V3, con un 50 % más de parámetros, tardaría 13 h 42 min
con la misma receta (capítulo 9).

## Reanudar sin miedo (la lección que aprendí después)

Un entrenamiento de horas en un portátil se va a interrumpir tarde o temprano: un corte de luz,
una actualización de Windows, tú mismo cerrando la ventana. Gemma entrenó sus 11 horas **sin
un solo punto de guardado** (`save_strategy="no"`). Salió bien, pero fue suerte: un corte en la
hora diez habría costado las diez horas.

Qwen V3 ya se entrenó con la lección aprendida: guarda un *checkpoint* cada 125 pasos y, al
arrancar, busca el último y continúa desde ahí (apéndice E). Perder como mucho 125 pasos es
aceptable; perderlo todo, no.

## Lo que te llevas de aquí

- QLoRA te deja entrenar modelos de 2–3B en 6 GB: base congelada a 4 bits y un adaptador
  pequeño.
- Si la respuesta es corta y el prompt largo, **enmascara el prompt**. Si no, entrenas al
  modelo a copiar.
- Una época completa (aquí, 625 pasos) es la unidad honesta de comparación.
- Guarda *checkpoints* y programa la reanudación desde el primer día.

**Lo que viene:** en el capítulo 5 afinamos a Qwen... o eso creíamos: la versión de 80
pasos que casi no aprendió nada.
