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

#### [20-10-2026 20:55] Reloj al estilo de los torneos + video promo
- **Pedido de Denis:** el reloj debe bajar como en un torneo normal y, si llega a 0, se pierde y se cierra la partida (de referencia, una partida de "3 min" en chess.com).
- **Cambio:** el reloj pasó de Fischer (suma fija por jugada; con la IA respondiendo en ~1.5 s el reloj subía) a **Bronstein** (devuelve lo pensado hasta el tope; **nunca sube**). PGN con `[ClockMode "Bronstein"]`.
- Ritmo por defecto del lobby: **3+0**, solo baja. Al caer la bandera aparece un cartel sobre el tablero, como en chess.com ("Ganan las negras · Tiempo agotado", Nueva / Revancha).
- 19 tests del frontend en la HP Omen, uno nuevo: con Bronstein el reloj no sube en 50 jugadas rápidas.
- **Video promo:** `F:\vertex-videos\chess_arena.py`, escena `ChessArenaPromo`, ~61 s, con todas las cifras medidas. Render 1080p en `F:\vertex-videos\media\videos\chess_arena\1080p60\ChessArenaPromo.mp4`. El link de Hugging Face del cierre (`huggingface.co/Denisijcu`) está pendiente de confirmar cuando suba los modelos.

## 2026-10-20 — Copa Vertex Verano 2026, ronda 1 (todos contra todos, 7 jugadores, 2+1 Bronstein)

- Motor del árbitro 1-0 Qwen V3 + árbitro (mate, 109 medias jugadas).
- Gemma 2B puro 0-1 **Qwen legacy + árbitro** (mate, 38 medias jugadas).
- Qwen legacy puro 0-1 **Gemma 2B + árbitro** (mate, 44 medias jugadas).
- Dato para el libro: el Qwen **legacy** (0 % de jugadas válidas con árbitro; el adaptador viejo de 80 pasos) ganó por mate. No eligió ni una jugada: jugaron los candidatos del árbitro. Es la tesis del libro en una sola partida.
- Los tres que jugaron con árbitro ganaron o perdieron solo contra el motor; los dos "puros" perdieron los dos.
- Ronda 2 en curso: Qwen V3 puro vs Motor. Qwen V3 repite Rg1/Rh1 mientras la dama negra se come el flanco de rey. Relojes en 1:59 (Bronstein: con respuestas de ~0,6 s el reloj casi no se mueve, como debe ser).

## 2026-10-20 — Copa Vertex Verano 2026: resultado final (torneo 4bwm13pspa)

- 7 jugadores, todos contra todos, 21 partidas, 2+1 Bronstein. Duró 41,5 min (01:16→01:57 UTC). 18 mates, 3 tablas por triple repetición; blancas 11, negras 7. Ninguna caída de bandera.
- Corte a las 21:44: Ollama se cayó (WinError 10054/10061); Denis lo levantó y el torneo siguió desde la ronda 6 sin perder nada.
- **Clasificación:** Motor 6/6 · Qwen V3 + árbitro 4 · Gemma + árbitro 4 · Qwen legacy + árbitro 4 · Gemma puro 1 · Qwen V3 puro 1 · Qwen legacy puro 1.
- **Con árbitro vs sin árbitro: 9-0.** Todo jugador con árbitro le ganó a todo jugador puro.
- **Entre los tres con árbitro, un ciclo perfecto:** legacy le ganó a Gemma, Gemma a V3, V3 a legacy. Empate a 4.
- **Entre los puros:** las 3 partidas fueron tablas por triple repetición.
- **Jugadas válidas:** Gemma + árbitro 99,5 %, Qwen V3 + árbitro 95,3 %, Gemma puro 97,8 %, Qwen V3 puro 97,8 %, Qwen legacy puro 3,2 %, **Qwen legacy + árbitro 0,5 % (1 de 193)**.
- Conclusión para el libro: el legacy + árbitro sacó los mismos puntos que los modelos entrenados eligiendo 1 jugada de 193. Lo que da los puntos es el árbitro (el filtro de candidatos), no el modelo.

## 2026-10-20 — Libro "Jaque al modelo": manuscrito completo (borrador 1)

- `libro/manuscrito/`: 5 front, 13 capítulos, apéndices A (comandos con directorio), B (hiperparámetros) y C (3 partidas clave), conclusión y sobre el autor. ~12.200 palabras.
- Licencias verificadas en el Hub: Qwen2.5-3B-Instruct = **Qwen Research License (no comercial)**, requiere aviso y "Built with Qwen"; Gemma 2 2B = Gemma Terms of Use.
- ZeroGPU (docs HF): solo SDK Gradio + PyTorch (Ollama no corre ahí); la cuota la gasta el visitante (2 min sin cuenta, 5 gratis, 40 PRO).
- Pendiente: maquetar (build_pdf.py 6x9 / build_epub.py desde F:\vertex-lab\docs), portada, ficha KDP; tiempo de entrenamiento de Gemma (no hay log en disco).
- Dato de Denis: el entrenamiento de Gemma (625 pasos) tardó unas 11 h. Añadido al cap. 4 y al apéndice B. "Sobre el autor" aprobado tal cual.

## 2026-10-20 — Modelos publicados en Hugging Face

- `Denisijcu/vertexqwen`: GGUF legacy + V3, Modelfiles, LICENSE (Qwen Research, no comercial), NOTICE, ficha corregida (antes decía apache-2.0 y 150 pasos).
- `Denisijcu/vertexgemma`: GGUF (export del 18-oct, el de 625 pasos; mismo tamaño que el local), Modelfile, NOTICE (Gemma Terms of Use), ficha corregida (antes decía 80 pasos y "Unsloth QLoRA"). Commit 94401347.
- Fichas fuente en `hf_upload/`, scripts `upload_vertexqwen_card.py` y `upload_vertexgemma_card.py` (solo suben texto).
- El cierre del video (`huggingface.co/Denisijcu`) queda confirmado: el perfil lista los dos modelos.

