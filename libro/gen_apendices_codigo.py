"""Genera los apéndices D–J con el código completo del proyecto (copiado de E:\\vertex-chess-arena)."""
from pathlib import Path

SRC = Path("codigo") if Path("codigo").exists() else Path(__file__).resolve().parent.parent  # en la máquina: E:\\vertex-chess-arena
MAN = Path(__file__).resolve().parent / "manuscrito"

def block(rel, lang):
    code = (SRC / rel).read_text(encoding="utf-8").rstrip("\n")
    fence = "````" if "```" in code else "```"
    return f"### `{rel}`\n\n{fence}{{.{lang} .numberLines}}\n{code}\n{fence}\n"

APX = [
 ("apendice-d-datos.md", "Apéndice D — El pipeline de datos", """
Estos dos scripts producen y verifican el dataset del capítulo 3. Se ejecutan desde
`E:\\vertex-chess-arena` con el entorno virtual del proyecto (apéndice A).

**Cómo leer `01_build_chess_dataset.py`.** Las primeras líneas redirigen todas las cachés de
Hugging Face al disco del proyecto *antes* de importar `datasets` (capítulo 2). Después hay una
función por fuente:

- `format_record` convierte una posición y su jugada en la conversación de tres mensajes. Aquí
  está la línea `legal_sans[:45]`, el recorte silencioso que descubrimos en el capítulo 3.
- `extract_lichess_evals` lee en *streaming* las evaluaciones de Lichess y se queda solo con
  posiciones decisivas.
- `extract_lichess_puzzles` aplica primero la jugada del rival (el formato de los *puzzles*
  guarda la posición anterior al error) y reserva la cuota de mates directos.
- `extract_sft_20k` completa con el conjunto curado.
- `main` junta las tres fuentes, baraja con semilla 42 y escribe el JSONL.

Todas comparten el conjunto `global_seen`, que evita repetir un FEN aunque venga de dos
fuentes distintas.

**Cómo leer `01b_audit_chess_dataset.py`.** Relee el archivo terminado y comprueba cuotas,
legalidad, formato de la respuesta y reparto por bando y fase. Es la auditoría que *sí*
existía; el capítulo 3 cuenta la que faltaba.
""", [("scripts/01_build_chess_dataset.py", "python"), ("scripts/01b_audit_chess_dataset.py", "python")]),

 ("apendice-e-entrenamiento.md", "Apéndice E — Los dos entrenamientos", """
Este es el corazón técnico del libro: dos scripts que entrenan dos modelos de familias
distintas **con la misma receta**, línea por línea, en una GPU de 6 GB. Compararlos uno al lado
del otro es la mejor forma de ver qué es receta (idéntico en los dos) y qué es adaptación a cada
arquitectura (lo único que cambia).

**Lo que es idéntico.** Las constantes del principio: `LORA_R = 8`, `LORA_ALPHA = 16`,
`LEARNING_RATE = 5e-5`, `WARMUP_STEPS = 15`, lote 1 × 8, `MAX_SEQ_LENGTH = 384`, una época,
semilla 42, `fp16`, atención `eager`, *gradient checkpointing* y los siete módulos LoRA.

**Lo que cambia, y por qué.**

- **La plantilla de chat.** Gemma no tiene rol de sistema: `to_chess_turns` pega el texto de
  sistema al principio del mensaje del usuario y llama `model` al turno del asistente. Qwen sí
  tiene rol de sistema y usa ChatML.
- **El enmascarado.** En Gemma, `encode_turns` codifica turno a turno y pone `-100` en todo lo
  que no es la respuesta del modelo. En Qwen, `encode_example` pide el texto del prompt con
  `apply_chat_template(..., tokenize=False, add_generation_prompt=True)`, lo codifica aparte
  (capítulo 9) y añade `<|im_end|>` a la respuesta para que el modelo aprenda a cerrar su turno.
- **El modelo base**, cada uno en su versión de 4 bits.
- **Los puntos de guardado.** Gemma entrenó sin ninguno (`save_strategy="no"`). Qwen V3 guarda
  cada 125 pasos y reanuda solo desde el último (`resume_from_checkpoint`), la lección del
  capítulo 4.

Los dos usan `DataCollatorForSeq2Seq`, que rellena las secuencias de un lote y respeta las
etiquetas `-100`. Gemma tardó unas 11 horas; Qwen V3, 13 h 42 min.
""", [("scripts/03_train_gemma_chess.py", "python"), ("scripts/02_train_qwen_chess.py", "python")]),

 ("apendice-f-exportacion.md", "Apéndice F — Exportación a GGUF y Modelfiles", """
`export_contender` fusiona el adaptador con su modelo base y cuantiza a `q4_k_m` con Unsloth.
`write_clean_modelfiles` escribe los Modelfiles con la plantilla de chat **explícita** y los
`stop` de cada familia (capítulo 6).

Fíjate en el bloque final de `main`: solo exporta un GGUF si todavía no existe. Así, al
reexportar Qwen V3 no se tocó el GGUF de Gemma con el que ya se habían jugado partidas, y las
cifras del libro siguen correspondiendo a los archivos publicados.
""", [("scripts/05_export_both_gguf.py", "python")]),

 ("apendice-g-arbitro.md", "Apéndice G — El árbitro", """
El archivo más largo del proyecto y el protagonista del libro. Para no perderse, conviene
leerlo en este orden:

1. **Las constantes del principio**: `SYSTEM_PROMPT` (el del entrenamiento), `LEGACY_SYSTEM_PROMPT`
   (el que usaba la arena antes de la auditoría), los modos `arbiter`/`pure` y los respaldos
   `random`/`engine`. El tercer modo de la app, el motor jugando solo, lo resuelve la API
   (apéndice I) llamando directamente a la búsqueda.
2. **`request_model_move`**, al final: es la puerta de entrada. Pide las opciones, construye el
   prompt, llama a Ollama, interpreta la respuesta y, si falla, aplica el respaldo.
3. **`get_options`**: en modo `pure` devuelve todas las jugadas legales; en modo `arbiter`, los
   candidatos.
4. **`_get_candidate_moves`**: mate en una, búsqueda a profundidad 2, hasta 4 jugadas a menos de
   180 centipeones de la mejor, orden de *mop-up* en finales ganados y filtro anti-repetición
   (capítulo 7).
5. **`parse_llm_move`**: el parser estricto V3. Su *docstring* explica qué dejó de aceptar.
6. **`_fallback_move`**: tres líneas que resumen la auditoría del capítulo 8. Con `random`, fallar
   no se premia.
7. **La búsqueda**: `_search_root_moves`, `_search_minimax` (alfa-beta) y `_quiescence`.
8. **La evaluación**: `_static_material_and_board_eval`, `_evaluate_move` y las ayudas de
   finales (`_mop_up_endgame_bonus`, `_is_mop_up_mode`).

Todo lo que está por encima de `get_options` es *el motor*: lo que juega. Todo lo que está por
debajo es *la interfaz con el modelo*: lo que mide.
""", [("arena/engine_arbiter.py", "python")]),

 ("apendice-h-arena.md", "Apéndice H — La arena por consola y los diagnósticos", """
Tres scripts cortos que hicieron más por este libro que cualquier otro:

- **`match_runner.py`** juega partidas entre dos modelos, **alternando colores**, reclamando la
  triple repetición (`claim_draw`) y guardando cada resultado en `logs/arena_results.jsonl`. El
  modo (`--mode pure` o `--mode arbiter`) es un argumento, no una constante escondida.
- **`probe_bias.py`** es el sondeo del capítulo 9: las mismas posiciones del dataset para cada
  modelo, con su prompt de entrenamiento exacto, y dos contadores (formato y acierto). Sin
  tablero, sin árbitro, sin respaldo.
- **`duel_both_colors.py`** es el duelo del capítulo 8: dos partidas con el árbitro original y
  colores cambiados. Fue el que produjo la tabla que cambió la historia.
""", [("arena/match_runner.py", "python"), ("diagnostics/probe_bias.py", "python"),
      ("diagnostics/duel_both_colors.py", "python")]),

 ("apendice-i-api.md", "Apéndice I — La API del backend", """
`api_server.py` es la API V3 con FastAPI que usa la aplicación de torneos (capítulo 10). Se
configura con variables de entorno (`OLLAMA_URL`, `ALLOWED_ORIGINS`, `ARENA_DATA_DIR`,
`FRONTEND_DIST`), lo que la deja lista para desplegarse fuera de la máquina de desarrollo.

Tres detalles para leerla:

- **`arbiter_for`** guarda un árbitro por partida (`game_id`), porque el árbitro recuerda las
  posiciones recientes para su filtro anti-repetición. Dos partidas simultáneas no se mezclan.
- **`ai_move`** devuelve, además de la jugada, si salió limpia o fue respaldo, las opciones
  ofrecidas y el tiempo de respuesta. Si Ollama no contesta, responde **503** con el código
  `LLM_UNAVAILABLE`: nunca inventa una jugada.
- **Los errores** salen siempre con la misma forma, `{"error": {"code", "message"}}`, gracias a
  los tres manejadores de excepciones del principio.

Al final, la ruta comodín sirve la aplicación Angular compilada, y `/legacy` la página antigua.
""", [("arena/api_server.py", "python")]),

 ("apendice-j-reloj-torneos.md", "Apéndice J — El reloj y la lógica de torneos", """
Dos archivos TypeScript de la aplicación Angular, sin dependencias de interfaz: se pueden
probar y reutilizar por separado.

**`chess-clock.ts`** es el reloj Bronstein del capítulo 10. El estado vive en *signals* de
Angular. La línea clave está en `press`: al terminar una jugada se devuelve lo pensado, **hasta**
el incremento, así que el reloj nunca sube. `tick` detecta la caída de bandera.

**`tournament-logic.ts`** contiene todo el reglamento de los torneos:

- `bergerRounds`: el calendario de todos contra todos con el método del círculo de Berger, con
  un "descanso" ficticio si el número de jugadores es impar.
- `buildPairings`: convierte las rondas en partidas y reparte los colores de forma voraz para
  que cada jugador tenga blancas y negras equilibradas.
- `standings`: puntos, partidas, victorias, tablas, derrotas, desempate **Sonneborn-Berger**,
  porcentaje de jugadas válidas, tiempo medio y caídas de bandera.
- `crosstable`: la tabla cruzada.
""", [("frontend/src/app/core/chess-clock.ts", "typescript"),
      ("frontend/src/app/core/tournament-logic.ts", "typescript")]),
]

for fn, title, intro, files in APX:
    parts = [f"# {title}\n", intro.strip() + "\n"] + [block(r, l) for r, l in files]
    (MAN / fn).write_text("\n".join(parts), encoding="utf-8")
    print(fn)
