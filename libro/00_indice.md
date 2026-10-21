# Jaque al modelo
## Afiné dos IAs para jugar ajedrez y descubrí que el árbitro jugaba por ellas

**Autor:** Denis Sanchez Leyva — Vertex Coders LLC (Miami, FL)
**Estado:** índice aprobado el 20-10-2026. Fuente principal: `logs/bitacora.md`.

## Tabla de contenido (borrador)

1. **La idea:** dos modelos, un dataset, un duelo.
2. **El laboratorio:** una GTX 1660 Ti de 6 GB, el disco E: aislado y por qué Turing complica el fp16.
3. **El dataset:** 5,000 posiciones de Lichess (evaluaciones, puzzles y SFT), filtradas y auditadas con python-chess.
4. **Afinando a Gemma 2 (2B):** la odisea de la VRAM, la pérdida fusionada de Unsloth y el entrenamiento por turnos con máscara -100.
5. **Afinando a Qwen 2.5 (3B):** la versión de 80 pasos que casi no aprendió nada.
6. **Del adaptador a Ollama:** GGUF q4_k_m, Modelfiles y plantillas de chat.
7. **El árbitro:** alpha-beta, quiescencia, SEE, mop-up… y por qué un LLM necesita niñera en ajedrez.
8. **"Qwen siempre gana":** la auditoría. El fallback que premiaba fallar, el adaptador equivocado, el código muerto y el parser indulgente.
9. **Un duelo justo:** el entrenamiento espejo, el modo puro y el fallback aleatorio.
10. **La arena profesional:** Angular, relojes Fischer, reglas FIDE, torneos con Berger y Sonneborn-Berger.
11. **La verdad del tablero:** Qwen V3 contra Gemma en modo puro. *(Pendiente: se escribe con los resultados reales.)*
12. **Lecciones para quien afina modelos:** medir al modelo y no al sistema.
13. **Publicarlo sin gastar:** Hugging Face con ZeroGPU y Netlify.

**Apéndices:** comandos con su directorio, hiperparámetros de ambos modelos y PGN de las partidas clave.
