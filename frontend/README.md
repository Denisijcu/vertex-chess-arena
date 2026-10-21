# Vertex Chess Arena — App web (Angular)

App de torneos con reloj para la arena Qwen vs Gemma. Angular 21 standalone con signals y zoneless,
Tailwind 4, cm-chessboard (tablero) y chess.js (reglas).

## Qué trae

- **Partida libre**: tú contra la IA o IA contra IA. Eliges color o lo dejas al azar.
- **Ritmos**: ½+0, 1+0, 2+1 (bullet) · 3+0, 3+2, 5+0, 5+3 (blitz) · 10+0, 10+5, 15+10 (rápidas) ·
  30+0, 30+20 (clásicas) · personalizado. Reloj Fischer con incremento y décimas por debajo de 20 s.
- **Reglas de cierre FIDE**: mate, ahogado, material insuficiente, triple repetición, 50 jugadas,
  bandera. Si cae la bandera pero el rival no tiene material para dar mate, son tablas.
- **Modos de la IA**:
  - **LLM puro**: elige entre todas las jugadas legales.
  - **LLM + árbitro**: el motor filtra 4 candidatas.
  - **Motor**: solo alpha-beta, como línea base.
- **Torneos**: match a N partidas con colores alternos, todos contra todos e ida y vuelta (tablas de
  Berger). Clasificación con desempate Sonneborn-Berger, tabla cruzada, % de respuestas válidas,
  tiempo medio por jugada y derrotas por tiempo. El torneo sigue jugando aunque cambies de pantalla.
- **Historial**: todas las partidas con visor jugada a jugada (teclas ← →) y descarga PGN con
  `[%clk]` y `[%emt]`.

## Requisitos

- Node.js **20.19+, 22.12+ o 24+**. Compruébalo con `node -v`.
- La API de la arena corriendo en el puerto 8000 (`arena/api_server.py`).
- Ollama con los modelos creados (`vertexqwen-v3`, `vertexgemma`, `vertexqwen`). El jugador
  "Motor del árbitro" funciona aunque Ollama esté apagado.

## Desarrollo (dos terminales)

Antes de arrancar, revisa que los puertos estén libres:
```powershell
netstat -ano | findstr ":8000 :4200"
```
Si el 8000 está ocupado por una API vieja, ciérrala con Ctrl+C en su terminal.

```powershell
# Terminal 1 — desde E:\vertex-chess-arena\arena
..\venv\Scripts\python.exe -m uvicorn api_server:app --host 127.0.0.1 --port 8000

# Terminal 2 — desde E:\vertex-chess-arena\frontend
npm ci
npm start
```
Abre http://localhost:4200. `ng serve` manda `/api` y `/health` al puerto 8000 (`proxy.conf.json`).

## Producción local (un solo puerto)

```powershell
# Desde E:\vertex-chess-arena\frontend
npm run build

# Desde E:\vertex-chess-arena\arena
..\venv\Scripts\python.exe -m uvicorn api_server:app --host 127.0.0.1 --port 8000
```
Abre http://127.0.0.1:8000. FastAPI sirve `frontend/dist/vertex-chess-arena/browser` si existe.
La página vieja sigue en `/legacy`.

## Tests

```powershell
# Desde E:\vertex-chess-arena\frontend  (relojes, Berger, clasificación, partida)
npm test -- --watch=false

# Desde E:\vertex-chess-arena\arena  (API; no necesita Ollama)
..\venv\Scripts\python.exe -m pip install pytest httpx
..\venv\Scripts\python.exe -m pytest -q tests
```

## Estructura

```text
src/app/
├── core/
│   ├── models.ts                  tipos compartidos
│   ├── time-controls.ts           ritmos, categorías y formato de reloj
│   ├── chess-clock.ts             reloj Fischer (performance.now)
│   ├── live-game.ts               partida en vivo: reglas, turnos de IA, bandera, PGN
│   ├── tournament-logic.ts        Berger, clasificación, Sonneborn-Berger, tabla cruzada
│   ├── tournament-runner.service.ts  corre torneos y los guarda en el backend
│   ├── game-session.service.ts    partida libre + revancha
│   ├── players.store.ts           jugadores disponibles (API /api/players)
│   └── api.service.ts             cliente HTTP con timeouts y errores tipados
├── shared/                        tablero, reloj, franja de jugador, lista de jugadas, selector de ritmo
└── features/                      lobby, partida, torneos (lista + detalle), historial
```

## Problemas frecuentes

- **"No hay conexión con la API"**: uvicorn no está corriendo en el 8000, o está corriendo la API
  vieja. Reinícialo con el comando de arriba.
- **"Ollama no respondió"**: abre Ollama y revisa `ollama list`. La partida se congela con los
  relojes parados; pulsa *Reintentar*.
- **`npm install` falla con `Cannot read properties of null (reading 'edgesOut')`**: es un bug de
  npm 10. Usa `npm ci`, que respeta el `package-lock.json` y no se topa con el bug.

## Licencias de terceros

- cm-chessboard: MIT.
- Piezas Cburnett (Wikimedia): CC BY-SA 3.0; la atribución está en el pie de la app.
- chess.js: BSD-2.
- Lucide: ISC.
