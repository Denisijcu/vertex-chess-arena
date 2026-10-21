# Capítulo 6 — Del adaptador a Ollama

> Borrador. Fuente: scripts/05_export_both_gguf.py, models/gguf/Modelfile.* y la bitácora.

Un adaptador LoRA no se puede servir solo: necesita su modelo base al lado. Para jugar
cientos de partidas lo práctico es fusionar los dos, comprimirlos y servirlos con Ollama.

## De LoRA a GGUF

Unsloth hace la fusión y la conversión en una llamada:

```python
model.save_pretrained_gguf(
    str(temp_export_dir),
    tokenizer,
    quantization_method="q4_k_m",
)
```

`q4_k_m` es una cuantización de 4 bits que mantiene en más precisión las capas más
sensibles. Es el punto medio habitual entre tamaño y calidad. Resultado en disco:

| Modelo | GGUF |
|---|---|
| Qwen 2.5 3B (legacy y V3) | 1,93 GB cada uno |
| Gemma 2 2B | 1,71 GB |

Curiosidad útil: el GGUF del legacy y el del V3 pesan **exactamente** lo mismo, al byte.
La cuantización fija el tamaño; el contenido de los pesos no. No uses el tamaño para saber
qué modelo tienes.

## El Modelfile

Ollama necesita un `Modelfile` que diga qué GGUF cargar y cómo hablarle. El de Qwen legacy
era así de corto:

```
FROM ./vertex-chess-qwen-q4_k_m.gguf
PARAMETER temperature 0.1
PARAMETER repeat_penalty 1.15
PARAMETER num_ctx 512
```

Sin `TEMPLATE` y sin `stop`. Ollama intenta deducir la plantilla de chat de los metadatos
del GGUF, y muchas veces acierta. Pero "muchas veces" no es una base para un experimento.
El de la V3 la deja escrita:

```
FROM ./vertex-chess-qwen-v3-q4_k_m.gguf
TEMPLATE """{{- range .Messages }}<|im_start|>{{ .Role }}
{{ .Content }}<|im_end|>
{{ end }}<|im_start|>assistant
"""
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"
PARAMETER temperature 0.1
PARAMETER repeat_penalty 1.15
PARAMETER num_ctx 1024
```

Tres cambios:

1. **La plantilla explícita** reproduce exactamente el formato ChatML con el que Qwen se
   entrenó: cada mensaje entre `<|im_start|>` y `<|im_end|>`, y el turno del asistente abierto
   al final.
2. **Los `stop`** cortan la generación en cuanto el modelo cierra su turno. Sin ellos, un
   modelo pequeño puede seguir escribiendo un segundo turno inventado.
3. **`num_ctx 1024`**. Con la lista completa de jugadas legales, algunos prompts del medio
   juego pasan de 512 tokens. Si el contexto se queda corto, Ollama recorta el prompt y el modelo
   deja de ver parte de lo que le mandamos, sin ningún aviso en la respuesta.

Se registra con:

```powershell
# Desde E:\vertex-chess-arena\models\gguf
ollama create vertexqwen-v3 -f Modelfile.qwen-v3
```

## Probar antes de jugar

Antes de poner un modelo en la arena, pregúntale a mano por una posición del dataset y
mira la respuesta cruda. Treinta segundos. Si el legacy hubiera pasado por esa prueba el
17 de octubre, habríamos visto la prosa en lugar de `Best move:` y este libro sería otro.

## Lo que te llevas de aquí

- Exporta a GGUF `q4_k_m` para servir modelos de 2–3B en 6 GB.
- Escribe la plantilla de chat y los `stop` en el Modelfile. No dependas de la detección.
- Calcula el contexto con el prompt más largo, no con el típico.
- El tamaño del archivo no identifica la versión del modelo.
- Una pregunta manual antes del primer partido vale más que cien partidas.

**Lo que viene:** en el capítulo 7 conocemos al árbitro, el programa que sostenía a los
modelos... y que acabó jugando por ellos.
