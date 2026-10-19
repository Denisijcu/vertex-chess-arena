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

  Aquí tienes el resumen técnico estructurado y directo para actualizar tu bitácora de **Vertex Coders LLC** sobre los avances en la *Vertex Chess Arena*:

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



