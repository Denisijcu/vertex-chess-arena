import subprocess
import json

# Definir la solicitud JSON-RPC para llamar a la herramienta get_ai_chess_move
request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "get_ai_chess_move",
        "arguments": {
            "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            "model_name": "vertexqwen"
        }
    }
}

# Ruta a tu entorno virtual y al servidor MCP
python_path = r"E:\vertex-chess-arena\venv\Scripts\python.exe"
script_path = r"E:\vertex-chess-arena\mcp_server\vertex_chess_mcp.py"

print(">>> Iniciando prueba de comunicación con el Servidor MCP...")

# Lanzar el proceso MCP
process = subprocess.Popen(
    [python_path, script_path],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Inicializar protocolo MCP (Handshake obligatorio)
init_request = {
    "jsonrpc": "2.0",
    "id": 0,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test-cli", "version": "1.0"}
    }
}

# Enviar inicialización y la llamada a la herramienta
payload = json.dumps(init_request) + "\n" + json.dumps(request) + "\n"
stdout, stderr = process.communicate(input=payload, timeout=30)

print("\n=== RESPUESTA DEL SERVIDOR MCP ===")
print(stdout)

if stderr:
    print("\n[STDERR / LOGS]:")
    print(stderr)