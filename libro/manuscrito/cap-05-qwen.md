# Capítulo 5 — Afinando a Qwen 2.5 (3B)

> Borrador. Fuente: scripts/02_train_qwen_chess_v2_legacy.py, models/qwen_chess_adapter,
> models/adapters/qwen_chess_lora, models/checkpoints_qwen y la bitácora.

Qwen fue el modelo fácil. Cabía, arrancaba, entrenaba rápido. Precisamente por eso nadie lo
miró con lupa, y ahí empezó el problema.

## Tres Qwen en la misma carpeta

Al auditar el proyecto (capítulo 8) aparecieron **tres** versiones de Qwen afinado. Conviene
presentarlas aquí, porque la confusión entre ellas explica media historia:

| Versión | Dónde vive | Receta | ¿Llegó a la arena? |
|---|---|---|---|
| **Legacy** | `models/qwen_chess_adapter` (17-oct, 03:15) | 80 pasos, `r=8`, pérdida sobre todo el texto | **Sí.** Era el que jugaba |
| V2 | `models/adapters/qwen_chess_lora` (17-oct, 13:25) | 250 pasos, `r=16`, `alpha=32`, `lr 1.5e-4` | No. Nunca se exportó |
| V3 | `models/qwen_chess_adapter_v3` (20-oct) | Receta espejo de Gemma, 625 pasos | Sí, desde el capítulo 9 |

El script de exportación buscaba el adaptador en `models/qwen_chess_adapter`. El script de
entrenamiento V2 guardaba en `models/adapters/qwen_chess_lora`. Dos rutas distintas, y
ningún error: el exportador encontró un adaptador válido (el viejo) y lo convirtió sin
quejarse. **Durante todo el experimento, el Qwen de la arena fue el de 80 pasos.**

## Cómo entrenaba la versión vieja

Los scripts V1 y V2 usaban `SFTTrainer` de la librería TRL con la opción
`dataset_text_field="text"`: se le pasa la conversación entera ya formateada como un solo
texto y el entrenador calcula la pérdida **sobre todo**. Sistema, FEN, lista de jugadas y
respuesta.

Recuerda el capítulo 4. Cada ejemplo tiene unos 270 tokens de prompt y unos 15 de respuesta.
Si la pérdida cuenta todo, más del 90 % del esfuerzo se va en aprender a reproducir prompts.
La curva de pérdida baja (la V2 pasó de 2,33 a 0,55 en 250 pasos) y parece que el modelo
aprende. Lo que aprende es a copiar FEN.

Y 250 pasos con lote efectivo de 8 son 2.000 ejemplos: **0,4 épocas**. Ni siquiera vio el
dataset completo una vez. El legacy, con 80 pasos, vio 640.

## Qué sabía hacer el legacy

En el sondeo del capítulo 9 le dimos al legacy 40 posiciones del propio dataset de
entrenamiento. Resultado: **0 de 40** respuestas con el formato `Best move:`. Siempre
contestaba con prosa del estilo *"The strongest tactical move in this position is..."*.
No había aprendido ni la forma de la respuesta.

Y sin embargo, ganaba. El capítulo 8 explica cómo.

## Lo que te llevas de aquí

- Cuando un script entrena y otro exporta, **una sola constante** debe definir la ruta del
  adaptador. Dos rutas escritas a mano son dos versiones de la verdad.
- Un exportador que "encuentra algo" no es un exportador que encuentra lo correcto. Imprime
  la fecha y el `train_log` del adaptador que exportas.
- Una curva de pérdida que baja no prueba que el modelo aprenda la tarea. Pregunta **qué**
  tokens están en la pérdida.
- Cuenta épocas, no pasos: pasos × lote ÷ tamaño del dataset.

**Lo que viene:** en el capítulo 6 pasamos del adaptador a Ollama, el camino que siguieron
los dos modelos para llegar al tablero.
