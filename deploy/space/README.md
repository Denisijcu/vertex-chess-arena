---
title: Vertex Chess Arena API
emoji: ♟️
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: 6.27.0
app_file: app.py
python_version: "3.10"
pinned: false
license: other
short_description: Backend de la app de torneos Qwen vs Gemma (Jaque al modelo)
models:
- Denisijcu/vertexqwen
- Denisijcu/vertexgemma
---

# Vertex Chess Arena — API (ZeroGPU)

Backend de la app de torneos de ajedrez del libro *Jaque al modelo*. Corre el mismo árbitro
que la arena local y genera las jugadas con los adaptadores LoRA publicados:

- [Denisijcu/vertexqwen](https://huggingface.co/Denisijcu/vertexqwen): Qwen 2.5 3B, V3 y legacy (**Built with Qwen**).
- [Denisijcu/vertexgemma](https://huggingface.co/Denisijcu/vertexgemma): Gemma 2 2B.

Aquí los modelos corren en bfloat16 con `transformers` + `peft`; en el libro se midieron como
GGUF `q4_k_m` en Ollama, así que alguna jugada puede salir distinta.

**Licencias:** Qwen 2.5 3B se usa bajo la Qwen Research License (uso no comercial). Gemma is
provided under and subject to the Gemma Terms of Use found at ai.google.dev/gemma/terms.

La cuota de GPU de ZeroGPU la gasta quien juega (2 min/día sin cuenta de Hugging Face). Cuando se acaba,
las jugadas se generan en CPU con los GGUF `q4_k_m` (llama.cpp): más lentas, pero sin límite.
