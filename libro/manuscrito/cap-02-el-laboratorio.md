# Capítulo 2 — El laboratorio

> Borrador. Fuente: logs/bitacora.md (2026-10-16 y 2026-10-17), scripts del proyecto.

Todo este proyecto vive en una sola carpeta de un disco aparte: `E:\vertex-chess-arena`.
Parece un detalle de orden, pero es la primera decisión técnica del libro.

## Aislar el laboratorio

Afinar modelos genera basura en cantidades industriales: modelos descargados de varios
gigas, cachés de datasets, archivos temporales, compilaciones. Por defecto, las librerías de
Hugging Face y PyTorch lo guardan todo en la carpeta del usuario, en el disco `C:`. Con dos
modelos y tres datasets, el disco del sistema se llena antes de que te des cuenta.

La solución es redirigir todas las cachés al disco del proyecto, al principio de cada
script y antes de importar nada:

```python
BASE_DIR = Path("E:/vertex-chess-arena").resolve()
CACHE_DIR = BASE_DIR / ".cache"
os.environ["HF_HOME"] = str(CACHE_DIR / "huggingface")
os.environ["TORCH_HOME"] = str(CACHE_DIR / "torch")
os.environ["TMP"] = str(CACHE_DIR / "tmp")
os.environ["TEMP"] = str(CACHE_DIR / "tmp")
```

Con eso, el proyecto completo (modelos, datos, cachés, adaptadores) cabe y se borra en una
sola carpeta. Y un entorno virtual de Python (`venv`) dentro de la misma carpeta guarda
las versiones exactas que funcionaron.

## La GPU: una Turing de 6 GB

La tarjeta es una **NVIDIA GeForce GTX 1660 Ti** de portátil, con **6 GB** de memoria y
arquitectura **Turing**. Tres datos de esa ficha condicionan todo lo demás:

1. **6 GB de memoria.** Un modelo de 3B en precisión completa ocupa unos 12 GB. No cabe ni
   para mirarlo. Por eso usamos **QLoRA**: el modelo base se carga comprimido a 4 bits y solo
   se entrenan unas matrices pequeñas que se le añaden (el *adaptador* LoRA). Qwen 3B queda
   en unos 2 GB; Gemma 2B, en algo menos.
2. **Turing no soporta `bf16`.** El formato numérico que usan casi todos los tutoriales
   modernos para entrenar no existe en esta tarjeta. Hay que usar `fp16`.
3. **Esta 1660 Ti no tiene *tensor cores*.** Son los circuitos especializados que aceleran
   las multiplicaciones de matrices en las GPU RTX. Sin ellos, el `fp16` funciona, pero
   despacio. Este dato no lo vi venir, y explica una de las cifras más dolorosas del libro: el
   entrenamiento final de Qwen tardó **unos 79 segundos por paso**.

## Las trampas de Gemma con 6 GB

Gemma 2 tiene un vocabulario enorme: unos **256.000 tokens**. Cada vez que el modelo predice
la siguiente palabra, produce una puntuación para cada uno de esos 256.000 tokens. Con
secuencias de cientos de tokens, esa matriz de puntuaciones, por sí sola, se come buena
parte de la memoria.

El primer intento de entrenar a Gemma usaba Unsloth, un framework que acelera el
*fine-tuning* fusionando operaciones. Al llegar al **paso 9** se cayó con este error:

```
Unsloth: No or negligible GPU memory available for fused cross entropy
```

La "entropía cruzada fusionada" es justo la optimización que calcula la pérdida sobre ese
vocabulario gigante. En 6 GB no había sitio. Los intentos siguientes chocaron con el
asignador de memoria de PyTorch y con dependencias que pedían un compilador de C que la
máquina no tenía.

La solución, documentada en la bitácora del 17 de octubre, tuvo cuatro partes:

- Desactivar la pérdida fusionada (`UNSLOTH_USE_UNSLOTH_FUSED_CE=0`) y, al final, entrenar
  a Gemma sin Unsloth, con las librerías estándar: `transformers`, `peft` y `bitsandbytes`.
- Cargar el modelo en `torch.float16` con atención `eager` (la implementación más simple y
  la que Gemma 2 recomienda por cómo limita sus valores internos).
- Limitar la longitud a **384 tokens**, que cubren de sobra una posición con su lista de
  jugadas y la respuesta.
- Ajustar el asignador de memoria:

```python
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True,max_split_size_mb:32"
```

Con eso, Gemma entrenó entero. El capítulo 4 cuenta cómo.

## Inferencia: Ollama

Para jugar, los modelos no corren en Python. Se convierten a **GGUF** (el formato de
llama.cpp), se comprimen a 4 bits (`q4_k_m`) y se sirven con **Ollama**, que los expone en
`http://127.0.0.1:11434`. El árbitro les manda cada posición por HTTP y lee la respuesta.

Esto tiene una consecuencia que conviene tener presente desde ya: **Ollama y el
entrenamiento comparten la misma GPU**. Si juegas una partida mientras entrenas, los dos se
pelean por los 6 GB. Lo medimos sin querer: el entrenamiento de Qwen pasó de 79 a unos 145
segundos por paso mientras se jugaban partidas en la arena.

## Lo que te llevas de aquí

- Aísla el laboratorio en una carpeta y redirige todas las cachés allí antes de importar
  nada.
- Lee la ficha de tu GPU antes de copiar un tutorial: memoria, soporte de `bf16` y *tensor
  cores* cambian qué puedes hacer y cuánto va a tardar.
- Los vocabularios grandes cuestan memoria en el cálculo de la pérdida. Con 6 GB, las
  optimizaciones "fusionadas" pueden ser el problema y no la solución.
- No entrenes y sirvas modelos a la vez en la misma GPU si quieres tiempos predecibles.

**Lo que viene:** en el capítulo 3 construimos el dataset: 5.000 posiciones y un detalle que
pasó desapercibido.
