# Bitácora de Ingeniería — Proyecto: Vertex Chess Arena (Qwen vs. Gemma)
- **Director:** Denis Sanchez Leyva — CEO, Vertex Coders LLC
- **Unidad de Aislamiento:** `E:\vertex-chess-arena` (6GB VRAM GTX 1660 Ti)
- **Dataset Fuente:** `Lichess/standard-chess-games` (Streaming Parquet + Filtro Elo >= 2200)
- **Objetivo:** Afinar Qwen 2.5 y Gemma con el mismo corpus táctico (FEN + Legal Moves -> Best SAN Move) y enfrentarlos en una Arena local.

## [2026-10-16] — Fase 1: Inicialización y Pipeline de Extracción Lichess
- Estructura creada en `E:\vertex-chess-arena`.
- Diseño del extractor en streaming (`01_build_chess_dataset.py`) usando `python-chess` para validar legalidad de cada jugada y limpiar anotaciones `%clk`.

### [17-10-2026] — Hardening de Entrenamiento y Optimización VRAM para Gemma 2 (2B)

* **Problema Identificado:** 
  * El entrenamiento previo de Gemma 2 en la GTX 1660 Ti (6 GB VRAM) arrojaba un `RuntimeError` (`Unsloth: No or negligible GPU memory available for fused cross entropy`) al alcanzar el step 9. 
  * Los intentos posteriores con `transformers` fallaban por restricciones de asignadores de caché de PyTorch (`CachingAllocator option max_split_size_mb too small`) y dependencias cruzadas con `torchao` y `cl.exe`.

* **Solución de Ingeniería Aplicada:**
  * **Eliminación de Kernels Fusionados:** Se desactivó por completo la pérdida cruzada fusionada de Unsloth (`UNSLOTH_USE_UNSLOTH_FUSED_CE="0"`) para evitar desbordamientos de VRAM con el enorme vocabulario de 256k tokens de Gemma 2.
  * **Migración a Entrenador Nativo Secuencial:** Se rediseñó `scripts/03_train_gemma_chess.py` adoptando una arquitectura limpia turno a turno (estilo *Vertex Core v9*), utilizando `DataCollatorForSeq2Seq` con enmascaramiento estricto de labels (`-100`) para entrenar únicamente la respuesta del modelo y omitir los tokens de usuario/sistema.
  * **Hardening de Memoria Turing (GTX 1660 Ti):** 
    * Longitud máxima ajustada a `MAX_SEQ_LENGTH = 384`.
    * Configuración de variables de entorno estables: `PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True,max_split_size_mb:32"`.
    * Carga del modelo base en `torch.float16` nativo con atención `attn_implementation="eager"`, evitando simulaciones `bf16` y garantizando estabilidad total en la propagación hacia atrás (`backward()`).

* **Estado Actual:** 
  * Gemma 2 (2B) arrancó su ciclo de entrenamiento de 80 steps de forma limpia y fluida, listo para empaquetarse junto a Qwen 2.5 (3B) en formato GGUF (`q4_k_m`) y ser desplegado en la Vertex Chess Arena.


---

### 📝 BITÁCORA DE PROYECTO: Vertex Chess Arena

**Fase:** Optimización del Árbitro Táctico y Benchmarking de Modelos LLM Locales

**Autor:** Denis Sanchez Leyva (CEO & AI Systems Architect, Vertex Coders LLC)

#### 1. Resumen Ejecutivo y Hallazgos del Experimento

* **Infraestructura:** HP Omen workstation (NVIDIA GTX 1660 Ti, 6 GB VRAM) ejecutando QLoRA mediante Unsloth y Ollama para inferencia local.
* **Entrenamiento:** Se completaron ciclos de ajuste fino en modelos de la familia Gemma 2 (2B) utilizando un *Grandmaster Blend* de 5,000 posiciones FEN. A pesar de escalar el entrenamiento hasta **625 pasos**, los adaptadores de Gemma mostraron menor destreza táctica y estructural frente a las líneas base de **Qwen 2.5 (entrenado con ~150 pasos)**.
* **Conclusión Arquitectónica:** Qwen demuestra mayor competencia nativa en el procesamiento de cadenas FEN densas, árboles de variantes SAN y estabilidad en el razonamiento formal bajo temperatura baja (`temperature=0.05`).

#### 2. Evolución del Motor Árbitro (`engine_arbiter.py`)

