# Capítulo 13 — Publicarlo sin gastar

> Borrador. Modelos ya publicados en Hugging Face (20-10-2026); Space y Netlify, plan todavía no ejecutado. Fuentes: documentación de Hugging Face
> ZeroGPU (consultada el 20-10-2026), licencias de Qwen 2.5 3B y Gemma 2 2B.
> Revisar cifras y pasos al desplegar.

Un experimento que solo corre en mi portátil no lo puede comprobar nadie. El último paso es
publicarlo: los modelos en Hugging Face, el backend en un Space con GPU compartida y la app
en Netlify, para que cualquiera pueda jugar desde el móvil. Con una condición: **no añadir
gastos nuevos**. Ya pago Hugging Face PRO y Netlify; lo que no quepa ahí, no se despliega.

## La arquitectura

```
Móvil / navegador
      │
      ▼
Netlify  ──  la app Angular (archivos estáticos)
      │  HTTPS
      ▼
Hugging Face Space (ZeroGPU)  ──  árbitro + modelos
      ▲
      │  descarga al arrancar
Hugging Face Hub  ──  adaptadores LoRA de Qwen V3 y Gemma
```

## Los modelos en el Hub

Este paso ya está hecho. Los dos modelos están publicados como GGUF `q4_k_m`, listos para
Ollama:

- **`Denisijcu/vertexqwen`**: Qwen V3 y, para quien quiera reproducir el libro, el legacy.
- **`Denisijcu/vertexgemma`**: Gemma 2 2B.

La primera versión de las fichas tenía tres errores que este libro habría señalado en
cualquier otro proyecto: una licencia equivocada (Apache 2.0 para un derivado de Qwen 2.5 3B,
que no lo es), un número de pasos inventado y promesas de "nivel gran maestro". Las fichas
corregidas dicen qué es cada archivo, el prompt exacto, la receta del capítulo 9, las cifras
del sondeo y del torneo, **las limitaciones** (aprende el formato, no juega bien sin ayuda) y
la licencia correcta de cada uno, con su archivo de aviso.

Para el Space hará falta además subir los **adaptadores LoRA** (unos 60 MB el de Qwen, unos
42 MB el de Gemma): ZeroGPU trabaja con PyTorch, no con GGUF.

## El backend en ZeroGPU

**ZeroGPU** reparte GPUs de un grupo compartido: el Space no tiene GPU fija, la pide cuando
una función la necesita y la suelta al terminar. Tres datos de la documentación cambian el
diseño:

1. **Solo funciona con el SDK de Gradio.** El backend no puede ser el FastAPI tal cual. Hay
   que envolverlo en una app Gradio y exponer las funciones como API.
2. **Solo PyTorch.** Ollama no corre ahí. Los modelos se cargan con `transformers` +
   `peft` (base + adaptador), en la GPU, al arrancar el Space.
3. **La función que usa la GPU se marca con `@spaces.GPU`:**

```python
import spaces

@spaces.GPU(duration=20)
def ai_move(model_id: str, fen: str, mode: str) -> dict:
    ...  # arbitro.get_options + generate + parse
```

El árbitro (búsqueda alfa-beta, parser, reglas) no necesita GPU y corre fuera de esa
función. El modo `engine` no gasta GPU.

### La cuota

La cuota de ZeroGPU es **diaria y la gasta quien usa el Space**, no quien lo publica:

| Visitante | Cuota diaria |
|---|---|
| Sin cuenta | 2 minutos |
| Cuenta gratis | 5 minutos |
| Cuenta PRO | 40 minutos |

Cada jugada de un modelo de 2–3B tarda en torno a un segundo de GPU, más el tiempo de pedir
la GPU. Una partida de 50 jugadas del modelo cabe en la cuota de un visitante sin cuenta,
pero no muchas más. Por eso la app debe:

- Ofrecer primero **humano contra modelo**, que gasta la mitad que modelo contra modelo.
- Avisar cuando la cuota se acaba, y ofrecer seguir contra el motor (sin GPU).
- Dejar los torneos completos de IA contra IA como **repeticiones** de partidas ya jugadas
  (el historial y los PGN), no en directo.

## La app en Netlify

La app Angular se compila (`npm run build`) y se publica como archivos estáticos. Hay que
cambiar dos cosas:

- La URL de la API apunta al Space en lugar de a `localhost:8000`.
- Los torneos y el historial dejan de guardarse en el disco del backend. Un Space gratuito
  pierde los archivos al reiniciarse, así que los torneos de cada visitante se guardan en su
  navegador y los torneos "oficiales" (como la Copa del capítulo 11) se publican como datos
  estáticos dentro de la app.

## Las licencias

Antes de publicar, la parte que no se puede saltar:

- **Qwen 2.5 3B Instruct** está bajo la **Qwen Research License**: uso **no comercial**
  (investigación o evaluación). Un demo gratuito y público encaja; cobrar por el modelo o
  meterlo en un producto de pago requiere pedir licencia a Alibaba Cloud. Al distribuir el
  adaptador hay que incluir copia de la licencia, el aviso *"Qwen is licensed under the Qwen
  RESEARCH LICENSE AGREEMENT, Copyright (c) Alibaba Cloud. All Rights Reserved."* y mostrar
  **"Built with Qwen"** en la documentación.
- **Gemma 2 2B** está bajo los **Gemma Terms of Use**, que permiten uso comercial respetando
  su política de uso prohibido. Al redistribuir hay que incluir sus términos y el aviso
  correspondiente.
- **Piezas Cburnett** (CC BY-SA 3.0) y **cm-chessboard** (MIT): ya están acreditadas en el
  pie de la app.

El libro se puede vender: describe el experimento, no distribuye los pesos.

## La lista de comprobación

1. Subir los adaptadores LoRA junto a los GGUF ya publicados.
2. Crear el Space con Gradio, `transformers`, `peft` y el árbitro; probar `ai_move` con
   las 40 posiciones del sondeo y comparar con las cifras del capítulo 9.
3. Cambiar la URL de la API en la app, compilar y publicar en Netlify.
4. Probar desde un móvil, sin cuenta de Hugging Face, una partida completa.
5. Añadir el enlace de la app a las fichas de los modelos y a la descripción del video.

## Lo que te llevas de aquí

- Lee las restricciones de la plataforma **antes** de diseñar el despliegue: ZeroGPU impone
  Gradio y PyTorch.
- Una GPU compartida con cuota por visitante obliga a diseñar la experiencia alrededor del
  gasto.
- Sube adaptadores, no modelos completos, cuando el modelo base ya está en el Hub.
- Las licencias de los modelos base viajan con tus adaptadores. Léelas enteras.
