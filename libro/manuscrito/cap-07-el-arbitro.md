# Capítulo 7 — El árbitro

> Borrador. Fuente: arena/engine_arbiter.py (V3) y su versión anterior
> arena/engine_arbiter_pre_v3_bak.py.

Un modelo de 3B que elige jugadas por instinto pierde contra cualquiera que sepa contar
material. La primera semana de partidas lo dejó claro: regalaba piezas, daba jaques sin
sentido y, en finales ganados, paseaba la dama en círculos hasta tablas. La respuesta fue
ponerle una niñera. La llamé **el árbitro**.

## Qué hace el árbitro

El árbitro es una clase de Python, `ChessArbiter`, de casi mil líneas. Tiene dos trabajos
que conviene separar desde ya, porque toda la historia del libro depende de esa separación:

1. **Llevar la partida:** comprobar que la jugada es legal, pasar el turno, detectar mate,
   tablas, repetición. Es trabajo de notario. Lo hace `python-chess` y no tiene discusión.
2. **Elegir candidatos:** antes de preguntarle al modelo, reducir la lista de jugadas a unas
   pocas "razonables". Esto ya no es notaría. Esto es **jugar**.

## Cómo elige los candidatos

El método `_get_candidate_moves` sigue cuatro pasos:

1. **Si hay mate en una, solo ofrece esa.** El modelo no tiene nada que decidir.
2. **Busca con alfa-beta a profundidad 2**: mira cada jugada propia y la mejor respuesta del
   rival, y puntúa la posición resultante.
3. **Extiende con quiescencia**: en las posiciones con capturas o jaques pendientes sigue
   mirando hasta 4 medias jugadas más, para no evaluar una posición en mitad de un cambio de
   piezas.
4. **Se queda con hasta 4 jugadas** cuya puntuación esté a menos de 180 centipeones de la
   mejor.

La función de evaluación suma material, actividad de piezas y seguridad del rey, y añade
reglas aprendidas a golpes en las partidas de prueba:

- **Filtro de intercambios (SEE):** penaliza dar un alfil o un caballo por un peón defendido.
- **Anti-jaques eternos:** a partir del segundo jaque seguido sin captura, cada jaque resta
  280 puntos.
- **Mop-up (rematar finales ganados):** con ventaja de 350 o más y el rival casi sin
  material, premia encerrar al rey en una caja con la dama y acercar el rey propio, y mira el
  mate en 2.
- **Simplificar cuando vas ganando:** bonificación por cambiar piezas mayores.

## El modelo dentro de una jaula

Piensa en lo que significa ese cuarto paso. El modelo ya no elige entre 30 o 40 jugadas
legales. Elige entre **cuatro**, todas aprobadas por una búsqueda que no regala material y
que nunca se pierde un mate en una. Para un jugador de ajedrez es como jugar con un
entrenador que te tapa todas las jugadas malas y te deja escoger entre las buenas.

Y hay un detalle que ningún prompt dice: en la versión original, el prompt seguía llamando
a esas cuatro jugadas `Legal moves (SAN)`. El modelo creía que tenía todo el tablero delante
y en realidad le daban un menú.

## Lo que el árbitro hacía cuando el modelo fallaba

Si el modelo contestaba algo que no se podía leer, el árbitro necesitaba una jugada de
todas formas. La versión original lo resolvía así:

```python
# La respuesta no se pudo validar: devolvemos un movimiento legal de respaldo,
# pero NO fingimos que Gemma acertó.
return candidate_moves[0], False
```

`candidate_moves[0]` es la primera de la lista. Y la lista viene ordenada por la búsqueda.
Es decir: **cuando el modelo fallaba, jugaba la mejor jugada del motor.**

El comentario es honesto: marca la jugada como no acertada. Pero en el tablero no queda
ninguna marca. La jugada del motor cuenta igual para ganar.

Guarda esta línea. Es la protagonista del capítulo 8.

## Lo que te llevas de aquí

- Separa en tu código lo que es **verificar** (reglas, legalidad) de lo que es **decidir**
  (filtrar, ordenar, elegir). Lo primero no cambia el resultado; lo segundo sí.
- Un filtro de candidatos es un jugador. Si lo pones delante de tu modelo, mides a los dos.
- Nombra las cosas por lo que son. Una lista filtrada no es `Legal moves`.
- Revisa qué hace tu sistema **cuando el modelo falla**. Ahí suelen esconderse las ayudas.

**Lo que viene:** en el capítulo 8, la auditoría. Por qué Qwen siempre ganaba.