## 2026-10-20 — Libro maquetado (borrador 1)

- Video subido a YouTube: https://youtu.be/2_t0ijTg1_M (enlazado en "Sobre el autor").
- `libro/Jaque-al-modelo-interior-6x9.pdf`: 57 páginas (KDP cuenta 58), pandoc + XeLaTeX, Source Serif 4 / Source Sans 3. Sin avisos de fuentes; un desborde de 0,15 pt.
- `libro/Jaque-al-modelo.epub`: EPUB 3 reflowable con portada.
- `libro/portada/`: arte generado por código (`make_art.py`: tablero en perspectiva, rey Staunton dibujado a mano, 4 casillas candidatas en ámbar), portada envolvente 12,381 × 9,25 in (lomo 0,131 in, sin texto: KDP lo exige desde 79 páginas) y portada eBook 1600×2560.
- `libro/kdp-ficha.md`: título, descripción HTML, 7 palabras clave, categorías, ficha técnica, precio sugerido (eBook 9,99 / paperback 19,99), checklist.
- Cap. 13 actualizado: modelos ya publicados en HF y la corrección de sus fichas.

## 2026-10-20 — Libro ampliado con el código completo (146 páginas)

- Pedido de Denis: 57 páginas era poco para 19,99. Se añaden los apéndices D–J con el código completo y una guía de lectura por archivo: datos (01, 01b), entrenamientos (03 Gemma, 02 Qwen V3, comparados), exportación (05), árbitro (engine_arbiter.py), arena y diagnósticos (match_runner, probe_bias, duel_both_colors), API (api_server.py) y reloj/torneos (chess-clock.ts, tournament-logic.ts). ~3.000 líneas con números de línea.
- Interior: 146 páginas. Portada regenerada: 12,579 × 9,25 in, lomo 0,329 in, ahora con texto en el lomo.
- Corrección encontrada al revisar el código: Gemma entrenó **sin checkpoints** (`save_strategy="no"`); solo Qwen V3 guarda cada 125 pasos. Arreglado en el cap. 4 y el apéndice A.
- `libro/gen_apendices_codigo.py` regenera los apéndices desde el código real si cambia algo.

## 2026-10-20 — Portada v2 (aprobada por Denis)

- Idea de Denis: cartel de gran pelea. Rey blanco (Qwen, luz cian) vs rey negro (Gemma, luz violeta), "QWEN 2.5 VS GEMMA 2", focos y público; detrás, la sombra gigante del árbitro en ámbar y sus 4 casillas candidatas. Título dorado en Anton, subtítulo y autor en Oswald (OFL).
- `libro/portada/make_cover_front.py` genera `frente.png`; `build_cover.py 146` arma paperback y eBook. EPUB regenerado con la portada nueva.

## 2026-10-20 — Libro enviado a KDP

- Kindle eBook (12,99 USD) y paperback (19,99 USD, Expanded Distribution activada) en revisión el 21-oct. Portada v2 en los dos.
- Pendiente: cuando salga el enlace de Amazon, correr `libro\publicar_enlace_amazon.py <url>` y hacer push del README.

## 2026-10-21 — Deploy público: Space de HF (ZeroGPU) + Netlify (preparado)

- `arena/engine_arbiter.py` V4: `request_model_move(..., chat_fn=None)`; Ollama queda como `_chat_ollama` por defecto y `build_messages` es estático. +2 tests (16 en total).
- `deploy/space/`: app Gradio 6.27 con `@spaces.GPU(duration=20)`; Qwen2.5-3B-Instruct + adaptadores v3 y legacy (PEFT, uno activo por jugada), unsloth/gemma-2-2b-it + adaptador; bf16, greedy, 48 tokens, repetition_penalty 1.15. Endpoints `/health`, `/players`, `/ai_move` (el motor no usa GPU). Probado en el contenedor con modelos simulados: endpoints, errores `CODIGO: mensaje` y partida completa desde la app.
- `deploy/publicar_space.py`: sube los adaptadores (`adapter-v3`, `adapter-legacy`, `adapter`), las fichas y el Space, y pide ZeroGPU.
- Frontend: configuración `netlify` (`npm run build:netlify`) que usa `@gradio/client` 2.7.1 contra el Space y guarda partidas y torneos en el navegador; la Copa Vertex Verano 2026 viene incluida (`public/showcase.json`, solo lectura). Avisos de cuota de GPU. `netlify.toml` en la raíz. 19 tests del frontend pasan; builds local y netlify OK.

## 2026-10-21 — Deploy público en vivo

- App: https://vertex-ai-chess.netlify.app (Netlify, build `netlify` desde GitHub).
- API: https://huggingface.co/spaces/Denisijcu/vertex-chess-arena (Gradio + ZeroGPU, `zero-a10g`, RUNNING).
- Error del primer arranque: `RuntimeError: No CUDA GPUs are available` al cargar los adaptadores. PEFT los cargaba directamente en "cuda" y en ZeroGPU no hay GPU real fuera de `@spaces.GPU`. Arreglo: `torch_device="cpu"` en `PeftModel.from_pretrained` y `load_adapter`, y luego `.to("cuda")` del modelo entero (ZeroGPU lo emula al arrancar).
- Denis jugando desde la app pública a las 08:25.
