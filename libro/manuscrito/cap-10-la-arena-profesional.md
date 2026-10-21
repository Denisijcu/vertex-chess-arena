# Capítulo 10 — La arena profesional

> Borrador. Fuente: frontend/ (Angular), arena/api_server.py (API V3) y la bitácora
> (19 y 20-10-2026).

La primera interfaz era una página HTML con un tablero y un botón. Servía para ver partidas,
no para un torneo. Para que otras personas pudieran jugar, y para que los resultados
tuvieran la seriedad de un torneo de verdad, hacía falta una aplicación con reloj,
calendario de rondas, clasificación y partidas descargables.

## La pila

| Pieza | Elección | Por qué |
|---|---|---|
| Frontend | **Angular 21.2**, componentes *standalone*, sin zone.js, con *signals* | Moderno y predecible |
| Estilos | Tailwind 4 | Rápido para un diseño oscuro y *responsive* |
| Tablero | `cm-chessboard` (MIT) | Ligero, accesible, sin dependencias pesadas |
| Piezas | Cburnett (CC BY-SA 3.0) | Las clásicas, con licencia que permite uso comercial |
| Reglas en el navegador | `chess.js` | Validar jugadas humanas y generar PGN |
| Backend | FastAPI, API V3 | Habla con Ollama y guarda partidas y torneos |

Dos decisiones de esa tabla vienen con historia:

- **¿Por qué Angular 21 y no 22?** Angular 22 pide una versión de Node más nueva que la que
  había en la máquina (24.13). Antes de elegir versión, se comprobó qué Node y qué npm había
  instalados. Actualizar Node por una versión mayor del framework no aportaba nada al
  proyecto.
- **¿Por qué Cburnett y no otras piezas más bonitas?** Algunas colecciones populares tienen
  licencias **no comerciales**. Si el libro y la app se venden o se publican, eso importa.

## El backend: una API pequeña y honesta

- `POST /api/ai-move` pide una jugada a un modelo en el modo indicado (`pure`, `arbiter` o
  `engine`) y devuelve, además de la jugada, si salió limpia o fue respaldo y cuánto tardó.
  Si Ollama no responde, devuelve **503** con un error claro; nunca inventa una jugada.
- `POST /api/games` guarda cada partida terminada en un JSONL y la añade al PGN histórico.
- `GET/PUT /api/tournaments/{id}` guarda el estado del torneo después de cada partida.

Esta última decisión salvó la Copa del capítulo 11: cuando Ollama se cayó en la ronda 6, no
se perdió nada.

## El reloj: la lección de chess.com

Primera versión: reloj **Fischer**, que suma un incremento fijo después de cada jugada. Es
el de casi todos los torneos online. Con humanos funciona. Con una IA que contesta en un
segundo, no: con 3+2, el modelo gasta un segundo y gana dos. **El reloj subía.**

Mi primera reacción fue explicar que eso es correcto según el reglamento. La respuesta de
Denis fue mejor: *"como en los campeonatos normales: el reloj baja, y si llega a cero
pierdes"*. Tenía razón en lo que importa: la experiencia que se espera de un reloj de
ajedrez es que baje.

La solución fue el reloj **Bronstein**: después de cada jugada se devuelve lo que pensaste,
**hasta** el valor del incremento. Si piensas 0,6 s con +1, recuperas 0,6 s. Nunca acabas
con más tiempo del que tenías al empezar la jugada:

```ts
rem[side] += Math.min(thinkMs, this.control.incMs);
```

El ritmo por defecto pasó a 3+0. Y cuando el reloj llega a cero aparece un cartel sobre el
tablero, como en chess.com: quién gana, por qué, y los botones de partida nueva y revancha.
Con una excepción del reglamento FIDE (artículo 6.9): si al que le queda tiempo no tiene
material para dar mate, la caída de bandera es **tablas**, no derrota.

## Dos fallos que no eran del código

- **"El reloj no camina, se queda en 3:00."** No era Angular. Era el **traductor
  automático de Chrome**: al traducir la página al español, reemplazaba los nodos de texto y
  Angular seguía actualizando nodos que ya no estaban en pantalla. Solución:
  `translate="no"` en el HTML y la meta `notranslate`.
- **"No se pudo crear el torneo."** El torneo sí se creaba. Lo que fallaba era la
  navegación: tras una actualización de la app, el navegador pedía un fragmento de JavaScript
  que ya no existía. Solución: separar *crear* de *navegar*, y recargar la página si falla la
  carga de un fragmento.

## Torneos

- **Formatos:** match a N partidas con colores alternos, todos contra todos y doble vuelta.
- **Emparejamientos:** tablas de **Berger**, el método clásico para todos contra todos,
  con un ajuste para equilibrar los colores de cada jugador.
- **Desempate:** **Sonneborn-Berger**, la suma de los puntos de los rivales a los que
  ganaste más la mitad de los de aquellos con los que hiciste tablas. Premia los resultados
  contra los fuertes.
- **Tabla cruzada** y **PGN del torneo** con los tiempos de reloj de cada jugada
  (`%clk`, `%emt`) y la cabecera `ClockMode "Bronstein"`.

## Móvil

En un teléfono de 390 px, la pantalla de partida medía 557 px de ancho. Los culpables
fueron tres clásicos de CSS Grid y Flexbox: hijos sin `min-width: 0`, un reloj demasiado
grande y columnas de tabla que no hacían falta en pantalla pequeña. Tras el arreglo, la app
cabe entera en un móvil, que era el objetivo: que cualquiera pudiera jugar desde el
teléfono.

## Lo que te llevas de aquí

- Comprueba las versiones instaladas antes de elegir las del framework.
- Revisa la licencia de cada recurso gráfico si vas a publicar.
- Un reloj correcto según el reglamento puede ser incorrecto para el usuario. Bronstein
  resuelve el caso de jugadores que responden en un segundo.
- Si algo "no se actualiza" en pantalla, sospecha también de las extensiones del navegador.
- Guarda el estado del torneo después de cada partida.
- Prueba en un móvil real (o en su ancho) desde el principio.

**Lo que viene:** en el capítulo 11, la verdad del tablero.
