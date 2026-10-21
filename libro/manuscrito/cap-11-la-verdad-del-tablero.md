# Capítulo 11 — La verdad del tablero

> Borrador. Fuente: diagnostics/tourney_pure_v3.txt, logs/tournaments/4bwm13pspa.json y
> logs/bitacora.md (2026-10-20).
> Todas las cifras salen de esos archivos.

## Primero, el duelo puro

Con el árbitro honesto y Qwen reentrenado, el primer examen fue un match de 10 partidas en
modo puro, colores alternos: **Gemma 5,5 – Qwen V3 4,5**. Pero la cifra engaña. Solo hubo
**una partida decisiva** (Gemma dio mate con negras); las otras nueve fueron tablas por
triple repetición, y las partidas 1, 5 y 9 fueron idénticas jugada por jugada. Gemma
contestó en formato válido el 99,2 % de las veces; Qwen V3, el 95,5 %.

Dos modelos que repiten la misma partida no están compitiendo: están recitando. Faltaba
ver qué pasaba en un torneo completo.

## La Copa Vertex Verano 2026

Después de todos los arreglos quedaba una prueba que ningún gráfico sustituye: un torneo de
verdad, con reloj, todos contra todos, y con el árbitro a la vista en vez de escondido.

## El formato

- **7 jugadores**, todos contra todos a una vuelta: **21 partidas** en 7 rondas.
- **Ritmo 2+1 Bronstein:** 2 minutos por bando; después de cada jugada se devuelve lo
  pensado, hasta 1 segundo. El reloj nunca sube.
- **Límite de 150 jugadas** (300 medias jugadas) y tablas por triple repetición.

Los jugadores no eran siete modelos, sino tres modelos en dos modos cada uno, más el motor:

| Jugador | Qué es |
|---|---|
| Qwen V3 puro | El Qwen reentrenado (cap. 9) eligiendo entre **todas** las jugadas legales |
| Qwen V3 + árbitro | El mismo modelo, eligiendo entre los **candidatos** que filtra el árbitro |
| Gemma puro | Gemma 2B entre todas las jugadas legales |
| Gemma + árbitro | Gemma 2B entre los candidatos del árbitro |
| Qwen legacy puro | El adaptador viejo de 80 pasos (cap. 5) |
| Qwen legacy + árbitro | El adaptador viejo con candidatos del árbitro |
| Motor del árbitro | La búsqueda alfa-beta del árbitro jugando sola, sin modelo |

Recuerda la regla honesta del capítulo 9: si un modelo contesta algo inválido, la jugada se
elige **al azar** entre sus opciones. Sin ayuda del motor.

## La clasificación

| # | Jugador | Puntos | Jugadas válidas |
|---|---|---|---|
| 1 | Motor del árbitro | **6 / 6** | — |
| 2 | Qwen V3 + árbitro | 4 | 95,3 % |
| 2 | Gemma + árbitro | 4 | 99,5 % |
| 2 | Qwen legacy + árbitro | 4 | **0,5 %** |
| 5 | Gemma puro | 1 | 97,8 % |
| 5 | Qwen V3 puro | 1 | 97,8 % |
| 5 | Qwen legacy puro | 1 | 3,2 % |

El torneo duró 41 minutos y medio. Hubo 18 mates y 3 tablas por triple repetición. Las
blancas ganaron 11 partidas y las negras 7. Nadie perdió por tiempo.

A mitad de la ronda 6, Ollama se cayó (la conexión se cortó en medio de una jugada de Qwen).
Se levantó a mano, se pulsó *Reintentar* y el torneo siguió sin perder nada: cada partida
terminada ya estaba guardada en el backend.

## Tres lecturas

### 1. Árbitro contra puro: 9 a 0

Hubo nueve partidas entre un jugador con árbitro y uno sin árbitro. **Las ganó todas el que
tenía árbitro.** No importó qué modelo había detrás de cada lado: Gemma con árbitro le ganó
a Gemma pura, Qwen V3 con árbitro le ganó a Qwen V3 puro, y el legacy con árbitro le ganó a
todos los puros.

### 2. El jugador que no jugó

El dato más importante del libro está en una fila de esa tabla. **Qwen legacy + árbitro**
hizo 193 jugadas y solo **una** salió de su respuesta. Las otras 192 fueron azar entre los
candidatos del árbitro. Y aun así sacó **4 puntos**, los mismos que los dos modelos que sí
aprendieron el formato. Le dio mate a Gemma con árbitro en 79 medias jugadas.

Dicho en claro: con el árbitro filtrando candidatos, **elegir al azar rinde igual que elegir
con un modelo afinado**. Los puntos los pone el filtro. Es exactamente lo que pasaba al
principio del experimento, cuando "Qwen siempre ganaba".

### 3. Sin árbitro, nadie sabe ganar

Las tres partidas entre jugadores puros terminaron en **tablas por triple repetición**.
Gemma pura y Qwen V3 puro contestan en el formato correcto casi siempre (97,8 % los dos),
pero no tienen plan: mueven una torre de ida y vuelta mientras el rival hace lo mismo. Saber
**decir** una jugada legal no es saber **jugar**.

Y entre los tres con árbitro salió un ciclo perfecto, como piedra, papel o tijera: el
legacy le ganó a Gemma, Gemma a Qwen V3 y Qwen V3 al legacy. Es lo que esperas cuando las
diferencias entre jugadores son ruido.

## Lo que dice y lo que no dice

Este torneo **no** dice que Qwen y Gemma sean iguales. En el sondeo de los capítulo 9,
sobre las mismas 40 posiciones, Gemma acertó la mejor jugada 9 veces y Qwen V3 4. Lo que el
torneo dice es más incómodo: **una arena con árbitro no puede medir esa diferencia**,
porque el árbitro la tapa. Para comparar modelos hay que mirar el modo puro y las métricas
por posición, no la clasificación con ayuda.

Tampoco es una muestra grande: una partida por emparejamiento. Para conclusiones finas haría
falta repetir con colores cambiados y muchas más partidas. Pero el 9 a 0 y la fila del
legacy no necesitan estadística fina para entenderse.

## Lo que te llevas de aquí

- Si tu sistema tiene un "ayudante" (un filtro, un *reranker*, un *fallback*), mide el
  sistema **con y sin** él, y añade un jugador que no haga nada para ver cuánto aporta solo.
- Un jugador al azar dentro de tu arena es la mejor línea base que existe. Si empata con tu
  modelo, el que juega es la arena.
- Formato correcto no es competencia. Mide las dos cosas por separado.
- Guarda cada partida al terminarla; los cortes van a pasar.

**Lo que viene:** en el capítulo 12, lo que aprendí y lo que haría distinto.
