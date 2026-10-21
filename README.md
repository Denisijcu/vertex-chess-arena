# Vertex Chess Arena — Qwen 2.5 (3B) vs Gemma 2 (2B)

**Director & CEO:** Denis Sanchez Leyva (Vertex Coders LLC — Miami, FL)
**Entorno:** laboratorio aislado en `E:\vertex-chess-arena` (NVIDIA GeForce GTX 1660 Ti, 6 GB VRAM)

## Modelos, video y libro

- **Modelos (GGUF para Ollama):** [Denisijcu/vertexqwen](https://huggingface.co/Denisijcu/vertexqwen) · [Denisijcu/vertexgemma](https://huggingface.co/Denisijcu/vertexgemma)
- **Video:** [Afiné dos IAs para jugar ajedrez… y el árbitro jugaba por ellas](https://youtu.be/2_t0ijTg1_M)
- **Libro:** *Jaque al modelo: afiné dos IAs para jugar ajedrez y descubrí que el árbitro jugaba por ellas* — próximamente en Amazon <!-- AMAZON -->

## Qué es

Dos modelos abiertos afinados con QLoRA sobre **el mismo dataset** de ajedrez (5,000 posiciones:
2,000 evaluaciones Lichess, 2,000 puzzles Lichess, 1,000 de `chess-sft-20k`) y enfrentados en una
arena local con `python-chess`, Ollama, FastAPI y chessboard.js.

## Dos formas de medir (V3)

| Modo | Qué recibe el LLM | Qué mide |
|---|---|---|
| `pure` (por defecto) | Todas las jugadas legales, prompt idéntico al del entrenamiento | **Al modelo**. Es el duelo justo. |
| `arbiter` | Hasta 4 candidatas filtradas por alpha-beta prof. 2 + quiescencia | Al sistema híbrido motor + LLM |

En ambos modos una respuesta inválida se reemplaza por una jugada **aleatoria** entre las opciones
(antes era la mejor del motor, y eso premiaba fallar). El parser es estricto: solo cuenta como
acierto un SAN/UCI exacto de las opciones ofrecidas.

> Lección de la V2 (ver `logs/bitacora.md`, 2026-10-20): "Qwen siempre gana" era un artefacto.
> El árbitro jugaba por los modelos y el Qwen exportado era un adaptador de 80 pasos entrenado con
> otro dataset y sin máscara de pérdida. Gemma era el modelo mejor entrenado.

## Receta de entrenamiento (idéntica para ambos)

Mismo `Trainer` + `DataCollatorForSeq2Seq`, pérdida solo sobre la respuesta (`-100` en el prompt),
LoRA r=8 / alpha=16 en q,k,v,o,gate,up,down; lr 5e-5, warmup 15, cosine, 1 época (625 pasos),
batch efectivo 8, fp16, atención eager, seed 42, `MAX_SEQ_LENGTH=384`.

## Estructura

```text
E:\vertex-chess-arena\
├── dataset\processed\train_chess_elite.jsonl   # 5,000 posiciones (FEN + legales -> "Best move: SAN (UCI: ...)")
├── scripts\
│   ├── 01_build_chess_dataset.py / 01b_audit_chess_dataset.py
│   ├── 02_train_qwen_chess.py        # Qwen V3 — espejo de Gemma
│   ├── 03_train_gemma_chess.py       # Gemma 2 2B
│   ├── 04_test_chess_adapters.py
│   └── 05_export_both_gguf.py        # GGUF q4_k_m + Modelfiles con TEMPLATE explícito
├── arena\
│   ├── engine_arbiter.py             # modos pure/arbiter, parser estricto, anti-repetición
│   ├── match_runner.py               # torneo con colores alternos y claim_draw
│   ├── api_server.py                 # API V3: jugadores, jugadas, partidas, torneos; sirve la app
│   ├── index.html                    # página vieja (/legacy)
│   ├── tests\test_api.py             # 8 tests de la API (sin Ollama)
│   └── test_arbiter_v3.py            # 14 tests (no requieren Ollama)
├── frontend\                        # app Angular 21: relojes, bullet→clásicas, torneos, historial
├── diagnostics\                      # probe_bias.py, duel_both_colors.py
└── logs\                             # bitacora.md, matches_history.pgn, arena_results.jsonl
```

## Cómo correrlo

Todos los comandos usan el venv del proyecto.

1. **Entrenar** (desde `E:\vertex-chess-arena`):
   ```powershell
   venv\Scripts\python.exe scripts\02_train_qwen_chess.py
   venv\Scripts\python.exe scripts\03_train_gemma_chess.py
   ```
2. **Exportar y registrar** (export desde `E:\vertex-chess-arena`, `ollama create` desde `models\gguf`):
   ```powershell
   venv\Scripts\python.exe scripts\05_export_both_gguf.py
   cd models\gguf
   ollama create vertexqwen-v3 -f Modelfile.qwen-v3
   ```
3. **Tests y diagnóstico** (desde `E:\vertex-chess-arena\arena`):
   ```powershell
   ..\venv\Scripts\python.exe -m unittest -v test_arbiter_v3.py
   ..\venv\Scripts\python.exe ..\diagnostics\probe_bias.py 40 vertexqwen-v3 vertexgemma
   ```
4. **Torneo** (desde `E:\vertex-chess-arena\arena`):
   ```powershell
   ..\venv\Scripts\python.exe match_runner.py --games 10 --mode pure
   ```
5. **App web de torneos (Angular)**: ver `frontend/README.md`. Resumen:
   ```powershell
   # Desde E:\vertex-chess-arena\frontend
   npm ci
   npm run build
   # Desde E:\vertex-chess-arena\arena
   ..\venv\Scripts\python.exe -m uvicorn api_server:app --host 127.0.0.1 --port 8000
   ```
   Abrir `http://127.0.0.1:8000`. La página vieja sigue en `/legacy`.