* **Superación del Bucle de Jaques Eternos:**
* Se implementó el registro de jaques consecutivos sin captura (`self.consecutive_checks`) aplicando una penalización severa (`-280 pts` por iteración a partir del segundo jaque consecutivo) para erradicar las series de más de 40 jaques con la Dama.
* Se eliminó la exención de penalización por repetición en movimientos que daban jaque (`and not board.gives_check(mv)`), obligando al motor a priorizar la progresión de peones pasados y el acercamiento del Rey.


* **Blindaje de la Función Mop-Up (Finales Ganados):**
* Sincronización del umbral de activación (`_is_mop_up_mode` ajustado a ventaja $\ge 350$ pts con material enemigo $\le 100$ pts).
* Integración de la técnica de la **"Caja de la Dama + Marcha del Rey"** y detección de mate forzado en 2 jugadas (`2-ply checkmate lookahead`), permitiendo remates limpios con el Rey y la Dama en menos de 8 jugadas tras la coronación, sin ahogamientos (*stalemate*).


* **Filtros Tácticos de Seguridad (SEE y Legitimidad):**
* Corrección de la falsa detección de defensa del Rey (`can_legally_recapture`) utilizando movimientos legales reales de `python-chess` para evitar entregas de piezas en casillas controladas por el rival (ej. errores del tipo `56... Qg4+??`).
* Implementación del filtro SEE estricto (`bad_trade_penalty`) para prohibir cambios desfavorables (ej. regalar un Alfil o Caballo por un peón defendido).
* Incorporación de la **Regla de Simplificación de Grandes Maestros**: bonificación al bando ganador por forzar el cambio de piezas mayores/damas para simplificar la partida y entrar al final Mop-Up.


---

### [20-10-2026] — Auditoría del duelo: ¿por qué Qwen "siempre ganaba"?

**Pregunta:** Qwen 2.5 (3B) le ganaba a Gemma 2 (2B) a pesar de tener menos pasos de entrenamiento.

**Respuesta corta:** el duelo no medía a los modelos. Lo decidía el motor del árbitro, y el Qwen de Ollama prácticamente no tenía el fine-tune.

#### Hallazgos (medidos en la HP Omen, no supuestos)

