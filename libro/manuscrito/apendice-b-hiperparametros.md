# Apéndice B — Hiperparámetros

> Fuente: scripts/03_train_gemma_chess.py, scripts/02_train_qwen_chess.py (V3),
> scripts/02_train_qwen_chess_v2_legacy.py y los adaptadores en models/.

## Recetas finales (las del duelo justo)

| Parámetro | Gemma 2 2B | Qwen 2.5 3B V3 |
|---|---|---|
| Modelo base | `unsloth/gemma-2-2b-it-bnb-4bit` | `unsloth/Qwen2.5-3B-Instruct-bnb-4bit` |
| LoRA `r` / `alpha` / *dropout* | 8 / 16 / 0,0 | 8 / 16 / 0,0 |
| Módulos LoRA | `q,k,v,o,gate,up,down_proj` | `q,k,v,o,gate,up,down_proj` |
| Tasa de aprendizaje | 5e-5 | 5e-5 |
| Calentamiento / programa | 15 pasos / coseno | 15 pasos / coseno |
| Lote por dispositivo × acumulación | 1 × 8 | 1 × 8 |
| Épocas / pasos | 1 / 625 | 1 / 625 |
| Longitud máxima | 384 | 384 |
| Precisión / atención | `fp16` / `eager` | `fp16` / `eager` |
| Optimizador | `adamw_torch` | `adamw_torch` |
| Semilla | 42 | 42 |
| Pérdida | solo respuesta | solo respuesta + `<|im_end|>` |
| Adaptador | ~42 MB | ~60 MB |

Duración en la GTX 1660 Ti: Gemma, unas 11 h; Qwen V3, 13 h 42 min (pérdida 4,23 → 0,23, media 0,36).

## Las versiones anteriores de Qwen

| | Legacy (el que jugó) | V2 (nunca exportado) |
|---|---|---|
| Carpeta | `models\qwen_chess_adapter` | `models\adapters\qwen_chess_lora` |
| LoRA `r` / `alpha` | 8 / 16 | 16 / 32 |
| Pasos | 80 | 250 (0,4 épocas) |
| Tasa de aprendizaje | — | 1,5e-4 |
| Pérdida | sobre todo el texto | sobre todo el texto (2,33 → 0,55) |

## Inferencia (Ollama)

| Parámetro | Valor |
|---|---|
| Cuantización | `q4_k_m` |
| Contexto | 1024 |
| Temperatura (Modelfile) | 0,1 |
| `repeat_penalty` | 1,15 |
| `stop` (Qwen) | `<|im_end|>`, `<|endoftext|>` |
