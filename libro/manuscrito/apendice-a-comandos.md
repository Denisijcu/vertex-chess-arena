# Apéndice A — Comandos, con su directorio

> Todos los comandos son de PowerShell en Windows y usan el entorno virtual del proyecto.
> Antes de cada bloque se indica **desde qué carpeta** se ejecuta.

## Entrenar

Desde `E:\vertex-chess-arena`:

```powershell
venv\Scripts\python.exe scripts\01_build_chess_dataset.py
venv\Scripts\python.exe scripts\01b_audit_chess_dataset.py
venv\Scripts\python.exe scripts\02_train_qwen_chess.py
venv\Scripts\python.exe scripts\03_train_gemma_chess.py
```

El de Qwen V3 guarda un *checkpoint* cada 125 pasos: si se interrumpe, el mismo comando lo
reanuda. El de Gemma no guarda puntos intermedios (capítulo 4).

## Exportar y registrar en Ollama

Desde `E:\vertex-chess-arena`:

```powershell
venv\Scripts\python.exe scripts\05_export_both_gguf.py
```

Desde `E:\vertex-chess-arena\models\gguf`:

```powershell
ollama create vertexqwen-v3 -f Modelfile.qwen-v3
ollama create vertexgemma -f Modelfile.gemma
ollama list
```

Si Ollama no responde (en el navegador, `http://127.0.0.1:11434` debe decir *"Ollama is
running"*), ciérralo desde la bandeja del sistema y, desde cualquier carpeta:

```powershell
ollama serve
```

## Tests y diagnóstico

Desde `E:\vertex-chess-arena\arena`:

```powershell
..\venv\Scripts\python.exe -m unittest -v test_arbiter_v3.py
..\venv\Scripts\python.exe -m pytest tests -q
..\venv\Scripts\python.exe ..\diagnostics\probe_bias.py 40 vertexqwen-v3 vertexgemma vertexqwen
```

## Partidas por consola

Desde `E:\vertex-chess-arena\arena`:

```powershell
..\venv\Scripts\python.exe match_runner.py --games 10 --mode pure
..\venv\Scripts\python.exe match_runner.py --games 4 --mode arbiter
```

## La app de torneos

Desde `E:\vertex-chess-arena\frontend`:

```powershell
npm ci
npm run build
npm test
```

Desde `E:\vertex-chess-arena\arena`:

```powershell
..\venv\Scripts\python.exe -m uvicorn api_server:app --host 127.0.0.1 --port 8000
```

Abre `http://127.0.0.1:8000`. La página antigua sigue en `/legacy`.