1. **El árbitro jugaba por los modelos.** `_get_candidate_moves` corre alpha-beta de profundidad 2 + quiescencia y le ofrece al LLM solo hasta 4 jugadas a ≤180 cp de la mejor. Si la respuesta no se podía validar, se jugaba `candidate_moves[0]`, o sea, **la mejor jugada del motor**. Fallar se premiaba.
   - Duelo con colores invertidos (diagnostics/duel_both_colors.py): Qwen ganó las dos.
     - Qwen blancas 1-0 (45 jugadas): Qwen 14 fallbacks, jugó la top-1 del motor 25/45; Gemma 0 fallbacks, top-1 11/44.
     - Gemma blancas 0-1 (78 jugadas): Qwen 16 fallbacks; Gemma 1 fallback.
   - En las partidas de Denis en la web del mismo día quedó 1-1 (Gemma con negras mató con 47...Qbg1#): con el árbitro dentro, el resultado es ruido del motor.
2. **`vertexqwen` se comportaba como Qwen base.** Sobre 40 posiciones del propio dataset con el prompt exacto de entrenamiento (incluso en modo raw ChatML): Qwen 0/40 en formato `Best move:` y 2/40 aciertos; Gemma 40/40 en formato y 9/40 aciertos. **Gemma era el modelo mejor entrenado.**
   - Se exportó `models/qwen_chess_adapter` = corrida vieja de **80 pasos** (r=8, lr pico 5e-5) sobre el dataset viejo de **3,000** filas (epoch 0.213 en el paso 80). La V2 de 250 pasos (r=16, `models/adapters/qwen_chess_lora`) nunca se exportó.
   - `SFTTrainer` sin máscara: la pérdida incluía system + FEN + lista de legales; la respuesta es ~5% de los tokens. Gemma sí enmascaraba con `-100`.
   - Delta LoRA muy pequeño (media |B| ≈ 0.0005) y luego cuantizado a q4_k_m.
   - Conclusión: **no fue "mismo dataset, menos pasos"**: fue otro dataset, otra pérdida y un adaptador casi invisible.
3. **`_evaluate_move` era código muerto.** Anti-jaque perpetuo, mop-up, SEE, simplificación y la penalización por repetición no se llamaban desde ningún sitio. Por eso aparecían bucles `Ra7+ Ra8+` y `Nf8+ Nd7+`.
4. **Sesgos del montaje:** `match_runner` siempre ponía a Qwen con blancas; temperatura 0.05 → partidas casi idénticas; no se cobraban tablas por triple repetición (`is_game_over()` sin `claim_draw`).
5. **Prompt de arena distinto al de entrenamiento:** otro system prompt, línea extra "Side to move" y solo 4 candidatas.
6. **Parser indulgente:** `parse_san` aceptaba "Bxf7" sin captura y el escaneo de prosa tomaba cualquier token con forma de jugada → "clean hits" inflados.

#### Cambios aplicados (V3)

- `scripts/02_train_qwen_chess.py` → **Qwen V3, espejo exacto de Gemma**: mismo dataset (5,000), mismo `Trainer` + `DataCollatorForSeq2Seq`, máscara `-100` sobre el prompt (solo aprende `Best move: ... <|im_end|>`), r=8, alpha=16, lr=5e-5, warmup 15, cosine, 1 época (625 pasos), batch efectivo 8, fp16, eager, seed 42. Checkpoint cada 125 pasos con reanudación automática. La V2 quedó en `02_train_qwen_chess_v2_legacy.py`.
- `arena/engine_arbiter.py`: prompt idéntico al del dataset; modo `pure` (todas las legales) y `arbiter` (top-4); fallback aleatorio por defecto; parser estricto; filtro anti-repetición; `_evaluate_move` conectado para ordenar jugadas en finales mop-up. Copia previa: `engine_arbiter_pre_v3_bak.py`.
- `arena/api_server.py` + `index.html`: selector de modo (Pure/Arbiter) y de versión de Qwen (v3/legacy).
- `arena/match_runner.py`: torneo de N partidas alternando colores, `claim_draw`, resumen en `logs/arena_results.jsonl`.
- `scripts/05_export_both_gguf.py`: exporta solo Qwen V3 → `vertex-chess-qwen-v3-q4_k_m.gguf`; Modelfiles con `TEMPLATE` y `stop` explícitos. El GGUF de Gemma no se toca.
- `arena/test_arbiter_v3.py`: 14 tests (parser, fallback, prompt = dataset, modos, anti-repetición, mate KQ vs K) — 14/14 OK.
- `diagnostics/`: `probe_bias.py` (formato y aciertos por modelo) y `duel_both_colors.py`.

#### Estado

- Entrenamiento Qwen V3 lanzado el 20-10-2026 ~03:10 (Miami). ~80 s/paso en la GTX 1660 Ti (sin tensor cores) → ~14 h para 625 pasos. Log: `logs/train_qwen_v3.log`.
- Pendiente: exportar V3, `ollama create vertexqwen-v3`, correr `probe_bias.py` y torneo `--mode pure` de 10 partidas.
- Limitación conocida: no hay set de evaluación separado; los aciertos de `probe_bias.py` son sobre posiciones de entrenamiento. La prueba real es el torneo en modo puro.

### [20-10-2026] — App web de torneos (Angular) y API V3

**Pedido de Denis:** reemplazar la página temporal por una app profesional en Angular 19+ standalone, con reloj y torneos en distintos ritmos (bullet, blitz, rápidas, clásicas).

**Decisiones**
- **Angular 21** (standalone, signals, zoneless) en `frontend/`. Angular 22 pide Node ≥ 24.15 y la HP Omen tiene Node 24.13.1 / npm 11.19.
- Tablero **cm-chessboard** (MIT) con piezas **Cburnett** (CC BY-SA 3.0, atribuidas en el pie). Se descartó Chessground (GPL) y las piezas Staunty (no comerciales).
- Reglas con **chess.js**. Tailwind 4 e iconos Lucide, siguiendo el design system del Plan Maestro (oscuro, glass, cian → violeta).
- El reloj de la IA corre durante toda la petición: latencia de Ollama + búsqueda del árbitro. En bullet la velocidad del modelo forma parte del resultado.
- Bandera según FIDE 6.9: si el rival no tiene material para dar mate, son tablas.
- Torneos: match con colores alternos, todos contra todos e ida y vuelta, con tablas de Berger y balance de colores ±1. Clasificación: puntos → Sonneborn-Berger → victorias.
- Nuevo jugador **"Motor del árbitro"** (modo `engine`): alpha-beta sin LLM, como línea base.

**API V3 (`arena/api_server.py`)**
- `GET /api/players`
- `POST /api/ai-move` con modos `pure | arbiter | engine`, un árbitro por partida (`game_id`) y 503 si Ollama no responde.
- `GET/POST /api/games` (`logs/arena_games.jsonl` + PGN).
- `GET/PUT /api/tournaments` (`logs/tournaments/`).
- Errores JSON uniformes, CORS por variable de entorno, sirve `frontend/dist` y deja la página vieja en `/legacy`.
- Copia previa: `api_server_pre_app_bak.py`.

**Verificación (en la nube, con un Ollama simulado)**
- 18 tests del frontend (reloj, Berger 2–8 jugadores, clasificación, partida) y 8 de la API.
- Recorrido con Playwright: partida IA vs IA ½+0 terminada por triple repetición; humano vs IA 5+3 (tras 1.e4 el reloj marcó 5:02 por el incremento); match de 2 partidas; round robin de 3 con el motor; historial con visor; vista de móvil.
- Pendiente: probar con los modelos reales cuando termine el entrenamiento de Qwen V3.


#### [20-10-2026 04:25] Primera prueba real de la app
- **Reloj congelado en 3:00:** el traductor de Chrome estaba traduciendo la página (la barra decía "Sand", "Departure", "Spin"). Reemplaza los nodos de texto y Angular deja de actualizarlos. El PGN muestra que los relojes sí corrían (Qwen llegó a 2:01). Arreglo: `translate="no"` y `<meta name="google" content="notranslate">` en `index.html`; recompilado.
- **Juegan mal en modo puro:** es lo esperado y es el dato honesto.
  - Qwen legacy: **1 % de respuestas válidas**; casi todas sus jugadas fueron al azar.
  - Gemma: 97 % válidas, pero no sabe rematar. Con material de sobra se quedó paseando el rey (Kh6–Kg7).
  - Sin el árbitro, el nivel real de los modelos queda a la vista.
- Jugar con Ollama mientras se entrena frena el entrenamiento: pasó de ~78 s/paso a ~145 s/paso.

#### [20-10-2026 04:40] Libro
- Título elegido: **"Jaque al modelo: afiné dos IAs para jugar ajedrez y descubrí que el árbitro jugaba por ellas"**.
- Índice de 13 capítulos en `libro/00_indice.md`. Los capítulos 11 y 12 esperan los resultados de Qwen V3.

### [20-10-2026 17:15] Qwen V3 terminado: resultados del duelo justo

**Entrenamiento**
- 625/625 pasos en 13 h 42 min, a ~79 s/paso; subió a ~145 s/paso mientras se usó Ollama al mismo tiempo.
- Pérdida solo sobre la respuesta: 4.2 → 0.23 (media 0.36).
- Adaptador en `models/qwen_chess_adapter_v3`. GGUF `models/gguf/vertex-chess-qwen-v3-q4_k_m.gguf`, registrado como `vertexqwen-v3`.

**Diagnóstico** (`probe_bias.py`, las mismas 40 posiciones del dataset, parser estricto)

| Modelo | Formato `Best move:` | Acierta la jugada del dataset |
|---|---|---|
| vertexqwen (legacy, 80 pasos) | 0/40 | 0/40 |
| **vertexqwen-v3** | **39/40** | **4/40** |
| **vertexgemma** | **40/40** | **9/40** |

El fine-tune de Qwen ahora sí funciona (formato correcto). Aun así, Gemma acierta el doble de jugadas con la misma receta.

**Torneo modo puro** (`match_runner.py --games 10 --mode pure`, colores alternos)
- **Gemma 5.5 – 4.5 Qwen V3.** Una sola partida decisiva: Gemma con negras dio mate en 28 jugadas (partida 7). Las otras 9 fueron tablas por triple repetición.
- Jugadas válidas: Gemma 99.2 % (241/243), Qwen V3 95.5 % (233/244).
- Las partidas 1, 5 y 9 fueron **idénticas** (repetición en 9 plies). Con temperatura 0.05 y sin aperturas variadas, los modelos repiten la misma partida.

**Match modo árbitro** (`--games 4 --mode arbiter`, fallback aleatorio)
- Qwen V3 2.5 – 1.5 Gemma. Las blancas ganaron las 3 partidas decisivas.
- Con el motor delante, el resultado lo decide sobre todo el color, no el modelo.

**Conclusiones para el libro (capítulo 11)**
1. Con entrenamiento idéntico, **Gemma 2 (2B) es un poco mejor modelo de ajedrez que Qwen 2.5 (3B)**: más aciertos, más respuestas válidas y la única victoria en modo puro. El "Qwen siempre gana" de la V2 era un artefacto del árbitro.
2. Ninguno de los dos sabe ganar partidas: casi todo termina en repeticiones. Aprendieron formato y algo de táctica, pero no planes.
3. Próximos pasos posibles:
   - Aperturas variadas: arrancar desde 2–4 jugadas de libro al azar, como se hace al probar motores.
   - Algo de temperatura en las respuestas.
   - Datos de finales y mates.
   - Más pasos o un modelo más grande.
